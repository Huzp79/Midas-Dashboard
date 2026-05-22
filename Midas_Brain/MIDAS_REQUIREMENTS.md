# MIDAS REQUIREMENTS & ARCHITECTURE
> Version: 3.2 | วันที่: 2026-05-22
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
- CME Data         → Max Pain, Call/Put Wall, COT (cme_scraper.py ✅)

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

## 16. CURRENT STATUS (ณ 22 พฤษภาคม 2026 — v3.2)

```
✅ ระบบรันได้แล้ว Multi-Symbol Auto-Trading (Demo Account)
✅ MT5 (XM Global) เชื่อมต่อได้ ส่ง JSON ออกมา 11 ไฟล์ต่อ Symbol
✅ 4-State Machine: SCANNING → WATCHING → EXECUTE → MONITORING (แยกต่อ Symbol)
✅ 9 Symbols: GOLD, BTCUSD, EURUSD, GBPJPY, GBPUSD, AUDUSD, USDCAD, USDCHF, ETHUSD
✅ Morning Brief รองรับ 9 Symbols (JSON + Markdown บันทึกอัตโนมัติ)
✅ Pre-Trade Brief Output: entry_zone_top/btm, sl_level, tp_level, invalidate_if_above
✅ State Machine ใช้ Morning Brief Entry Zone เป็นจุดเริ่ม WATCHING
✅ Python เช็ค Sweep/Squeeze/Histogram ฟรีทุก 60 วิ ก่อนปลุก Claude
✅ SL/TP คำนวณโดย Python จาก OB จริง (ไม่ให้ Claude เดา)
✅ Dynamic Lot Size จาก Balance จริงใน MT5 (Tiered Risk %)
✅ Trade Journal บันทึกอัตโนมัติ (ภาษาไทย)
✅ Telegram Alert ส่งได้เมื่อเปิดไม้ + แจ้งตอนปิดไม้ + Journal บันทึกผล
✅ Entry Price จริงจาก MT5 (actual fill price ไม่ใช่ค่าประมาณ)
✅ Move SL to Break Even อัตโนมัติเมื่อ BOS เกิดใน M5
✅ Daily Trade Limit 5 ไม้/วัน ต่อ Symbol
✅ Invalidation Rules: หมดเวลา 2 ชม + ราคาทะลุ Invalidation Level
✅ Pre-Entry Logic: วาง Pending Order ก่อน Squeeze ระเบิด (Squeeze ON + ราคาใน Zone)
✅ Hermes (background thread): ข่าว + Macro 3 รอบ/วัน
✅ Night Watch: ดูแลไม้กลางคืน 00:00 + 02:00 BKK
✅ Librarian Agent (librarian.py) รัน Auto ทุกวันจันทร์
✅ Obsidian Knowledge Graph ครบ — Constitution เป็นศูนย์กลาง
✅ Indicator Philosophy บันทึกใน Constitution แล้ว
   (HTF Structure = Bias หลัก, iCHoCH ใน LTF = Pullback ไม่ใช่ Reversal)
✅ ไม้แรก TP สำเร็จ +$112
✅ CME Scraper (cme_scraper.py) ทำงานได้แล้ว
   - Vol2Vol: Put/Call Volume, Volatility, Future Price
   - OI Heatmap: Put Wall, Call Wall, Max Pain (131 strikes)
   - COT Report: Managed Money Net Position
   - Basis คำนวณอัตโนมัติ (GC Futures - Gold Spot)
   - ปรับ Strike ทุกตัวด้วย Basis ให้ตรง Spot จริง
   - เขียนสรุปลง Midas_Brain/data/market/CME_Daily.md
   - Chrome Debug Port 9222 ต้องเปิดค้างไว้ก่อน
✅ CME Scraper รวมใน Hermes รันอัตโนมัติ 06:30
   (Hermes.py เรียก fetch_all() ใน write_intelligence_report() เมื่อ hour=6)
✅ Midas อ่าน CME_Daily.md ใน Morning Brief
   (brain.py inject Put Wall/Call Wall/Max Pain + คำอธิบายเข้า user_prompt)
✅ start_midas.bat เปิดทุกอย่างด้วย Double Click
   (Chrome debug port 9222 → รอ 3 วิ → CMD รัน main.py ด้วย pushd path)
✅ Auto เลือก Expiry ใหม่อัตโนมัติ (DTE Sort)
   (cme_scraper.py _select_nearest_weekly() sort by DTE ≥ 0)
✅ Hermes.py rename fix (hermes.py → Hermes.py — case-sensitive import)
✅ Telegram Cleanup — แจ้งแค่ที่จำเป็น:
   - Execute Trade: Entry, SL, TP, Lot, เหตุผลสั้นๆ
   - BE Alert: เมื่อ SL ย้ายมา Break Even
   - TP Hit / SL Hit: ผลกำไร/ขาดทุน
   - Action D (Night Watch): ติดลบแต่โครงสร้างดี รอเจ้าของตัดสินใจ
   - Morning Brief: ไม่ส่ง Telegram (บันทึกไฟล์เงียบๆ)
   - Night Watch Round 1: ไม่ส่ง Telegram (log เท่านั้น)
   - CME Change: ส่งเฉพาะถ้า needs_action = true
✅ CME Hourly Schedule (Hermes.py + main.py):
   - Vol2Vol ทุกชั่วโมง (XX:00) → เช็ค PC Ratio เปลี่ยน > 0.3
   - OI Matrix ทุก 6 ชั่วโมง (06/12/18/23) → เช็ค OI Wall ย้าย > 50 pts
   - COT เฉพาะวันศุกร์ 06:00
   - cme_snapshot.json เก็บ State ข้ามรอบ
✅ CME Change Alert (brain.analyze_cme_change()):
   - รับ alerts จาก Hermes.check_cme_alerts()
   - ดึง Open Positions จาก MT5 มาประกอบ Context
   - ส่ง Claude วิเคราะห์ว่าควรถือต่อหรือปรับ
   - แจ้ง Telegram เฉพาะถ้า needs_action = true
✅ CME_Options_Knowledge.md — ความรู้ CME ครบถ้วนสำหรับ Midas
   (Max Pain, Put/Call Wall, PC Ratio, COT, Basis, วิธีใช้ร่วม SMC + ตัวอย่าง)
```

---

## 17. NEXT STEPS (เรียงตาม Priority)

```
✅ Spread Filter — เสร็จแล้ว
✅ Invalidation Rules — เสร็จแล้ว
✅ Morning Brief 3 ครั้ง/วัน — เสร็จแล้ว
✅ Night Watch — เสร็จแล้ว
✅ 4-State Machine — เสร็จแล้ว
✅ 9 Symbols + Morning Brief Entry Zone — เสร็จแล้ว
✅ CME Scraper (Vol2Vol + OI Heatmap + COT + Basis) — เสร็จแล้ว
✅ CME Scraper รวมใน Hermes 06:30 — เสร็จแล้ว
✅ Midas อ่าน CME_Daily.md ใน Morning Brief — เสร็จแล้ว
✅ start_midas.bat (One-click launcher) — เสร็จแล้ว
✅ Auto เลือก Expiry ใหม่อัตโนมัติ — เสร็จแล้ว
✅ Pre-Entry Logic (Pending Order ก่อน Squeeze ระเบิด) — เสร็จแล้ว
✅ Telegram แจ้งตอนปิดไม้ + Journal บันทึกผล — เสร็จแล้ว
✅ Entry Price จริงจาก MT5 — เสร็จแล้ว
✅ Telegram Cleanup (แจ้งแค่ที่จำเป็น) — เสร็จแล้ว
✅ CME Hourly Schedule — เสร็จแล้ว
✅ CME Change Alert (analyze_cme_change) — เสร็จแล้ว
✅ CME_Options_Knowledge.md — เสร็จแล้ว
✅ Hermes.py rename fix — เสร็จแล้ว

🔴 P1: Telegram Two-Way (รับคำสั่งจาก Telegram)
   ปัจจุบัน: Telegram ส่งได้ทางเดียว (แจ้งเตือน)
   ต้องการ: รับคำสั่งจาก Telegram เช่น /status /pause /close_all

🔴 P2: Backtest Logic ย้อนหลัง
   ทดสอบ Setup + Entry Logic กับ Historical Data ก่อน Live Trade
   หา Win Rate จริงของ Core Setup บน GOLD

🟡 P3: Crypto 24H Scanning (BTCUSD/ETHUSD ไม่มีเวลาหยุด)
   ปัจจุบัน: ใช้เวลาทำการเดียวกับ Forex (08:00–23:30)
   ต้องการ: สแกน Crypto ตลอด 24 ชั่วโมง แยก Thread

🟡 P4: Librarian (รอ Journal สะสม 1 สัปดาห์)
   ต้องมี Trade Journal ≥ 1 สัปดาห์ก่อน Report จะมีความหมาย
   เพิ่ม field ผล Win/Loss ใน Journal เพื่อคำนวณ Win Rate จริงได้

🟢 P5: Live Trade เมื่อผ่านเกณฑ์ทั้งหมด
   ดูเกณฑ์ใน Section 18
```

---

## 18. เกณฑ์ก่อน Live Trade

```
ต้องผ่านทุกข้อก่อน เปลี่ยนจาก Demo → Live:

✅ Win Rate ≥ 45% จากไม้จริง ≥ 20 ไม้
✅ RR เฉลี่ย ≥ 1:2
✅ ไม่มี Bug ร้ายแรงใน 1 สัปดาห์ (ระบบรันเสถียร)
✅ Librarian วิเคราะห์ได้แล้ว (มี Journal สะสม ≥ 1 สัปดาห์)

ยังไม่ผ่าน → Demo ต่อไป ห้ามรีบ
```

---

## 19. HOW TO START NEW CONVERSATION

เมื่อเปิด Conversation ใหม่กับ Claude ให้ส่งข้อความนี้

```
"อ่าน MIDAS_REQUIREMENTS.md นี้ก่อนเลย
นี่คือระบบ AI Trading Agent ที่กำลังสร้างอยู่
ต้องการให้ช่วย [บอกสิ่งที่ต้องการ]"

แนบไฟล์: MIDAS_REQUIREMENTS.md
```

Claude จะเข้าใจ Context ทั้งหมดได้ทันทีโดยไม่ต้องเล่าใหม่

---

*Requirements version 3.2*
*อัปเดตจากการสัมภาษณ์เจ้าของระบบ + SMC Model ของ Craig Percoco*
*อัปเดตครั้งต่อไปหลังทดสอบ Demo 2 สัปดาห์ หรือเมื่อ Priority ใหม่เพิ่มเข้ามา*

---

related: [[00_Midas_Constitution]] [[MIDAS_PROMPT_BLUEPRINT]]
