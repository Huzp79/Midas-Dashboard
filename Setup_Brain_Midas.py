import os

print("🧠 Midas: กำลังลงเสาเข็มสร้างสมอง...")

# 1. กำหนดโครงสร้างโฟลเดอร์ทั้งหมด
folders = [
    "Midas_Brain/raw/market_data",   # เก็บข้อมูลกราฟที่ดึงจาก MT5 (เช่น 10 แท่งที่บอสดึงได้)
    "Midas_Brain/raw/trades",        # เก็บประวัติการเข้าเทรด
    "Midas_Brain/wiki/strategies",   # ให้ AI สรุปแผนการเทรดมาเก็บไว้ที่นี่
    "Midas_Brain/wiki/lessons"       # ให้ AI สรุปบทเรียนเวลาเทรดพลาด
]

for folder in folders:
    os.makedirs(folder, exist_ok=True)
    print(f"📁 สร้างโครงสร้าง: {folder}")

# 2. สร้างหน้า Dashboard (หน้าแรกของสมอง)
dashboard_content = """# 🧠 Midas Central Command

นี่คือคลังสมองส่วนกลาง (Knowledge Base) ของ AI Agent Midas 

* โฟลเดอร์ `raw/` : บอสมีหน้าที่เอาข้อมูลดิบมาโยนใส่ไว้ที่นี่
* โฟลเดอร์ `wiki/` : Midas จะเอาข้อมูลไปวิเคราะห์ แล้วมาเขียนสรุปไว้ที่นี่

สถานะ: 🟢 พร้อมรับข้อมูลจากบอสแล้ว!
"""

with open("Midas_Brain/00_Dashboard.md", "w", encoding="utf-8") as file:
    file.write(dashboard_content)

print("\n✅ สร้างคลังสมองเสร็จสมบูรณ์ 100%! บรรลุเป้าหมายคืนนี้แล้วครับบอส!")