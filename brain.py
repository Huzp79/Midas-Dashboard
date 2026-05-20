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
INTELLIGENCE_PATH = os.path.join(BASE_DIR, "raw", "market_data", "daily_intelligence.md")

PRICE_FILTERS = {
    "GOLD":   100,
    "BTCUSD": 1000,
    "EURUSD": 0.5,
    "GBPJPY": 100,
}
TRADE_LOG_DIR     = os.path.join(BASE_DIR, "raw", "trades")
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
# 🧠 6. สมองหลัก
# ==========================================
def think_and_trade(symbol="GOLD"):
    print("🧠 [Midas Brain]: กำลังวิเคราะห์ตลาด...")

    market_data_path = os.path.join(BASE_DIR, "raw", "market_data", f"latest_data_{symbol}.md")
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

    user_prompt = f"""[CONSTITUTION & RULES]:
{constitution}
{intel_section}

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
- is_firing_now ของ Squeeze:
  true + ทิศทางตรง Bias = ยิงได้ ✅

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
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
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
                lot = 0.02 if confidence == "HIGH" else 0.01
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

if __name__ == "__main__":
    think_and_trade()