import json
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timezone, timedelta
import os
import yfinance as yf

# ==========================================
# 🛠️ CONFIGURATION
# ==========================================
BRAIN_RAW_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Midas_Brain", "data", "market")
INTELLIGENCE_FILE = os.path.join(BRAIN_RAW_DIR, "daily_intelligence.md")
CME_SNAPSHOT_FILE = os.path.join(BRAIN_RAW_DIR, "cme_snapshot.json")

# คำต้องห้าม (Blacklist) ถ้าเจอให้ขึ้นเตือนสีแดง!
CRITICAL_KEYWORDS = ["NFP", "Non-Farm", "FOMC", "CPI", "Interest Rate", "Fed Rate", "Powell"]

def create_directory():
    if not os.path.exists(BRAIN_RAW_DIR):
        os.makedirs(BRAIN_RAW_DIR)

# ==========================================
# 🪽 1. ดึงข่าวจาก FOREX FACTORY
# ==========================================
def fetch_forex_factory_news():
    print("📡 [Hermes]: กำลังบินไปสืบข่าวจาก Forex Factory...")
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    news_list = []
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        today_date = datetime.now().strftime("%m-%d-%Y")
        
        for event in root.findall('event'):
            date = event.find('date').text
            impact = event.find('impact').text
            country = event.find('country').text
            
            # กรองเอาเฉพาะ "วันนี้" + "ข่าวส้ม/แดง" (เผื่อไว้ทุกสกุลเงินหลักให้ Midas ประเมินเอง)
            if date == today_date and impact in ["High", "Medium"] and country in ["USD", "EUR", "GBP", "JPY", "CNY"]:
                title = event.find('title').text
                time = event.find('time').text
                forecast = event.find('forecast').text if event.find('forecast') is not None else "N/A"
                previous = event.find('previous').text if event.find('previous') is not None else "N/A"
                
                # เช็คว่าเป็นข่าวระดับพระกาฬหรือไม่
                is_critical = any(keyword.lower() in title.lower() for keyword in CRITICAL_KEYWORDS)
                
                news_list.append({
                    "time": time,
                    "currency": country,
                    "impact": impact,
                    "title": title,
                    "forecast": forecast,
                    "previous": previous,
                    "is_critical": is_critical
                })
        return news_list
    except Exception as e:
        print(f"❌ [Hermes]: ดึงข่าว Forex Factory ไม่สำเร็จ -> {e}")
        return []

# ==========================================
# 📊 2. ดึงข้อมูล MACRO MACRO & SENTIMENT (YFINANCE)
# ==========================================
def fetch_market_context():
    print("🔭 [Hermes]: กำลังสแกนเรดาร์ DXY, US10Y และ VIX...")
    context_data = {}
    
    tickers = {
        "DXY": "DX-Y.NYB",   # ดอลลาร์อินเด็กซ์
        "US10Y": "^TNX",     # ผลตอบแทนพันธบัตร 10 ปี
        "VIX": "^VIX",       # ดัชนีความกลัว (หุ้น)
        "GVZ": "^GVZ"        # ดัชนีความผันผวนของทองคำ
    }
    
    for name, symbol in tickers.items():
        try:
            ticker = yf.Ticker(symbol)
            # ดึงข้อมูล 2 วันล่าสุดเพื่อหา % การเปลี่ยนแปลง
            hist = ticker.history(period="2d")
            if len(hist) >= 2:
                prev_close = hist['Close'].iloc[0]
                current_price = hist['Close'].iloc[1]
                change_pct = ((current_price - prev_close) / prev_close) * 100
                context_data[name] = {
                    "price": round(current_price, 2),
                    "change": round(change_pct, 2)
                }
            else:
                context_data[name] = {"price": "N/A", "change": 0.0}
        except Exception:
            context_data[name] = {"price": "N/A", "change": 0.0}
            
    return context_data

# ==========================================
# 📝 3. เขียนรายงานลับส่งให้ MIDAS
# ==========================================
def write_intelligence_report(news_data, context_data):
    create_directory()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    
    with open(INTELLIGENCE_FILE, 'w', encoding='utf-8') as f:
        f.write(f"# 🕵️‍♂️ HERMES DAILY INTELLIGENCE REPORT\n")
        f.write(f"**Date:** {today_str} | **Last Updated:** {time_str}\n")
        f.write("---\n\n")
        
        # ส่วนที่ 1: Macro Context (DXY, Yields, Volatility)
        f.write("## 🌍 1. GLOBAL MARKET CONTEXT\n")
        f.write("> **คำแนะนำ:** ใช้ข้อมูลนี้ประเมินความแข็งแกร่งของเทรนด์ก่อนตัดสินใจเข้าเทรด\n\n")
        
        f.write(f"- **DXY (US Dollar Index):** {context_data.get('DXY', {}).get('price', 'N/A')} ({context_data.get('DXY', {}).get('change', 0)}%)\n")
        f.write(f"- **US10Y (Bond Yield 10Y):** {context_data.get('US10Y', {}).get('price', 'N/A')}% ({context_data.get('US10Y', {}).get('change', 0)}%)\n")
        f.write(f"- **VIX (Fear Index):** {context_data.get('VIX', {}).get('price', 'N/A')} *(>20 = ตลาดผันผวนสูง)*\n")
        f.write(f"- **GVZ (Gold Volatility):** {context_data.get('GVZ', {}).get('price', 'N/A')}\n\n")
        
        # ส่วนที่ 2: Economic Calendar
        f.write("---\n## 🚨 2. ECONOMIC CALENDAR (Medium/High Impact)\n")
        f.write("> **คำแนะนำ:** หลีกเลี่ยงการเปิดออเดอร์ใหม่ก่อนข่าวกล่องแดง 15 นาที\n\n")
        
        if not news_data:
            f.write("✅ **วันนี้ไม่มีข่าวสำคัญ (ทางสะดวก!)**\n")
        else:
            for news in news_data:
                # ตกแต่งหน้าตาให้ AI อ่านแล้วเข้าใจความรุนแรง
                impact_icon = "🟥 HIGH" if news['impact'] == "High" else "🟧 MEDIUM"
                danger_alert = " ⚠️ **[CRITICAL DANGER: ระวังตลาดสวิงรุนแรง!]**" if news['is_critical'] else ""
                
                f.write(f"- ⏰ **{news['time']}** | [{news['currency']}] {impact_icon} : {news['title']}{danger_alert}\n")
                f.write(f"  *คาดการณ์: {news['forecast']} | ครั้งก่อน: {news['previous']}*\n\n")

    print(f"✅ [Hermes]: วางแฟ้มข่าวสำเร็จ! เข้าไปดูได้ที่ {INTELLIGENCE_FILE}")
    _fetch_and_append_cme()

# ==========================================
# 📊 CME GOLD INTELLIGENCE (06:30 BKK only)
# ==========================================
def _fetch_and_append_cme():
    """ดึง CME Gold data แล้ว append ลง daily_intelligence.md — รันเฉพาะตอน 06:xx BKK"""
    if datetime.now().hour != 6:
        return
    print("📊 [Hermes]: กำลังดึง CME Gold data...")
    try:
        import cme_scraper
        cme_scraper.fetch_all()
        cme_path = os.path.join(BRAIN_RAW_DIR, "CME_Daily.md")
        if not os.path.exists(cme_path):
            print("⚠️ [Hermes]: CME_Daily.md ไม่พบหลัง fetch_all()")
            return
        with open(cme_path, 'r', encoding='utf-8') as cf:
            cme_content = cf.read()
        with open(INTELLIGENCE_FILE, 'a', encoding='utf-8') as f:
            f.write("\n\n---\n## 📊 3. CME GOLD INTELLIGENCE\n")
            f.write("> **คำแนะนำ:** ใช้ Max Pain + Put/Call Wall ประกอบ Institutional Bias ก่อนตัดสินใจเข้า Gold\n\n")
            f.write(cme_content)
        print("✅ [Hermes]: CME data เพิ่มเข้า daily_intelligence.md แล้ว")
    except Exception as e:
        err = str(e)
        if "9222" in err or "ECONNREFUSED" in err.upper() or "connect" in err.lower():
            print("⚠️ [Hermes]: CME ข้ามไป — Chrome Debug Port 9222 ไม่ได้เปิด")
        else:
            print(f"⚠️ [Hermes]: CME ดึงไม่ได้ — {type(e).__name__}: {e}")

# ==========================================
# 📰 ตรวจข่าวแดงใน X นาที (Bangkok Time)
# ==========================================
def is_high_impact_news_near(minutes=30):
    """ตรวจว่ามีข่าว HIGH Impact ใน daily_intelligence.md ภายใน X นาที (แปลง EDT/EST→Bangkok)"""
    if not os.path.exists(INTELLIGENCE_FILE):
        return False
    try:
        with open(INTELLIGENCE_FILE, 'r', encoding='utf-8') as f:
            content = f.read()

        now_utc = datetime.now(timezone.utc)
        # US Eastern: EDT (UTC-4) มีนาคม-พฤศจิกายน, EST (UTC-5) พฤศจิกายน-มีนาคม
        ff_offset = timedelta(hours=-4) if 3 <= now_utc.month <= 11 else timedelta(hours=-5)
        ff_tz     = timezone(ff_offset)
        thai_tz   = timezone(timedelta(hours=7))

        now_thai = datetime.now(thai_tz)
        now_ff   = datetime.now(ff_tz)

        matches = re.findall(r'⏰ \*\*(.+?)\*\*.*?🟥 HIGH', content)
        for t_str in matches:
            try:
                news_naive = datetime.strptime(t_str.strip(), "%I:%M%p")
                news_ff    = news_naive.replace(
                    year=now_ff.year, month=now_ff.month, day=now_ff.day,
                    tzinfo=ff_tz
                )
                news_thai  = news_ff.astimezone(thai_tz)
                diff_min   = (news_thai - now_thai).total_seconds() / 60
                if -5 <= diff_min <= minutes:
                    return True
            except:
                continue
    except:
        pass
    return False

# ==========================================
# 📊 CME Schedule Functions
# ==========================================

def _save_cme_snapshot(data):
    try:
        create_directory()
        existing = {}
        if os.path.exists(CME_SNAPSHOT_FILE):
            with open(CME_SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        existing.update(data)
        existing["last_updated"] = datetime.now().isoformat()
        with open(CME_SNAPSHOT_FILE, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ [CME Snapshot]: {e}")


def load_prev_snapshot():
    """โหลด CME snapshot ล่าสุด (เรียกจาก main.py ตอนเริ่มระบบ)"""
    try:
        if os.path.exists(CME_SNAPSHOT_FILE):
            with open(CME_SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def fetch_cme_vol2vol_data():
    """ดึง Vol2Vol data — รัน ทุกชั่วโมง (XX:00)"""
    try:
        import cme_scraper
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            ctx = pw.chromium.connect_over_cdp("http://localhost:9222").contexts[0]
            d = cme_scraper._run_vol2vol(ctx)

        pc_ratio = None
        if d.get("put_volume") and d.get("call_volume") and d["call_volume"] > 0:
            pc_ratio = round(d["put_volume"] / d["call_volume"], 3)

        snapshot = {
            "put_volume":   d.get("put_volume"),
            "call_volume":  d.get("call_volume"),
            "pc_ratio":     pc_ratio,
            "volatility":   d.get("volatility"),
            "future_price": d.get("future_price"),
        }
        _save_cme_snapshot(snapshot)
        print(f"✅ [CME Vol2Vol]: PC Ratio={pc_ratio} | Fut={d.get('future_price')}")
        return snapshot
    except Exception as e:
        err = str(e)
        if "9222" in err or "connect" in err.lower():
            print("⚠️ [CME Vol2Vol]: Chrome Debug Port 9222 ไม่ได้เปิด")
        else:
            print(f"⚠️ [CME Vol2Vol]: {e}")
        return None


def fetch_cme_oi_matrix_data():
    """ดึง OI Matrix data — รัน ทุก 6 ชั่วโมง (06/12/18/23)"""
    import cme_scraper
    import time as _time
    from playwright.sync_api import sync_playwright

    for attempt in range(1, 4):
        try:
            _time.sleep(3 * attempt)  # ให้ Chrome ตั้งตัวก่อน โดยเฉพาะหลัง Vol2Vol
            with sync_playwright() as pw:
                ctx = pw.chromium.connect_over_cdp("http://localhost:9222").contexts[0]
                d = cme_scraper._run_oi_heatmap(ctx)

            snapshot = {
                "put_wall":     d.get("put_wall"),
                "call_wall":    d.get("call_wall"),
                "max_pain":     d.get("max_pain"),
                "put_wall_oi":  d.get("put_wall_oi"),
                "call_wall_oi": d.get("call_wall_oi"),
            }
            _save_cme_snapshot(snapshot)
            print(f"✅ [CME OI]: Put Wall={d.get('put_wall')} | Call Wall={d.get('call_wall')}")
            return snapshot
        except Exception as e:
            err = str(e)
            if "9222" in err or "connect" in err.lower():
                print("⚠️ [CME OI]: Chrome Debug Port 9222 ไม่ได้เปิด")
                return None
            print(f"⚠️ [CME OI] attempt {attempt}/3: {e}")
    return None


def fetch_cme_cot_data():
    """ดึง COT data — รัน เฉพาะวันศุกร์ 06:00"""
    try:
        import cme_scraper
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            ctx = pw.chromium.connect_over_cdp("http://localhost:9222").contexts[0]
            d = cme_scraper._run_cot(ctx)
        print(f"✅ [CME COT]: MM Net={d.get('mm_net'):,}")
        return d
    except Exception as e:
        err = str(e)
        if "9222" in err or "connect" in err.lower():
            print("⚠️ [CME COT]: Chrome Debug Port 9222 ไม่ได้เปิด")
        else:
            print(f"⚠️ [CME COT]: {e}")
        return None


def check_cme_alerts(prev_snapshot, current_snapshot):
    """เปรียบเทียบ snapshot — Return list of alerts หรือ None ถ้าไม่มีอะไรเปลี่ยน"""
    alerts = []

    # Put/Call Ratio เปลี่ยน > 0.3
    prev_pc = prev_snapshot.get("pc_ratio")
    curr_pc = current_snapshot.get("pc_ratio")
    if prev_pc is not None and curr_pc is not None:
        change = abs(curr_pc - prev_pc)
        if change > 0.3:
            alerts.append({
                "type":    "pc_ratio",
                "prev":    prev_pc,
                "current": curr_pc,
                "change":  round(change, 3),
                "message": f"Put/Call Ratio เปลี่ยน {change:.3f} ({prev_pc} → {curr_pc})",
            })

    # OI Wall ย้าย > 50 points
    for wall in ["put_wall", "call_wall"]:
        prev_w = prev_snapshot.get(wall)
        curr_w = current_snapshot.get(wall)
        if prev_w is not None and curr_w is not None:
            move = abs(curr_w - prev_w)
            if move > 50:
                alerts.append({
                    "type":    wall,
                    "prev":    prev_w,
                    "current": curr_w,
                    "move":    move,
                    "message": f"{wall.replace('_', ' ').title()} ย้าย {move:.0f} pts ({prev_w} → {curr_w})",
                })

    return alerts if alerts else None


# ==========================================
# 🚀 MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("===========================================")
    print("  🪽 HERMES THE INTEL SCOUT (V1.6) ONLINE")
    print("===========================================")
    
    # 1. ดึงข่าว
    news = fetch_forex_factory_news()
    # 2. ดึงสถานการณ์ตลาด
    context = fetch_market_context()
    # 3. เขียนลงไฟล์
    write_intelligence_report(news, context)