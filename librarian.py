import os
import re
from datetime import datetime, timedelta

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
TRADE_LOG_DIR = os.path.join(BASE_DIR, "Midas_Brain", "data", "journal")
LESSONS_DIR   = os.path.join(BASE_DIR, "Midas_Brain", "wiki", "lessons")
REPORT_PATH   = os.path.join(LESSONS_DIR, "weekly_report.md")

# ==========================================
# 📖 1. อ่านและ Parse Journal Files
# ==========================================
def parse_journals(days=7):
    entries = []
    if not os.path.exists(TRADE_LOG_DIR):
        return entries

    cutoff = datetime.now().date() - timedelta(days=days)

    for filename in sorted(os.listdir(TRADE_LOG_DIR)):
        if not filename.endswith(".md"):
            continue
        try:
            file_date = datetime.strptime(filename.replace(".md", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date < cutoff:
            continue

        filepath = os.path.join(TRADE_LOG_DIR, filename)
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()

        # แยกแต่ละ entry ด้วย separator
        blocks = content.split("-" * 40)
        for block in blocks:
            entry = {"date": str(file_date)}
            m = re.search(r"## 🕒 (\d{2}:\d{2}:\d{2})", block)
            if not m:
                continue
            entry["time"] = m.group(1)
            entry["hour"] = int(m.group(1).split(":")[0])

            m = re.search(r"\*\*Action:\*\* (\w+).*?\*\*Confidence:\*\* (\w+)", block)
            if m:
                entry["action"]     = m.group(1)
                entry["confidence"] = m.group(2)

            m = re.search(r"\*\*Score:\*\* (\d+)/10.*?\*\*RR:\*\* 1:([\d.]+)", block)
            if m:
                entry["score"] = int(m.group(1))
                entry["rr"]    = float(m.group(2))

            m = re.search(r"\*\*Bias:\*\* (\w+)", block)
            if m:
                entry["bias"] = m.group(1)

            m = re.search(r"\*\*Reason:\*\* (.+)", block)
            if m:
                entry["reason"] = m.group(1).strip()

            if "action" in entry:
                entries.append(entry)

    return entries

# ==========================================
# 📊 2. วิเคราะห์ Stats
# ==========================================
def analyze(entries):
    if not entries:
        return None

    trades = [e for e in entries if e.get("action") in ["BUY", "SELL"]]
    waits  = [e for e in entries if e.get("action") == "WAIT"]

    # Action breakdown
    buy_count  = sum(1 for e in trades if e["action"] == "BUY")
    sell_count = sum(1 for e in trades if e["action"] == "SELL")

    # Confidence breakdown
    conf_count = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for e in trades:
        c = e.get("confidence", "LOW")
        conf_count[c] = conf_count.get(c, 0) + 1

    # Score average
    scores = [e["score"] for e in entries if "score" in e]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Session breakdown (Bangkok Time)
    def session(hour):
        if 8  <= hour < 12: return "Morning (08-12)"
        if 12 <= hour < 17: return "Afternoon (12-17)"
        if 17 <= hour < 24: return "Evening (17-23)"
        return "Other"

    session_count = {}
    for e in trades:
        s = session(e.get("hour", 0))
        session_count[s] = session_count.get(s, 0) + 1

    best_session = max(session_count, key=session_count.get) if session_count else "N/A"

    # Bias breakdown
    bias_count = {}
    for e in trades:
        b = e.get("bias", "NEUTRAL")
        bias_count[b] = bias_count.get(b, 0) + 1

    # Low-score trades (Score < 6 แต่ยังเทรด — ผิด Rules)
    rule_breaks = [e for e in trades if e.get("score", 10) < 6]

    return {
        "total_entries": len(entries),
        "total_trades":  len(trades),
        "total_waits":   len(waits),
        "buy_count":     buy_count,
        "sell_count":    sell_count,
        "conf_count":    conf_count,
        "avg_score":     avg_score,
        "session_count": session_count,
        "best_session":  best_session,
        "bias_count":    bias_count,
        "rule_breaks":   rule_breaks,
    }

# ==========================================
# 📝 3. เขียน Weekly Report
# ==========================================
def write_report(stats):
    os.makedirs(LESSONS_DIR, exist_ok=True)
    now       = datetime.now()
    week_str  = now.strftime("สัปดาห์ที่ %W/%Y")
    date_str  = now.strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"# 📚 Librarian Weekly Report")
    lines.append(f"**สร้างเมื่อ:** {date_str} | **ครอบคลุม:** {week_str} (7 วันล่าสุด)\n")
    lines.append("---\n")

    if not stats:
        lines.append("⚠️ ไม่พบข้อมูล Trade Journal ในช่วง 7 วันที่ผ่านมา")
    else:
        lines.append("## 📊 สรุปภาพรวม\n")
        lines.append(f"| รายการ | ค่า |")
        lines.append(f"|---|---|")
        lines.append(f"| การวิเคราะห์ทั้งหมด | {stats['total_entries']} ครั้ง |")
        lines.append(f"| ไม้ที่ยิง (BUY/SELL) | {stats['total_trades']} ไม้ |")
        lines.append(f"| รอบที่สั่ง WAIT | {stats['total_waits']} ครั้ง |")
        lines.append(f"| BUY / SELL | {stats['buy_count']} / {stats['sell_count']} |")
        lines.append(f"| Score เฉลี่ย | {stats['avg_score']}/10 |")
        lines.append(f"| Session ที่เทรดมากสุด | {stats['best_session']} |")
        lines.append("")

        lines.append("## ⏰ Session Breakdown\n")
        for s, count in sorted(stats["session_count"].items(), key=lambda x: -x[1]):
            lines.append(f"- **{s}:** {count} ไม้")
        lines.append("")

        lines.append("## 🎯 Confidence Breakdown\n")
        for c in ["HIGH", "MEDIUM", "LOW"]:
            count = stats["conf_count"].get(c, 0)
            lines.append(f"- **{c}:** {count} ไม้")
        lines.append("")

        lines.append("## 📐 Bias Breakdown\n")
        for b, count in sorted(stats["bias_count"].items(), key=lambda x: -x[1]):
            lines.append(f"- **{b}:** {count} ไม้")
        lines.append("")

        lines.append("## ⚠️ Rule Violations (Score < 6 แต่ยังเทรด)\n")
        if stats["rule_breaks"]:
            for e in stats["rule_breaks"]:
                lines.append(f"- {e['date']} {e.get('time','')} | {e['action']} | Score={e.get('score','?')} | {e.get('reason','')[:80]}")
        else:
            lines.append("✅ ไม่พบการละเมิด Rule ในสัปดาห์นี้")
        lines.append("")

        lines.append("## 💡 บทเรียนอัตโนมัติ\n")
        if stats["avg_score"] < 6:
            lines.append("- ⚠️ Score เฉลี่ยต่ำกว่า 6 — ควรเข้มงวด Checklist มากขึ้น")
        if stats["rule_breaks"]:
            lines.append(f"- ⚠️ มีการเทรดทั้งหมด {len(stats['rule_breaks'])} ครั้งที่ Score < 6 — ควรบังคับ WAIT อัตโนมัติ")
        if stats["sell_count"] > stats["buy_count"] * 2 or stats["buy_count"] > stats["sell_count"] * 2:
            lines.append("- ⚠️ สัดส่วน BUY/SELL เอียงมาก — ตรวจสอบ Bias จาก HTF อีกครั้ง")
        if not stats["rule_breaks"] and stats["avg_score"] >= 7:
            lines.append("- ✅ สัปดาห์นี้ทำตาม Rules ได้ดี Score เฉลี่ยสูง")

    lines.append("\n---")
    lines.append("*สร้างอัตโนมัติโดย Librarian Agent*")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ [Librarian]: เขียนรายงานเสร็จแล้ว → {REPORT_PATH}")

# ==========================================
# 🚀 Main Entry Point
# ==========================================
def run_librarian():
    print("📚 [Librarian]: เริ่มวิเคราะห์ Trade Journal...")
    entries = parse_journals(days=7)
    print(f"📖 [Librarian]: พบ {len(entries)} entries ใน 7 วันล่าสุด")
    stats = analyze(entries)
    write_report(stats)

if __name__ == "__main__":
    run_librarian()
