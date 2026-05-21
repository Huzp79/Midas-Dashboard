import time
import os
import json
import threading
from datetime import datetime, timezone, timedelta, time as datetime_time

import feed_midas
import brain
import auto_trade
import Hermes
import librarian

print("🚀 [Midas Core]: กำลังบูตระบบ (SMC State Machine)...")

SYMBOLS = ["GOLD", "BTCUSD", "EURUSD", "GBPJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "ETHUSD"]

# ==========================================
# 🛠️ Helper: อ่าน JSON จาก MT5
# ==========================================
def get_json_data(symbol, indicator, timeframe):
    path = f"C:/Users/huzwi/AppData/Roaming/MetaQuotes/Terminal/BB16F565FAAA6B23A20C26C49416FF05/MQL5/Files/{symbol}/{indicator}_{symbol}_PERIOD_{timeframe}.json"
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return None

# ==========================================
# ⏰ เช็คเวลาทำการ (Bangkok Time)
# ==========================================
def is_trading_time():
    thai_tz = timezone(timedelta(hours=7))
    now = datetime.now(thai_tz).time()
    return datetime_time(8, 0) <= now <= datetime_time(23, 30)

# ==========================================
# 🗺️ อ่าน Entry Zone จาก Morning Brief
# ==========================================
MORNING_BRIEF_JSON = os.path.join("Midas_Brain", "data", "market", "morning_brief.json")

def read_morning_brief_zone(symbol):
    try:
        if os.path.exists(MORNING_BRIEF_JSON):
            with open(MORNING_BRIEF_JSON, "r", encoding="utf-8") as f:
                brief = json.load(f)
            info = brief.get(symbol, {})
            bias = info.get("bias", "WAIT")
            if bias == "WAIT":
                return None
            ez_top = float(info.get("entry_zone_top") or 0)
            ez_btm = float(info.get("entry_zone_btm") or 0)
            if ez_top == 0 or ez_btm == 0:
                return None
            return {
                "bias":                bias,
                "entry_zone_top":      ez_top,
                "entry_zone_btm":      ez_btm,
                "invalidate_if_above": float(info.get("invalidate_if_above") or 0),
            }
    except Exception as e:
        print(f"⚠️ [MorningBrief Zone]: {e}")
    return None


# ==========================================
# 👁️ STATE 2: เช็ค Watching Conditions
# ==========================================
def check_watching_conditions(st, symbol):
    checklist = (st.get("watch_checklist") or {}).get("watch_for", {})
    bias      = st.get("active_bias", "NONE")
    results   = {}

    # Sweep (M5)
    if checklist.get("sweep", True):
        data     = get_json_data(symbol, "lq_sweep_state", "M5")
        bars_ago = (data or {}).get("trigger", {}).get("bars_ago", -1)
        zones    = (data or {}).get("zones", {})
        has_dir  = (bias == "BEARISH" and zones.get("bearish_top", 0) > 0) or \
                   (bias == "BULLISH" and zones.get("bullish_btm", 0) > 0)
        results["sweep"] = (0 <= bars_ago <= 3) and has_dir

    # Squeeze OFF + Momentum ตรง Bias (M1)
    if checklist.get("squeeze_off", True):
        data     = get_json_data(symbol, "squeeze_state", "M1")
        sqstate  = (data or {}).get("squeeze_state", "ON")
        momentum = float((data or {}).get("momentum", 0))
        results["squeeze_off"] = sqstate == "OFF" and (
            (bias == "BEARISH" and momentum < 0) or
            (bias == "BULLISH" and momentum > 0)
        )

    # Histogram darkening (momentum เคลื่อนทิศทาง Bias มากขึ้น)
    if checklist.get("histogram_dark", True):
        data     = get_json_data(symbol, "squeeze_state", "M1")
        momentum = float((data or {}).get("momentum", 0))
        prev     = st.get("prev_momentum", momentum)
        results["histogram_dark"] = (
            (bias == "BEARISH" and momentum < prev) or
            (bias == "BULLISH" and momentum > prev)
        )
        st["prev_momentum"] = momentum

    all_met = bool(results) and all(results.values())
    return all_met, results


# ==========================================
# 🚨 STATE 2: เช็ค Invalidation
# ==========================================
def check_invalidation_watching(st, symbol):
    data  = get_json_data(symbol, "smc_state", "M15")
    price = (data or {}).get("current_price", 0)
    bias  = st.get("active_bias", "NONE")
    inv   = st.get("invalidate_if_above", 0)

    if price and inv > 0:
        if bias == "BEARISH" and price > inv:
            return True, f"ราคา ({price}) เกิน Invalidation ({inv})"
        if bias == "BULLISH" and price < inv:
            return True, f"ราคา ({price}) ต่ำกว่า Invalidation ({inv})"

    if st.get("armed_time") and time.time() - st["armed_time"] > 7200:
        return True, "หมดเวลา 2 ชั่วโมง"

    return False, ""


# ==========================================
# 📡 STATE 4: เช็ค M5 BOS (Internal Trend เปลี่ยน)
# ==========================================
def check_m5_bos(st, symbol):
    data     = get_json_data(symbol, "smc_state", "M5")
    internal = (data or {}).get("structure", {}).get("internal_trend", "NONE")
    bias     = st.get("active_bias", "NONE")
    prev     = st.get("prev_m5_internal", "NONE")
    st["prev_m5_internal"] = internal
    return (
        (bias == "BEARISH" and internal == "BEARISH" and prev != "BEARISH") or
        (bias == "BULLISH" and internal == "BULLISH" and prev != "BULLISH")
    )


# ==========================================
# 🎫 ดึง Ticket ล่าสุดของ Symbol จาก MT5
# ==========================================
def get_latest_ticket(symbol):
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return None
        positions = mt5.positions_get(symbol=symbol)
        mt5.shutdown()
        return max(p.ticket for p in positions) if positions else None
    except Exception:
        return None


# ==========================================
# 🔍 STATE 4: เช็คว่า Trade ยังเปิดอยู่
# ==========================================
def is_trade_open(ticket):
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return True
        positions = mt5.positions_get(ticket=ticket)
        mt5.shutdown()
        return bool(positions)
    except Exception:
        return True


# ==========================================
# 🛡️ STATE 4: ย้าย SL to Break Even
# ==========================================
def move_sl_to_breakeven(ticket):
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return False
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            mt5.shutdown()
            return False
        p       = pos[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "ticket": ticket,
            "sl":     p.price_open,
            "tp":     p.tp,
        }
        result = mt5.order_send(request)
        mt5.shutdown()
        if result is None:
            print("⚠️ MT5 ไม่ตอบสนอง ไม่สามารถย้าย SL ได้")
            return False
        ok = result.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            print(f"🛡️ [BE]: Ticket {ticket} SL → {p.price_open}")
        return ok
    except Exception as e:
        print(f"⚠️ [BE]: {e}")
        return False

# ==========================================
# 🪽 Hermes Background Thread
# ==========================================
def _hermes_background():
    HERMES_SCHEDULE      = ["06:30", "13:30", "18:30"]
    BRIEF_SCHEDULE       = ["07:00", "14:00", "19:00"]
    NIGHT_WATCH_SCHEDULE = ["00:00", "02:00"]
    hermes_last_run      = None
    brief_last_run       = None
    night_watch_last_run = None

    print("🪽 [Hermes Thread]: ปลุก Hermes รอบแรก...")
    try:
        news    = Hermes.fetch_forex_factory_news()
        context = Hermes.fetch_market_context()
        Hermes.write_intelligence_report(news, context)
    except Exception as e:
        print(f"⚠️ [Hermes Thread]: รอบแรกผิดพลาด — {e}")

    while True:
        now_hm = datetime.now().strftime("%H:%M")
        key    = (datetime.now().date(), now_hm)

        # Hermes schedule (ข่าว + Macro)
        if now_hm in HERMES_SCHEDULE and hermes_last_run != key:
            print(f"⏰ [Hermes Thread]: ถึงเวลา {now_hm} — ปล่อย Hermes...")
            try:
                news    = Hermes.fetch_forex_factory_news()
                context = Hermes.fetch_market_context()
                Hermes.write_intelligence_report(news, context)
                hermes_last_run = key
            except Exception as e:
                print(f"⚠️ [Hermes Thread]: {e}")

        # Morning Brief schedule (วิเคราะห์ตลาด + Telegram)
        if now_hm in BRIEF_SCHEDULE and brief_last_run != key:
            print(f"🌅 [Hermes Thread]: ถึงเวลา {now_hm} — สร้าง Morning Brief...")
            try:
                msg = brain.morning_brief(SYMBOLS)
                if msg:
                    auto_trade.send_telegram_message(msg)
                brief_last_run = key
            except Exception as e:
                print(f"⚠️ [Brief]: {e}")

        # Night Watch schedule (ดูแลไม้กลางคืน)
        if now_hm in NIGHT_WATCH_SCHEDULE and night_watch_last_run != key:
            is_final = (now_hm == "02:00")
            label    = "FINAL" if is_final else "Round 1"
            print(f"🌙 [Night Watch]: {label} ({now_hm}) — ตรวจ Open Positions...")
            try:
                nw_result = brain.night_watch(SYMBOLS)

                if not nw_result:
                    msg = f"🌙 Night Watch {label}: ไม่มีไม้เปิดอยู่"
                    if is_final:
                        msg += " — Midas Idle จนถึง 07:00"
                    auto_trade.send_telegram_message(msg)

                elif not is_final:
                    # Round 1: รายงานสรุปเท่านั้น ไม่ดำเนินการ
                    lines = [f"🌙 Night Watch R1 ({now_hm}) — {len(nw_result)} ไม้:"]
                    for ticket, info in nw_result.items():
                        lines.append(
                            f"• #{ticket} {info.get('symbol')} | "
                            f"Action={info.get('action')} | "
                            f"P&L={info.get('profit', 0):.2f}"
                        )
                    auto_trade.send_telegram_message("\n".join(lines))

                else:
                    # Round 2 FINAL: ดำเนินการตาม Action
                    for ticket_str, info in nw_result.items():
                        ticket   = int(ticket_str)
                        action   = info.get("action", "D")
                        symbol   = info.get("symbol", "")
                        profit   = info.get("profit", 0)
                        reason   = info.get("reason", "")
                        volume   = info.get("volume", 0.01)
                        pos_type = info.get("pos_type", 0)

                        if action in ["B", "C"]:
                            print(f"🌙 [Night Watch]: ปิดไม้ #{ticket} ({action}) — {reason}")
                            closed = auto_trade.close_mt5_position(ticket, symbol, volume, pos_type)
                            icon   = "✅" if closed else "❌"
                            auto_trade.send_telegram_message(
                                f"{icon} Night Watch ปิดไม้: {symbol} #{ticket}\n"
                                f"Action={action} | P&L={profit:.2f}\n"
                                f"เหตุผล: {reason}"
                            )
                        elif action == "D":
                            print(f"🌙 [Night Watch]: แจ้งเจ้าของ #{ticket} — {reason}")
                            auto_trade.send_telegram_message(
                                f"⚠️ Night Watch แจ้งเตือน: {symbol} #{ticket}\n"
                                f"P&L={profit:.2f} | โครงสร้างยังดี\n"
                                f"เหตุผล: {reason}\n"
                                f"รอการตัดสินใจจากเจ้าของ"
                            )
                        else:  # A = HOLD
                            print(f"🌙 [Night Watch]: ถือต่อ #{ticket} {symbol} — {reason}")

                night_watch_last_run = key
            except Exception as e:
                print(f"⚠️ [Night Watch]: {e}")

        time.sleep(30)

# ==========================================
# 🔄 Main Loop — State Machine
# ==========================================
def main_loop():
    print("="*50)
    print("⚡ SMC State Machine: ONLINE")
    print(f"📋 Symbols: {SYMBOLS}")
    print("="*50 + "\n")

    # เริ่ม Hermes ใน background thread
    hermes_thread = threading.Thread(target=_hermes_background, daemon=True, name="HermesThread")
    hermes_thread.start()
    print("🪽 [Hermes Thread]: ONLINE\n")

    # State แยกต่อ Symbol
    states = {
        sym: {
            "bot_state":           "SCANNING",
            "active_bias":         "NONE",
            "watch_checklist":     None,
            "prev_momentum":       0.0,
            "prev_m5_internal":    "NONE",
            "armed_time":          0,
            "invalidate_if_above": 0,
            "open_ticket":         None,
            "daily_trades":        0,
        }
        for sym in SYMBOLS
    }

    MAX_DAILY_TRADES    = 5
    today               = datetime.now().date()
    librarian_ran_today = False

    while True:
        now_str = datetime.now().strftime('%H:%M:%S')

        # รีเซ็ต Counter วันใหม่
        if datetime.now().date() != today:
            today               = datetime.now().date()
            librarian_ran_today = False
            for sym in SYMBOLS:
                states[sym]["daily_trades"]    = 0
                states[sym]["bot_state"]       = "SCANNING"
                states[sym]["active_bias"]     = "NONE"
                states[sym]["watch_checklist"] = None
                states[sym]["open_ticket"]     = None
            print(f"[{now_str}] 🌅 วันใหม่ รีเซ็ต Counter ทุก Symbol")

        # รัน Librarian ทุกวันจันทร์ (weekday 0)
        if datetime.now().weekday() == 0 and not librarian_ran_today:
            print(f"[{now_str}] 📚 วันจันทร์ — ปลุก Librarian วิเคราะห์สัปดาห์ที่ผ่านมา...")
            librarian.run_librarian()
            librarian_ran_today = True

        # เช็คเวลาทำการ (เหมือนกันทุก Symbol)
        if not is_trading_time():
            print(f"[{now_str}] 🌙 นอกเวลาทำการ — Midas พักผ่อน")
            time.sleep(60)
            continue

        # ==========================================
        # วนทุก Symbol
        # ==========================================
        for symbol in SYMBOLS:
            st      = states[symbol]
            now_str = datetime.now().strftime('%H:%M:%S')

            if st["daily_trades"] >= MAX_DAILY_TRADES:
                print(f"[{now_str}] [{symbol}] 🛑 ครบ {MAX_DAILY_TRADES} ไม้แล้ว — ข้าม")
                continue

            feed_midas.run_feeder(symbol)

            # ─────────────────────────────────────
            # STATE 1: SCANNING
            # ─────────────────────────────────────
            if st["bot_state"] == "SCANNING":
                zone = read_morning_brief_zone(symbol)
                if not zone:
                    print(f"[{now_str}] [{symbol}] 💤 ไม่มี Zone จาก Morning Brief")
                    continue

                data  = get_json_data(symbol, "smc_state", "M15")
                price = (data or {}).get("current_price", 0)
                ez_top, ez_btm = zone["entry_zone_top"], zone["entry_zone_btm"]

                if not price or not (ez_btm <= price <= ez_top):
                    print(f"[{now_str}] [{symbol}] 💤 ราคา {price} ยังไม่เข้า Zone [{ez_btm}–{ez_top}]")
                    continue

                print(f"\n[{now_str}] [{symbol}] 🚨 ราคา {price} เข้า Zone! ปลุก Midas ครั้งที่ 1...")
                checklist = brain.request_watch_checklist(symbol)
                if not checklist:
                    print(f"[{symbol}] ⚠️ ขอ Checklist ไม่ได้ — ข้าม")
                    continue

                st["watch_checklist"]     = checklist
                st["active_bias"]         = checklist.get("bias", zone["bias"])
                st["invalidate_if_above"] = zone["invalidate_if_above"]
                st["armed_time"]          = time.time()
                st["prev_momentum"]       = 0.0
                st["prev_m5_internal"]    = "NONE"
                st["bot_state"]           = "WATCHING"

            # ─────────────────────────────────────
            # STATE 2: WATCHING
            # ─────────────────────────────────────
            elif st["bot_state"] == "WATCHING":
                is_inv, inv_reason = check_invalidation_watching(st, symbol)
                if is_inv:
                    print(f"[{now_str}] [{symbol}] ❌ INVALIDATE: {inv_reason} → SCANNING")
                    st["bot_state"]       = "SCANNING"
                    st["active_bias"]     = "NONE"
                    st["watch_checklist"] = None
                    continue

                all_met, results = check_watching_conditions(st, symbol)
                status = " | ".join(f"{k}={'✅' if v else '❌'}" for k, v in results.items())
                print(f"[{now_str}] [{symbol}] 👁️ WATCHING {st['active_bias']} | {status}")

                if all_met:
                    print(f"[{symbol}] ✅ ครบทุกเงื่อนไข! ปลุก Midas ครั้งที่ 2...")
                    st["bot_state"] = "EXECUTE"

            # ─────────────────────────────────────
            # STATE 3: EXECUTE
            # ─────────────────────────────────────
            elif st["bot_state"] == "EXECUTE":
                decision, calc_data = brain.request_execute(symbol, st["watch_checklist"])

                if not decision:
                    print(f"[{symbol}] ⚠️ Midas ไม่ตอบ → SCANNING")
                    st["bot_state"]       = "SCANNING"
                    st["active_bias"]     = "NONE"
                    st["watch_checklist"] = None
                    continue

                action        = decision.get("action", "WAIT")
                entry, sl, tp, rr = calc_data if calc_data else (None, None, None, 0)

                if action in ["BUY", "SELL"] and entry is not None:
                    print(f"[{symbol}] 💥 [FIRE]: {action}! Entry={entry} SL={sl} TP={tp}")
                    if not auto_trade.check_spread_safe(symbol):
                        st["bot_state"]       = "SCANNING"
                        st["active_bias"]     = "NONE"
                        st["watch_checklist"] = None
                        continue
                    lot        = brain.calculate_lot_size(symbol, entry, sl)
                    is_success = auto_trade.execute_mt5_order(action, symbol, lot, sl, tp)
                    if is_success:
                        auto_trade.send_telegram_alert(action, symbol, entry, sl, tp, decision.get("reason"))
                        ticket = get_latest_ticket(symbol)
                        st["open_ticket"]   = ticket
                        st["daily_trades"] += 1
                        st["bot_state"]     = "MONITORING"
                        print(f"[{symbol}] 📊 ไม้ที่ {st['daily_trades']}/{MAX_DAILY_TRADES} | Ticket={ticket}")
                    else:
                        print(f"[{symbol}] ❌ Execute ล้มเหลว → SCANNING")
                        st["bot_state"]       = "SCANNING"
                        st["active_bias"]     = "NONE"
                        st["watch_checklist"] = None
                else:
                    print(f"[{symbol}] ⏸️ Midas สั่ง WAIT — {decision.get('reason', '')}")
                    st["bot_state"]       = "SCANNING"
                    st["active_bias"]     = "NONE"
                    st["watch_checklist"] = None

            # ─────────────────────────────────────
            # STATE 4: MONITORING
            # ─────────────────────────────────────
            elif st["bot_state"] == "MONITORING":
                ticket = st.get("open_ticket")
                if not ticket or not is_trade_open(ticket):
                    print(f"[{now_str}] [{symbol}] ✅ ไม้ปิดแล้ว (TP/SL Hit) → SCANNING")
                    st["bot_state"]       = "SCANNING"
                    st["active_bias"]     = "NONE"
                    st["watch_checklist"] = None
                    st["open_ticket"]     = None
                    continue

                print(f"[{now_str}] [{symbol}] 🔍 MONITORING Ticket={ticket} ({st['active_bias']})")
                if check_m5_bos(st, symbol):
                    print(f"[{symbol}] 🛡️ BOS ใน M5 — ย้าย SL to Break Even")
                    ok = move_sl_to_breakeven(ticket)
                    if ok:
                        auto_trade.send_telegram_message(f"🛡️ {symbol}: SL ย้าย BE แล้ว (BOS M5)")

        print(f"⏳ รอสแกนรอบถัดไป (60 วินาที)...")
        time.sleep(60)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n🛑 ปิดระบบอย่างปลอดภัย!")
