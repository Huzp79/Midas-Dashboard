import sys
import io
import os
import re
import time
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from playwright.sync_api import sync_playwright

# ─── URLs ────────────────────────────────────────────────────────────────────
CME_VOL2VOL_URL = "https://www.cmegroup.com/tools-information/quikstrike/vol2vol-expected-range.html"
CME_HEATMAP_URL = "https://www.cmegroup.com/tools-information/quikstrike/open-interest-heatmap.html"
CME_COT_URL     = "https://www.cmegroup.com/tools-information/quikstrike/commitment-of-traders.html"

# ─── Element IDs ─────────────────────────────────────────────────────────────
CHART_ID        = "MainContent_ucViewControl_IntegratedV2VExpectedRange_ucChart_divChart"
OI_MATRIX_TAB   = "MainContent_ucViewControl_IntegratedVOIHeatMap_lbOIMatrix"
OI_STRIKES_DD   = "MainContent_ucViewControl_IntegratedVOIHeatMap_ucMatrixTB_ddlStrikes"
COT_PREFIX      = "ctl00_MainContent_ucViewControl_IntegratedCOTSheet"
COT_TABLE_ID    = "ctl00_MainContent_ucViewControl_IntegratedCOTSheet_ucSummaryTable_tblCOT"

WEEKLY_GROUPS   = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays"]
MIDAS_BRAIN_DIR = os.path.join(os.path.dirname(__file__), "Midas_Brain", "data", "market")

# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_frame(page):
    """Return QuikStrike iframe content_frame for any CME QuikStrike page."""
    iframe_el = page.query_selector('[id^="cmeIframe"]') \
             or page.query_selector('iframe[src*="quikstrike"]')
    if not iframe_el:
        raise RuntimeError("QuikStrike iframe not found")
    frame = iframe_el.content_frame()
    if not frame:
        raise RuntimeError("Could not access QuikStrike iframe content")
    return frame


def _close_popup(frame, popup_id):
    frame.evaluate(
        f'() => {{ const p = document.querySelector("#{popup_id}"); if (p) p.style.display = "none"; }}'
    )
    time.sleep(0.2)


def _select_gold(frame):
    """Navigate product selector: arrow → Metals → Precious Metals → Gold."""
    _close_popup(frame, "ctl11_ucProductSelectorPopup_pnlProductSelectorPopup")
    _close_popup(frame, "ctl11_ucProductOnlyPopup_pnlProductSelectorPopup")

    frame.click("#ctl11_hlProductArrow", force=True)
    time.sleep(0.5)
    if frame.evaluate(
        '() => window.getComputedStyle(document.querySelector'
        '("#ctl11_ucProductSelectorPopup_pnlProductSelectorPopup")).display'
    ) == "none":
        frame.click("#ctl11_hlProductArrow", force=True)
        time.sleep(0.5)

    frame.evaluate("""
        () => {
            const m = document.querySelector(".groups a[groupid='6']");
            if (m) { m.dispatchEvent(new MouseEvent("mouseover",{bubbles:true})); m.click(); }
        }
    """)
    time.sleep(0.5)
    frame.evaluate("""
        () => { const el = document.querySelector(".families a[familyid='6']"); if(el) el.click(); }
    """)
    time.sleep(0.5)

    name = frame.evaluate("""
        () => {
            for (const p of document.querySelectorAll(".products a"))
                if (p.innerText.includes("Gold")) { p.click(); return p.innerText.trim(); }
            return null;
        }
    """)
    if not name:
        raise RuntimeError("Gold (OG|GC) not found in product selector")
    print(f"  [Product] {name}")
    time.sleep(5)
    return name


def _select_nearest_weekly(frame):
    """Open expiry selector, pick the nearest weekly. Returns expiry info dict."""
    _close_popup(frame, "ctl00_ucSelector_pnlExpirations")
    frame.click("#ctl00_ucSelector_hlExpiration", force=True)
    time.sleep(0.5)

    exps = frame.evaluate("""
        (wg) => {
            const tbl = document.querySelector("#ctl00_ucSelector_pnlExpirations .grid.eselect");
            if (!tbl) return [];
            const ths = Array.from(tbl.querySelectorAll("th"));
            const tds = Array.from(tbl.querySelectorAll("tbody tr:nth-child(2) td"));
            const out = [];
            ths.forEach((th, i) => {
                if (!wg.includes(th.innerText.trim())) return;
                (tds[i]?.querySelectorAll("a") || []).forEach(a => {
                    const m = (a.getAttribute("title")||"").match(/([\d.]+) DTE/);
                    out.push({
                        id:      a.id,
                        symbol:  a.querySelector(".bold")?.innerText.trim() || "",
                        expDate: a.querySelectorAll("div")[1]?.innerText.trim() || "",
                        dte:     m ? parseFloat(m[1]) : 9999,
                        group:   th.innerText.trim()
                    });
                });
            });
            return out;
        }
    """, WEEKLY_GROUPS)

    if not exps:
        raise RuntimeError("No weekly expirations found")

    pos = sorted([e for e in exps if e["dte"] > 0], key=lambda x: x["dte"])
    nearest = (pos or sorted(exps, key=lambda x: -x["dte"]))[0]
    print(f"  [Expiry]  {nearest['symbol']} ({nearest['expDate']}, DTE={nearest['dte']})")

    frame.evaluate(f"""
        () => {{ const l = document.getElementById("{nearest['id']}"); if (l) l.click(); }}
    """)
    time.sleep(5)
    return nearest


def _calc_max_pain(rows):
    """Strike that minimises total ITM options value (standard Max Pain formula)."""
    best_k, best_pain = None, float("inf")
    for k_row in rows:
        k = k_row["strike"]
        p = sum((k - r["strike"]) * r["call_oi"] for r in rows if r["strike"] < k)
        p += sum((r["strike"] - k) * r["put_oi"]  for r in rows if r["strike"] > k)
        if p < best_pain:
            best_pain, best_k = p, k
    return best_k


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE EXTRACTORS  (accept browser context, return dicts)
# ═══════════════════════════════════════════════════════════════════════════════

def _run_vol2vol(ctx):
    """Extract Vol2Vol data. Returns dict."""
    page = next((pg for pg in ctx.pages if "vol2vol" in pg.url.lower()), None)
    if not page:
        page = ctx.new_page()
        page.goto(CME_VOL2VOL_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

    print(f"\n[Vol2Vol] {page.url}")
    frame = _get_frame(page)
    frame.wait_for_load_state("domcontentloaded", timeout=15000)
    time.sleep(2)

    _select_gold(frame)
    nearest = _select_nearest_weekly(frame)
    print("  [Wait]    3s for chart data...")
    time.sleep(3)

    text = frame.inner_text(f"#{CHART_ID}")
    m_vol = re.search(r"Put:\s*([\d,]+)\s+Call:\s*([\d,]+)\s+Vol:\s*([\d.]+)", text)
    m_fut = re.search(r"Future:\s*([\d,]+(?:\.\d+)?)", text)

    return {
        "put_volume":   int(m_vol.group(1).replace(",","")) if m_vol else None,
        "call_volume":  int(m_vol.group(2).replace(",","")) if m_vol else None,
        "volatility":   float(m_vol.group(3))              if m_vol else None,
        "future_price": float(m_fut.group(1).replace(",","")) if m_fut else None,
        "expiry_symbol": nearest["symbol"],
        "expiry_date":   nearest["expDate"],
        "expiry_dte":    nearest["dte"],
    }


def _run_oi_heatmap(ctx):
    """Extract OI heatmap data. Returns dict."""
    page = next((pg for pg in ctx.pages if "heatmap" in pg.url.lower()), None)
    if not page:
        page = ctx.new_page()
        page.goto(CME_HEATMAP_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(6)

    print(f"\n[OI Heatmap] {page.url}")
    frame = _get_frame(page)
    frame.wait_for_load_state("domcontentloaded", timeout=15000)
    time.sleep(2)

    _select_gold(frame)
    nearest = _select_nearest_weekly(frame)

    print("  [Tab]     Switching to OI Matrix...")
    frame.evaluate(f'() => {{ const b=document.getElementById("{OI_MATRIX_TAB}"); if(b) b.click(); }}')
    time.sleep(3)

    print("  [Strikes] Setting to All...")
    frame.evaluate(f"""
        () => {{
            const s = document.getElementById("{OI_STRIKES_DD}");
            if (!s) return;
            for (const o of s.options)
                if (o.text.includes("All")) {{ s.value=o.value; s.dispatchEvent(new Event("change",{{bubbles:true}})); return; }}
        }}
    """)
    time.sleep(4)

    raw = frame.evaluate("""
        () => {
            const tbl = document.querySelector(".grid-thm.grid-thm-v2");
            if (!tbl) return {latestDate:"?", rows:[]};
            const d = Array.from(tbl.querySelectorAll("thead tr:nth-child(2) th span"))
                          .map(s=>s.innerText.trim()).find(t=>t) || "?";
            const rows = [];
            for (const tr of tbl.querySelectorAll("tbody tr")) {
                const cells = Array.from(tr.querySelectorAll("td"));
                if (cells.length < 3) continue;
                const s = cells[0].innerText.trim().replace(/,/g,"");
                if (!s || isNaN(parseFloat(s))) continue;
                const c = parseInt(cells[1].getAttribute("title")||"0") || 0;
                const p = parseInt(cells[2].getAttribute("title")||"0") || 0;
                if (c||p) rows.push({strike:parseFloat(s), callOI:c, putOI:p});
            }
            return {latestDate:d, rows};
        }
    """)

    rows      = raw["rows"]
    if not rows:
        raise RuntimeError("No OI data found")

    put_wall  = max(rows, key=lambda r: r["putOI"])
    call_wall = max(rows, key=lambda r: r["callOI"])
    pain_in   = [{"strike":r["strike"],"call_oi":r["callOI"],"put_oi":r["putOI"]} for r in rows]
    max_pain  = _calc_max_pain(pain_in)

    print(f"  [OI]      {len(rows)} strikes parsed (date: {raw['latestDate']})")
    return {
        "put_wall":      put_wall["strike"],
        "put_wall_oi":   put_wall["putOI"],
        "call_wall":     call_wall["strike"],
        "call_wall_oi":  call_wall["callOI"],
        "max_pain":      max_pain,
        "data_date":     raw["latestDate"],
        "expiry_symbol": nearest["symbol"],
        "expiry_date":   nearest["expDate"],
        "expiry_dte":    nearest["dte"],
        "rows":          rows,
    }


def _run_cot(ctx):
    """Extract COT Managed Money data for Gold. Returns dict."""
    page = next((pg for pg in ctx.pages if "commitment" in pg.url.lower()), None)
    if not page:
        page = ctx.new_page()
        page.goto(CME_COT_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(6)

    print(f"\n[COT] {page.url}")
    frame = _get_frame(page)
    frame.wait_for_load_state("domcontentloaded", timeout=15000)
    time.sleep(2)

    _select_gold(frame)

    # Click "Table" sub-tab for structured COT summary
    print("  [Tab]     Switching to COT Table...")
    frame.evaluate(f'() => {{ const b=document.getElementById("{COT_PREFIX}_lbSummaryTable"); if(b) b.click(); }}')
    time.sleep(3)

    cot = frame.evaluate(f"""
        () => {{
            const tbl = document.getElementById("{COT_TABLE_ID}");
            if (!tbl) return null;

            // Row 0 = date/OI header  Row 1 = column headers  Row 2 = LONG  Row 3 = SHORT
            const rows = Array.from(tbl.querySelectorAll("tr"));

            // Parse date + total OI from first row
            const hdrText = rows[0]?.innerText.trim() || "";
            const dateM = hdrText.match(/(\\d+\\/\\d+\\/\\d+)/);
            const oiM   = hdrText.match(/Total OI:\\s*([\\d,]+)/i);

            // Find Managed Money column index from header row
            const hdrs = Array.from(rows[1]?.querySelectorAll("th,td") || [])
                             .map(c => c.innerText.trim().toUpperCase());
            const mmIdx = hdrs.findIndex(h => h.includes("MANAGED"));
            if (mmIdx < 0) return {{error: "Managed Money column not found", hdrs}};

            // Helper: extract first number from cell text like "127,242 3.2%"
            const num = cell => {{
                const m = (cell?.innerText || "").replace(/,/g,"").match(/(\\d+)/);
                return m ? parseInt(m[1]) : 0;
            }};

            // LONG row = rows[2], SHORT row = rows[3]
            const longCells  = Array.from(rows[2]?.querySelectorAll("th,td") || []);
            const shortCells = Array.from(rows[3]?.querySelectorAll("th,td") || []);

            const mmLong  = num(longCells[mmIdx]);
            const mmShort = num(shortCells[mmIdx]);

            return {{
                date:     dateM ? dateM[1] : "?",
                total_oi: oiM   ? parseInt(oiM[1].replace(/,/g,"")) : 0,
                mm_long:  mmLong,
                mm_short: mmShort,
                mm_net:   mmLong - mmShort,
            }};
        }}
    """)

    if not cot or "error" in cot:
        raise RuntimeError(f"COT parse failed: {cot}")

    print(f"  [COT]     As of {cot['date']} | MM Long={cot['mm_long']:,}  Short={cot['mm_short']:,}  Net={cot['mm_net']:,}")
    return cot


# ═══════════════════════════════════════════════════════════════════════════════
#  MT5 SPOT PRICE
# ═══════════════════════════════════════════════════════════════════════════════

def _get_gold_spot_mt5():
    """Return mid-price of GOLD (XAUUSD) from MT5, or None if unavailable."""
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            print(f"  [MT5]     Connect failed: {mt5.last_error()}")
            return None
        for sym in ("GOLD", "XAUUSD"):
            tick = mt5.symbol_info_tick(sym)
            if tick and tick.bid > 0:
                mid = round((tick.bid + tick.ask) / 2, 2)
                mt5.shutdown()
                print(f"  [MT5]     {sym} spot = {mid}")
                return mid
        mt5.shutdown()
        print("  [MT5]     No GOLD/XAUUSD tick found")
        return None
    except ImportError:
        print("  [MT5]     MetaTrader5 package not installed")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  MARKDOWN WRITER
# ═══════════════════════════════════════════════════════════════════════════════

def _write_cme_daily(v2v, oi, cot, spot, basis, adj):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# CME Gold Daily Intelligence",
        f"**Updated:** {now}",
        f"",
        f"## Expiry",
        f"| Field       | Value |",
        f"|-------------|-------|",
        f"| Symbol      | {v2v['expiry_symbol']} |",
        f"| Exp Date    | {v2v['expiry_date']} |",
        f"| DTE         | {v2v['expiry_dte']} |",
        f"",
        f"## Vol2Vol — Options Activity",
        f"| Field        | Value |",
        f"|--------------|-------|",
        f"| Put Volume   | {v2v['put_volume']:,} |" if v2v['put_volume'] else "| Put Volume   | N/A |",
        f"| Call Volume  | {v2v['call_volume']:,} |" if v2v['call_volume'] else "| Call Volume  | N/A |",
        f"| Volatility   | {v2v['volatility']}% |" if v2v['volatility'] else "| Volatility   | N/A |",
        f"| GC Futures   | {v2v['future_price']} |" if v2v['future_price'] else "| GC Futures   | N/A |",
        f"",
        f"## OI Heatmap — Key Levels (Futures)",
        f"| Level      | Strike (Futures) | Strike (Spot adj) | OI |",
        f"|------------|-----------------|-------------------|----|",
        f"| Put Wall   | {oi['put_wall']:.0f} | {adj['put_wall']:.0f} | {oi['put_wall_oi']:,} |",
        f"| Call Wall  | {oi['call_wall']:.0f} | {adj['call_wall']:.0f} | {oi['call_wall_oi']:,} |",
        f"| Max Pain   | {oi['max_pain']:.0f} | {adj['max_pain']:.0f} | — |",
        f"| Data Date  | {oi['data_date']} | | |",
        f"",
        f"## Basis",
        f"| Field        | Value |",
        f"|--------------|-------|",
        f"| GC Futures   | {v2v['future_price']} |" if v2v['future_price'] else "| GC Futures   | N/A |",
        f"| Gold Spot    | {spot if spot else 'N/A'} |",
        f"| Basis        | {f'{basis:+.2f}' if basis is not None else 'N/A'} |",
        f"",
        f"## COT — Managed Money (as of {cot['date']})",
        f"| Field        | Contracts |",
        f"|--------------|-----------|",
        f"| Long         | {cot['mm_long']:,} |",
        f"| Short        | {cot['mm_short']:,} |",
        f"| Net Position | {cot['mm_net']:,} |",
        f"| Total OI     | {cot['total_oi']:,} |",
        f"",
        f"---",
        f"*Source: CME QuikStrike + MT5 (GOLD spot)*",
    ]
    os.makedirs(MIDAS_BRAIN_DIR, exist_ok=True)
    path = os.path.join(MIDAS_BRAIN_DIR, "CME_Daily.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n  [File]    Written → {path}")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC STANDALONE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_vol2vol():
    with sync_playwright() as pw:
        ctx = pw.chromium.connect_over_cdp("http://localhost:9222").contexts[0]
        d = _run_vol2vol(ctx)
        print()
        print("=" * 52)
        print("  VOL2VOL  —  Gold (OG|GC)")
        print(f"  Expiry      : {d['expiry_symbol']} ({d['expiry_date']}, DTE={d['expiry_dte']})")
        print(f"  Put Volume  : {d['put_volume']:,}"  if d['put_volume']  else "  Put Volume  : N/A")
        print(f"  Call Volume : {d['call_volume']:,}" if d['call_volume'] else "  Call Volume : N/A")
        print(f"  Volatility  : {d['volatility']}%"  if d['volatility']  else "  Volatility  : N/A")
        print(f"  Futures     : {d['future_price']}"  if d['future_price'] else "  Futures     : N/A")
        print("=" * 52)


def fetch_oi_heatmap():
    with sync_playwright() as pw:
        ctx = pw.chromium.connect_over_cdp("http://localhost:9222").contexts[0]
        d = _run_oi_heatmap(ctx)
        print()
        print("=" * 62)
        print("  OI HEATMAP  —  Gold (OG|GC)")
        print(f"  Expiry      : {d['expiry_symbol']} ({d['expiry_date']}, DTE={d['expiry_dte']})")
        print(f"  Data Date   : {d['data_date']}")
        print(f"  Put Wall    : {d['put_wall']:.0f}  (OI={d['put_wall_oi']:,})")
        print(f"  Call Wall   : {d['call_wall']:.0f}  (OI={d['call_wall_oi']:,})")
        print(f"  Max Pain    : {d['max_pain']:.0f}")
        print()
        print(f"  {'Strike':>7}  {'Call OI':>8}  {'Put OI':>8}")
        print(f"  {'-------':>7}  {'--------':>8}  {'--------':>8}")
        for r in sorted(d["rows"], key=lambda x: x["strike"]):
            print(f"  {r['strike']:>7.0f}  {r['callOI']:>8,}  {r['putOI']:>8,}")
        print("=" * 62)


def fetch_cot():
    with sync_playwright() as pw:
        ctx = pw.chromium.connect_over_cdp("http://localhost:9222").contexts[0]
        d = _run_cot(ctx)
        print()
        print("=" * 52)
        print("  COT  —  Gold (OG|GC)  Managed Money")
        print(f"  As of Date  : {d['date']}")
        print(f"  Long        : {d['mm_long']:,}")
        print(f"  Short       : {d['mm_short']:,}")
        print(f"  Net Position: {d['mm_net']:,}")
        print(f"  Total OI    : {d['total_oi']:,}")
        print("=" * 52)


# ═══════════════════════════════════════════════════════════════════════════════
#  FETCH ALL
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_all():
    """Run all three scrapers, get MT5 spot, calc Basis, write CME_Daily.md."""
    print("=" * 62)
    print("  FETCH ALL  —  Gold CME Intelligence")
    print("=" * 62)

    with sync_playwright() as pw:
        ctx = pw.chromium.connect_over_cdp("http://localhost:9222").contexts[0]

        v2v = _run_vol2vol(ctx)
        oi  = _run_oi_heatmap(ctx)
        cot = _run_cot(ctx)

    # MT5 Spot (outside playwright context — no Chrome dependency)
    print("\n[MT5 Spot]")
    spot = _get_gold_spot_mt5()

    # Basis  (GC Futures − Gold Spot)
    basis = None
    if v2v["future_price"] and spot:
        basis = round(v2v["future_price"] - spot, 2)
        print(f"  [Basis]   GC {v2v['future_price']} − Spot {spot} = {basis:+.2f}")

    # Adjusted levels (Futures level − Basis → Spot-equivalent)
    def adj(level):
        return round(level - basis, 1) if basis is not None and level else level

    adjusted = {
        "put_wall":  adj(oi["put_wall"]),
        "call_wall": adj(oi["call_wall"]),
        "max_pain":  adj(oi["max_pain"]),
    }

    # Write markdown
    path = _write_cme_daily(v2v, oi, cot, spot, basis, adjusted)

    # Print combined summary
    print()
    print("=" * 62)
    print("  SUMMARY  —  Gold CME Daily")
    print("=" * 62)
    print(f"  Expiry      : {v2v['expiry_symbol']} ({v2v['expiry_date']}, DTE={v2v['expiry_dte']})")
    print()
    print("  ── Options Activity (Vol2Vol) ──────────────────────")
    print(f"  GC Futures  : {v2v['future_price']}")
    print(f"  Volatility  : {v2v['volatility']}%")
    print(f"  Put Volume  : {v2v['put_volume']:,}"  if v2v['put_volume']  else "  Put Volume  : N/A")
    print(f"  Call Volume : {v2v['call_volume']:,}" if v2v['call_volume'] else "  Call Volume : N/A")
    print()
    print("  ── Key Levels (OI Heatmap) ─────────────────────────")
    print(f"  {'Level':<12} {'Futures':>8}  {'Spot Adj':>8}  {'OI':>6}")
    print(f"  {'-'*12} {'--------':>8}  {'--------':>8}  {'------':>6}")
    print(f"  {'Put Wall':<12} {oi['put_wall']:>8.0f}  {adjusted['put_wall']:>8.0f}  {oi['put_wall_oi']:>6,}")
    print(f"  {'Call Wall':<12} {oi['call_wall']:>8.0f}  {adjusted['call_wall']:>8.0f}  {oi['call_wall_oi']:>6,}")
    print(f"  {'Max Pain':<12} {oi['max_pain']:>8.0f}  {adjusted['max_pain']:>8.0f}  {'—':>6}")
    print()
    print("  ── Basis ───────────────────────────────────────────")
    print(f"  Gold Spot   : {spot if spot else 'N/A'}")
    print(f"  Basis       : {f'{basis:+.2f}' if basis is not None else 'N/A'}")
    print()
    print("  ── COT Managed Money ───────────────────────────────")
    print(f"  As of Date  : {cot['date']}")
    print(f"  Long        : {cot['mm_long']:,}")
    print(f"  Short       : {cot['mm_short']:,}")
    print(f"  Net Position: {cot['mm_net']:,}  {'(Bullish)' if cot['mm_net']>0 else '(Bearish)'}")
    print()
    print(f"  Saved → {path}")
    print("=" * 62)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "vol2vol"
    if   cmd == "oi":      fetch_oi_heatmap()
    elif cmd == "cot":     fetch_cot()
    elif cmd == "all":     fetch_all()
    else:                  fetch_vol2vol()
