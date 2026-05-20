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

SYMBOLS = ["GOLD", "BTCUSD", "EURUSD", "GBPJPY"]

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
# 🚦 ด่านที่ 1: ราคาเข้าโซน M15 ไหม?
# ==========================================
def check_m15_zone(symbol):
    data = get_json_data(symbol, "smc_state", "M15")
    if not data:
        return False, "NONE"

    price = data.get("current_price", 0)
    zones = data.get("zones", {})
    BUFFER = 10

    bear_ob_top = zones.get("bear_ob_top", 0)
    bear_ob_btm = zones.get("bear_ob_btm", 0)
    bull_ob_top = zones.get("bull_ob_top", 0)
    bull_ob_btm = zones.get("bull_ob_btm", 0)

    if bear_ob_top > 0 and (bear_ob_btm - BUFFER) <= price <= (bear_ob_top + BUFFER):
        return True, "BEARISH_ZONE"
    if bull_ob_top > 0 and (bull_ob_btm - BUFFER) <= price <= (bull_ob_top + BUFFER):
        return True, "BULLISH_ZONE"

    return False, "NONE"

# ==========================================
# 🚦 ด่านที่ 2: มี Sweep M5 สด ตรง Bias ไหม?
# ==========================================
def check_m5_sweep(bias, symbol):
    data = get_json_data(symbol, "lq_sweep_state", "M5")
    if not data:
        return False

    zones    = data.get("zones", {})
    bars_ago = data.get("trigger", {}).get("bars_ago", -1)

    if bars_ago == -1 or bars_ago > 3:
        return False

    if bias == "BEARISH" and zones.get("bearish_top", 0) > 0:
        return True
    if bias == "BULLISH" and zones.get("bullish_btm", 0) > 0:
        return True

    return False

# ==========================================
# 🚦 ด่านที่ 3: Squeeze M1 ระเบิดตรง Bias ไหม?
# ==========================================
def check_m1_squeeze(bias, symbol):
    data = get_json_data(symbol, "squeeze_state", "M1")
    if not data:
        return False

    trigger   = data.get("trigger", {})
    is_firing = trigger.get("is_firing_now", False)
    fire_dir  = trigger.get("fire_direction", "NONE")

    return is_firing and fire_dir == bias

# ==========================================
# 🔍 Pre-Filter: H4+H1 Bias ตรงกันไหม?
# ==========================================
def check_h4_h1_alignment(symbol):
    h4 = get_json_data(symbol, "smc_state", "H4")
    h1 = get_json_data(symbol, "smc_state", "H1")
    if not h4 or not h1:
        return False
    h4_trend = h4.get("structure", {}).get("swing_trend")
    h1_trend = h1.get("structure", {}).get("swing_trend")
    return h4_trend == h1_trend

# ==========================================
# 🚨 Invalidation Rules (STATE 2+3)
# ==========================================
def _check_invalidation(st, symbol, now_str):
    # Rule 1: หมดเวลา 2 ชั่วโมง
    if time.time() - st["armed_time"] > 7200:
        print(f"[{now_str}] [{symbol}] ❌ INVALIDATE: หมดเวลา 2 ชั่วโมง → SCANNING")
        return True

    # Rule 2: H1 Trend เปลี่ยนจาก Bias ที่ตั้งไว้
    h1_data  = get_json_data(symbol, "smc_state", "H1")
    h1_trend = h1_data.get("structure", {}).get("swing_trend") if h1_data else None
    if h1_trend and h1_trend != st["active_bias"]:
        print(f"[{now_str}] [{symbol}] ❌ INVALIDATE: H1 Trend พัง ({h1_trend} ≠ {st['active_bias']}) → SCANNING")
        return True

    # Rule 3: ราคาทะลุโซน OB อ้างอิง
    m15_data = get_json_data(symbol, "smc_state", "M15")
    price    = m15_data.get("current_price", 0) if m15_data else 0
    if price > 0 and st["ref_ob_top"] > 0:
        if st["active_bias"] == "BEARISH" and price > st["ref_ob_top"]:
            print(f"[{now_str}] [{symbol}] ❌ INVALIDATE: ราคา ({price}) ทะลุ Bear OB Top ({st['ref_ob_top']}) → SCANNING")
            return True
        if st["active_bias"] == "BULLISH" and price < st["ref_ob_btm"]:
            print(f"[{now_str}] [{symbol}] ❌ INVALIDATE: ราคา ({price}) ทะลุ Bull OB Btm ({st['ref_ob_btm']}) → SCANNING")
            return True

    # Rule 4: มีข่าวแดงใน 30 นาที
    if Hermes.is_high_impact_news_near(minutes=30):
        print(f"[{now_str}] [{symbol}] ❌ INVALIDATE: มีข่าว HIGH Impact ใน 30 นาที → SCANNING")
        return True

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
            "bot_state":    "SCANNING",
            "active_bias":  "NONE",
            "last_h1_trend": None,
            "daily_trades": 0,
            "armed_time":   0,
            "ref_ob_top":   0,
            "ref_ob_btm":   0,
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
                states[sym]["daily_trades"]  = 0
                states[sym]["bot_state"]     = "SCANNING"
                states[sym]["active_bias"]   = "NONE"
                states[sym]["last_h1_trend"] = None
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

            # เช็ค Daily Limit ของ Symbol นี้
            if st["daily_trades"] >= MAX_DAILY_TRADES:
                print(f"[{now_str}] [{symbol}] 🛑 ครบ {MAX_DAILY_TRADES} ไม้แล้ว — ข้าม")
                continue

            # อัปเดตข้อมูลจาก MT5
            feed_midas.run_feeder(symbol)

            # เช็คโซน M15
            in_zone, zone_type = check_m15_zone(symbol)

            if not in_zone:
                if st["bot_state"] != "SCANNING":
                    print(f"[{now_str}] [{symbol}] ⚠️ ราคาหลุดโซน รีเซ็ตกลับ SCANNING")
                    st["bot_state"]   = "SCANNING"
                    st["active_bias"] = "NONE"
                else:
                    print(f"[{now_str}] [{symbol}] 💤 ราคายังไม่เข้าโซน")
                continue

            # เช็ค H4+H1 Alignment ก่อนปลุก Brain
            if not check_h4_h1_alignment(symbol):
                print(f"[{now_str}] [{symbol}] ⛔ SKIP: H4+H1 Bias ขัดกัน")
                continue

            # ==========================================
            # STATE MACHINE (ต่อ Symbol)
            # ==========================================

            # STATE 1: เพิ่งเข้าโซน → ถาม Claude หา Bias
            if st["bot_state"] == "SCANNING":
                h1_data         = get_json_data(symbol, "smc_state", "H1")
                current_h1_trend = h1_data.get("structure", {}).get("swing_trend") if h1_data else None

                if current_h1_trend == st["last_h1_trend"]:
                    print(f"[{now_str}] [{symbol}] ⏸️ H1 ยังเหมือนเดิม ({current_h1_trend}) — ข้ามไป")
                    continue

                print(f"\n[{now_str}] [{symbol}] 🚨 H1 เปลี่ยนเป็น {current_h1_trend}! ราคาเข้า {zone_type} ปลุก Midas...")
                st["last_h1_trend"] = current_h1_trend
                result = brain.think_and_trade(symbol)

                if result and result != (None, None):
                    decision, _ = result
                    if decision:
                        st["active_bias"] = decision.get("bias", "NONE")
                        if st["active_bias"] in ["BULLISH", "BEARISH"]:
                            ref_zones = h1_data.get("zones", {}) if h1_data else {}
                            if st["active_bias"] == "BEARISH":
                                st["ref_ob_top"] = ref_zones.get("bear_ob_top", 0)
                                st["ref_ob_btm"] = ref_zones.get("bear_ob_btm", 0)
                            else:
                                st["ref_ob_top"] = ref_zones.get("bull_ob_top", 0)
                                st["ref_ob_btm"] = ref_zones.get("bull_ob_btm", 0)
                            st["armed_time"] = time.time()
                            print(f"🧠 [{symbol}] Bias = {st['active_bias']} → [ARMED] (OB ref: {st['ref_ob_btm']}-{st['ref_ob_top']})")
                            st["bot_state"] = "ARMED"
                        else:
                            print(f"[{symbol}] ⏸️ โครงสร้างขัดแย้ง → รอต่อ")

            # STATE 2: ได้ Bias แล้ว → รอ Sweep M5 สด
            elif st["bot_state"] == "ARMED":
                if _check_invalidation(st, symbol, now_str):
                    st["bot_state"]   = "SCANNING"
                    st["active_bias"] = "NONE"
                    continue
                print(f"\n[{now_str}] [{symbol}] 🛡️ [ARMED] รอ Sweep ฝั่ง {st['active_bias']} บน M5...")
                if check_m5_sweep(st["active_bias"], symbol):
                    print(f"[{symbol}] 💥 พบ Sweep สด! → [READY_TO_FIRE]")
                    st["bot_state"] = "READY_TO_FIRE"

            # STATE 3: Sweep แล้ว → รอ Squeeze ระเบิด แล้วยิง
            elif st["bot_state"] == "READY_TO_FIRE":
                if _check_invalidation(st, symbol, now_str):
                    st["bot_state"]   = "SCANNING"
                    st["active_bias"] = "NONE"
                    continue
                print(f"\n[{now_str}] [{symbol}] 🎯 [READY] รอ Squeeze ระเบิดทาง {st['active_bias']}...")

                if check_m1_squeeze(st["active_bias"], symbol):
                    print(f"[{symbol}] 🔥 Squeeze ระเบิด! ปลุก Midas ยืนยันและยิง...")
                    result = brain.think_and_trade(symbol)

                    if result and result != (None, None):
                        decision, calc_data = result

                        if decision is None or calc_data is None:
                            print(f"[{symbol}] ⚠️ Brain ไม่ตอบ รีเซ็ต SCANNING")
                            st["bot_state"]   = "SCANNING"
                            st["active_bias"] = "NONE"
                            continue

                        action = decision.get("action", "WAIT")
                        entry  = calc_data[0]
                        sl     = calc_data[1]
                        tp     = calc_data[2]
                        reason = decision.get("reason", "")

                        if action in ["BUY", "SELL"] and entry is not None:
                            print(f"[{symbol}] 💥 [FIRE]: {action}! Entry={entry} SL={sl} TP={tp}")
                            if not auto_trade.check_spread_safe(symbol):
                                st["bot_state"]   = "SCANNING"
                                st["active_bias"] = "NONE"
                                continue
                            is_success = auto_trade.execute_mt5_order(action, symbol, 0.01, sl, tp)

                            if is_success:
                                auto_trade.send_telegram_alert(action, symbol, entry, sl, tp, reason)
                                st["daily_trades"] += 1
                                print(f"[{symbol}] 📊 ไม้ที่ {st['daily_trades']}/{MAX_DAILY_TRADES}")
                                time.sleep(120)

                        elif action in ["BUY", "SELL"] and entry is None:
                            print(f"[{symbol}] 🚨 คำนวณ SL/TP ไม่ได้ — ยกเลิก")
                        else:
                            print(f"[{symbol}] ⏸️ Midas สั่ง WAIT วินาทีสุดท้าย")

                        st["bot_state"]   = "SCANNING"
                        st["active_bias"] = "NONE"

        print(f"⏳ รอสแกนรอบถัดไป (60 วินาที)...")
        time.sleep(60)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n🛑 ปิดระบบอย่างปลอดภัย!")
