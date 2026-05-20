import MetaTrader5 as mt5
import json
import os
from datetime import datetime

def run_feeder(symbol="GOLD"):
    """ดึงข้อมูล Indicator ทั้งหมดจาก MT5 แล้วบันทึกเป็น Markdown"""

    if not mt5.initialize():
        print(f"❌ เชื่อมต่อ MT5 ไม่สำเร็จ: {mt5.last_error()}")
        return

    tf_list = ["PERIOD_H4", "PERIOD_H1", "PERIOD_M30", "PERIOD_M15", "PERIOD_M5", "PERIOD_M1"]

    indicators = {
        "SMC God Eye":      "smc_state",
        "MACD Divergence":  "macd_state",
        "Liquidity Sweep":  "lq_sweep_state",
        "Volume Profile":   "volume_profile_state",
        "Squeeze Momentum": "squeeze_state"
    }

    terminal_info = mt5.terminal_info()
    if terminal_info is None:
        mt5.shutdown()
        return

    base_dir = os.path.join(terminal_info.data_path, "MQL5", "Files", symbol)
    market_report = f"# 📊 MIDAS MARKET REPORT - {symbol}\n**Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    files_found = 0

    for tf_name in tf_list:
        tf_label = tf_name.replace('PERIOD_', '')
        market_report += f"## ⏳ {tf_label}\n"
        has_data = False

        for ind_name, file_prefix in indicators.items():
            json_path = os.path.join(base_dir, f"{file_prefix}_{symbol}_{tf_name}.json")

            if not os.path.exists(json_path):
                continue

            has_data = True
            files_found += 1

            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if file_prefix == "smc_state":
                    market_report += f"- **[SMC]:** Price={data['current_price']} | Swing={data['structure']['swing_trend']} | Internal={data['structure']['internal_trend']}\n"
                    market_report += f"  - 🟢 Bull OB({data['zones']['bull_ob_top']}-{data['zones']['bull_ob_btm']}) FVG({data['zones']['bull_fvg_top']}-{data['zones']['bull_fvg_btm']})\n"
                    market_report += f"  - 🔴 Bear OB({data['zones']['bear_ob_top']}-{data['zones']['bear_ob_btm']}) FVG({data['zones']['bear_fvg_top']}-{data['zones']['bear_fvg_btm']})\n"

                elif file_prefix == "macd_state":
                    market_report += f"- **[MACD]:** Divergence={data['divergence']} | Hist={data.get('histogram', 'N/A')}\n"

                elif file_prefix == "lq_sweep_state":
                     trigger    = data.get('trigger', {})
                     bars_ago   = trigger.get('bars_ago', -1)
                     has_sweep  = trigger.get('has_recent_sweep', False)
                     sweep_type = trigger.get('sweep_type', 'NONE')
                     zones = data.get('zones', {})
                     market_report += f"- **[LQ Sweep]:** has_sweep={has_sweep} | sweep_type={sweep_type} | bars_ago={bars_ago} | 🟢({zones.get('bullish_top')}-{zones.get('bullish_btm')}) 🔴({zones.get('bearish_top')}-{zones.get('bearish_btm')})\n"
                     
                elif file_prefix == "volume_profile_state":
                    zones = data.get('zones', {})
                    market_report += f"- **[Volume Profile]:** POC={zones.get('poc')} | VAL={zones.get('val')} VAH={zones.get('vah')}\n"

                elif file_prefix == "squeeze_state":
                    trigger = data.get("trigger", {})
                    is_firing  = trigger.get("is_firing_now", False)
                    fire_dir   = trigger.get("fire_direction", "NONE")
                    bars_since = trigger.get("bars_since_fire", -1)
                    market_report += f"- **[Squeeze]:** State={data.get('squeeze_state')} | is_firing_now={is_firing} | Direction={fire_dir} | bars_since={bars_since}\n"

            except Exception as e:
                market_report += f"- ⚠️ Error {ind_name}: {e}\n"

        if not has_data:
            market_report += "- ❌ ไม่มีข้อมูล\n"

        market_report += "\n"

    # บันทึกไฟล์
    save_dir  = "Midas_Brain/data/market"
    save_path = os.path.join(save_dir, f"latest_data_{symbol}.md")
    os.makedirs(save_dir, exist_ok=True)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write(market_report)

    print(f"✅ [Feeder]: พบ {files_found} ไฟล์ JSON — อัปเดต latest_data_{symbol}.md เรียบร้อย")

    # ไม่ shutdown ที่นี่ — ให้ main.py จัดการ MT5 connection เอง

if __name__ == "__main__":
    print("👁️ [Midas Eyes]: รันแบบ Standalone...")
    run_feeder()
    mt5.shutdown()  # shutdown เฉพาะตอนรันตรงเท่านั้น