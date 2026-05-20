import schedule
import time
import subprocess
import sys
from datetime import datetime

def send_hermes():
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{now}] ⏰ ถึงเวลาแล้ว! ปล่อยตัวเทพ Hermes บินไปหาข่าว...")
    
    # สั่งรันไฟล์ hermes.py เหมือนที่เราพิมพ์ใน Terminal
    try:
        subprocess.run([sys.executable, "hermes.py"], check=True)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🏁 Hermes ทำงานรอบนี้เสร็จสิ้น กลับมาแสตนด์บาย!\n")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการรัน Hermes: {e}")

# ==========================================
# ⏰ ตั้งเวลาการทำงาน (Bangkok Time)
# ==========================================
# รอบ 1: Pre-Asia (เตรียมรับเช้าวันใหม่)
schedule.every().day.at("06:30").do(send_hermes)

# รอบ 2: Pre-London (เตรียมรับโวลุ่มยุโรป)
schedule.every().day.at("13:30").do(send_hermes)

# รอบ 3: Pre-NY (เตรียมรับโวลุ่มอเมริกา + ข่าวกล่องแดง)
schedule.every().day.at("18:30").do(send_hermes)

# ==========================================
if __name__ == "__main__":
    print("===========================================")
    print("  ⏳ HERMES SCHEDULER: ONLINE & WAITING")
    print("===========================================")
    print("รอบการทำงานที่ตั้งไว้:")
    print("  1. Pre-Asia   : 06:30 น.")
    print("  2. Pre-London : 13:30 น.")
    print("  3. Pre-NY     : 18:30 น.")
    print("-------------------------------------------")
    print("...ระบบกำลังเฝ้ารอเวลา (เปิดหน้าต่างนี้ทิ้งไว้)...")
    
    # รันลูปเช็คเวลาไปเรื่อยๆ
    while True:
        schedule.run_pending()
        time.sleep(30) # เช็คนาฬิกาทุกๆ 30 วินาทีเพื่อไม่ให้กิน CPU