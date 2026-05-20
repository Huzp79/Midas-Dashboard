# MIDAS PROMPT BLUEPRINT v1.0
> เอกสารนี้คือ Blueprint สำหรับสร้าง Prompt Logic ของ Midas
> AI ใดก็สามารถเอาไปต่อยอดได้ทันที

---

## CONTEXT: Midas คืออะไร

Midas คือ AI Trading Agent ที่รันบน Python + MT5 (XM Broker)
- เทรด GOLD (XAUUSD) เป็นหลัก + Forex คู่อื่นถ้ามีโอกาส
- Style: SMC (Smart Money Concepts) + Multi-Timeframe
- เทรดจบในวัน ไม่ถือข้ามคืน
- เวลาทำการ: 08:00–23:30 Bangkok Time
- ข้อมูลที่ได้รับ: JSON จาก MT5 Indicator 5 ตัว (SMC God Eye, MACD, LQ Sweep, Volume Profile, Squeeze Momentum)

---

## CORE PHILOSOPHY (สิ่งที่ต้องเข้าใจก่อน)

```
ปัญหาของ Rule-Based AI:
  กฎเยอะ → ไม่เคยเทรด (ตึงเกินไป)
  กฎน้อย → เทรดผิดบ่อย (หลวมเกินไป)

สิ่งที่ Midas ต้องทำได้:
  "คิดแบบเทรดเดอร์" ไม่ใช่ "นับ Checklist"
  ประเมิน Context ทั้งหมดแล้วถามตัวเองว่า
  "ถ้าเป็นเงินตัวเอง จะเข้าไหม?"
```

---

## DATA INPUT STRUCTURE

Midas ได้รับข้อมูลในรูปแบบนี้ทุกรอบ (ทุก 60 วินาที เมื่อราคาเข้า POI)

```json
// SMC God Eye (มีทุก TF: H4, H1, M30, M15, M5, M1)
{
  "current_price": 3245.50,
  "structure": {
    "swing_trend": "BULLISH|BEARISH",
    "internal_trend": "BULLISH|BEARISH",
    "swing_high": 3280.00,
    "swing_low": 3210.00
  },
  "zones": {
    "bull_ob_top": 3220.00, "bull_ob_btm": 3215.00,
    "bear_ob_top": 3275.00, "bear_ob_btm": 3270.00,
    "bull_fvg_top": 3218.00, "bull_fvg_btm": 3214.00,
    "bear_fvg_top": 3278.00, "bear_fvg_btm": 3274.00
  }
}

// MACD Divergence (มีที่ H1)
{
  "divergence": "NONE|BULLISH|BEARISH|HIDDEN_BULLISH|HIDDEN_BEARISH",
  "macd_line": -9.81,
  "histogram": -4.56
}

// LQ Sweep (มีที่ M15, M5)
{
  "zones": {
    "bullish_top": 3220.00, "bullish_btm": 3215.00,
    "bearish_top": 3275.00, "bearish_btm": 3270.00
  }
}

// Volume Profile (มีที่ M15)
{
  "zones": { "poc": 3235.00, "val": 3225.00, "vah": 3245.00 }
}

// Squeeze Momentum (มีที่ M1)
{
  "squeeze_state": "ON|OFF",
  "fire_signal": "BULLISH|BEARISH|NONE"
}
```

---

## PROMPT ARCHITECTURE

### Layer 1: System Prompt (ใส่ใน `system` parameter)
> โหลดจาก `00_Midas_Constitution.md`
> ความยาว: ~800 tokens
> อัปเดต: เมื่อ Logic เปลี่ยนเท่านั้น

```
หน้าที่: กำหนด Identity, Rules, Risk Management
ไม่ควรมี: ข้อมูลตลาด, ราคา, ตัวเลขใดๆ
```

### Layer 2: User Prompt (ส่งทุกครั้งที่วิเคราะห์)
> ความยาวเป้าหมาย: ~600 tokens
> ประกอบด้วย: Market Data + Thinking Framework + Output Format

```
หน้าที่: ให้ข้อมูลตลาดและบอกวิธีคิด
ไม่ควรมี: กฎซ้ำจาก System Prompt
```

### Layer 3: Output Format (JSON เท่านั้น)
> max_tokens: 300
> temperature: 0.1 (นิ่ง, ตรรกะ, ไม่สุ่ม)

---

## THINKING FRAMEWORK (หัวใจของ Prompt)

นี่คือวิธีที่ Midas ควร "คิด" ก่อนตัดสินใจ:

```
STEP 1 — BIG PICTURE [H4 + H1]
ถามว่า: "ตลาดกำลังทำอะไรอยู่?"
- Swing Trend H4 และ H1 ตรงกันไหม?
- ถ้าตรงกัน → Bias ชัด → ดูต่อ
- ถ้าขัดกัน → WAIT ทันที (ไม่มีข้อยกเว้น)

STEP 2 — LOCATION [M30 + M15]
ถามว่า: "ราคาอยู่ตรงไหนของโครงสร้าง?"
- อยู่ใกล้ OB หรือ FVG ที่ตรงกับ Bias → น่าสนใจ
- อยู่ใกล้ POC (Volume Profile) → ระวัง แรงต้านสูง
- อยู่กลางทาง ไม่มีโซน → ข้ามไป

STEP 3 — TRIGGER [M5 + M1]
ถามว่า: "มีอะไรบอกว่าตอนนี้คือจังหวะไหม?"
- มี LQ Sweep แล้วปิดกลับ → สัญญาณดี
- มี MSS (Market Structure Shift) → ยิ่งดี
- Squeeze กำลังระเบิด (Fire Signal) → เพิ่มความมั่นใจ
- แค่เห็น FVG แต่ไม่มี Trigger → รอก่อน

STEP 4 — HONEST CHECK
ถามว่า: "ถ้าเป็นเงินตัวเอง จะเข้าไหม?"
- เข้าได้สบายใจ → HIGH confidence
- เข้าได้แต่ต้องระวัง → MEDIUM confidence  
- ไม่แน่ใจ → WAIT (ไม่เข้าดีกว่า)
```

---

## OUTPUT SPECIFICATION

```json
{
  "summary": "สรุปภาพรวมตลาด 1 บรรทัด (ภาษาไทย)",
  "bias": "BULLISH|BEARISH|NEUTRAL",
  "action": "BUY|SELL|WAIT",
  "confidence": "HIGH|MEDIUM|LOW",
  "entry": 0.00,
  "sl": 0.00,
  "tp": 0.00,
  "score": 7,
  "reason": "เหตุผลแบบเทรดเดอร์ ไม่ใช่ Checklist (ภาษาไทย)"
}
```

**Confidence → Lot Size Mapping:**
```python
HIGH   → lot = 0.02  # เต็มที่
MEDIUM → lot = 0.01  # ระวัง
LOW    → ไม่เข้า แม้ action จะเป็น BUY/SELL
```

---

## RULES ที่ต้องอยู่ใน Constitution (ห้ามละเว้น)

```
ABSOLUTE RULES:
1. H4 + H1 Bias ขัดกัน → WAIT ทันที
2. Score < 6 → WAIT ทันที
3. ราคาอยู่ติด POC → WAIT (แรงต้านสูง)
4. หลัง 00:00 BKK → ไม่เปิด Order ใหม่
5. Daily Loss 3 ไม้ → หยุดทั้งวัน
6. Max 5 Trade/วัน
7. SL ต้องอยู่ใต้/เหนือ Swing Low/High เสมอ
8. Min R:R = 1:2
```

---

## CALIBRATION GUIDE
> สำหรับ AI ที่จะปรับ Prompt ต่อ

**ถ้า Midas ไม่เทรดเลย (Too Strict):**
```
- ลด Score threshold จาก 7 → 6
- เพิ่ม "MEDIUM confidence ก็เข้าได้"
- ผ่อน STEP 3 Trigger ให้ไม่ต้องครบทุกอย่าง
```

**ถ้า Midas เทรดบ่อยเกินไป (Too Loose):**
```
- เพิ่ม STEP 1 ให้เข้มขึ้น (H4+H1 ต้องชัด 100%)
- เพิ่มเงื่อนไข Killzone (London/NY เท่านั้น)
- บังคับให้มี Trigger ใน STEP 3 เสมอ
```

**ถ้า Win Rate ต่ำ:**
```
- เพิ่มน้ำหนัก STEP 2 (Location สำคัญมาก)
- บังคับ R:R ขั้นต่ำ 1:2.5
- เพิ่ม Filter: ห้ามเทรด Counter-Trend
```

**ถ้า Profit Factor ดีแต่ได้น้อยไม้:**
```
- ผ่อน STEP 3 (Trigger ไม่ต้องสมบูรณ์)
- เพิ่ม MEDIUM confidence lot เป็น 0.015
- ขยายเวลาทำการ
```

---

## FILES STRUCTURE ที่ต้องรู้

```
C:\Midas\
├── Midas_Brain\
│   ├── 00_Midas_Constitution.md  ← System Prompt หลัก
│   ├── raw\
│   │   ├── market_data\
│   │   │   └── latest_data.md    ← ข้อมูลตลาดล่าสุด
│   │   └── trades\               ← Trade Journal รายวัน
│   └── wiki\
│       ├── strategies\           ← กลยุทธ์ที่ผ่านการทดสอบ
│       └── lessons\              ← บทเรียนจากการเทรดผิดพลาด
├── main.py      ← ศูนย์บัญชาการ + Gatekeeper
├── brain.py     ← ส่งข้อมูลให้ Claude วิเคราะห์
├── feed_midas.py ← ดึงข้อมูลจาก MT5
└── auto_trade.py ← เปิด/ปิด Order + Telegram Alert
```

---

## CURRENT STATUS (ณ 20 พฤษภาคม 2026)

✅ ระบบรันได้แล้ว Auto-Trading Mode (Demo Account)
✅ MT5 (XM Global) เชื่อมต่อได้ ส่ง JSON ออกมา 11 ไฟล์
✅ Brain.py ใช้ Thinking Framework 4 Steps แล้ว
✅ Confidence → Lot Size ทำงานได้ (HIGH=0.02, MEDIUM=0.01)
✅ State Machine 3 ด่าน: SCANNING → ARMED → READY_TO_FIRE
✅ วิเคราะห์ตลาดได้สมเหตุสมผล
✅ Trade Journal บันทึกภาษาไทยถูกต้อง
✅ Telegram Alert พร้อมใช้
✅ Daily Trade Limit 5 ไม้/วัน
✅ SL/TP คำนวณโดย Python (ไม่ให้ Claude เดา)
✅ Hermes ดึงข่าว Forex Factory + Macro (DXY, VIX, GVZ) ได้

JSON Files ที่ใช้งานจริง (11 ไฟล์):
- SMC God Eye: H4, H1, M30, M15, M5, M1 ✅ ครบทุก TF
- MACD Divergence: H1 เท่านั้น ✅ (ไม่ต้องการ H4 — ออกแบบไว้แบบนี้)
- LQ Sweep: M15, M5 ✅
- Volume Profile: M15 ✅
- Squeeze Momentum: M1 ✅

⚠️ กำลังทดสอบบน Demo Account (ยังไม่ Live)
⚠️ SL/TP อ่านจาก Markdown ด้วย Regex (ยังไม่อ่าน JSON โดยตรง)
⚠️ H4+H1 Pre-Filter ยังไม่แยกเป็น Python Check (Claude ทำแทน)

---

## NEXT STEPS สำหรับ AI ที่รับช่วงต่อ

```
✅ Priority 1: ปรับ brain.py ให้ใช้ Thinking Framework 4 Steps — เสร็จแล้ว
✅ Priority 2: ระบบ Auto-Trading รันบน Demo — เสร็จแล้ว

🔴 Priority 3: เพิ่ม H4+H1 Pre-Filter ใน Python
   → ตอนนี้ Claude รับภาระเช็คแทน เสีย API Cost โดยไม่จำเป็น
   → ควรให้ Python อ่าน smc_state H4/H1 แล้วเช็ค swing_trend ก่อนปลุก Claude

🟡 Priority 4: แก้ SL/TP ให้อ่าน OB จาก JSON โดยตรง
   → ปัจจุบันใช้ Regex บน Markdown (เปราะบาง)
   → ควรอ่าน smc_state JSON แล้วดึง ob_top/ob_btm โดยตรง

🟡 Priority 5: วัด Win Rate หลังทดสอบ Demo 1-2 สัปดาห์
   → ปรับ Calibration ตาม Guide ด้านบน

🟢 Priority 6: สร้าง librarian.py
   → บันทึก Pattern + บทเรียนหลังแพ้ลงใน Wiki อัตโนมัติ

🟢 Priority 7: Dynamic Lot Sizing ตามขนาดพอร์ตจริง

🟢 Priority 8: Live Trade ด้วย Lot เล็กสุด (0.01) เมื่อ Demo ผ่านเกณฑ์
```

---

*Blueprint version 1.0 | สร้างโดย Claude Sonnet | ต่อยอดได้เลย*
