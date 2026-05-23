import time
import os
import json
import re
import threading
import requests
from datetime import datetime, timezone, timedelta, time as datetime_time

import feed_midas
import brain
import auto_trade
import Hermes
import librarian

print("🚀 [Midas Core]: กำลังบูตระบบ (SMC State Machine)...")

SYMBOLS        = ["GOLD", "BTCUSD", "EURUSD", "GBPJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "ETHUSD"]
CRYPTO_SYMBOLS = ["BTCUSD", "ETHUSD"]

IS_PAUSED = False  # /pause → True | /resume → False

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
# 🔍 STATE 4: เช็คว่า Trade ยังเปิดอยู่ (position)
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
# ⏳ STATE 2.5: เช็คว่า Pending Order ยังอยู่ใน Orders
# ==========================================
def is_pending_order_active(ticket):
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return False
        orders = mt5.orders_get(ticket=ticket)
        mt5.shutdown()
        return bool(orders)
    except Exception:
        return False

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
# 📓 บันทึกผล Trade ที่ปิดลง Journal
# ==========================================
def _append_trade_result_journal(symbol, ticket, trade_result):
    today = datetime.now().strftime("%Y-%m-%d")
    journal_path = os.path.join("Midas_Brain", "data", "journal", f"{today}.md")
    icon = "✅" if trade_result["result"] == "WIN" else ("🛡️" if trade_result["result"] == "BE" else "❌")
    try:
        with open(journal_path, "a", encoding="utf-8-sig") as f:
            f.write(f"\n## {icon} Trade Result — {datetime.now().strftime('%H:%M:%S')}\n")
            f.write(f"**Symbol:** {symbol} | **Ticket:** #{ticket}\n")
            f.write(f"**Result:** {trade_result['result']} | **P&L:** {trade_result['profit']:.2f} USD\n")
            f.write(f"**Exit Price:** {trade_result['exit_price']}\n")
            f.write("-" * 40 + "\n")
    except Exception as e:
        print(f"⚠️ [Journal Result]: {e}")

# ==========================================
# 🪽 Hermes Background Thread
# ==========================================
def _hermes_background():
    HERMES_SCHEDULE      = ["06:30", "13:30", "18:30"]
    BRIEF_SCHEDULE       = ["07:00", "14:00", "19:00"]
    NIGHT_WATCH_SCHEDULE = ["00:00", "02:00"]
    CME_OI_SCHEDULE      = ["06:00", "12:00", "18:00", "23:00"]
    hermes_last_run      = None
    brief_last_run       = None
    night_watch_last_run = None
    cme_vol2vol_last_run = None
    cme_oi_last_run      = None
    cme_cot_last_run     = None
    cme_prev_snapshot    = Hermes.load_prev_snapshot()

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

        # Morning Brief schedule (วิเคราะห์ตลาด — ไม่ส่ง Telegram)
        if now_hm in BRIEF_SCHEDULE and brief_last_run != key:
            print(f"🌅 [Hermes Thread]: ถึงเวลา {now_hm} — สร้าง Morning Brief...")
            try:
                brain.morning_brief(SYMBOLS)
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
                    print(f"🌙 [Night Watch]: {label} ไม่มีไม้เปิดอยู่")

                elif not is_final:
                    # Round 1: log เท่านั้น ไม่ส่ง Telegram
                    print(f"🌙 Night Watch R1 ({now_hm}) — {len(nw_result)} ไม้")
                    for ticket, info in nw_result.items():
                        print(f"  • #{ticket} {info.get('symbol')} | Action={info.get('action')} | P&L={info.get('profit', 0):.2f}")

                else:
                    # Round 2 FINAL: ดำเนินการตาม Action — ส่ง Telegram เฉพาะ Action D
                    for ticket_str, info in nw_result.items():
                        ticket   = int(ticket_str)
                        action   = info.get("action", "D")
                        symbol   = info.get("symbol", "")
                        profit   = info.get("profit", 0)
                        reason   = info.get("reason", "")
                        volume   = info.get("volume", 0.01)
                        pos_type = info.get("pos_type", 0)

                        if action in ["B", "C"]:
                            if symbol in CRYPTO_SYMBOLS:
                                print(f"🌙 [Night Watch]: Crypto #{ticket} {symbol} — ไม่ Force Close กลางคืน (Action={action}) | {reason}")
                            else:
                                print(f"🌙 [Night Watch]: ปิดไม้ #{ticket} ({action}) — {reason}")
                                auto_trade.close_mt5_position(ticket, symbol, volume, pos_type)
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

        # CME Vol2Vol ทุกชั่วโมง (XX:00)
        if datetime.now().strftime("%M") == "00" and cme_vol2vol_last_run != key:
            print(f"📊 [CME Thread]: Vol2Vol รอบ {now_hm}...")
            try:
                snapshot = Hermes.fetch_cme_vol2vol_data()
                if snapshot and cme_prev_snapshot:
                    alerts = Hermes.check_cme_alerts(cme_prev_snapshot, snapshot)
                    if alerts:
                        brain.analyze_cme_change(alerts)
                if snapshot:
                    cme_prev_snapshot = snapshot
                cme_vol2vol_last_run = key
            except Exception as e:
                print(f"⚠️ [CME Vol2Vol]: {e}")

        # CME OI Matrix ทุก 6 ชั่วโมง (06/12/18/23)
        if now_hm in CME_OI_SCHEDULE and cme_oi_last_run != key:
            print(f"📊 [CME Thread]: OI Matrix รอบ {now_hm}...")
            try:
                oi_snap = Hermes.fetch_cme_oi_matrix_data()
                if oi_snap and cme_prev_snapshot:
                    alerts = Hermes.check_cme_alerts(cme_prev_snapshot, oi_snap)
                    if alerts:
                        brain.analyze_cme_change(alerts)
                if oi_snap:
                    cme_prev_snapshot = {**(cme_prev_snapshot or {}), **oi_snap}
                cme_oi_last_run = key
            except Exception as e:
                print(f"⚠️ [CME OI]: {e}")

        # CME COT เฉพาะวันศุกร์ 06:00
        if now_hm == "06:00" and datetime.now().weekday() == 4 and cme_cot_last_run != key:
            print(f"📊 [CME Thread]: COT Friday รอบ {now_hm}...")
            try:
                Hermes.fetch_cme_cot_data()
                cme_cot_last_run = key
            except Exception as e:
                print(f"⚠️ [CME COT]: {e}")

        time.sleep(30)

# ==========================================
# 📡 Telegram Two-Way Polling Thread
# ==========================================
def _telegram_polling():
    """Background thread: รับคำสั่งจาก Telegram ทุก 3 วินาที"""
    global IS_PAUSED

    token   = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")

    if not token or not chat_id:
        print("⚠️ [TG Poll]: ไม่มี TELEGRAM_TOKEN หรือ CHAT_ID — ปิด Polling")
        return

    def reply(text):
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": text},
                timeout=5,
            )
        except Exception as e:
            print(f"⚠️ [TG Poll Reply]: {e}")

    # ดึง offset ปัจจุบันก่อนเพื่อข้ามข้อความเก่าทั้งหมด
    offset = None
    try:
        resp    = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                               params={"timeout": 0, "limit": 100}, timeout=10)
        updates = resp.json().get("result", [])
        if updates:
            offset = updates[-1]["update_id"] + 1
    except Exception:
        pass

    print("📡 [TG Poll]: Telegram Two-Way ONLINE")

    while True:
        try:
            params = {"timeout": 0, "limit": 10}
            if offset is not None:
                params["offset"] = offset
            resp    = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                                   params=params, timeout=5)
            updates = resp.json().get("result", [])

            for upd in updates:
                offset = upd["update_id"] + 1
                msg    = upd.get("message") or upd.get("channel_post") or {}
                text   = (msg.get("text") or "").strip()
                if not text.startswith("/"):
                    continue

                parts   = text.split()
                command = parts[0].lower()
                print(f"📡 [TG Poll]: คำสั่ง '{text}'")

                # /help
                if command == "/help":
                    reply(
                        "🤖 Midas Commands:\n\n"
                        "/status — Open Positions ทั้งหมด\n"
                        "/pause  — หยุดสแกนหาไม้ใหม่\n"
                        "/resume — เปิดสแกนต่อ\n"
                        "/close [ticket] — ปิดไม้ตาม Ticket\n"
                        "/report — สรุป P&L วันนี้\n"
                        "/help   — แสดงคำสั่งทั้งหมด"
                    )

                # /status
                elif command == "/status":
                    try:
                        import MetaTrader5 as mt5
                        if not mt5.initialize():
                            reply("❌ เชื่อมต่อ MT5 ไม่ได้")
                        else:
                            positions = mt5.positions_get()
                            mt5.shutdown()
                            if not positions:
                                paused_txt = " [PAUSED]" if IS_PAUSED else ""
                                reply(f"📭 ไม่มีไม้เปิดอยู่{paused_txt}")
                            else:
                                paused_txt = " [PAUSED]" if IS_PAUSED else ""
                                lines = [f"📊 Open Positions{paused_txt} ({len(positions)} ไม้):"]
                                for p in positions:
                                    direction = "BUY" if p.type == 0 else "SELL"
                                    icon      = "🟢" if p.profit >= 0 else "🔴"
                                    lines.append(
                                        f"{icon} #{p.ticket} {p.symbol} {direction}\n"
                                        f"   Entry={p.price_open} | SL={p.sl} | TP={p.tp}\n"
                                        f"   P&L={p.profit:+.2f} USD"
                                    )
                                reply("\n\n".join(lines))
                    except Exception as e:
                        reply(f"❌ /status error: {e}")

                # /pause
                elif command == "/pause":
                    IS_PAUSED = True
                    reply("⏸️ Midas PAUSED\nหยุดสแกนหาไม้ใหม่แล้ว\nไม้ที่เปิดอยู่จะยัง Monitor ต่อ\nพิมพ์ /resume เพื่อเปิดต่อ")
                    print("⏸️ [TG Poll]: ระบบ PAUSED")

                # /resume
                elif command == "/resume":
                    IS_PAUSED = False
                    reply("▶️ Midas RESUMED\nกลับมาสแกนหาไม้แล้ว")
                    print("▶️ [TG Poll]: ระบบ RESUMED")

                # /close [ticket]
                elif command == "/close":
                    if len(parts) < 2:
                        reply("❓ ใช้: /close [ticket]\nเช่น: /close 12345678")
                    else:
                        try:
                            ticket = int(parts[1])
                            ok, close_price = auto_trade.close_position_by_ticket(ticket)
                            if ok:
                                reply(f"✅ ปิดไม้ #{ticket} สำเร็จ @ {close_price}")
                            else:
                                reply(f"❌ ปิดไม้ #{ticket} ไม่สำเร็จ\nไม่พบ Position หรือ MT5 Error")
                        except ValueError:
                            reply("❓ Ticket ต้องเป็นตัวเลข เช่น: /close 12345678")

                # /report
                elif command == "/report":
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    j_path    = os.path.join("Midas_Brain", "data", "journal", f"{today_str}.md")
                    if not os.path.exists(j_path):
                        reply(f"📭 ยังไม่มี Journal วันนี้ ({today_str})")
                    else:
                        try:
                            with open(j_path, "r", encoding="utf-8-sig") as f:
                                content = f.read()
                            wins   = content.count("Result: WIN")   + content.count("**Result:** WIN")
                            losses = content.count("Result: LOSS")  + content.count("**Result:** LOSS")
                            bes    = content.count("Result: BE")    + content.count("**Result:** BE")
                            pnls   = re.findall(r"\*\*P&L:\*\* ([+-]?\d+\.?\d*) USD", content)
                            total  = sum(float(x) for x in pnls) if pnls else 0.0
                            reply(
                                f"📈 Daily Report — {today_str}\n\n"
                                f"✅ WIN: {wins} | ❌ LOSS: {losses} | 🛡️ BE: {bes}\n"
                                f"💰 Total P&L: {total:+.2f} USD"
                            )
                        except Exception as e:
                            reply(f"❌ /report error: {e}")

                else:
                    reply(f"❓ ไม่รู้จักคำสั่ง '{command}'\nพิมพ์ /help เพื่อดูคำสั่งทั้งหมด")

        except Exception as e:
            print(f"⚠️ [TG Poll]: {e}")

        time.sleep(3)


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

    # เริ่ม Telegram Two-Way Polling
    tg_thread = threading.Thread(target=_telegram_polling, daemon=True, name="TelegramPollThread")
    tg_thread.start()

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
            "entry_zone_top":      0,
            "entry_zone_btm":      0,
            "open_ticket":         None,
            "pending_ticket":      None,
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
                states[sym]["pending_ticket"]  = None
            print(f"[{now_str}] 🌅 วันใหม่ รีเซ็ต Counter ทุก Symbol")

        # รัน Librarian ทุกวันจันทร์ (weekday 0)
        if datetime.now().weekday() == 0 and not librarian_ran_today:
            print(f"[{now_str}] 📚 วันจันทร์ — ปลุก Librarian วิเคราะห์สัปดาห์ที่ผ่านมา...")
            librarian.run_librarian()
            librarian_ran_today = True

        # ==========================================
        # วนทุก Symbol
        # ==========================================
        for symbol in SYMBOLS:
            st      = states[symbol]
            now_str = datetime.now().strftime('%H:%M:%S')

            # Crypto ทำงาน 24 ชั่วโมง — Forex เช็คเวลาทำการปกติ 08:00–23:30
            if symbol not in CRYPTO_SYMBOLS and not is_trading_time():
                print(f"[{now_str}] [{symbol}] 🌙 นอกเวลาทำการ — ข้าม")
                continue

            if st["daily_trades"] >= MAX_DAILY_TRADES:
                print(f"[{now_str}] [{symbol}] 🛑 ครบ {MAX_DAILY_TRADES} ไม้แล้ว — ข้าม")
                continue

            feed_midas.run_feeder(symbol)

            # ข้ามสแกนถ้า PAUSED — ยกเว้น MONITORING (ยังดูแลไม้เปิดอยู่)
            if IS_PAUSED and st["bot_state"] != "MONITORING":
                print(f"[{now_str}] [{symbol}] ⏸️ PAUSED — ข้ามสแกน")
                continue

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
                st["entry_zone_top"]      = zone["entry_zone_top"]
                st["entry_zone_btm"]      = zone["entry_zone_btm"]
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

                # Squeeze ON + ราคาอยู่ใน Zone → Pre-Entry
                sq_data = get_json_data(symbol, "squeeze_state", "M1")
                if (sq_data or {}).get("squeeze_state") == "ON":
                    m15_data = get_json_data(symbol, "smc_state", "M15")
                    price    = (m15_data or {}).get("current_price", 0)
                    ez_top   = st.get("entry_zone_top", 0)
                    ez_btm   = st.get("entry_zone_btm", 0)
                    if price and ez_top and ez_btm and ez_btm <= price <= ez_top:
                        print(f"[{now_str}] [{symbol}] ⚡ Squeeze ON + ราคาในโซน → PRE_ENTRY")
                        st["bot_state"] = "PRE_ENTRY"
                        continue

                all_met, results = check_watching_conditions(st, symbol)
                status = " | ".join(f"{k}={'✅' if v else '❌'}" for k, v in results.items())
                print(f"[{now_str}] [{symbol}] 👁️ WATCHING {st['active_bias']} | {status}")

                if all_met:
                    print(f"[{symbol}] ✅ ครบทุกเงื่อนไข! ปลุก Midas ครั้งที่ 2...")
                    st["bot_state"] = "EXECUTE"

            # ─────────────────────────────────────
            # STATE 2.5: PRE_ENTRY
            # ─────────────────────────────────────
            elif st["bot_state"] == "PRE_ENTRY":
                is_inv, inv_reason = check_invalidation_watching(st, symbol)
                if is_inv:
                    if st.get("pending_ticket"):
                        auto_trade.cancel_pending_order(st["pending_ticket"])
                        auto_trade.send_telegram_message(
                            f"🗑️ {symbol}: ยกเลิก Pending Order #{st['pending_ticket']}\n{inv_reason}"
                        )
                    print(f"[{now_str}] [{symbol}] ❌ PRE_ENTRY INVALIDATE: {inv_reason} → SCANNING")
                    st["bot_state"]       = "SCANNING"
                    st["active_bias"]     = "NONE"
                    st["watch_checklist"] = None
                    st["pending_ticket"]  = None
                    continue

                if not st.get("pending_ticket"):
                    # ยังไม่มี Pending Order → ขอ Pre-Entry จาก Midas
                    pre = brain.request_pre_entry(symbol)
                    if not pre or pre.get("action") == "WAIT":
                        print(f"[{now_str}] [{symbol}] ⏸️ Pre-Entry WAIT → กลับ WATCHING")
                        st["bot_state"] = "WATCHING"
                        continue

                    action     = pre.get("action")
                    order_type = pre.get("order_type", "PENDING")
                    entry      = pre.get("entry")
                    sl         = pre.get("sl")
                    tp         = pre.get("tp")

                    if order_type == "MARKET":
                        print(f"[{now_str}] [{symbol}] ⚡ Pre-Entry MARKET → EXECUTE")
                        st["bot_state"] = "EXECUTE"
                    elif entry and order_type == "PENDING":
                        lot    = brain.calculate_lot_size(symbol, entry, sl)
                        ticket = auto_trade.place_pending_order(symbol, action, entry, sl, tp, lot)
                        if ticket:
                            st["pending_ticket"] = ticket
                            auto_trade.send_telegram_message(
                                f"⏳ {symbol}: วาง {action} LIMIT @ {entry}\n"
                                f"SL={sl} | TP={tp} | Ticket=#{ticket}"
                            )
                        else:
                            print(f"[{now_str}] [{symbol}] ❌ วาง Pending ไม่สำเร็จ → WATCHING")
                            st["bot_state"] = "WATCHING"
                    else:
                        st["bot_state"] = "WATCHING"

                else:
                    # มี Pending Order แล้ว → รอ Fill
                    pending_ticket = st["pending_ticket"]
                    if is_trade_open(pending_ticket):
                        # Filled! → MONITORING
                        print(f"[{now_str}] [{symbol}] ✅ Pending #{pending_ticket} Fill → MONITORING")
                        st["open_ticket"]    = pending_ticket
                        st["pending_ticket"] = None
                        st["daily_trades"]  += 1
                        st["bot_state"]      = "MONITORING"
                        auto_trade.send_telegram_message(
                            f"✅ {symbol}: Pending #{pending_ticket} Fill แล้ว!\n"
                            f"Bias={st['active_bias']} → เข้า MONITORING"
                        )
                    elif not is_pending_order_active(pending_ticket):
                        # ถูกยกเลิกโดย Broker หรือหมดอายุ
                        print(f"[{now_str}] [{symbol}] ⚠️ Pending #{pending_ticket} หมดอายุ → WATCHING")
                        st["pending_ticket"] = None
                        st["bot_state"]      = "WATCHING"
                    else:
                        print(f"[{now_str}] [{symbol}] ⏳ PRE_ENTRY: รอ Fill Pending #{pending_ticket}")

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
                    lot                      = brain.calculate_lot_size(symbol, entry, sl)
                    is_success, actual_entry = auto_trade.execute_mt5_order(action, symbol, lot, sl, tp)
                    if is_success:
                        fill_price = actual_entry or entry
                        auto_trade.send_telegram_alert(action, symbol, fill_price, sl, tp, decision.get("reason"))
                        try:
                            today_j = datetime.now().strftime("%Y-%m-%d")
                            j_path  = os.path.join("Midas_Brain", "data", "journal", f"{today_j}.md")
                            with open(j_path, "a", encoding="utf-8-sig") as f:
                                f.write(f"**Actual Fill:** {fill_price}\n")
                        except Exception:
                            pass
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
                    if ticket:
                        trade_result = auto_trade.get_closed_trade_result(ticket)
                        if trade_result:
                            icon = "✅" if trade_result["result"] == "WIN" else ("🛡️" if trade_result["result"] == "BE" else "❌")
                            auto_trade.send_telegram_message(
                                f"{icon} Midas Trade Closed\n\n"
                                f"{symbol} | {trade_result['result']}\n"
                                f"Exit: {trade_result['exit_price']}\n"
                                f"P&L: {trade_result['profit']:.2f} USD\n"
                                f"Ticket: #{ticket}"
                            )
                            _append_trade_result_journal(symbol, ticket, trade_result)
                            print(f"[{now_str}] [{symbol}] {icon} {trade_result['result']} | P&L={trade_result['profit']:.2f}")
                    print(f"[{now_str}] [{symbol}] ✅ ไม้ปิดแล้ว → SCANNING")
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
