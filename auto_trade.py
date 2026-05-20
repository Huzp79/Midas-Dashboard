import MetaTrader5 as mt5
import requests

# ==========================================
# 🛑 🛑 ตั้งค่า Telegram ของบอสตรงนี้ 🛑 🛑
# ==========================================
from dotenv import load_dotenv
import os
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MAX_SPREAD = {
    "GOLD":   60,
    "XAUUSD": 60,
    "BTCUSD": 5000,
}
_DEFAULT_MAX_SPREAD = 40

def check_spread_safe(symbol):
    """ตรวจ Spread ปัจจุบัน: True = ปลอดภัย, False = กว้างเกินไป"""
    if not mt5.initialize():
        print(f"⚠️ [Spread]: MT5 ไม่ตอบสนอง — ข้ามการตรวจ Spread")
        return True
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"⚠️ [Spread]: ดึงข้อมูล {symbol} ไม่ได้ — ข้ามการตรวจ Spread")
        return True
    spread     = info.spread
    max_spread = MAX_SPREAD.get(symbol, _DEFAULT_MAX_SPREAD)
    if spread <= max_spread:
        print(f"✅ [Spread]: {symbol} Spread={spread} ≤ {max_spread} — ปลอดภัย")
        return True
    print(f"🚫 [Spread]: {symbol} Spread={spread} > {max_spread} — กว้างเกินไป ยกเลิก")
    return False

def send_telegram_alert(action, symbol, entry, sl, tp, reason):
    """ส่งข้อความรายงานเจ้านายผ่าน Telegram"""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.startswith("ใส่_TOKEN"):
        print("⚠️ ข้ามการส่ง Telegram (บอสยังไม่ได้ใส่ Token)")
        return

    msg = f"🚨 <b>Midas Auto-Trade Alert</b> 🚨\n\n"
    msg += f"🔥 <b>Action:</b> {action} {symbol}\n"
    msg += f"🎯 <b>Entry:</b> {entry}\n"
    msg += f"🛡️ <b>SL:</b> {sl}\n"
    msg += f"💰 <b>TP:</b> {tp}\n\n"
    msg += f"🧠 <b>เหตุผลจากสมองกล:</b>\n{reason}"

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'HTML'})
        print("📲 ส่งรายงานเข้ามือถือบอสเรียบร้อย!")
    except Exception as e:
        print(f"❌ ส่ง Telegram ไม่สำเร็จ: {e}")

def send_telegram_message(text):
    """ส่งข้อความธรรมดา (ไม่ใช่ Trade Alert) ผ่าน Telegram"""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN.startswith("ใส่_TOKEN"):
        print("⚠️ ข้ามการส่ง Telegram (ยังไม่ได้ใส่ Token)")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text})
        print("📲 ส่ง Telegram Message เรียบร้อย!")
    except Exception as e:
        print(f"❌ ส่ง Telegram ไม่สำเร็จ: {e}")

def close_mt5_position(ticket, symbol, volume, pos_type):
    """ปิด Position ด้วย Ticket number (pos_type: 0=BUY, 1=SELL)"""
    if not mt5.initialize():
        print(f"❌ [Close]: MT5 ไม่ตอบสนอง")
        return False
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"❌ [Close]: ดึงราคา {symbol} ไม่ได้")
        return False
    close_price = tick.bid if pos_type == 0 else tick.ask
    close_type  = mt5.ORDER_TYPE_SELL if pos_type == 0 else mt5.ORDER_TYPE_BUY
    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       float(volume),
        "type":         close_type,
        "position":     ticket,
        "price":        close_price,
        "deviation":    20,
        "magic":        777777,
        "comment":      "Midas Night Watch",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ [Close]: ปิดไม้ #{ticket} ไม่สำเร็จ — {result.comment}")
        return False
    print(f"✅ [Close]: ปิดไม้ #{ticket} {symbol} สำเร็จ")
    return True

def execute_mt5_order(action, symbol="GOLD", lot=0.01, sl=0.0, tp=0.0):
    """มือปืนลั่นไกใน MT5"""
    # 1. เชื่อมต่อ MT5
    if not mt5.initialize():
        print("❌ เชื่อมต่อ MT5 ไม่สำเร็จ! เปิดโปรแกรม MT5 ไว้หรือเปล่า?")
        return False

    print(f"🔫 [HITMAN]: กำลังเตรียมลั่นไก {action} {lot} Lot...")

    # 2. ดึงราคาปัจจุบัน (Ask สำหรับ Buy, Bid สำหรับ Sell)
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print("❌ ดึงราคาไม่สำเร็จ! ชื่อคู่เงินถูกไหม?")
        return False
        
    price = tick.ask if action == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

    # 3. ประกอบร่างคำสั่งยิง
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot),
        "type": order_type,
        "price": price,
        "sl": float(sl) if sl else 0.0,
        "tp": float(tp) if tp else 0.0,
        "deviation": 20, # ยอมให้ราคาคลาดเคลื่อนได้ 20 จุด
        "magic": 777777, # เลขประจำตัวบอท
        "comment": "Midas Sniper AI",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # 4. ลั่นไก!
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ ยิงออเดอร์พลาด! MT5 แจ้ง Error: {result.comment} (Code: {result.retcode})")
        return False

    print(f"✅ ยิงเข้าเป้า! เปิดออเดอร์ {action} สำเร็จ (Ticket: {result.order})")
    return True