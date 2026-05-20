import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timezone, timedelta
import os
import yfinance as yf

# ==========================================
# 🛠️ CONFIGURATION
# ==========================================
BRAIN_RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Midas_Brain", "data", "market")
INTELLIGENCE_FILE = os.path.join(BRAIN_RAW_DIR, "daily_intelligence.md")

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
# 🚀 MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print("===========================================")
    print("  🪽 HERMES THE INTEL SCOUT (V1.5) ONLINE")
    print("===========================================")
    
    # 1. ดึงข่าว
    news = fetch_forex_factory_news()
    # 2. ดึงสถานการณ์ตลาด
    context = fetch_market_context()
    # 3. เขียนลงไฟล์
    write_intelligence_report(news, context)