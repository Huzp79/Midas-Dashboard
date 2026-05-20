# MIDAS REQUIREMENTS & ARCHITECTURE
> Version: 2.6 | วันที่: 2026-05-21
> เอกสารนี้คือ Source of Truth ของ Midas ทั้งหมด
> ห้ามเขียนโค้ดโดยไม่อ่านเอกสารนี้ก่อน

---

## 1. IDENTITY & PHILOSOPHY

Midas คือ AI Trading Agent ไม่ใช่ EA

```
EA  = ถ้า Indicator A + B + C → เทรด (ตายตัว)
AI  = อ่านตลาดแบบองค์รวม ตัดสินใจจากบริบท
      Indicator คือเครื่องมือช่วยยืนยัน ไม่ใช่ตัวตัดสิน
```

Midas ต้องคิดแบบเทรดเดอร์ SMC ที่มีประสบการณ์
ที่ถามตัวเองว่า "ถ้าเป็นเงินตัวเอง จะเข้าไหม?"

---

## 2. TRADING UNIVERSE

- สแกนทุกคู่เงินใน MT5 Market Watch
- GOLD (XAUUSD) คือ Primary Focus
- คู่อื่นเลือกเองตาม Setup ที่ดีที่สุดในขณะนั้น
- เวลาทำการ: 08:00–23:30 Bangkok Time

---

## 3. CORE SETUP (Trade DNA)

นี่คือ Setup ที่ได้ผลดีที่สุดสำหรับระบบนี้
อ้างอิงจากประสบการณ์จริงและ SMC Model ของ Craig Percoco

### STEP 1 — HTF Context (H4 + H1)
```
ราคาต้องวิ่งเข้าหาโซนสำคัญของ HTF
(Key Level = OB+, FVG, หรือ Liquidity Pool ของ H4/H1)

ถ้าราคายังไม่แตะโซนสำคัญ HTF → ไม่เทรด
```

### STEP 2 — Sweep + CHoCH/MSS (LTF)
```
เมื่อราคาชนโซน HTF แล้ว ต้องเกิด:
1. Liquidity Sweep (กวาดสภาพคล่อง)
2. CHoCH หรือ MSS (โครงสร้างกลับทิศ)
   พร้อมกับทิ้ง FVG ไว้ในจังหวะที่กระชากแรง

ถ้าไม่มี Sweep + CHoCH → รอต่อ ไม่เข้า
```

### STEP 3 — FVG + OB Confirmation (M15/M5)
```
FVG ที่เกิดจาก CHoCH ต้องมี OB สนับสนุนด้วย
(OB = แท่งเทียนสีตรงข้ามแท่งสุดท้ายก่อนกระชาก)

ถ้ามีแค่ FVG แต่ไม่มี OB รองรับ → Setup ไม่แข็งแรง
```

### STEP 4 — Entry Execution
```
ไม่เข้าทันทีที่ราคาแตะ FVG

รอให้ราคา Pullback มาที่ครึ่งทางของ FVG
(Consequential Encroachment = 50% ของ FVG)

จากนั้นค่อยตั้ง Pending Order หรือ Market Order
```

### STEP 5 — M1 Trigger (ยืนยันขั้นสุดท้าย)
```
Squeeze Momentum M1 เปลี่ยนสี
(สว่าง → เข้ม ในทิศทางที่ต้องการ)

นี่คือสัญญาณสุดท้ายก่อน Execute
```

---

## 4. RISK DEFINITION

```
SL: วางหลัง Swing High/Low ล่าสุด เสมอ
    ห้ามวางแค่หลังขอบ FVG
    (เจ้ามือจะสะบัดกิน SL ถ้าวางใกล้เกินไป)
    สำหรับ GOLD: SL ควรอยู่ที่ 300-800 pip

TP: โครงสร้างราคาถัดไป (Swing High/Low ถัดไป)
    Target RR ขั้นต่ำ 1:3
    ถ้ากราฟแรงและเกิด BOS → ปล่อยให้วิ่งต่อ

Lot Size: Midas ประเมินเองตาม Setup และขนาดพอร์ต
    พอร์ต < $200      → ALL IN ได้ (เป้าหมายปั้นพอร์ต)
    พอร์ต $200-500    → Risk 10-20% ต่อไม้
    พอร์ต $500-1000   → Risk 5-10% ต่อไม้
    พอร์ต $1000-3000  → Risk 2-5% ต่อไม้
    พอร์ต $3000-5000  → Risk 1-2% ต่อไม้
    พอร์ต > $5000     → Risk 0.5-1% ต่อไม้
```

---

## 5. TRADE MANAGEMENT

```
เมื่อราคาทำ BOS สำเร็จ (Break of Structure):
→ ย้าย SL มาที่ Break Even ทันที
→ ความเสี่ยงกลายเป็น 0%
→ ปล่อยให้วิ่งไปถึง TP หรือ BOS ถัดไป

เวลา 23:30 BKK:
→ Midas ประเมินสถานการณ์เอง
→ ถ้าโครงสร้างยังสนับสนุน → อาจถือต่อ
→ ถ้าโครงสร้างพัง → ปิดทันที
```

---

## 6. AI THINKING FRAMEWORK

Midas ต้องคิดตามลำดับนี้ก่อนทุกการตัดสินใจ

```
1. ตลาดกำลังทำอะไร? (ดูภาพรวมก่อน ไม่ดู Indicator)
   → ขึ้น/ลง/Sideway?
   → ถ้าไม่ชัด → ไม่เทรด

2. ราคาอยู่ตรงไหนของโครงสร้าง?
   → ใกล้โซน HTF สำคัญไหม?
   → กลางทาง? → ไม่เทรด R:R ไม่คุ้ม

3. เกิดเหตุการณ์สำคัญไหม?
   → Sweep + CHoCH เกิดแล้วไหม?
   → FVG ทิ้งไว้ไหม?
   → ถ้าไม่มี → รอ

4. CME บอกอะไร?
   → Max Pain อยู่ตรงไหน?
   → Call/Put Wall ใหญ่อยู่ที่ราคาไหน?
   → SMC และ CME ชี้ทิศเดียวกัน = Setup แข็งแกร่ง

5. SL สมเหตุสมผลไหม?
   → ไกลเกินไป → ไม่เทรด
   → แคบและอยู่หลัง Swing → ดำเนินการต่อ

6. ถ้าเป็นเงินตัวเอง เข้าไหม?
   → ใช่ชัดเจน → HIGH confidence → เข้า
   → ไม่แน่ใจ → WAIT เสมอ
```

---

## 7. PRE-FILTER SYSTEM (Python ทำฟรี ก่อนปลุก Claude)

```
ทุก 60 วินาที Python เช็คเองโดยไม่เสียเงิน:

เช็คที่ 1: H4 + H1 Swing Trend ตรงกันไหม?
→ ไม่ตรง → ข้ามทันที

เช็คที่ 2: ราคาเข้าใกล้ OB/FVG ของ HTF ไหม?
→ ยังไม่เข้า → ข้ามทันที

เช็คที่ 3: มี Sweep สด (bars_ago ≤ 3) ไหม?
→ ยังไม่มี → ข้ามทันที

ผ่านทั้ง 3 ข้อ → ปลุก Claude ครั้งเดียว
Claude วิเคราะห์และตัดสินใจ
```

---

## 8. MONEY MANAGEMENT

```
หลักการ:
พอร์ต < $200      → ALL IN ได้ (เป้าหมายปั้นพอร์ต 200-400%)
พอร์ต $200-500    → Risk 10-20% ต่อไม้
พอร์ต $500-1000   → Risk 5-10% ต่อไม้
พอร์ต $1000-3000  → Risk 2-5% ต่อไม้
พอร์ต $3000-5000  → Risk 1-2% ต่อไม้
พอร์ต > $5000     → Risk 0.5-1% ต่อไม้

ถ้าขาดทุน 3 ไม้ติดกัน:
→ หยุดเทรดทันที
→ ประเมินสาเหตุ (ดูข้อ 9)
```

---

## 9. LOSS MANAGEMENT & LEARNING

```
ทุกครั้งที่ขาดทุน Midas ต้องประเมิน:

กรณีที่ 1: ผิดเพราะตลาด
(News spike, Manipulation, Black Swan)
→ บันทึกลง Wiki:
  "Setup แบบนี้ในสภาวะแบบนี้ระวัง"
→ ครั้งหน้าเจอ Setup คล้ายกัน Score ต่ำลง

กรณีที่ 2: ผิดเพราะ Logic พัง
(Midas อ่านตลาดผิด สัญญาณไม่ Valid)
→ หยุดเทรดทันที
→ แจ้ง Claude Code ในเครื่องให้มาตรวจสอบและแก้ไข
→ รอการแก้ไขก่อนเทรดต่อ
```

---

## 10. REPORTING (Telegram)

```
ตอนเปิดไม้:
✅ Symbol และ Direction (BUY/SELL)
✅ Entry / SL / TP
✅ R:R ที่คาดไว้
✅ Score และ Confidence
✅ เหตุผลสั้นๆ แบบเทรดเดอร์

ตอนปิดไม้:
✅ ผลกำไร/ขาดทุน (pip และ $)
✅ เหตุผลที่ปิด

ระหว่างไม้เปิดอยู่:
❌ ไม่แจ้งอะไรทั้งนั้น

Daily Brief:
❌ ไม่ส่งอัตโนมัติ
✅ Midas วิเคราะห์ได้เสมอถ้าถาม
```

---

## 11. DATA SOURCES

```
MT5 Indicators (JSON ฟรี):
- SMC God Eye      → Structure, OB, FVG | TF: H4, H1, M30, M15, M5, M1 (ครบทุก TF)
- MACD Divergence  → Divergence         | TF: H1 เท่านั้น (ไม่ต้องการ H4)
- LQ Sweep         → Sweep Zone + bars_ago | TF: M15, M5
- Volume Profile   → POC, VAL, VAH      | TF: M15 เท่านั้น
- Squeeze Momentum → is_firing_now, direction | TF: M1 เท่านั้น

Hermes (External):
- Forex Factory    → ข่าว High/Medium Impact
- DXY, VIX, GVZ   → Macro Context
- CME Data         → Max Pain, Call/Put Wall (TODO)

Claude (เสียเงิน เรียกเฉพาะเมื่อจำเป็น):
- วิเคราะห์ภาพรวม
- ตัดสินใจเข้าไม้
- ประเมินการปิดไม้
- วิเคราะห์สาเหตุขาดทุน
```

---

## 12. SYSTEM ARCHITECTURE

```
[ทุก 60 วินาที]
Pre-Filter Python (ฟรี)
├── H4+H1 ตรงกัน?
├── ราคาใกล้โซน HTF?
└── Sweep สด?
    ↓ ผ่านทั้ง 3
Claude วิเคราะห์ (เสียเงิน)
├── อ่านภาพรวม SMC ทุก TF
├── ประเมิน CME Data
├── Score + Confidence
└── BUY / SELL / WAIT
    ↓ BUY หรือ SELL
Python คำนวณ SL/TP
(จาก Swing High/Low จริงๆ ไม่ให้ Claude เดา)
    ↓
MT5 Execute Order
    ↓
Telegram แจ้ง
    ↓
Journal บันทึก
    ↓
Wiki อัปเดต (Librarian - TODO)
```

---

## 13. FILES & RESPONSIBILITIES

```
main.py         → ศูนย์บัญชาการ + Pre-Filter + State Machine
brain.py        → ส่งข้อมูลให้ Claude วิเคราะห์
feed_midas.py   → ดึง JSON จาก MT5 Indicators
hermes.py       → ดึงข่าวและ Macro Data
auto_trade.py   → Execute Order + Telegram Alert
librarian.py    → วิเคราะห์ Trade + อัปเดต Wiki (TODO)

Midas_Brain/
├── 00_Midas_Constitution.md   → System Prompt หลักของ Claude
├── MIDAS_REQUIREMENTS.md      → เอกสารนี้
├── MIDAS_PROMPT_BLUEPRINT.md  → Blueprint สำหรับ AI อื่น
├── raw/
│   ├── market_data/           → ข้อมูลตลาดล่าสุด
│   └── trades/                → Trade Journal รายวัน
└── wiki/
    ├── strategies/            → Setup ที่ผ่านการทดสอบ
    └── lessons/               → บทเรียนจากการขาดทุน
```

---

## 14. WHAT MIDAS IS NOT

```
❌ ไม่ใช่ EA ที่ทำตาม Indicator อย่างเดียว
❌ ไม่ตัดสินจาก Indicator เพียงอย่างเดียว
❌ ไม่เทรดทุกครั้งที่มีสัญญาณ
❌ ไม่ส่ง Report โดยไม่จำเป็น
❌ ไม่เทรดถ้าโครงสร้างไม่ชัด
❌ ไม่เข้าทันทีที่เห็น FVG (ต้องรอ 50% ของ FVG)
❌ ไม่วาง SL แค่หลังขอบ FVG
```

---

## 15. SUCCESS CRITERIA

```
ระยะสั้น (1 เดือน):
- ไม่ขาดทุนเกิน 50% ของพอร์ต
- Win Rate ≥ 40%
- R:R เฉลี่ย ≥ 1:3

ระยะกลาง (3 เดือน):
- พอร์ต $50 → $200+ (400%)
- Win Rate ≥ 45%
- Midas เรียนรู้และปรับตัวได้จาก Wiki

ระยะยาว:
- ลด Risk ตามพอร์ตที่โตขึ้น
- Librarian สร้าง Wiki ที่มีคุณค่าจริงๆ
- Claude Code แก้ไข Logic ได้เองเมื่อพัง
```

---

## 16. CURRENT STATUS (ณ 20 พฤษภาคม 2026)

```
✅ ระบบรันได้แล้ว Multi-Symbol Auto-Trading (Demo Account)
   Symbols: GOLD, BTCUSD, EURUSD, GBPJPY — State Machine แยกอิสระต่อ Symbol
✅ MT5 (XM Global) เชื่อมต่อได้ ส่ง JSON ออกมา 11 ไฟล์ต่อ Symbol (44 ไฟล์รวม)
✅ State Machine 3 ด่าน: SCANNING → ARMED → READY_TO_FIRE (แยกต่อ Symbol)
✅ H4+H1 Pre-Filter ทำงานใน Python แล้ว ไม่เสีย API เมื่อ Bias ขัดกัน
✅ ปลุก Claude เมื่อ H1 swing_trend เปลี่ยนทิศเท่านั้น (ไม่ใช้ Cooldown Timer)
✅ SL/TP Regex แก้แล้ว ตรงกับ format จริงของ feed_midas.py
✅ SL/TP Filter ยืดหยุ่นตาม Symbol (GOLD>100, BTC>1000, Forex>0.5)
✅ Brain.py ใช้ Thinking Framework 4 Steps
✅ Confidence → Lot Size (HIGH=0.02, MEDIUM=0.01)
✅ Trade Journal บันทึกอัตโนมัติ (ภาษาไทย)
✅ Telegram Alert ส่งได้เมื่อเปิดไม้
✅ Daily Trade Limit 5 ไม้/วัน ต่อ Symbol
✅ Hermes รวมใน main.py อัตโนมัติ (background thread) ไม่ต้องเปิด Terminal แยก
   Schedule: 06:30 / 13:30 / 18:30 BKK + รันรอบแรกทันทีตอนบูต
✅ Librarian Agent สร้างแล้ว (librarian.py) รัน Auto ทุกวันจันทร์
   รอ Trade Journal สะสมก่อนจึงจะมีข้อมูลวิเคราะห์

JSON Files ที่ใช้งานจริง (11 ไฟล์ต่อ Symbol):
- SMC God Eye: H4, H1, M30, M15, M5, M1 ✅ ครบทุก TF
- MACD Divergence: H1 เท่านั้น ✅ (ไม่ต้องการ H4)
- LQ Sweep: M15, M5 ✅ (เพียงพอสำหรับ Trigger)
- Volume Profile: M15 ✅ (เพียงพอสำหรับ Location)
- Squeeze Momentum: M1 ✅ (Trigger หลัก)

✅ Obsidian Knowledge Graph ครบ — Constitution เป็นศูนย์กลาง
✅ โครงสร้าง 5 กลุ่ม: Market Data, Strategies, Knowledge, Journal, Lessons
✅ wiki/strategies/: SMC_Core_Setup, Killzone_Playbook, AMD_Pattern
✅ wiki/knowledge/: SMC_Concepts, Market_Psychology, Macro_Framework
✅ Folder refactor: raw/ → data/market + data/journal

สิ่งที่ยังต้องพัฒนา:
⚠️ ยังไม่ได้เปิด Live Trading
⚠️ Spread Filter ยังไม่ได้ implement (GOLD>60pip, Forex>40pip, BTC>5000pip)
⚠️ Morning Brief 3 ครั้ง/วัน ยังไม่มี
⚠️ Invalidation Rules ยังไม่มี (OB ทะลุ, Setup อายุ>2ชม ฯลฯ)
⚠️ Sentinel Agent (Monitor Trade ที่เปิดอยู่) ยังไม่มี
```

---

## 17. NEXT STEPS (เรียงตาม Priority)

```
✅ Priority 1: Spread Filter — เสร็จแล้ว
   ก่อนยิง Order เช็ค Spread ใน MT5 ว่าไม่กว้างเกิน:
   GOLD   → Spread ≤ 60 pip
   Forex  → Spread ≤ 40 pip
   BTCUSD → Spread ≤ 5000 pip
   ถ้า Spread กว้างกว่านี้ → ยกเลิก Order ทันที

✅ Priority 2: Invalidation Rules — เสร็จแล้ว
   Setup ที่ ARMED อยู่ต้องถูกยกเลิกและรีเซ็ต SCANNING เมื่อ:
   - Rule 1: Setup อายุเกิน 2 ชั่วโมงนับจาก ARMED
   - Rule 2: H1 swing_trend เปลี่ยนทิศ (Bias เดิมไม่ valid แล้ว)
   - Rule 3: OB Reference ถูกทะลุ (ใช้ H1 OB เป็น Reference ไม่ใช่ M15 OB)
   - Rule 4: มีข่าวแดง HIGH Impact ใน 30 นาทีข้างหน้า (แปลง EDT/EST→Bangkok แล้ว)

✅ Priority 3: Morning Brief (3 ครั้ง/วัน) — เสร็จแล้ว
   สรุปภาพรวมตลาดก่อนเข้าแต่ละ Session ส่งผ่าน Telegram:
   - 07:00 BKK → Pre-Asia Brief
   - 14:00 BKK → Pre-London Brief
   - 19:00 BKK → Pre-NY Brief
   brain.morning_brief() วิเคราะห์ทุก Symbol พร้อมกันในครั้งเดียว (ประหยัด Token)
   บันทึกลง morning_brief.md + ส่ง Telegram อัตโนมัติ

✅ Night Watch — เสร็จแล้ว
   ดูแลไม้ที่เปิดอยู่ช่วงกลางคืน รัน 2 รอบผ่าน background thread:
   - 00:00 BKK → Round 1: วิเคราะห์ + รายงานสรุปเท่านั้น ไม่ดำเนินการ
   - 02:00 BKK → FINAL: ดำเนินการตาม Action
     Action A = HOLD (กำไร + โครงสร้างดี) → log ถือต่อ
     Action B = CLOSE (เสมอทุน/กำไรน้อย + ไม่ชัด) → ปิดไม้ทันที
     Action C = CLOSE (ติดลบ + โครงสร้างพัง) → ปิดไม้ทันที
     Action D = ALERT (ติดลบ + โครงสร้างยังดี) → Telegram แจ้งเจ้าของรอตัดสินใจ
   ถ้าไม่มีไม้เปิด @ 02:00 → แจ้ง "Idle จนถึง 07:00"

🟡 Priority 4: Wait_for Output Format ใน Claude Response
   เพิ่ม field ใน JSON Output ของ Brain:
   "wait_for": "อธิบายว่ารอเหตุการณ์อะไรก่อนถึงจะเทรด"
   ใช้เพื่อ Log และแสดงใน Telegram ว่า Midas รออะไรอยู่

🟢 Priority 5: Sentinel Agent
   Monitor Trade ที่เปิดอยู่ใน MT5 แบบ Real-time:
   - เช็ค BOS (Break of Structure) → ย้าย SL to Break Even
   - เช็คเวลา 23:30 → ประเมินว่าถือต่อหรือปิด
   - แจ้ง Telegram เมื่อ TP หรือ SL ถูก Hit

🟢 Priority 6: Librarian (รอ Trade Journal สะสมก่อน)
   ต้องมี Trade Journal ≥ 1 สัปดาห์ก่อน Report จะมีความหมาย
   เพิ่ม field ผล Win/Loss ใน Journal เพื่อคำนวณ Win Rate จริงได้

🔵 Priority 7: COT Report (Phase 2)
   ดึงข้อมูล Commitment of Traders จาก CFTC
   ใช้ประกอบการวิเคราะห์ Institutional Bias รายสัปดาห์
```

---

## 18. HOW TO START NEW CONVERSATION

เมื่อเปิด Conversation ใหม่กับ Claude ให้ส่งข้อความนี้

```
"อ่าน MIDAS_REQUIREMENTS.md นี้ก่อนเลย
นี่คือระบบ AI Trading Agent ที่กำลังสร้างอยู่
ต้องการให้ช่วย [บอกสิ่งที่ต้องการ]"

แนบไฟล์: MIDAS_REQUIREMENTS.md
```

Claude จะเข้าใจ Context ทั้งหมดได้ทันทีโดยไม่ต้องเล่าใหม่

---

*Requirements version 2.6*
*อัปเดตจากการสัมภาษณ์เจ้าของระบบ + SMC Model ของ Craig Percoco*
*อัปเดตครั้งต่อไปหลังทดสอบ Demo 2 สัปดาห์ หรือเมื่อ Priority ใหม่เพิ่มเข้ามา*

---

related: [[00_Midas_Constitution]] [[MIDAS_PROMPT_BLUEPRINT]]
