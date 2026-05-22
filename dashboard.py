import os
import re
import json
from datetime import datetime, date
from pathlib import Path
from flask import Flask, render_template_string

app = Flask(__name__)

BASE_DIR          = "Midas_Brain"
JOURNAL_DIR       = os.path.join(BASE_DIR, "data", "journal")
CME_DAILY_PATH    = os.path.join(BASE_DIR, "data", "market", "CME_Daily.md")
CME_SNAPSHOT_PATH = os.path.join(BASE_DIR, "data", "market", "cme_snapshot.json")
MORNING_BRIEF_MD  = os.path.join(BASE_DIR, "data", "market", "morning_brief.md")
MORNING_BRIEF_JSON= os.path.join(BASE_DIR, "data", "market", "morning_brief.json")
INTELLIGENCE_PATH = os.path.join(BASE_DIR, "data", "market", "daily_intelligence.md")

# ─────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def get_mt5_account():
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return None
        info = mt5.account_info()
        mt5.shutdown()
        if not info:
            return None
        return {
            "balance":  round(info.balance, 2),
            "equity":   round(info.equity, 2),
            "margin":   round(info.margin, 2),
            "free_margin": round(info.margin_free, 2),
            "profit":   round(info.profit, 2),
            "currency": info.currency,
            "server":   info.server,
            "login":    info.login,
        }
    except Exception:
        return None


def get_mt5_positions():
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return []
        raw = mt5.positions_get()
        mt5.shutdown()
        if not raw:
            return []
        rows = []
        for p in raw:
            rows.append({
                "ticket":     p.ticket,
                "symbol":     p.symbol,
                "type":       "BUY" if p.type == 0 else "SELL",
                "volume":     p.volume,
                "open_price": round(p.price_open, 5),
                "current":    round(p.price_current, 5),
                "sl":         round(p.sl, 5) if p.sl else "—",
                "tp":         round(p.tp, 5) if p.tp else "—",
                "profit":     round(p.profit, 2),
                "swap":       round(p.swap, 2),
                "open_time":  datetime.fromtimestamp(p.time).strftime("%H:%M:%S"),
            })
        return rows
    except Exception:
        return []


def parse_journal_entries(text):
    """Parse journal .md → list of dicts"""
    entries = []
    blocks = re.split(r'\n## 🕒 ', text)
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().split('\n')
        time_str = lines[0].strip() if lines else ""
        entry = {"time": time_str}
        for line in lines[1:]:
            m = re.match(r'\*\*Symbol:\*\* (.+)', line)
            if m: entry["symbol"] = m.group(1).strip()
            m = re.match(r'\*\*Action:\*\* (\w+) \| \*\*Confidence:\*\* (\w+)', line)
            if m:
                entry["action"] = m.group(1).strip()
                entry["confidence"] = m.group(2).strip()
            m = re.match(r'\*\*Score:\*\* ([\d.]+)/10 \| \*\*RR:\*\* ([\d.:]+)', line)
            if m:
                entry["score"] = m.group(1).strip()
                entry["rr"]    = m.group(2).strip()
            m = re.match(r'\*\*Bias:\*\* (.+)', line)
            if m: entry["bias"] = m.group(1).strip()
            m = re.match(r'\*\*Reason:\*\* (.+)', line)
            if m: entry["reason"] = m.group(1).strip()
            m = re.match(r'\*\*Summary:\*\* (.+)', line)
            if m: entry["summary"] = m.group(1).strip()
            # Win/Loss entries
            m = re.match(r'\*\*Result:\*\* (.+)', line)
            if m: entry["result"] = m.group(1).strip()
            m = re.match(r'\*\*PnL:\*\* (.+)', line)
            if m: entry["pnl"] = m.group(1).strip()
        if "symbol" in entry:
            entries.append(entry)
    return entries


def get_all_journal_data():
    """Load all journal files → aggregated stats + entries list"""
    all_entries = []
    daily_pnl = {}

    for f in sorted(Path(JOURNAL_DIR).glob("20*.md")):
        day = f.stem
        text = f.read_text(encoding="utf-8", errors="ignore")
        entries = parse_journal_entries(text)
        for e in entries:
            e["date"] = day
        all_entries.extend(entries)

    # Count trades (non-WAIT actions)
    trades = [e for e in all_entries if e.get("action") in ("BUY", "SELL")]
    wins   = [e for e in trades if float(e.get("pnl", "0").replace("$","").replace("+","") or 0) > 0]
    total_pnl = sum(
        float(e.get("pnl", "0").replace("$","").replace("+","") or 0)
        for e in trades if "pnl" in e
    )

    # Per-symbol breakdown
    symbol_stats = {}
    for e in trades:
        sym = e.get("symbol", "?")
        if sym not in symbol_stats:
            symbol_stats[sym] = {"trades": 0, "wins": 0, "pnl": 0.0}
        symbol_stats[sym]["trades"] += 1
        pnl_val = float(e.get("pnl", "0").replace("$","").replace("+","") or 0)
        symbol_stats[sym]["pnl"] += pnl_val
        if pnl_val > 0:
            symbol_stats[sym]["wins"] += 1

    # Daily P&L
    for e in trades:
        day = e.get("date", "?")
        pnl_val = float(e.get("pnl", "0").replace("$","").replace("+","") or 0)
        daily_pnl[day] = daily_pnl.get(day, 0.0) + pnl_val

    win_rate = round(len(wins) / len(trades) * 100, 1) if trades else 0.0

    return {
        "entries":      all_entries,
        "trades":       trades,
        "win_rate":     win_rate,
        "total_pnl":    round(total_pnl, 2),
        "symbol_stats": symbol_stats,
        "daily_pnl":    daily_pnl,
    }


def get_today_journal():
    today = date.today().strftime("%Y-%m-%d")
    path  = os.path.join(JOURNAL_DIR, f"{today}.md")
    text  = read_file(path)
    if not text:
        return {"trades": 0, "waits": 0, "wins": 0, "entries": []}
    entries = parse_journal_entries(text)
    trades  = [e for e in entries if e.get("action") in ("BUY","SELL")]
    waits   = [e for e in entries if e.get("action") == "WAIT"]
    wins    = [e for e in trades if float(e.get("pnl","0").replace("$","").replace("+","") or 0) > 0]
    return {"trades": len(trades), "waits": len(waits), "wins": len(wins), "entries": entries}


def parse_cme_daily():
    text = read_file(CME_DAILY_PATH)
    if not text:
        return {}
    out = {}
    patterns = {
        "updated":    r'\*\*Updated:\*\* (.+)',
        "symbol":     r'\| Symbol\s+\| (.+?) \|',
        "exp_date":   r'\| Exp Date\s+\| (.+?) \|',
        "dte":        r'\| DTE\s+\| (.+?) \|',
        "put_volume": r'\| Put Volume\s+\| (.+?) \|',
        "call_volume":r'\| Call Volume\s+\| (.+?) \|',
        "volatility": r'\| Volatility\s+\| (.+?) \|',
        "gc_futures": r'\| GC Futures\s+\| (.+?) \|',
        "put_wall_f": r'\| Put Wall\s+\| (.+?) \| (.+?) \| (.+?) \|',
        "call_wall_f":r'\| Call Wall\s+\| (.+?) \| (.+?) \| (.+?) \|',
        "max_pain_f": r'\| Max Pain\s+\| (.+?) \| (.+?) \|',
        "basis":      r'\| Basis\s+\| (.+?) \|',
        "cot_long":   r'\| Long\s+\| (.+?) \|',
        "cot_short":  r'\| Short\s+\| (.+?) \|',
        "cot_net":    r'\| Net Position\s+\| (.+?) \|',
    }
    for key, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            if key in ("put_wall_f","call_wall_f"):
                out[key] = {"futures": m.group(1).strip(), "spot": m.group(2).strip(), "oi": m.group(3).strip()}
            elif key == "max_pain_f":
                out[key] = {"futures": m.group(1).strip(), "spot": m.group(2).strip()}
            else:
                out[key] = m.group(1).strip()
    return out


def read_cme_snapshot():
    text = read_file(CME_SNAPSHOT_PATH)
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def read_morning_brief_json():
    text = read_file(MORNING_BRIEF_JSON)
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


# ─────────────────────────────────────────────
# Base layout
# ─────────────────────────────────────────────

def base_page(title, body, refresh=30):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template_string(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{refresh}">
<title>Midas — {title}</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
<style>
  body {{ background:#0d1117; color:#e6edf3; font-family:'Segoe UI',sans-serif; }}
  .navbar {{ background:#161b22!important; border-bottom:1px solid #30363d; }}
  .card {{ background:#161b22; border:1px solid #30363d; }}
  .card-header {{ background:#1f2937; border-bottom:1px solid #30363d; font-weight:600; }}
  .table {{ color:#e6edf3; }}
  .table-dark {{ --bs-table-bg:#161b22; --bs-table-border-color:#30363d; }}
  .badge-bullish {{ background:#1a4731; color:#3fb950; }}
  .badge-bearish {{ background:#4d1a1a; color:#f85149; }}
  .badge-neutral  {{ background:#2d2d2d; color:#8b949e; }}
  .profit  {{ color:#3fb950; }}
  .loss    {{ color:#f85149; }}
  .neutral {{ color:#8b949e; }}
  .stat-card {{ border-left:4px solid #58a6ff; }}
  .stat-val  {{ font-size:1.6rem; font-weight:700; }}
  .refresh-badge {{ font-size:.75rem; color:#8b949e; }}
  pre {{ color:#e6edf3; background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:12px; font-size:.82rem; max-height:400px; overflow-y:auto; }}
</style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark px-3">
  <a class="navbar-brand fw-bold" href="/"><i class="bi bi-robot text-warning"></i> MIDAS</a>
  <div class="navbar-nav ms-3">
    <a class="nav-link {'active fw-bold' if title=='Overview' else ''}" href="/">Overview</a>
    <a class="nav-link {'active fw-bold' if title=='Monitor' else ''}"  href="/monitor">Monitor</a>
    <a class="nav-link {'active fw-bold' if title=='Journal' else ''}"  href="/journal">Journal</a>
    <a class="nav-link {'active fw-bold' if title=='CME' else ''}"      href="/cme">CME</a>
  </div>
  <span class="ms-auto refresh-badge"><i class="bi bi-arrow-clockwise"></i> auto {refresh}s &nbsp;|&nbsp; {now}</span>
</nav>
<div class="container-fluid py-3">
{body}
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body></html>""")


# ─────────────────────────────────────────────
# Route: Overview /
# ─────────────────────────────────────────────

@app.route("/")
def overview():
    acct      = get_mt5_account()
    positions = get_mt5_positions()
    today     = get_today_journal()
    cme       = parse_cme_daily()
    snap      = read_cme_snapshot()

    online = acct is not None
    status_badge = ('<span class="badge bg-success fs-6">ONLINE</span>'
                    if online else
                    '<span class="badge bg-danger fs-6">OFFLINE</span>')

    # Account cards
    if acct:
        profit_cls = "profit" if acct["profit"] >= 0 else "loss"
        acct_html = f"""
<div class="row g-3 mb-3">
  <div class="col-md-3"><div class="card stat-card h-100 p-3">
    <div class="text-muted small">Balance</div>
    <div class="stat-val">${acct['balance']:,.2f}</div>
    <div class="text-muted small">{acct['currency']} · {acct['server']}</div>
  </div></div>
  <div class="col-md-3"><div class="card stat-card h-100 p-3" style="border-left-color:#3fb950">
    <div class="text-muted small">Equity</div>
    <div class="stat-val">${acct['equity']:,.2f}</div>
    <div class="text-muted small">Free Margin: ${acct['free_margin']:,.2f}</div>
  </div></div>
  <div class="col-md-3"><div class="card stat-card h-100 p-3" style="border-left-color:{'#3fb950' if acct['profit']>=0 else '#f85149'}">
    <div class="text-muted small">Floating P&L</div>
    <div class="stat-val {profit_cls}">${acct['profit']:+,.2f}</div>
    <div class="text-muted small">{len(positions)} open position(s)</div>
  </div></div>
  <div class="col-md-3"><div class="card stat-card h-100 p-3" style="border-left-color:#f0883e">
    <div class="text-muted small">Today</div>
    <div class="stat-val">{today['trades']} trades</div>
    <div class="text-muted small">{today['wins']} wins · {today['waits']} scans</div>
  </div></div>
</div>"""
    else:
        acct_html = '<div class="alert alert-warning">MT5 not connected — showing file data only</div>'

    # Open positions table
    if positions:
        rows = ""
        for p in positions:
            pc = "profit" if p["profit"] >= 0 else "loss"
            tc = "text-success" if p["type"] == "BUY" else "text-danger"
            rows += f"""<tr>
  <td class="text-muted">{p['ticket']}</td>
  <td><strong>{p['symbol']}</strong></td>
  <td class="{tc} fw-bold">{p['type']}</td>
  <td>{p['volume']}</td>
  <td>{p['open_price']}</td>
  <td>{p['current']}</td>
  <td class="text-danger">{p['sl']}</td>
  <td class="text-success">{p['tp']}</td>
  <td class="{pc} fw-bold">${p['profit']:+,.2f}</td>
  <td class="text-muted">{p['open_time']}</td>
</tr>"""
        pos_html = f"""
<div class="card mb-3">
  <div class="card-header"><i class="bi bi-graph-up-arrow text-warning"></i> Open Positions</div>
  <div class="table-responsive">
    <table class="table table-dark table-sm table-hover mb-0">
      <thead><tr>
        <th>Ticket</th><th>Symbol</th><th>Type</th><th>Vol</th>
        <th>Entry</th><th>Current</th><th>SL</th><th>TP</th>
        <th>P&L</th><th>Time</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""
    else:
        pos_html = '<div class="alert" style="background:#1f2937;color:#8b949e">No open positions</div>'

    # CME summary
    cme_html = ""
    if cme:
        pw  = cme.get("put_wall_f",  {})
        cw  = cme.get("call_wall_f", {})
        mp  = cme.get("max_pain_f",  {})
        net = cme.get("cot_net", "—")
        net_cls = "profit" if net.startswith("-") is False and net != "—" else "loss"
        cme_html = f"""
<div class="card mb-3">
  <div class="card-header"><i class="bi bi-bar-chart-fill text-info"></i> CME Gold — {cme.get('updated','')}</div>
  <div class="card-body">
    <div class="row g-3">
      <div class="col-sm-4"><div class="p-3 rounded" style="background:#0d2b1a">
        <div class="text-muted small">Put Wall (Support)</div>
        <div class="fs-4 profit fw-bold">{pw.get('spot','—')}</div>
        <div class="text-muted small">Futures: {pw.get('futures','—')} · OI: {pw.get('oi','—')}</div>
      </div></div>
      <div class="col-sm-4"><div class="p-3 rounded" style="background:#2b0d0d">
        <div class="text-muted small">Call Wall (Resistance)</div>
        <div class="fs-4 loss fw-bold">{cw.get('spot','—')}</div>
        <div class="text-muted small">Futures: {cw.get('futures','—')} · OI: {cw.get('oi','—')}</div>
      </div></div>
      <div class="col-sm-4"><div class="p-3 rounded" style="background:#1a1a2b">
        <div class="text-muted small">Max Pain</div>
        <div class="fs-4 fw-bold" style="color:#79c0ff">{mp.get('spot','—')}</div>
        <div class="text-muted small">Futures: {mp.get('futures','—')}</div>
      </div></div>
    </div>
    <div class="row g-3 mt-1">
      <div class="col-sm-3"><span class="text-muted">DTE:</span> <strong>{cme.get('dte','—')}</strong></div>
      <div class="col-sm-3"><span class="text-muted">Volatility:</span> <strong>{cme.get('volatility','—')}</strong></div>
      <div class="col-sm-3"><span class="text-muted">PC Ratio:</span> <strong>{snap.get('pc_ratio','—')}</strong></div>
      <div class="col-sm-3"><span class="text-muted">COT Net:</span> <strong class="{net_cls}">{net}</strong></div>
    </div>
  </div>
</div>"""

    # Morning brief quick table
    brief = read_morning_brief_json()
    if brief:
        brows = ""
        for sym, info in brief.items():
            bias = info.get("bias","—")
            if "BULL" in bias:
                bc = "badge-bullish"
                icon = "🟢"
            elif "BEAR" in bias:
                bc = "badge-bearish"
                icon = "🔴"
            else:
                bc = "badge-neutral"
                icon = "⚪"
            brows += f"""<tr>
  <td><strong>{sym}</strong></td>
  <td><span class="badge {bc}">{icon} {bias}</span></td>
  <td>{info.get('wait_for','-')[:60]}</td>
  <td class="text-danger small">{info.get('entry_zone_btm','-')} – <span class="text-success">{info.get('entry_zone_top','-')}</span></td>
  <td class="text-muted small">{info.get('note','-')[:60]}</td>
</tr>"""
        brief_html = f"""
<div class="card mb-3">
  <div class="card-header"><i class="bi bi-sunrise text-warning"></i> Morning Brief</div>
  <div class="table-responsive">
    <table class="table table-dark table-sm table-hover mb-0">
      <thead><tr><th>Symbol</th><th>Bias</th><th>Waiting For</th><th>Entry Zone</th><th>Note</th></tr></thead>
      <tbody>{brows}</tbody>
    </table>
  </div>
</div>"""
    else:
        brief_html = ""

    body = f"""
<div class="d-flex align-items-center mb-3 gap-3">
  <h4 class="mb-0"><i class="bi bi-speedometer2 text-warning"></i> Overview</h4>
  {status_badge}
</div>
{acct_html}
{pos_html}
{brief_html}
{cme_html}"""

    return base_page("Overview", body)


# ─────────────────────────────────────────────
# Route: Monitor /monitor
# ─────────────────────────────────────────────

@app.route("/monitor")
def monitor():
    brief_md    = read_file(MORNING_BRIEF_MD) or "ไม่มีข้อมูล"
    intelligence= read_file(INTELLIGENCE_PATH) or "ไม่มีข้อมูล"
    snap        = read_cme_snapshot()
    brief_json  = read_morning_brief_json()

    # Symbol state from morning brief JSON
    if brief_json:
        state_rows = ""
        for sym, info in brief_json.items():
            bias = info.get("bias","—")
            if "BULL" in bias:   bc, icon = "badge-bullish", "🟢"
            elif "BEAR" in bias: bc, icon = "badge-bearish", "🔴"
            else:                bc, icon = "badge-neutral",  "⚪"
            state_rows += f"""<tr>
  <td><strong>{sym}</strong></td>
  <td><span class="badge {bc}">{icon} {bias}</span></td>
  <td class="text-muted small">{info.get('wait_for','-')[:80]}</td>
  <td>{info.get('entry_zone_btm','-')} – {info.get('entry_zone_top','-')}</td>
  <td class="text-danger small">{info.get('sl_level','-')}</td>
  <td class="text-success small">{info.get('tp_level','-')}</td>
</tr>"""
        state_html = f"""
<div class="card mb-3">
  <div class="card-header"><i class="bi bi-table text-info"></i> Symbol States (from Morning Brief)</div>
  <div class="table-responsive">
    <table class="table table-dark table-sm table-hover mb-0">
      <thead><tr><th>Symbol</th><th>Bias</th><th>Waiting For</th><th>Entry Zone</th><th>SL</th><th>TP</th></tr></thead>
      <tbody>{state_rows}</tbody>
    </table>
  </div>
</div>"""
    else:
        state_html = ""

    # CME snapshot details
    snap_time = snap.get("last_updated","—")
    if snap_time and snap_time != "—":
        try:
            snap_time = datetime.fromisoformat(snap_time).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    pc = snap.get("pc_ratio", "—")
    pc_cls = "loss" if isinstance(pc, float) and pc > 1.3 else ("profit" if isinstance(pc, float) and pc < 0.7 else "neutral")

    snap_html = f"""
<div class="card mb-3">
  <div class="card-header"><i class="bi bi-activity text-warning"></i> CME Live Snapshot — {snap_time}</div>
  <div class="card-body">
    <div class="row g-3">
      <div class="col-sm-2"><div class="text-muted small">PC Ratio</div><div class="fs-5 fw-bold {pc_cls}">{pc}</div></div>
      <div class="col-sm-2"><div class="text-muted small">Put Vol</div><div class="fs-5">{snap.get('put_volume','—')}</div></div>
      <div class="col-sm-2"><div class="text-muted small">Call Vol</div><div class="fs-5">{snap.get('call_volume','—')}</div></div>
      <div class="col-sm-2"><div class="text-muted small">Volatility</div><div class="fs-5">{snap.get('volatility','—')}%</div></div>
      <div class="col-sm-2"><div class="text-muted small">Put Wall</div><div class="fs-5 profit">{snap.get('put_wall','—')}</div></div>
      <div class="col-sm-2"><div class="text-muted small">Call Wall</div><div class="fs-5 loss">{snap.get('call_wall','—')}</div></div>
    </div>
  </div>
</div>"""

    body = f"""
<h4 class="mb-3"><i class="bi bi-display text-warning"></i> Live Monitor</h4>
{state_html}
{snap_html}
<div class="row g-3">
  <div class="col-lg-6">
    <div class="card h-100">
      <div class="card-header"><i class="bi bi-sunrise text-warning"></i> Morning Brief</div>
      <div class="card-body p-0">
        <pre class="m-0 rounded-0" style="border:none">{brief_md}</pre>
      </div>
    </div>
  </div>
  <div class="col-lg-6">
    <div class="card h-100">
      <div class="card-header"><i class="bi bi-newspaper text-info"></i> Hermes Intelligence</div>
      <div class="card-body p-0">
        <pre class="m-0 rounded-0" style="border:none">{intelligence}</pre>
      </div>
    </div>
  </div>
</div>"""

    return base_page("Monitor", body)


# ─────────────────────────────────────────────
# Route: Journal /journal
# ─────────────────────────────────────────────

@app.route("/journal")
def journal():
    data = get_all_journal_data()
    wr   = data["win_rate"]
    pnl  = data["total_pnl"]
    pnl_cls = "profit" if pnl >= 0 else "loss"
    wr_cls  = "profit" if wr >= 45 else ("neutral" if wr >= 35 else "loss")

    # Summary cards
    summary_html = f"""
<div class="row g-3 mb-3">
  <div class="col-md-3"><div class="card stat-card p-3">
    <div class="text-muted small">Total Trades</div>
    <div class="stat-val">{len(data['trades'])}</div>
  </div></div>
  <div class="col-md-3"><div class="card stat-card p-3" style="border-left-color:#3fb950">
    <div class="text-muted small">Win Rate</div>
    <div class="stat-val {wr_cls}">{wr}%</div>
    <div class="text-muted small">Target: ≥45%</div>
  </div></div>
  <div class="col-md-3"><div class="card stat-card p-3" style="border-left-color:{'#3fb950' if pnl>=0 else '#f85149'}">
    <div class="text-muted small">Total P&L</div>
    <div class="stat-val {pnl_cls}">${pnl:+,.2f}</div>
  </div></div>
  <div class="col-md-3"><div class="card stat-card p-3" style="border-left-color:#f0883e">
    <div class="text-muted small">Trading Days</div>
    <div class="stat-val">{len(data['daily_pnl'])}</div>
  </div></div>
</div>"""

    # Symbol breakdown
    sym_rows = ""
    for sym, s in sorted(data["symbol_stats"].items(), key=lambda x: -x[1]["trades"]):
        wr2 = round(s["wins"]/s["trades"]*100, 1) if s["trades"] else 0
        pc2 = "profit" if s["pnl"] >= 0 else "loss"
        sym_rows += f"""<tr>
  <td><strong>{sym}</strong></td>
  <td>{s['trades']}</td>
  <td>{s['wins']}</td>
  <td class="{'profit' if wr2>=45 else 'loss'}">{wr2}%</td>
  <td class="{pc2}">${s['pnl']:+,.2f}</td>
</tr>"""

    sym_html = f"""
<div class="card mb-3">
  <div class="card-header"><i class="bi bi-pie-chart text-info"></i> Per-Symbol Breakdown</div>
  <div class="table-responsive">
    <table class="table table-dark table-sm table-hover mb-0">
      <thead><tr><th>Symbol</th><th>Trades</th><th>Wins</th><th>Win Rate</th><th>P&L</th></tr></thead>
      <tbody>{sym_rows if sym_rows else '<tr><td colspan="5" class="text-muted text-center">No completed trades yet</td></tr>'}</tbody>
    </table>
  </div>
</div>"""

    # Daily P&L
    daily_rows = ""
    for day in sorted(data["daily_pnl"].keys(), reverse=True):
        val = data["daily_pnl"][day]
        dc  = "profit" if val >= 0 else "loss"
        daily_rows += f"<tr><td>{day}</td><td class='{dc} fw-bold'>${val:+,.2f}</td></tr>"

    daily_html = f"""
<div class="card mb-3">
  <div class="card-header"><i class="bi bi-calendar-check text-warning"></i> Daily P&L</div>
  <div class="table-responsive">
    <table class="table table-dark table-sm mb-0" style="max-width:400px">
      <thead><tr><th>Date</th><th>P&L</th></tr></thead>
      <tbody>{daily_rows if daily_rows else '<tr><td colspan="2" class="text-muted text-center">No P&L data</td></tr>'}</tbody>
    </table>
  </div>
</div>"""

    # Recent entries (last 30)
    recent = list(reversed(data["entries"]))[:30]
    entry_rows = ""
    for e in recent:
        ac = e.get("action","—")
        if ac == "BUY":    aclass = "text-success fw-bold"
        elif ac == "SELL": aclass = "text-danger fw-bold"
        else:              aclass = "text-muted"
        score = e.get("score","—")
        entry_rows += f"""<tr>
  <td class="text-muted">{e.get('date','')} {e.get('time','')}</td>
  <td><strong>{e.get('symbol','—')}</strong></td>
  <td class="{aclass}">{ac}</td>
  <td>{e.get('bias','—')}</td>
  <td>{score}</td>
  <td class="text-muted small" style="max-width:300px">{e.get('summary',e.get('reason',''))[:80]}</td>
</tr>"""

    entries_html = f"""
<div class="card">
  <div class="card-header"><i class="bi bi-journal-text"></i> Recent Journal Entries (last 30)</div>
  <div class="table-responsive">
    <table class="table table-dark table-sm table-hover mb-0">
      <thead><tr><th>Time</th><th>Symbol</th><th>Action</th><th>Bias</th><th>Score</th><th>Summary</th></tr></thead>
      <tbody>{entry_rows if entry_rows else '<tr><td colspan="6" class="text-muted text-center">No entries</td></tr>'}</tbody>
    </table>
  </div>
</div>"""

    body = f"""
<h4 class="mb-3"><i class="bi bi-journal-text text-warning"></i> Trade Journal</h4>
{summary_html}
<div class="row g-3">
  <div class="col-lg-8">{entries_html}</div>
  <div class="col-lg-4">{sym_html}{daily_html}</div>
</div>"""

    return base_page("Journal", body)


# ─────────────────────────────────────────────
# Route: CME Dashboard /cme
# ─────────────────────────────────────────────

@app.route("/cme")
def cme_dashboard():
    cme  = parse_cme_daily()
    snap = read_cme_snapshot()
    raw  = read_file(CME_DAILY_PATH) or "ไม่มีข้อมูล CME"

    pw   = cme.get("put_wall_f",  {})
    cw   = cme.get("call_wall_f", {})
    mp   = cme.get("max_pain_f",  {})
    pc   = snap.get("pc_ratio", "—")

    # PC Ratio interpretation
    if isinstance(pc, (int, float)):
        if pc < 0.7:    pc_label, pc_cls = "Bullish (Call Heavy)", "profit"
        elif pc > 2.0:  pc_label, pc_cls = "Extreme Put — Contrarian Bullish", "profit"
        elif pc > 1.3:  pc_label, pc_cls = "Bearish / Fear (Put Heavy)", "loss"
        else:           pc_label, pc_cls = "Neutral", "neutral"
    else:
        pc_label, pc_cls = "—", "neutral"

    # COT interpretation
    net_str = cme.get("cot_net","0").replace(",","")
    try:
        net_val = int(net_str)
        cot_cls = "profit" if net_val > 0 else "loss"
        cot_label = "MM Net Long (Bullish)" if net_val > 0 else "MM Net Short (Bearish)"
    except Exception:
        cot_cls, cot_label = "neutral", "—"

    # Spot price from snapshot vs walls
    spot = snap.get("future_price", 0)
    basis = 0
    try:
        basis_str = cme.get("basis","0").replace("+","")
        basis = float(basis_str)
    except Exception:
        pass
    spot_adj = round(spot - basis, 2) if spot and basis else "—"

    levels_html = f"""
<div class="row g-3 mb-3">
  <div class="col-md-4">
    <div class="card h-100" style="border-color:#3fb950">
      <div class="card-header" style="color:#3fb950"><i class="bi bi-shield-fill-check"></i> Put Wall — Institutional Support</div>
      <div class="card-body text-center">
        <div class="display-5 profit fw-bold">{pw.get('spot','—')}</div>
        <div class="text-muted mt-2">Futures: {pw.get('futures','—')}</div>
        <div class="text-muted">OI: {pw.get('oi','—')} contracts</div>
        <hr>
        <small class="text-muted">Gold above Put Wall + Bullish Bias = Strong Support</small>
      </div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card h-100" style="border-color:#79c0ff">
      <div class="card-header" style="color:#79c0ff"><i class="bi bi-bullseye"></i> Max Pain</div>
      <div class="card-body text-center">
        <div class="display-5 fw-bold" style="color:#79c0ff">{mp.get('spot','—')}</div>
        <div class="text-muted mt-2">Futures: {mp.get('futures','—')}</div>
        <div class="text-muted">DTE: {cme.get('dte','—')}</div>
        <hr>
        <small class="text-muted">Market makers pull price toward Max Pain before expiry</small>
      </div>
    </div>
  </div>
  <div class="col-md-4">
    <div class="card h-100" style="border-color:#f85149">
      <div class="card-header" style="color:#f85149"><i class="bi bi-shield-fill-x"></i> Call Wall — Institutional Resistance</div>
      <div class="card-body text-center">
        <div class="display-5 loss fw-bold">{cw.get('spot','—')}</div>
        <div class="text-muted mt-2">Futures: {cw.get('futures','—')}</div>
        <div class="text-muted">OI: {cw.get('oi','—')} contracts</div>
        <hr>
        <small class="text-muted">Price approaching Call Wall without OB = expect rejection</small>
      </div>
    </div>
  </div>
</div>"""

    metrics_html = f"""
<div class="row g-3 mb-3">
  <div class="col-md-3"><div class="card p-3">
    <div class="text-muted small">PC Ratio</div>
    <div class="fs-3 fw-bold {pc_cls}">{pc}</div>
    <div class="text-muted small">{pc_label}</div>
  </div></div>
  <div class="col-md-3"><div class="card p-3">
    <div class="text-muted small">Volatility (IV)</div>
    <div class="fs-3 fw-bold">{snap.get('volatility','—')}%</div>
    <div class="text-muted small">Implied Volatility</div>
  </div></div>
  <div class="col-md-3"><div class="card p-3">
    <div class="text-muted small">COT Managed Money</div>
    <div class="fs-3 fw-bold {cot_cls}">{cme.get('cot_net','—')}</div>
    <div class="text-muted small">{cot_label}</div>
  </div></div>
  <div class="col-md-3"><div class="card p-3">
    <div class="text-muted small">Basis (GC − Spot)</div>
    <div class="fs-3 fw-bold">+{basis}</div>
    <div class="text-muted small">GC: {snap.get('future_price','—')} · Spot adj: {spot_adj}</div>
  </div></div>
</div>"""

    vol_html = f"""
<div class="card mb-3">
  <div class="card-header"><i class="bi bi-bar-chart text-info"></i> Vol2Vol — Options Activity</div>
  <div class="card-body">
    <div class="row g-3">
      <div class="col-sm-4">
        <div class="text-muted small">Put Volume</div>
        <div class="fs-4 loss">{snap.get('put_volume','—')}</div>
      </div>
      <div class="col-sm-4">
        <div class="text-muted small">Call Volume</div>
        <div class="fs-4 profit">{snap.get('call_volume','—')}</div>
      </div>
      <div class="col-sm-4">
        <div class="text-muted small">Snapshot Updated</div>
        <div class="fs-6 text-muted">{snap.get('last_updated','—')}</div>
      </div>
    </div>
  </div>
</div>"""

    raw_html = f"""
<div class="card">
  <div class="card-header"><i class="bi bi-file-text text-muted"></i> CME_Daily.md Raw — {cme.get('updated','')}</div>
  <div class="card-body p-0">
    <pre class="m-0 rounded-0" style="border:none">{raw}</pre>
  </div>
</div>"""

    body = f"""
<h4 class="mb-3"><i class="bi bi-bar-chart-fill text-warning"></i> CME Gold Dashboard</h4>
{levels_html}
{metrics_html}
{vol_html}
{raw_html}"""

    return base_page("CME", body)


# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🌐 Midas Dashboard: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
