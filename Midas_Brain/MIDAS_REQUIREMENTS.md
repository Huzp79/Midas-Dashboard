# MIDAS REQUIREMENTS & ARCHITECTURE
> Version: 3.5 | วันที่: 2026-05-24
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

**Primary (CME Wall + SMC Precision):**
- GOLD (XAUUSD), BTCUSD
- ไม่ใช้ Score System — ดุลยพินิจ Midas + CME Data

**Secondary (SMC Pure + Score System ≥ 7):**
- EURUSD, GBPJPY, GBPUSD, AUDUSD, USDCAD, USDCHF, ETHUSD

**เวลาทำการ:**
- Forex + GOLD: สแกน 08:00–00:00 Bangkok Time
- Crypto (BTC/ETH): ไม่มีกฎเวลา ยกเว้นข่าวใหญ่
- หลัง 00:00 → ตรวจว่ามีไม้เปิดอยู่ไหม ถ้าไม่มี → ปิดระบบ รอ 07:00
- 02:00 → ประเมินสถานการณ์ แจ้ง Telegram ถ้าไม่แน่ใจ (รอตอบ 15 นาที)

---

## 3. CORE SETUP — Secondary + ETH (Trade DNA)

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

## 3B. STRATEGY: GOLD + BTC

> CME Wall + SMC Precision — ไม่ใช้ Score System

```
Entry:     FVG หลัง MSS ที่บริเวณ Put/Call Wall
SL:        Low/High ที่ Wall
TP Base:   1 Block (GOLD = $25 | BTC = $1,000)
TP Extend: 2–3 Block ถ้า Volume สูง + Killzone + โครงสร้างไม่เสีย
Trail SL:  ครึ่ง Block ทุกครั้งที่ผ่าน 1 Block
```

---

## 3C. CME INTEGRATION (GOLD + BTC เท่านั้น)

```
Put Wall        = แนวรับ Institutional
Call Wall       = แนวต้าน Institutional
Max Pain        = Target ก่อน Expiry
Confluence Zone = CME Wall + SMC OB + POC ห่างกันไม่เกิน 10 points
                  → เสริมความมั่นใจ ไม่บังคับ
วันศุกร์ DTE ใกล้ 0 → ยังเทรดได้ ถ้าไม่มั่นใจลด Risk
```

---

## 3D. MACD RULES (H1 เท่านั้น)

```
Timeframe:       H1 เท่านั้น (ไม่ดู H4, M15, M5)
ดู:              Divergence + Signal Crossover

GOLD + BTC:      เสริมความมั่นใจ ไม่ใช่เงื่อนไขบังคับ
Secondary + ETH: เป็นส่วนหนึ่งของ Score
                 +1 ถ้าไม่มี Divergence ขัด
                 +1 ถ้า Signal Cross ตรง Bias
```

---

## 3E. SCORE SYSTEM (Secondary + ETH เท่านั้น)

| Condition | Points |
|---|---|
| H4 + H1 Bias ตรงกัน | +2 |
| MACD H1 ไม่มี Divergence ขัด | +1 |
| MACD H1 Signal Cross ตรง Bias | +1 |
| LQ Sweep M15 | +2 |
| MSS M5 | +2 |
| อยู่ใน Killzone | +1 |
| M1 FVG/OB Entry | +1 |
| **รวม** | **/10** |

```
Score 9-10 → ใช้ Risk สูงสุดของ Tier | RR ขั้นต่ำ 1:1
Score 7-8  → ใช้ Risk ต่ำสุดของ Tier  | RR ขั้นต่ำ 1:2
Score < 7  → ไม่เข้า
```

---

## 4. RISK DEFINITION

```
SL: วางหลัง Swing High/Low ล่าสุด เสมอ
    ห้ามวางแค่หลังขอบ FVG
    (เจ้ามือจะสะบัดกิน SL ถ้าวางใกล้เกินไป)
    สำหรับ GOLD: SL ควรอยู่ที่ 300-800 pip

TP: โครงสร้างราคาถัดไป (Swing High/Low ถัดไป)
    Target RR ขั้นต่ำ:
      Score 9-10 → RR 1:1 ขึ้นไป
      Score 7-8  → RR 1:2 ขึ้นไป
    ถ้ากราฟแรงและเกิด BOS → ปล่อยให้วิ่งต่อ

Lot Size: Midas ประเมินเองตาม Setup และขนาดพอร์ต
    พอร์ต < $200        → Max 50% ต่อไม้ — Midas ตัดสินใจเอง
    พอร์ต $200-$1,000   → Max 20% ต่อไม้
    พอร์ต $1,000-$5,000 → Max 5% ต่อไม้
    พอร์ต > $5,000      → Max 1% ต่อไม้
    Score 9-10 → ใช้ Risk สูงสุดของ Tier (Secondary + ETH)
    Score 7-8  → ใช้ Risk ต่ำสุดของ Tier  (Secondary + ETH)
```

---

## 5. TRADE MANAGEMENT

```
Secondary + ETH — Break Even Rule:
เมื่อราคาทำ BOS สำเร็จ (Break of Structure):
→ ย้าย SL มาที่ Break Even ทันที
→ ความเสี่ยงกลายเป็น 0%
→ ปล่อยให้วิ่งไปถึง TP หรือ BOS ถัดไป

GOLD + BTC — Trail SL Rule:
→ Trail SL ครึ่ง Block ทุกครั้งที่ผ่าน 1 Block
→ GOLD: 1 Block = $25 | BTC: 1 Block = $1,000

หลัง 00:00 BKK:
→ ตรวจสอบว่ามีไม้เปิดอยู่ไหม
→ ถ้าไม่มี → ปิดระบบทั้งหมด รอ 07:00
→ ถ้ามี → Python Monitor ตาม Watch List ที่ Midas กำหนด

02:00 BKK:
→ Midas ประเมินสถานการณ์
→ ถ้าไม่แน่ใจ → แจ้ง Telegram รอตอบ 15 นาที
→ ถ้าไม่ตอบภายใน 15 นาที → Midas ตัดสินใจเอง
→ ถ้าไม่มีไม้ → ปิดระบบ รอ 07:00
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

4. CME บอกอะไร? (GOLD+BTC เท่านั้น)
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
Risk Per Trade (ตาม Portfolio Size):
พอร์ต < $200        → Max 50% ต่อไม้ — Midas ตัดสินใจเอง
พอร์ต $200-$1,000   → Max 20% ต่อไม้
พอร์ต $1,000-$5,000 → Max 5% ต่อไม้
พอร์ต > $5,000      → Max 1% ต่อไม้

Risk Modifier ตาม Score (Secondary + ETH):
Score 9-10 → ใช้ Risk สูงสุดของ Tier
Score 7-8  → ใช้ Risk ต่ำสุดของ Tier

Max Open Trades:
พอร์ต < $200      → Max 1 ไม้
พอร์ต $200-$500   → Max 2 ไม้
พอร์ต $500-$1,000 → Max 3 ไม้
พอร์ต > $1,000    → Max 4 ไม้ (GOLD + BTC + Secondary 2)

Min Risk:Reward:
Score 9-10 → RR 1:1 ขึ้นไป
Score 7-8  → RR 1:2 ขึ้นไป
Score < 7  → ไม่เข้า

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
✅ Score และ Confidence (Secondary+ETH) | CME Confluence (GOLD+BTC)
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
- MACD Divergence  → Divergence + Signal Crossover | TF: H1 เท่านั้น (ไม่ต้องการ H4)
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
- R:R เฉลี่ย ≥ 1:2

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

## 16. CURRENT STATUS (ณ 24 พฤษภาคม 2026 — v3.5)

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
✅ Prompt Caching — ลด API Cost ~50%
   (Constitution cached ใน system list ทุก 5 นาที ครอบคลุมทุกฟังก์ชัน Claude 7 ตัว)
✅ Crypto 24H Scanning — BTCUSD/ETHUSD ไม่มีเวลาหยุด
   (แยก Time Check ออกจาก Forex ใน State Machine main.py)
✅ Telegram Group — ส่งเข้า Group "Ai Midas Signal" แทน Direct Message
   (Group CHAT_ID: -5251407528)
✅ Web Dashboard (dashboard.py) — Flask, 4 หน้า, Dark Theme, port 5000
   - Overview: Balance, Equity, Floating P&L, Open Positions Live, CME Summary
   - Monitor: Symbol States, CME Snapshot, Morning Brief, Hermes Intelligence
   - Journal: Trade History, Win Rate, P&L รายวัน, Per-Symbol Breakdown
   - CME: Put Wall, Call Wall, Max Pain, Vol2Vol, COT, Raw CME_Daily.md
   - Auto refresh 30 วินาที, เข้าจากมือถือผ่าน WiFi เดียวกันได้
✅ Spread Filter (กรองตอน Spread สูงผิดปกติ)
✅ BTC CME Scraper (Vol2Vol + OI Heatmap)
✅ Vol2Vol หยุดหลัง 00:00 BKK และเสาร์-อาทิตย์
✅ ngrok Auto URL ส่ง Telegram อัตโนมัติ
✅ GitHub Pages Redirect (redirect.html)
✅ start_midas.bat รัน ngrok + dashboard + notify
✅ Constitution v2.0 — Sync กับ Requirements ครบทุกจุด
✅ Strategy GOLD+BTC: CME Wall + SMC Precision (ไม่มี Score)
✅ Strategy Secondary+ETH: SMC Pure + Score ≥ 7
✅ Entry Flexible — OB Retest / FVG Fill / MSS Break / Squeeze Fire ตามดุลยพินิจ
✅ Risk Tiered ตามพอร์ต (Max 50% → 1%) + Max Open Trades (1 → 4 ไม้)
✅ Night Protocol — Dynamic Monitor + Midas ตัดสินใจเองถ้าไม่ตอบใน 15 นาที
✅ MACD H1 Divergence + Signal Crossover (Secondary Score +1 / GOLD+BTC เสริมความมั่นใจ)
✅ brain.py อัปเดต System Prompt ทุกฟังก์ชันตาม Strategy ใหม่
✅ CME Integration ชัดเจน — เฉพาะ GOLD+BTC, ปรับแผนทันทีถ้า Wall เปลี่ยน
```

---

## 17. NEXT STEPS (เรียงตาม Priority)

```
🔴 P1: Telegram Two-Way — รับคำสั่งจาก Telegram
   ปัจจุบัน: Telegram ส่งได้ทางเดียว (แจ้งเตือน)
   ต้องการ: รับคำสั่งจาก Telegram เช่น /status /pause /close_all

🔴 P2: GitHub Pages Redirect — แสดงปุ่มก่อน Redirect
   ปัจจุบัน: redirect.html auto-redirect ทันที
   ต้องการ: แสดงปุ่มเปิดลิงก์ก่อน ไม่ auto-redirect

🟡 P3: Night Protocol Code — main.py ปิดระบบตอน 00:00 ถ้าไม่มีไม้
   ปัจจุบัน: Night Watch ตรวจสอบแต่ยังไม่ปิดระบบอัตโนมัติ
   ต้องการ: ถ้าไม่มีไม้เปิดอยู่หลัง 00:00 → shutdown + รอ 07:00

🟡 P4: Librarian — รอ Journal สะสม 1 สัปดาห์
   ต้องมี Trade Journal ≥ 1 สัปดาห์ก่อน Report จะมีความหมาย
   เพิ่ม field ผล Win/Loss ใน Journal เพื่อคำนวณ Win Rate จริงได้

🟢 P5: Live Trade เมื่อผ่านเกณฑ์ทั้งหมด
   Win Rate ≥ 45% จาก 20 ไม้จริง (ดูเกณฑ์ใน Section 18)
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

*Requirements version 3.5 | อัปเดต: 2026-05-24*
*อัปเดตจากการสัมภาษณ์เจ้าของระบบ + SMC Model ของ Craig Percoco*
*อัปเดตครั้งต่อไปหลังทดสอบ Demo 2 สัปดาห์ หรือเมื่อ Priority ใหม่เพิ่มเข้ามา*

---

related: [[00_Midas_Constitution]] [[MIDAS_PROMPT_BLUEPRINT]]
