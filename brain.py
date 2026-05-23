import os
import json
import re
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv
from auto_trade import execute_mt5_order, send_telegram_alert

# ==========================================
# ⚙️ 1. ตั้งค่าระบบ & โมเดล
# ==========================================
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    print("❌ ไม่พบ API Key!")
    quit()

client = Anthropic(api_key=api_key)
AI_MODEL = "claude-haiku-4-5-20251001"

# ==========================================
# 📂 2. เส้นทางไฟล์
# ==========================================
BASE_DIR          = "Midas_Brain"
CONSTITUTION_PATH = os.path.join(BASE_DIR, "00_Midas_Constitution.md")
INTELLIGENCE_PATH       = os.path.join(BASE_DIR, "data", "market", "daily_intelligence.md")
MORNING_BRIEF_PATH      = os.path.join(BASE_DIR, "data", "market", "morning_brief.md")
MORNING_BRIEF_JSON_PATH = os.path.join(BASE_DIR, "data", "market", "morning_brief.json")
CME_DAILY_PATH          = os.path.join(BASE_DIR, "data", "market", "CME_Daily.md")

PRICE_FILTERS = {
    "GOLD":   100,
    "BTCUSD": 1000,
    "EURUSD": 0.5,
    "GBPJPY": 100,
    "GBPUSD": 0.5,
    "AUDUSD": 0.5,
    "USDCAD": 0.5,
    "USDCHF": 0.5,
    "ETHUSD": 100,
}
TRADE_LOG_DIR     = os.path.join(BASE_DIR, "data", "journal")
os.makedirs(TRADE_LOG_DIR, exist_ok=True)

# ==========================================
# 📖 3. อ่านไฟล์
# ==========================================
def read_file(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

# ==========================================
# 🧮 4. คำนวณ SL/TP (Python ทำเอง ไม่ให้ AI เดา)
# ==========================================
def calculate_gold_sl_tp(action, score, market_data_text, symbol="GOLD"):
    if action not in ["BUY", "SELL"]:
        return None, None, None, 0

    rr = 5.0 if score >= 9 else 3.0 if score >= 7 else 2.0
    buffer = 1.5

    try:
        # แบ่ง MD ออกเป็น Section ตาม TF
        # หา Section M15 ก่อน ถ้าไม่มีเอา M5
        m15_section = ""
        m5_section  = ""

        lines = market_data_text.split('\n')
        current_tf = ""
        for line in lines:
            if "M15" in line and "##" in line:
                current_tf = "M15"
            elif "M5" in line and "##" in line and "M15" not in line:
                current_tf = "M5"
            elif "## ⏳" in line:
                current_tf = "OTHER"

            if current_tf == "M15":
                m15_section += line + "\n"
            elif current_tf == "M5":
                m5_section += line + "\n"

        # เลือก Section ที่จะใช้
        search_text = m15_section if m15_section else m5_section

        price_min = PRICE_FILTERS.get(symbol, 0.5)

        if action == "BUY":
            matches = re.findall(r'Bull OB\(([\d.]+)-([\d.]+)\)', search_text)
            valid = [(float(a), float(b)) for a, b in matches if float(a) > price_min]
            if not valid:
                raise ValueError("หา Bull OB ไม่เจอใน M15/M5")
            ob_top, ob_btm = valid[0]
            entry = ob_top
            sl    = ob_btm - buffer
            tp    = entry + ((entry - sl) * rr)
        else:
            matches = re.findall(r'Bear OB\(([\d.]+)-([\d.]+)\)', search_text)
            valid = [(float(a), float(b)) for a, b in matches if float(a) > price_min]
            if not valid:
                raise ValueError("หา Bear OB ไม่เจอใน M15/M5")
            ob_top, ob_btm = valid[0]
            entry = ob_btm
            sl    = ob_top + buffer
            tp    = entry - ((sl - entry) * rr)

        return round(entry, 2), round(sl, 2), round(tp, 2), rr

    except Exception as e:
        print(f"⚠️ [Calculator]: {e}")
        return None, None, None, 0

# ==========================================
# 📝 5. บันทึก Journal
# ==========================================
def append_to_journal(decision_data, calc_data, symbol="GOLD"):
    today_date = datetime.now().strftime("%Y-%m-%d")
    journal_path = os.path.join(TRADE_LOG_DIR, f"{today_date}.md")
    entry, sl, tp, rr = calc_data

    with open(journal_path, "a", encoding="utf-8-sig") as f:
        f.write(f"\n## 🕒 {datetime.now().strftime('%H:%M:%S')}\n")
        f.write(f"**Symbol:** {symbol}\n")
        f.write(f"**Action:** {decision_data.get('action')} | **Confidence:** {decision_data.get('confidence')}\n")
        f.write(f"**Score:** {decision_data.get('score')}/10 | **RR:** 1:{rr}\n")
        f.write(f"**Bias:** {decision_data.get('bias')}\n")
        if entry:
            f.write(f"**Plan:** Entry={entry} | SL={sl} | TP={tp}\n")
        f.write(f"**Reason:** {decision_data.get('reason')}\n")
        f.write(f"**Summary:** {decision_data.get('summary')}\n")
        f.write("-" * 40 + "\n")

# ==========================================
# 💰 6. คำนวณ Lot Size จาก Portfolio Risk
# ==========================================
def calculate_lot_size(symbol, entry, sl):
    """คำนวณ Lot Size จาก Balance จริงใน MT5 ตาม Tiered Risk %"""
    import MetaTrader5 as mt5

    try:
        if not mt5.initialize():
            print("⚠️ [LotCalc]: MT5 ไม่ตอบสนอง — ใช้ Lot 0.01")
            return 0.01

        acct = mt5.account_info()
        info = mt5.symbol_info(symbol)
        mt5.shutdown()

        if not acct or not info:
            return 0.01

        balance = acct.balance

        # Tiered Risk ตาม Portfolio Size
        if balance < 200:
            risk_pct = 1.000   # ALL IN
        elif balance < 500:
            risk_pct = 0.150   # 15%
        elif balance < 1000:
            risk_pct = 0.075   # 7.5%
        elif balance < 3000:
            risk_pct = 0.035   # 3.5%
        elif balance < 5000:
            risk_pct = 0.015   # 1.5%
        else:
            risk_pct = 0.0075  # 0.75%

        risk_amount = balance * risk_pct
        sl_distance = abs(entry - sl)
        if sl_distance == 0:
            return info.volume_min

        # Dollar risk per 1 lot สำหรับ SL distance นี้
        dollar_per_lot = (sl_distance / info.trade_tick_size) * info.trade_tick_value
        lot = risk_amount / dollar_per_lot

        # Clamp และปัดให้ตรง Broker step
        lot = max(info.volume_min, min(info.volume_max, lot))
        step = info.volume_step
        lot = round(round(lot / step) * step, 8)

        print(f"💰 [LotCalc]: Balance=${balance:.0f} | Risk={risk_pct*100:.3g}% | Amount=${risk_amount:.2f} | SL_dist={sl_distance:.2f} | Lot={lot}")
        return lot

    except Exception as e:
        print(f"⚠️ [LotCalc]: {e} — ใช้ Lot 0.01")
        return 0.01


# ==========================================
# 🧠 7. สมองหลัก
# ==========================================
def think_and_trade(symbol="GOLD"):
    print("🧠 [Midas Brain]: กำลังวิเคราะห์ตลาด...")

    market_data_path = os.path.join(BASE_DIR, "data", "market", f"latest_data_{symbol}.md")
    constitution = read_file(CONSTITUTION_PATH)
    market_data  = read_file(market_data_path)

    if not constitution or not market_data:
        print("⚠️ ขาดข้อมูลสำคัญ ยกเลิก")
        return None, None

    # เพิ่มข่าวจาก Hermes ถ้ามี
    intelligence = read_file(INTELLIGENCE_PATH)
    intel_section = f"\n[HERMES INTELLIGENCE - News & Macro]:\n{intelligence}" if intelligence else ""

    system_prompt = """You are MIDAS, an elite AI trading agent specializing in Smart Money Concepts (SMC).
You think like an experienced SMC trader who reads charts holistically — not a checklist robot.
Python handles all math (Entry, SL, TP). Your job: structure analysis and timing judgment only.
CRITICAL: Output ONLY a valid JSON object. No markdown, no explanation, no extra text."""

    user_prompt = f"""{intel_section}

[MARKET DATA]:
{market_data}

[THINKING FRAMEWORK]:

STEP 1 - BIG PICTURE (H4 + H1)
- H4 และ H1 Swing Trend ตรงกันไหม? ถ้าไม่ตรง → WAIT ทันที
- ถ้า Hermes แจ้งข่าวแดงใน 30 นาทีข้างหน้า → WAIT ทันที

STEP 2 - LOCATION (M30 + M15)
- ราคาอยู่ใกล้โซน OB/FVG ที่ตรงกับ Bias ไหม?
- อยู่ติด POC → ระวัง แรงต้านสูง

STEP 3 - TRIGGER (M5 + M1) ← สำคัญที่สุด
- bars_ago ของ LQ Sweep:
  0-1 = สดมาก ✅ | 2-3 = พอได้ ⚠️ | 4+ หรือ -1 = ❌ WAIT
- Squeeze Logic (อ่านให้ครบก่อนตัดสิน):
  squeeze_state = OFF + momentum > 0 + Bias BULLISH = ✅ เข้าได้
  squeeze_state = OFF + momentum < 0 + Bias BEARISH = ✅ เข้าได้
  is_firing_now = true คือโบนัส ไม่ใช่เงื่อนไขบังคับ
  ถ้า squeeze_state = OFF และ momentum ตรง Bias → ผ่าน แม้ bars_since_fire = -1
  ห้าม WAIT เพราะ is_firing_now = false ถ้า Squeeze ระเบิดไปแล้วและ momentum ยังวิ่งอยู่

STEP 4 - HONEST CHECK
- ถ้าเป็นเงินตัวเอง เข้าไหม?
- ใช่ชัดเจน → HIGH | ไม่แน่ใจ → MEDIUM | ไม่เอา → LOW + WAIT

Score 8-10 + HIGH/MEDIUM → BUY หรือ SELL
Score ต่ำกว่า 6 หรือ LOW → WAIT เสมอ

Output JSON เท่านั้น (ห้ามใส่ entry, sl, tp — Python คำนวณเอง):
{{
    "summary": "สรุปตลาด 1 บรรทัด (ภาษาไทย)",
    "bias": "BULLISH|BEARISH|NEUTRAL",
    "action": "BUY|SELL|WAIT",
    "confidence": "HIGH|MEDIUM|LOW",
    "score": <0-10>,
    "reason": "อธิบายในไม่กี่ประโยค เน้นความสดของ Trigger (ภาษาไทย)"
}}"""

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=600,
            temperature=0.1,
            system=[
                {"type": "text", "text": constitution, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": system_prompt}
            ],
            messages=[{"role": "user", "content": user_prompt}],
            betas=["prompt-caching-2024-07-31"]
        )

        raw = response.content[0].text.strip().replace("```json","").replace("```","").strip()
        decision = json.loads(raw)

        print("\n" + "="*50)
        print("🎯 MIDAS DECISION:")
        print(json.dumps(decision, indent=4, ensure_ascii=False))

        action     = decision.get("action")
        score      = decision.get("score", 0)
        confidence = decision.get("confidence", "LOW")
        calc_data  = (None, None, None, 0)

        if action in ["BUY", "SELL"]:
            print("\n🧮 [Calculator]: คำนวณ SL/TP...")
            entry, sl, tp, rr = calculate_gold_sl_tp(action, score, market_data, symbol)
            calc_data = (entry, sl, tp, rr)

            if entry is not None:
                print(f"✅ Entry={entry} | SL={sl} | TP={tp} (RR 1:{rr})")
                lot = calculate_lot_size(symbol, entry, sl)
                is_success = execute_mt5_order(action, symbol="GOLD", lot=lot, sl=sl, tp=tp)
                if is_success:
                    send_telegram_alert(action, "GOLD", entry, sl, tp, decision.get("reason"))
            else:
                print("⚠️ คำนวณ SL/TP ไม่ได้ — ยกเลิก Order")

        elif action == "WAIT":
            print(f"⏸️ WAIT | Score={score}/10 | {decision.get('reason')}")

        print("="*50 + "\n")
        append_to_journal(decision, calc_data)
        return decision, calc_data

    except json.JSONDecodeError:
        print(f"❌ JSON ผิดรูปแบบ:\n{raw}")
        return None, None
    except Exception as e:
        print(f"❌ สมองมีปัญหา: {e}")
        return None, None

# ==========================================
# 🌅 Morning Brief (ทุก Symbol พร้อมกัน)
# ==========================================
def morning_brief(symbols):
    """วิเคราะห์ทุก Symbol ในครั้งเดียว — คืน string สำหรับ Telegram"""
    print("🌅 [Morning Brief]: รวบรวมข้อมูลทุก Symbol...")

    sections = []
    for sym in symbols:
        path = os.path.join(BASE_DIR, "data", "market", f"latest_data_{sym}.md")
        data = read_file(path)
        if data:
            sections.append(f"### [{sym}]\n{data}")

    if not sections:
        print("⚠️ [Morning Brief]: ไม่มีข้อมูลตลาด ยกเลิก")
        return None

    constitution  = read_file(CONSTITUTION_PATH) or ""
    intelligence  = read_file(INTELLIGENCE_PATH)
    intel_section = f"\n[HERMES INTELLIGENCE]:\n{intelligence}" if intelligence else ""

    cme_raw = read_file(CME_DAILY_PATH)
    cme_section = (
        "\n[CME OPTIONS INTELLIGENCE (GOLD + BTC เท่านั้น)]:\n"
        + cme_raw
        + "\nวิธีใช้ CME Data ใน Entry Planning:\n"
        + "- Put Wall (Spot adj) = Strike ที่ Put OI สูงสุด → แรงรับ Institutional"
          " ถ้า GOLD อยู่เหนือ Put Wall และ Bias BULLISH → Entry Zone แข็งแกร่ง\n"
        + "- Call Wall (Spot adj) = Strike ที่ Call OI สูงสุด → แรงต้าน Institutional"
          " ระวังหากราคาวิ่งชน Call Wall โดยไม่มี OB รองรับ\n"
        + "- Max Pain (Spot adj) = Strike ที่ทำให้ Options Value รวมต่ำสุด"
          " → ตลาดมักดึงราคากลับหา Max Pain ก่อน Expiry ถ้า GOLD ห่าง Max Pain มากให้ระวัง Reversal\n"
        + "- ระดับทั้งหมด Spot-adjusted แล้ว (หัก Basis จาก GC Futures) เทียบกับ MT5 ได้โดยตรง\n"
        + "- COT MM Net > 0 = Institutional Long > Short → เสริม BULLISH Bias\n"
    ) if cme_raw else ""

    sym_lines = "\n".join(
        f'  "{s}": {{"bias": "BULLISH|BEARISH|WAIT", "wait_for": "...", '
        f'"entry_zone_top": 0.0, "entry_zone_btm": 0.0, '
        f'"sl_level": 0.0, "tp_level": 0.0, '
        f'"invalidate_if_above": 0.0, "note": "..."}},'
        for s in symbols
    )

    system_prompt = """You are MIDAS, an elite AI trading agent specializing in SMC and CME Options Data.
Give a concise briefing for each symbol based on current market structure and news.

STRATEGY RULES (apply per symbol):
- GOLD / BTCUSD (Primary): CME Wall + SMC Precision — ไม่มี Score ใช้ดุลยพินิจ + CME Data
- Secondary / ETHUSD: SMC Pure + Score ≥ 7 เท่านั้น — ไม่ใช้ CME
- Entry Method: ยืดหยุ่น — OB Retest, FVG Fill, MSS Break, Squeeze Fire หรือผสมกัน ตาม Context
CRITICAL: Output ONLY a valid JSON object. No markdown, no explanation, no extra text."""

    sections_str = "\n\n".join(sections)
    user_prompt = f"""[MARKET DATA]:
{sections_str}
{intel_section}
{cme_section}
For each symbol assess bias and identify key levels from actual OB/FVG/Swing High/Low in the data.
Rules:
- entry_zone_top / entry_zone_btm: the OB or FVG zone to watch for entry (aligned with bias)
- sl_level: beyond the swept liquidity or outside the OB (invalidation point)
- tp_level: GOLD/BTC → CME Wall ในทิศ Bias | Secondary/ETH → Structure Target ถัดไป
- invalidate_if_above: price level that would break the bearish thesis (or below for bullish)
- GOLD + BTC: ใช้ CME Wall เป็น Key Level — entry zone ควรอยู่ใกล้ Put Wall หรือ Call Wall
- Secondary + ETH: ใช้ SMC Structure เท่านั้น ไม่ใช้ CME
- Do NOT invent levels — use only values visible in the market data above

Output ONLY this JSON (fill numeric values, remove placeholder text):
{{
{sym_lines}
}}"""

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=2500,
            temperature=0.1,
            system=[
                {"type": "text", "text": constitution, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": system_prompt}
            ],
            messages=[{"role": "user", "content": user_prompt}],
            betas=["prompt-caching-2024-07-31"]
        )

        raw   = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        brief = json.loads(raw)

        # บันทึก JSON สำหรับ State Machine
        with open(MORNING_BRIEF_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(brief, f, ensure_ascii=False, indent=2)

        # บันทึก markdown
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(MORNING_BRIEF_PATH, "w", encoding="utf-8") as f:
            f.write(f"# 🌅 MIDAS MORNING BRIEF\n**{time_str} (BKK)**\n\n")
            for sym, info in brief.items():
                f.write(f"## {sym}\n")
                f.write(f"- **Bias:** {info.get('bias', 'N/A')}\n")
                f.write(f"- **รอ:** {info.get('wait_for', '-')}\n")
                ez_top = info.get('entry_zone_top', 0)
                ez_btm = info.get('entry_zone_btm', 0)
                if ez_top and ez_btm:
                    f.write(f"- **Entry Zone:** {ez_btm} – {ez_top}\n")
                if info.get('sl_level'):
                    f.write(f"- **SL:** {info['sl_level']}\n")
                if info.get('tp_level'):
                    f.write(f"- **TP:** {info['tp_level']}\n")
                if info.get('invalidate_if_above'):
                    f.write(f"- **Invalidate if above:** {info['invalidate_if_above']}\n")
                if info.get("note"):
                    f.write(f"- **Note:** {info['note']}\n")
                f.write("\n")

        # สร้าง Telegram message
        hm  = datetime.now().strftime("%H:%M")
        lines = [f"🌅 MIDAS BRIEF {hm} (BKK)"]
        for sym, info in brief.items():
            bias     = info.get("bias", "N/A")
            wait_for = info.get("wait_for", "")
            note     = info.get("note", "")
            icon     = "🟢" if bias == "BULLISH" else "🔴" if bias == "BEARISH" else "⚪"
            line     = f"{icon} {sym}: {bias}"
            if wait_for and wait_for not in ("-", "..."):
                line += f" | {wait_for}"
            if note and note not in ("-", "..."):
                line += f" ({note})"
            lines.append(line)

        print(f"✅ [Morning Brief]: เสร็จแล้ว")
        return "\n".join(lines)

    except json.JSONDecodeError:
        print(f"❌ [Morning Brief]: JSON ผิดรูปแบบ:\n{raw}")
        return None
    except Exception as e:
        print(f"❌ [Morning Brief]: {e}")
        return None


# ==========================================
# 📋 STATE 1: ขอ Watch Checklist
# ==========================================
def request_watch_checklist(symbol):
    market_data_path = os.path.join(BASE_DIR, "data", "market", f"latest_data_{symbol}.md")
    constitution = read_file(CONSTITUTION_PATH)
    market_data  = read_file(market_data_path)
    if not constitution or not market_data:
        return None

    is_primary = symbol in ("GOLD", "BTCUSD")
    strategy_context = (
        "STRATEGY: GOLD/BTC — ตรวจสอบด้วยว่าราคาอยู่ใกล้ CME Put Wall หรือ Call Wall ไหม ถ้าไม่ใกล้ Wall → ระมัดระวังมากขึ้น"
        if is_primary else
        "STRATEGY: Secondary/ETH — ใช้ SMC Structure เท่านั้น ไม่ต้องเช็ค CME"
    )

    system_prompt = """You are MIDAS, an elite AI trading agent specializing in SMC and CME Options Data.
Price has entered the watch zone from the Morning Brief. Analyze market structure and return a watch checklist.
CRITICAL: Output ONLY a valid JSON object. No markdown, no explanation, no extra text."""

    user_prompt = f"""[MARKET DATA]:
{market_data}

Price has entered the Entry Zone identified in the Morning Brief.
Analyze current H4/H1 structure and decide what trigger conditions must be met before executing.
{strategy_context}

Output ONLY this JSON:
{{
    "watch_for": {{
        "sweep": true,
        "squeeze_off": true,
        "histogram_dark": true
    }},
    "bias": "BULLISH|BEARISH",
    "invalidate_if": "อธิบาย price level หรือ condition ที่จะยกเลิก Setup นี้",
    "summary": "สรุปสั้นๆ ว่ากำลังรอดูอะไร (ภาษาไทย)"
}}"""

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=400,
            temperature=0.1,
            system=[
                {"type": "text", "text": constitution, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": system_prompt}
            ],
            messages=[{"role": "user", "content": user_prompt}],
            betas=["prompt-caching-2024-07-31"]
        )
        raw    = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        print(f"\n📋 [{symbol}] Watch Checklist: {result.get('summary', '')}")
        return result
    except Exception as e:
        print(f"❌ [Watch Checklist] {symbol}: {e}")
        return None


# ==========================================
# ⚡ STATE 2.5: Pre-Entry (Squeeze ON + ราคาใน Zone)
# ==========================================
def request_pre_entry(symbol):
    """ปลุก Midas เมื่อ Squeeze = ON + ราคาใน Zone — ตัดสิน PENDING/MARKET/WAIT"""
    market_data_path = os.path.join(BASE_DIR, "data", "market", f"latest_data_{symbol}.md")
    constitution = read_file(CONSTITUTION_PATH)
    market_data  = read_file(market_data_path)
    if not constitution or not market_data:
        return None

    is_primary = symbol in ("GOLD", "BTCUSD")
    cme_note = (
        "GOLD/BTC Rule: Entry ต้องอยู่ใกล้ CME Wall (Put Wall หรือ Call Wall) — ถ้าราคาอยู่ห่าง Wall มาก → WAIT"
        if is_primary else
        "Secondary/ETH Rule: Entry ตาม SMC Structure เท่านั้น — OB Retest, FVG Fill, หรือ MSS Break"
    )

    system_prompt = """You are MIDAS, an elite AI trading agent specializing in SMC and CME Options Data.
Squeeze momentum is building (state=ON) and price is inside the Entry Zone.
Decide the best entry method — not fixed to OB only. Entry is flexible based on market context.
CRITICAL: Output ONLY a valid JSON object. No markdown, no explanation, no extra text."""

    user_prompt = f"""[MARKET DATA]:
{market_data}

CONTEXT: Squeeze state=ON (momentum building). Price is currently inside the Entry Zone.
{cme_note}

Entry Methods ที่ใช้ได้ (เลือกตาม Context):
- PENDING = วาง BUY_LIMIT / SELL_LIMIT (ราคาจะ Retest ก่อน)
- MARKET = เข้าทันที (momentum แรงพอแล้ว — MSS Break หรือ Squeeze Fire)
- WAIT = เงื่อนไขยังไม่เหมาะสม

Output ONLY this JSON:
{{
    "action": "BUY|SELL|WAIT",
    "order_type": "PENDING|MARKET",
    "reason": "อธิบายสั้นๆ (ภาษาไทย)"
}}"""

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=250,
            temperature=0.1,
            system=[
                {"type": "text", "text": constitution, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": system_prompt}
            ],
            messages=[{"role": "user", "content": user_prompt}],
            betas=["prompt-caching-2024-07-31"]
        )
        raw    = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

        action     = result.get("action", "WAIT")
        order_type = result.get("order_type", "PENDING")

        if action == "WAIT":
            print(f"⏸️ [Pre-Entry] {symbol}: WAIT — {result.get('reason', '')}")
            return result

        entry, sl, tp, rr = calculate_gold_sl_tp(action, 7, market_data, symbol)
        if entry is None:
            print(f"⚠️ [Pre-Entry] {symbol}: คำนวณ Entry ไม่ได้ → WAIT")
            return {"action": "WAIT", "order_type": "PENDING", "reason": "คำนวณ Entry ไม่ได้"}

        print(f"\n⚡ [Pre-Entry] {symbol}: {action} {order_type} @ {entry} | SL={sl} TP={tp}")
        return {
            "action":     action,
            "order_type": order_type,
            "entry":      entry,
            "sl":         sl,
            "tp":         tp,
            "reason":     result.get("reason", ""),
        }

    except Exception as e:
        print(f"❌ [Pre-Entry] {symbol}: {e}")
        return None


# ==========================================
# 🔥 STATE 3: ยืนยันและ Execute
# ==========================================
def request_execute(symbol, watch_checklist):
    market_data_path = os.path.join(BASE_DIR, "data", "market", f"latest_data_{symbol}.md")
    constitution = read_file(CONSTITUTION_PATH)
    market_data  = read_file(market_data_path)
    if not constitution or not market_data:
        return None, None

    checklist_str = json.dumps(watch_checklist, ensure_ascii=False, indent=2)

    system_prompt = """You are MIDAS, an elite AI trading agent specializing in SMC.
All trigger conditions have been confirmed by Python. Do a final sanity check and execute.
CRITICAL: Output ONLY a valid JSON object. No markdown, no explanation, no extra text."""

    is_primary = symbol in ("GOLD", "BTCUSD")
    tp_note = (
        "TP: GOLD = ทุก $25 คือ 1 Block | BTC = ทุก $1,000 คือ 1 Block — TP Base 1 Block, Trail SL ครึ่ง Block ทุกครั้งที่ผ่าน 1 Block"
        if is_primary else
        "TP: Structure Target ถัดไป (Swing High/Low หรือ OB ถัดไป) — เข้าเมื่อ Score ≥ 7 เท่านั้น"
    )

    user_prompt = f"""[MARKET DATA]:
{market_data}

[WATCH CHECKLIST — ALL CONDITIONS MET BY PYTHON]:
{checklist_str}

Python confirmed all triggers. Final check: is structure still valid?
If YES → BUY or SELL. If something changed → WAIT with reason.
{tp_note}

Output ONLY this JSON (ห้ามใส่ entry, sl, tp — Python คำนวณเอง):
{{
    "action": "BUY|SELL|WAIT",
    "score": <0-10>,
    "confidence": "HIGH|MEDIUM|LOW",
    "bias": "BULLISH|BEARISH|NEUTRAL",
    "reason": "อธิบายสั้นๆ (ภาษาไทย)",
    "summary": "สรุป 1 บรรทัด (ภาษาไทย)"
}}"""

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=400,
            temperature=0.1,
            system=[
                {"type": "text", "text": constitution, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": system_prompt}
            ],
            messages=[{"role": "user", "content": user_prompt}],
            betas=["prompt-caching-2024-07-31"]
        )
        raw      = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        decision = json.loads(raw)

        print("\n" + "="*50)
        print(f"🔥 [{symbol}] EXECUTE DECISION:")
        print(json.dumps(decision, indent=4, ensure_ascii=False))

        action    = decision.get("action")
        score     = decision.get("score", 0)
        calc_data = (None, None, None, 0)

        if action in ["BUY", "SELL"]:
            entry, sl, tp, rr = calculate_gold_sl_tp(action, score, market_data, symbol)
            calc_data = (entry, sl, tp, rr)
            if entry:
                print(f"✅ Entry={entry} | SL={sl} | TP={tp} (RR 1:{rr})")

        append_to_journal(decision, calc_data, symbol)
        return decision, calc_data

    except Exception as e:
        print(f"❌ [Execute] {symbol}: {e}")
        return None, None


# ==========================================
# 🌙 Night Watch (ตรวจ Open Positions)
# ==========================================
def night_watch(symbols):
    """ประเมิน Open Positions ทั้งหมด — return dict by ticket string"""
    import MetaTrader5 as mt5

    print("🌙 [Night Watch]: ตรวจสอบ Open Positions...")

    if not mt5.initialize():
        print("⚠️ [Night Watch]: MT5 ไม่ตอบสนอง")
        return {}

    raw_positions = mt5.positions_get()
    if not raw_positions:
        print("🌙 [Night Watch]: ไม่มีไม้เปิดอยู่")
        mt5.shutdown()
        return {}

    # เก็บ metadata ไว้ Enrich ผล Claude ทีหลัง
    pos_meta = {}
    pos_list = []
    for pos in raw_positions:
        pos_meta[str(pos.ticket)] = {
            "symbol":   pos.symbol,
            "pos_type": pos.type,          # 0=BUY, 1=SELL
            "volume":   pos.volume,
            "profit":   round(pos.profit, 2),
        }
        pos_list.append({
            "ticket":     pos.ticket,
            "symbol":     pos.symbol,
            "type":       "BUY" if pos.type == 0 else "SELL",
            "volume":     pos.volume,
            "open_price": round(pos.price_open, 5),
            "current":    round(pos.price_current, 5),
            "profit":     round(pos.profit, 2),
            "sl":         pos.sl,
            "tp":         pos.tp,
        })
    mt5.shutdown()

    # รวมข้อมูลตลาด
    sections = []
    for sym in symbols:
        path = os.path.join(BASE_DIR, "data", "market", f"latest_data_{sym}.md")
        data = read_file(path)
        if data:
            sections.append(f"### [{sym}]\n{data}")

    pos_json_str    = json.dumps(pos_list, indent=2, ensure_ascii=False)
    market_str      = "\n\n".join(sections) if sections else "ไม่มีข้อมูลตลาด"
    expected_entries = "\n".join(
        f'  "{t}": {{"action": "A|B|C|D", "reason": "เหตุผลสั้นๆ ภาษาไทย"}},'
        for t in pos_meta
    )

    constitution = read_file(CONSTITUTION_PATH) or ""

    system_prompt = """You are MIDAS Night Watch, monitoring open trading positions overnight.
Assess each position and decide:
A = HOLD (profitable + structure intact + safe overnight)
B = CLOSE (break-even/small profit + unclear or weakening structure)
C = CLOSE (losing + structure broken or reversed)
D = ALERT_OWNER (losing but structure still valid — let owner decide)
CRITICAL: Output ONLY a valid JSON object. No markdown, no explanation, no extra text."""

    user_prompt = f"""[OPEN POSITIONS]:
{pos_json_str}

[CURRENT MARKET STRUCTURE]:
{market_str}

Assess each position. Output JSON with one entry per ticket:
{{
{expected_entries}
}}"""

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=500,
            temperature=0.1,
            system=[
                {"type": "text", "text": constitution, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": system_prompt}
            ],
            messages=[{"role": "user", "content": user_prompt}],
            betas=["prompt-caching-2024-07-31"]
        )

        raw    = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

        # Enrich ด้วย position metadata จาก MT5
        enriched = {}
        for ticket_str, info in result.items():
            meta = pos_meta.get(ticket_str, {})
            enriched[ticket_str] = {
                "action":   info.get("action", "D"),
                "symbol":   meta.get("symbol", ""),
                "pos_type": meta.get("pos_type", 0),
                "volume":   meta.get("volume", 0.01),
                "profit":   meta.get("profit", 0),
                "reason":   info.get("reason", ""),
            }

        print(f"✅ [Night Watch]: วิเคราะห์ {len(enriched)} ไม้เสร็จแล้ว")
        return enriched

    except json.JSONDecodeError:
        print(f"❌ [Night Watch]: JSON ผิดรูปแบบ")
        return {}
    except Exception as e:
        print(f"❌ [Night Watch]: {e}")
        return {}


# ==========================================
# 🔔 CME Change Alert — วิเคราะห์เมื่อ CME เปลี่ยนแปลงรุนแรง
# ==========================================
def analyze_cme_change(alerts):
    """รับ list of alert dicts → ถามเหตุผลจาก Claude → ส่ง Telegram ถ้า needs_action"""
    from auto_trade import send_telegram_message
    import MetaTrader5 as mt5

    print(f"🔔 [CME Alert]: {len(alerts)} สัญญาณ...")

    open_positions = []
    try:
        if mt5.initialize():
            raw = mt5.positions_get()
            if raw:
                for pos in raw:
                    open_positions.append({
                        "ticket":     pos.ticket,
                        "symbol":     pos.symbol,
                        "type":       "BUY" if pos.type == 0 else "SELL",
                        "open_price": round(pos.price_open, 5),
                        "current":    round(pos.price_current, 5),
                        "profit":     round(pos.profit, 2),
                    })
            mt5.shutdown()
    except Exception:
        pass

    cme_raw      = read_file(CME_DAILY_PATH)
    constitution = read_file(CONSTITUTION_PATH) or ""
    alert_str    = "\n".join(f"- {a['message']}" for a in alerts)
    pos_str      = json.dumps(open_positions, ensure_ascii=False, indent=2) if open_positions else "ไม่มี Position เปิดอยู่"

    system_prompt = """You are MIDAS, monitoring significant CME Gold/BTC options changes (ใช้กับ GOLD และ BTCUSD เท่านั้น).
A sudden shift in options positioning may signal institutional intent change.
ถ้า CME Wall เปลี่ยน (Put Wall หรือ Call Wall ย้ายระดับ) → ต้องปรับแผนทันที อย่ารอ
CRITICAL: Output ONLY a valid JSON object. No markdown, no explanation, no extra text."""

    user_prompt = f"""[CME ALERTS — SIGNIFICANT CHANGES]:
{alert_str}

[CURRENT CME DATA]:
{cme_raw or 'ไม่มีข้อมูล'}

[OPEN POSITIONS]:
{pos_str}

Analyze (GOLD + BTC เท่านั้น):
1. Is this a significant institutional signal?
2. ถ้า CME Wall ย้ายตำแหน่ง → ประเมินว่าต้องปรับ Bias หรือ Key Level ไหม
3. If positions are open — should owner HOLD or REVIEW?
4. Is immediate owner action needed?

Output ONLY this JSON:
{{
    "signal_strength": "HIGH|MEDIUM|LOW",
    "interpretation": "อธิบายว่า CME เปลี่ยนแปลงหมายความว่าอะไร (ภาษาไทย)",
    "position_impact": "ผลกระทบต่อไม้ที่เปิดอยู่ หรือ ไม่มีไม้เปิด (ภาษาไทย)",
    "needs_action": true,
    "recommendation": "สิ่งที่เจ้าของควรทำ (ภาษาไทย)"
}}"""

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=400,
            temperature=0.1,
            system=[
                {"type": "text", "text": constitution, "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": system_prompt}
            ],
            messages=[{"role": "user", "content": user_prompt}],
            betas=["prompt-caching-2024-07-31"]
        )
        raw    = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

        needs_action = result.get("needs_action", False)
        print(f"🔔 [CME Change]: {result.get('signal_strength')} | needs_action={needs_action}")

        if needs_action:
            alert_lines = "\n".join(f"• {a['message']}" for a in alerts)
            msg = (
                f"⚠️ CME Gold Alert\n\n"
                f"📊 การเปลี่ยนแปลง:\n{alert_lines}\n\n"
                f"🔍 {result.get('interpretation', '')}\n"
            )
            if open_positions:
                msg += f"\n💼 ผลต่อไม้: {result.get('position_impact', '')}"
            msg += f"\n\n🎯 {result.get('recommendation', '')}"
            send_telegram_message(msg)
            print("📲 [CME Change]: แจ้งเจ้าของแล้ว")

        return result

    except Exception as e:
        print(f"❌ [CME Change]: {e}")
        return None


if __name__ == "__main__":
    think_and_trade()