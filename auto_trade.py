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

def close_position_by_ticket(ticket):
    """ปิดไม้ตาม Ticket เพียงอย่างเดียว — ค้นหา Symbol/Volume/Type จาก MT5 เอง
    Return (True, close_price) หรือ (False, None)"""
    if not mt5.initialize():
        print(f"❌ [/close]: MT5 ไม่ตอบสนอง")
        return False, None
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        mt5.shutdown()
        print(f"❌ [/close]: ไม่พบ Position #{ticket}")
        return False, None
    pos  = positions[0]
    tick = mt5.symbol_info_tick(pos.symbol)
    if not tick:
        mt5.shutdown()
        print(f"❌ [/close]: ดึงราคา {pos.symbol} ไม่ได้")
        return False, None
    close_price = tick.bid if pos.type == 0 else tick.ask
    close_type  = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       pos.symbol,
        "volume":       float(pos.volume),
        "type":         close_type,
        "position":     ticket,
        "price":        close_price,
        "deviation":    20,
        "magic":        777777,
        "comment":      "Midas /close command",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    mt5.shutdown()
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        comment = result.comment if result else "ไม่มีการตอบสนอง"
        print(f"❌ [/close]: ปิดไม้ #{ticket} ไม่สำเร็จ — {comment}")
        return False, None
    print(f"✅ [/close]: ปิดไม้ #{ticket} {pos.symbol} @ {close_price}")
    return True, close_price


def place_pending_order(symbol, action, entry, sl, tp, lot):
    """วาง Limit Order (BUY_LIMIT หรือ SELL_LIMIT) — Return ticket หรือ None"""
    if not mt5.initialize():
        print(f"❌ [Pending]: MT5 ไม่ตอบสนอง")
        return None
    order_type = mt5.ORDER_TYPE_BUY_LIMIT if action == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
    request = {
        "action":       mt5.TRADE_ACTION_PENDING,
        "symbol":       symbol,
        "volume":       float(lot),
        "type":         order_type,
        "price":        float(entry),
        "sl":           float(sl) if sl else 0.0,
        "tp":           float(tp) if tp else 0.0,
        "deviation":    20,
        "magic":        777777,
        "comment":      "Midas Pre-Entry",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    result = mt5.order_send(request)
    mt5.shutdown()
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        comment = result.comment if result else "ไม่มีการตอบสนอง"
        print(f"❌ [Pending]: วาง {action} LIMIT ไม่สำเร็จ — {comment}")
        return None
    print(f"✅ [Pending]: {action} LIMIT #{result.order} | {symbol} @ {entry}")
    return result.order

def cancel_pending_order(ticket):
    """ยกเลิก Pending Order — Return True/False"""
    try:
        if not mt5.initialize():
            return False
        result = mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})
        mt5.shutdown()
        if result is None:
            return False
        ok = result.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            print(f"🗑️ [Pending]: ยกเลิก Order #{ticket} สำเร็จ")
        return ok
    except Exception as e:
        print(f"⚠️ [Pending Cancel]: {e}")
        return False

def get_closed_trade_result(ticket):
    """ดึงผลการเทรดที่ปิดแล้วจาก MT5 History"""
    try:
        if not mt5.initialize():
            return None
        deals = mt5.history_deals_get(position=ticket)
        mt5.shutdown()
        if not deals:
            return None
        for deal in reversed(deals):
            if deal.entry == mt5.DEAL_ENTRY_OUT:
                profit = deal.profit + deal.swap + deal.commission
                result = "WIN" if profit > 0 else ("BE" if profit == 0 else "LOSS")
                return {"exit_price": deal.price, "profit": profit, "result": result}
        return None
    except Exception as e:
        print(f"⚠️ [TradeResult]: {e}")
        return None

def execute_mt5_order(action, symbol="GOLD", lot=0.01, sl=0.0, tp=0.0):
    """มือปืนลั่นไกใน MT5 — Return (True, actual_entry) หรือ (False, None)"""
    if not mt5.initialize():
        print("❌ เชื่อมต่อ MT5 ไม่สำเร็จ! เปิดโปรแกรม MT5 ไว้หรือเปล่า?")
        return (False, None)

    print(f"🔫 [HITMAN]: กำลังเตรียมลั่นไก {action} {lot} Lot...")

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print("❌ ดึงราคาไม่สำเร็จ! ชื่อคู่เงินถูกไหม?")
        mt5.shutdown()
        return (False, None)

    price      = tick.ask if action == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       float(lot),
        "type":         order_type,
        "price":        price,
        "sl":           float(sl) if sl else 0.0,
        "tp":           float(tp) if tp else 0.0,
        "deviation":    20,
        "magic":        777777,
        "comment":      "Midas Sniper AI",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ ยิงออเดอร์พลาด! MT5 แจ้ง Error: {result.comment} (Code: {result.retcode})")
        mt5.shutdown()
        return (False, None)

    # ดึง actual fill price — ใช้ result.price ก่อน ถ้าเป็น 0 ให้ดึงจาก position
    actual_entry = result.price
    if not actual_entry:
        pos = mt5.positions_get(ticket=result.order)
        actual_entry = pos[0].price_open if pos else 0

    mt5.shutdown()
    print(f"✅ ยิงเข้าเป้า! {action} สำเร็จ (Ticket: {result.order}) @ {actual_entry}")
    return (True, actual_entry)