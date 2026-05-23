# 📊 CME Options Knowledge

ความรู้เรื่อง CME Gold Options ที่ Midas ใช้ประกอบการวิเคราะห์ระดับ Institutional

---

## 1. CME และ Gold Futures คืออะไร

**CME (Chicago Mercantile Exchange)** คือตลาด Derivatives ที่ใหญ่ที่สุดในโลก Institutional Trader ซื้อขาย Gold ผ่าน CME ในรูปแบบ Futures และ Options ไม่ใช่ Spot

- **GC Futures** (Gold Futures) — สัญญาซื้อขายทองในอนาคต ราคาของ GC จะ **สูงกว่า Spot** เสมอ เพราะรวม Cost of Carry (ดอกเบี้ย + ค่าเก็บ)
- **OG Options** (Gold Options) — สิทธิ์ซื้อ/ขาย GC Futures ที่ Strike Price หนึ่งๆ ก่อน Expiry
- **Expiry** — วันหมดอายุของ Options แต่ละ Series (มีทั้ง Monthly และ Weekly)
- **DTE** (Days to Expiry) — จำนวนวันก่อน Expiry ยิ่งน้อย = Institutional ต้อง Hedge หรือ Roll มากขึ้น

> **สำคัญ:** ราคาใน CME เป็น **Futures Price** ต้องหัก Basis ก่อนเทียบกับ MT5 Spot ที่เทรดจริง

---

## 2. Max Pain คืออะไร และมีผลกับราคายังไง

**Max Pain** คือ Strike Price ที่ทำให้ **มูลค่ารวมของ Options ทุกสัญญาณเป็น 0 หรือต่ำที่สุด** — คือจุดที่ Options Seller (มักเป็น Market Maker) ขาดทุนน้อยที่สุด

### หลักการทำงาน
- Options Seller รับ Premium แล้ว **ต้องการให้ Options หมดอายุไร้ค่า (Worthless)**
- Market Maker มีแรงจูงใจดึงราคาเข้าหา Max Pain ก่อน Expiry (เรียกว่า **Pin Risk**)
- ยิ่งใกล้ Expiry (DTE < 3) แรงดึงยิ่งแรงขึ้น

### วิธีใช้
| สถานการณ์ | ความหมาย |
|---|---|
| Gold อยู่เหนือ Max Pain | แรงดึงลง → ระวัง SELL Setup |
| Gold อยู่ใต้ Max Pain | แรงดึงขึ้น → เสริม BUY Setup |
| Gold อยู่ใกล้ Max Pain (±20 pts) | ตลาดอาจ Consolidate → ลด Conviction |
| DTE < 3 + ราคาห่าง Max Pain > 50 pts | โอกาส Mean Reversion สูง |

> **อย่า Trade เพราะ Max Pain เพียงอย่างเดียว** ใช้เป็น Context เสริม SMC เท่านั้น

---

## 3. Put Wall และ Call Wall คืออะไร

**OI (Open Interest)** คือจำนวนสัญญา Options ที่ยังเปิดอยู่ที่ Strike ต่างๆ

- **Put Wall** — Strike ที่มี **Put OI สูงสุด** → บริเวณที่ Institutional ซื้อ Put มากที่สุด
- **Call Wall** — Strike ที่มี **Call OI สูงสุด** → บริเวณที่ Institutional ซื้อ Call มากที่สุด

### ความหมายเชิง SMC
| Level | ฟังก์ชัน | เหมือนกับ |
|---|---|---|
| **Put Wall** | แรงรับ Institutional (Support) | Demand Zone ระดับ Macro |
| **Call Wall** | แรงต้าน Institutional (Resistance) | Supply Zone ระดับ Macro |

### กฎการใช้
- Gold อยู่ **เหนือ Put Wall** + Bias BULLISH → Entry Zone แข็งแกร่ง Put Wall รองรับ Downside
- Gold **วิ่งชน Call Wall** โดยไม่มี OB รองรับ → ระวัง Rejection รุนแรง
- Put Wall หรือ Call Wall **ย้าย > 50 pts** ใน 6 ชั่วโมง → Institutional เปลี่ยน Positioning → ต้องทบทวน Bias

---

## 4. Put/Call Ratio บอกอะไร

**Put/Call Ratio (PC Ratio)** = Put Volume ÷ Call Volume

| ค่า | ความหมาย | Bias |
|---|---|---|
| < 0.7 | ซื้อ Call มาก = ตลาดมองขึ้น | Bullish |
| 0.7 – 1.3 | สมดุล | Neutral |
| > 1.3 | ซื้อ Put มาก = Hedge / มองลง | Bearish / Fear |
| > 2.0 | Put Heavy มาก = Panic Hedge หรือ Speculative Short | ระวังแรงขึ้น Contrarian |

### กฎการใช้
- **PC Ratio เปลี่ยน > 0.3 ใน 1 ชั่วโมง** → สัญญาณ Institutional เปลี่ยน Sentiment ฉับพลัน → ปลุก Midas
- PC Ratio สูง ≠ ราคาจะลงเสมอ เพราะ Hedge บางทีทำให้ตลาดขึ้นแรง (Short Squeeze)
- ดู PC Ratio **ร่วมกับ DTE** เสมอ: DTE ต่ำ + PC สูง = Expiry Hedge ไม่ใช่ Directional Bet

---

## 5. COT Report คืออะไร Managed Money หมายถึงอะไร

**COT (Commitment of Traders)** คือรายงานที่ CFTC บังคับให้ Institutional Trader รายงานขนาด Position ทุกสัปดาห์ (ออกทุกวันศุกร์)

### ประเภท Trader
| กลุ่ม | คือใคร |
|---|---|
| **Commercial** | Hedgers จริง เช่น เหมืองทอง, Jeweler |
| **Managed Money** | Hedge Fund, CTA, Asset Manager — **ที่ Midas ดู** |
| **Non-reportable** | Retail รายย่อย |

### Managed Money Net Position
- **MM Net > 0** (Long > Short) → Hedge Fund เชื่อ Gold จะขึ้น → เสริม BULLISH Bias
- **MM Net < 0** (Short > Long) → Hedge Fund เชื่อ Gold จะลง → เสริม BEARISH Bias
- **MM Net เปลี่ยนทิศ** (เช่นจาก Long มาก → เริ่มลด) → สัญญาณ Early Reversal

> COT เป็น **Lagging Indicator** (ข้อมูลล่าช้า 3 วัน) ใช้ยืนยัน Bias ระยะกลาง ไม่ใช่ Time Entry

---

## 6. Basis คืออะไร GC Futures vs Gold Spot

**Basis** = GC Futures Price − Gold Spot Price

- Futures มักสูงกว่า Spot เสมอ เรียกว่า **Contango** (ปกติ)
- ถ้า Futures ต่ำกว่า Spot เรียกว่า **Backwardation** (เกิดขึ้นช่วงวิกฤต Demand จริงสูงมาก)

### ทำไมต้องรู้
CME รายงานระดับ Put Wall / Call Wall / Max Pain เป็น **Futures Price** แต่ MT5 ใช้ **Spot Price** ต้องหัก Basis ก่อนเทียบ

```
Spot-equivalent Level = Futures Level − Basis
เช่น: Put Wall = 4570 (Futures), Basis = +20 → Put Wall Spot = 4550
```

- Basis ปกติอยู่ที่ **+10 ถึง +30** ขึ้นกับ DTE และ Interest Rate
- Midas คำนวณ Basis อัตโนมัติจาก MT5 Spot และ GC Futures ทุกรอบ CME Fetch

---

## 7. วิธีใช้ข้อมูลเหล่านี้ร่วมกับ SMC Analysis

CME Data เป็น **Macro Layer** ที่ซ้อนทับบน SMC Structure อย่าใช้ทดแทนกัน

### ลำดับความสำคัญ
```
H4/H1 SMC Trend  ←  ตัดสิน Bias หลัก
     ↓
CME Data          ←  ยืนยัน / เตือน / ปรับ Conviction
     ↓
M15/M5 Trigger    ←  หาจุด Entry จริง
```

### Matrix การใช้งาน
| SMC Signal | CME Signal | สรุป |
|---|---|---|
| HTF Bull OB + BOS | Gold เหนือ Put Wall, MM Net Long | ✅ High Conviction BUY |
| HTF Bear OB + CHoCH | Gold ใต้ Call Wall, MM Net Short | ✅ High Conviction SELL |
| M15 Bull OB | Gold ใกล้ Max Pain จาก Above | ⚠️ ลด Lot อาจ Pinned |
| HTF BUY Setup | PC Ratio พุ่งสูง > 2.0 ใน 1 ชม. | ⚠️ ระวัง Hedge ขนาดใหญ่ ทบทวน Bias |
| ไม่มี SMC Setup ชัด | CME ชัดมาก | ❌ ยัง WAIT — ต้องการทั้งคู่ |

---

## 8. ตัวอย่างจริง

### Case A: Max Pain 4600 + HTF Bear OB
```
สถานการณ์:
- Gold Spot ปัจจุบัน: 4640
- Max Pain (Spot adj): 4600
- HTF H4 Bear OB อยู่ที่: 4635–4650
- MM Net: -15,000 (Hedge Fund Short)
- PC Ratio: 1.8

วิเคราะห์:
1. Gold อยู่เหนือ Max Pain 40 pts → แรงดึงลงหา 4600
2. Bear OB H4 ที่ 4635–4650 = Supply Zone แข็งแกร่ง
3. MM Net Short → Hedge Fund เชื่อ Gold จะลง
4. PC Ratio 1.8 → Institutional Hedge Downside สูง

ผล: BEARISH Bias สูง รอ Rejection จาก Bear OB + Sweep High → SELL
Target: 4600 (Max Pain) เป็น TP แรก
```

### Case B: Put Wall ย้าย 80 pts ใน 6 ชั่วโมง
```
สถานการณ์:
- Put Wall เมื่อ 06:00: 4500
- Put Wall ตอนนี้ 12:00: 4580
- Gold Spot: 4555

วิเคราะห์:
- Institutional ย้าย Put Wall ขึ้น 80 pts = เพิ่ม Hedge ที่ระดับสูงขึ้น
- หมายความว่า Institutional ป้องกัน Downside ที่ระดับสูงขึ้น = มอง Upside มากขึ้น
- Gold ปัจจุบันต่ำกว่า Put Wall ใหม่ = อยู่ใน "Protected Zone"

ผล: Bullish Shift → ปลุก analyze_cme_change() → แจ้งเจ้าของ
```

### Case C: DTE = 0.5 + PC Ratio = 3.3
```
สถานการณ์: (เกิดจริงวันที่ 22 พ.ค. 2026)
- Expiry: ภายในวันเดียวกัน
- PC Ratio: 3.316 (Put Heavy มาก)
- Gold อยู่ใกล้ Max Pain

วิเคราะห์:
- PC สูงเพราะ Expiry Day Hedging ไม่ใช่ Directional Bet จริง
- ราคามักติด Max Pain ช่วง Expiry
- ไม่ควรตีความว่า Bearish

ผล: ลด Conviction ทั้งฝั่ง รอ Expiry ผ่านก่อนค่อย Re-assess
```

---

## Quick Reference

| ข้อมูล | ความถี่ | ใช้ทำอะไร |
|---|---|---|
| Vol2Vol (PC Ratio) | ทุกชั่วโมง | ดู Sentiment เปลี่ยนฉับพลัน |
| OI Matrix (Put/Call Wall) | ทุก 6 ชั่วโมง | ดู Support/Resistance Macro |
| COT (MM Net) | ทุกศุกร์ | ยืนยัน Bias ระยะกลาง |
| Max Pain | ทุก Fetch | Target ก่อน Expiry |
| Basis | ทุก Fetch | แปลง Futures → Spot |

---

related: [[00_Midas_Constitution]] [[wiki/knowledge/Macro_Framework]] [[wiki/knowledge/SMC_Concepts]]
