#!/usr/bin/env python3
"""Render paper-trade dashboard (index.html) from portfolio.json.

Usage:  python3 build.py
Reads ./portfolio.json, writes ./index.html . Pure stdlib, no network.
"""
import json, os, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "portfolio.json")
OUT = os.path.join(BASE, "index.html")

d = json.load(open(SRC, encoding="utf-8"))
pos = d["positions"]
live = d.get("status") == "open"

start = float(d["start_cash"])
cash = float(d.get("cash") or 0)

for p in pos:
    e, l, s = p.get("entry"), p.get("last"), float(p.get("shares") or 0)
    p["_cost"] = (e or 0) * s
    p["_mv"] = (l if l is not None else e or 0) * s
    p["_pl"] = p["_mv"] - p["_cost"]
    p["_plpct"] = (p["_pl"] / p["_cost"] * 100) if p["_cost"] else 0.0
    pc = p.get("prev_close")
    p["_day"] = ((l - pc) / pc * 100) if (l is not None and pc) else None

mv = sum(p["_mv"] for p in pos)
total = mv + cash
pl = total - start
plpct = pl / start * 100 if start else 0.0
for p in pos:
    p["_w"] = (p["_mv"] / total * 100) if total else 0.0

hist = d.get("history", [])
winners = sorted([p for p in pos if p["_cost"]], key=lambda x: -x["_plpct"])

# --- benchmark ---------------------------------------------------------------
bm = d.get("benchmark") or {}
bm_live = bool(bm.get("entry") and bm.get("last"))
bm_total = (bm["last"] * bm["shares"]) if bm_live else None
bm_pl = (bm_total - start) if bm_live else None
bm_plpct = (bm_pl / start * 100) if bm_live else None
alpha = (plpct - bm_plpct) if bm_live else None
bm_day = None
if bm_live and bm.get("prev_close"):
    bm_day = (bm["last"] - bm["prev_close"]) / bm["prev_close"] * 100

# Portfolio's own one-day move: value now vs value at yesterday's closes.
port_day = None
if live and all(p.get("prev_close") for p in pos):
    prev_total = sum(p["prev_close"] * float(p["shares"] or 0) for p in pos) + cash
    if prev_total:
        port_day = (total - prev_total) / prev_total * 100

PAL = ["#4f8ff7", "#f7a34f", "#5ecb9e", "#e26d8a", "#a98bf0",
       "#4fc7d8", "#f2d05a", "#8fb84f", "#ef7b5c", "#9aa4b2"]


def money(v, dp=2):
    return f"${v:,.{dp}f}"


def signed(v, dp=2, pct=False):
    s = "+" if v >= 0 else "−"
    return f"{s}{abs(v):,.{dp}f}{'%' if pct else ''}"


def cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "flat")


rows = []
for i, p in enumerate(pos):
    if live:
        day = ("<span class='%s'>%s</span>" % (cls(p["_day"]), signed(p["_day"], 2, True))
               ) if p["_day"] is not None else "<span class='flat'>&mdash;</span>"
        rows.append(f"""<tr>
  <td><span class="dot" style="background:{PAL[i%len(PAL)]}"></span><b>{p['ticker']}</b><div class="sub">{p['name']}</div></td>
  <td class="sec">{p['sector']}<div class="sub drv">{p['driver']}</div></td>
  <td class="n">{p['target']*100:.0f}%<div class="sub">now {p['_w']:.1f}%</div></td>
  <td class="n">{p['shares']:.4f}</td>
  <td class="n">{money(p['entry'])}</td>
  <td class="n">{money(p['last']) if p['last'] is not None else '&mdash;'}<div class="sub">{day}</div></td>
  <td class="n">{money(p['_mv'])}</td>
  <td class="n {cls(p['_pl'])}">{signed(p['_pl'])}<div class="sub {cls(p['_pl'])}">{signed(p['_plpct'],2,True)}</div></td>
</tr>""")
    else:
        rows.append(f"""<tr>
  <td><span class="dot" style="background:{PAL[i%len(PAL)]}"></span><b>{p['ticker']}</b><div class="sub">{p['name']}</div></td>
  <td class="sec">{p['sector']}<div class="sub drv">{p['driver']}</div></td>
  <td class="n">{p['target']*100:.0f}%</td>
  <td class="n pend">pending</td>
  <td class="n pend">pending</td>
  <td class="n pend">&mdash;</td>
  <td class="n">{money(start*p['target'])}</td>
  <td class="n pend">&mdash;</td>
</tr>""")

alloc_bar = "".join(
    f'<div class="seg" style="width:{(p["_w"] if live else p["target"]*100):.4f}%;background:{PAL[i%len(PAL)]}" title="{p["ticker"]}"></div>'
    for i, p in enumerate(pos))

if live and winners:
    best = "".join(
        f'<li><b>{p["ticker"]}</b><span class="{cls(p["_pl"])}">{signed(p["_plpct"],2,True)}</span></li>'
        for p in winners[:3])
    worst = "".join(
        f'<li><b>{p["ticker"]}</b><span class="{cls(p["_pl"])}">{signed(p["_plpct"],2,True)}</span></li>'
        for p in winners[-3:][::-1])
    movers = f'<div class="movers"><div><h3>Top 3</h3><ul>{best}</ul></div><div><h3>Bottom 3</h3><ul>{worst}</ul></div></div>'
else:
    movers = ""

logrows = "".join(
    f"<tr><td>{e.get('date','')}</td><td>{e.get('note','')}</td></tr>"
    for e in reversed(d.get("log", []))) or "<tr><td colspan='2' class='pend'>No entries yet.</td></tr>"

banner = "" if live else (
    '<div class="banner">Orders staged &mdash; not yet filled. Entry price will be the official '
    f'<b>market open on {d["entry_date"]}</b> (09:30 ET). The dashboard fills in automatically after the bell.</div>')

hist_json = json.dumps([{"d": h["date"], "v": round(h["value"], 2),
                         "b": (round(h["bench"], 2) if h.get("bench") else None)}
                        for h in hist])
has_bench_series = sum(1 for h in hist if h.get("bench")) >= 2

chart = ""
if len(hist) >= 2:
    chart = """<div class="card">
<h2>Portfolio vs S&amp;P 500</h2>
<div class="legend">
  <span><i style="background:#4f8ff7"></i>This portfolio</span>
  <span><i style="background:#f7a34f"></i>S&amp;P 500 (SPY)</span>
  <span class="note">both starting from $10,000 on the same day</span>
</div>
<canvas id="eq" height="90"></canvas></div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script>
const H = %s;
const ds = [{label:'Portfolio',data:H.map(x=>x.v),borderColor:'#4f8ff7',
  backgroundColor:'rgba(79,143,247,.13)',fill:true,tension:.25,pointRadius:2,borderWidth:2}];
if (%s) ds.push({label:'S&P 500',data:H.map(x=>x.b),borderColor:'#f7a34f',
  backgroundColor:'transparent',fill:false,tension:.25,pointRadius:2,borderWidth:2,
  borderDash:[5,4],spanGaps:true});
new Chart(document.getElementById('eq'), {type:'line',
 data:{labels:H.map(x=>x.d),datasets:ds},
 options:{plugins:{legend:{display:false},
   tooltip:{callbacks:{label:c=>c.dataset.label+': $'+c.parsed.y.toLocaleString(
     undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}}},
  interaction:{mode:'index',intersect:false},
  scales:{y:{ticks:{callback:v=>'$'+v.toLocaleString()}}},
  responsive:true,maintainAspectRatio:false}});
</script>""" % (hist_json, "true" if has_bench_series else "false")

# Head-to-head card, shown as soon as the benchmark has an entry price.
vs = ""
if live and bm_live:
    def _cell(v, dp=2, pct=False):
        return f'<span class="{cls(v)}">{signed(v, dp, pct)}</span>'
    vs = f"""<div class="card"><h2>Head to head</h2>
<table class="vs"><thead><tr><th></th><th class="n">Value</th><th class="n">P/L</th>
<th class="n">Return</th><th class="n">Today</th></tr></thead><tbody>
<tr><td><span class="dot" style="background:#4f8ff7"></span><b>This portfolio</b></td>
    <td class="n">{money(total)}</td><td class="n">{_cell(pl)}</td>
    <td class="n">{_cell(plpct,2,True)}</td>
    <td class="n">{_cell(port_day,2,True) if port_day is not None else '&mdash;'}</td></tr>
<tr><td><span class="dot" style="background:#f7a34f"></span><b>S&amp;P 500</b>
    <div class="sub">{bm.get('shares',0):.4f} SPY @ {money(bm['entry'])}</div></td>
    <td class="n">{money(bm_total)}</td><td class="n">{_cell(bm_pl)}</td>
    <td class="n">{_cell(bm_plpct,2,True)}</td>
    <td class="n">{_cell(bm_day,2,True) if bm_day is not None else '&mdash;'}</td></tr>
</tbody></table>
<div class="alpha {cls(alpha)}">{signed(alpha,2)} pts {'ahead of' if alpha >= 0 else 'behind'} the S&amp;P 500
<span class="sub">&nbsp;&middot;&nbsp; {money(abs(pl - bm_pl))} difference on $10,000</span></div>
</div>"""

updated = d.get("last_updated") or datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paper Trade &mdash; $10,000 Sector Core Portfolio</title>
<style>
:root{{--bg:#0e1116;--card:#161b23;--line:#242c38;--tx:#e6edf3;--mut:#8b98a8;
--up:#3fb950;--down:#f85149;--acc:#4f8ff7}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--tx);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;padding:28px 20px 60px}}
.wrap{{max-width:1180px;margin:0 auto}}
h1{{font-size:23px;margin:0 0 4px}}
.meta{{color:var(--mut);font-size:13px;margin-bottom:22px}}
.banner{{background:rgba(79,143,247,.1);border:1px solid rgba(79,143,247,.4);
border-radius:10px;padding:13px 16px;margin-bottom:20px;font-size:14px;color:#c8dcff}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-bottom:22px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}}
.kpi .l{{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.06em}}
.kpi .v{{font-size:26px;font-weight:650;margin-top:6px;font-variant-numeric:tabular-nums}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:18px 20px;margin-bottom:20px}}
.card h2{{font-size:14px;text-transform:uppercase;letter-spacing:.07em;
color:var(--mut);margin:0 0 14px;font-weight:600}}
.bar{{display:flex;height:16px;border-radius:8px;overflow:hidden;gap:1px}}
.seg{{height:100%}}
table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}
th{{text-align:left;color:var(--mut);font-size:11px;text-transform:uppercase;
letter-spacing:.06em;font-weight:600;padding:0 12px 10px;border-bottom:1px solid var(--line)}}
th.n,td.n{{text-align:right}}
td{{padding:13px 12px;border-bottom:1px solid var(--line);vertical-align:top}}
tr:last-child td{{border-bottom:none}}
.sub{{color:var(--mut);font-size:12px;margin-top:3px;font-weight:400}}
.drv{{max-width:270px}}
.sec{{font-size:13px}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}}
.up{{color:var(--up)}} .down{{color:var(--down)}} .flat,.pend{{color:var(--mut)}}
.kpi.hl{{border-color:rgba(79,143,247,.45);background:linear-gradient(180deg,rgba(79,143,247,.09),var(--card))}}
.legend{{display:flex;flex-wrap:wrap;gap:18px;align-items:center;margin:-4px 0 14px;font-size:13px}}
.legend i{{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:7px;vertical-align:-1px}}
.legend .note{{color:var(--mut);font-size:12px}}
table.vs td{{padding:12px}}
.alpha{{margin-top:14px;padding-top:13px;border-top:1px solid var(--line);font-size:16px;font-weight:600}}
.alpha .sub{{display:inline;font-weight:400}}
.movers{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}
.movers h3{{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin:0 0 8px}}
.movers ul{{list-style:none;margin:0;padding:0}}
.movers li{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line)}}
.foot{{color:var(--mut);font-size:12px;line-height:1.7;margin-top:26px;
border-top:1px solid var(--line);padding-top:16px}}
canvas{{max-height:220px}}
@media(max-width:760px){{.drv{{display:none}}.movers{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">

<h1>Paper Trade &mdash; $10,000 Sector Core Portfolio</h1>
<div class="meta">Entry basis: {d['price_basis']} &nbsp;&middot;&nbsp; Prices as of {d.get('last_price_date') or '&mdash;'} &nbsp;&middot;&nbsp; Built {updated}</div>

{banner}

<div class="kpis">
  <div class="kpi"><div class="l">Total value</div><div class="v">{money(total)}</div></div>
  <div class="kpi"><div class="l">Total P/L</div><div class="v {cls(pl)}">{signed(pl)}</div></div>
  <div class="kpi"><div class="l">Return</div><div class="v {cls(pl)}">{signed(plpct,2,True)}</div></div>
  <div class="kpi{' hl' if bm_live else ''}"><div class="l">vs S&amp;P 500</div>
    <div class="v {cls(alpha) if bm_live else 'flat'}">{signed(alpha,2) + ' pts' if bm_live else '&mdash;'}</div>
    <div class="sub">{('S&amp;P ' + signed(bm_plpct,2,True)) if bm_live else 'benchmark pending'}</div></div>
</div>

<div class="card"><h2>Allocation</h2><div class="bar">{alloc_bar}</div></div>

<div class="card"><h2>Holdings</h2>
<table><thead><tr>
<th>Ticker</th><th>Sector / driver</th><th class="n">Target</th><th class="n">Shares</th>
<th class="n">Entry</th><th class="n">Last</th><th class="n">Value</th><th class="n">P/L</th>
</tr></thead><tbody>
{''.join(rows)}
</tbody></table></div>

{vs}

{chart}

{('<div class="card"><h2>Movers</h2>' + movers + '</div>') if movers else ''}

<div class="card"><h2>Activity log</h2>
<table><thead><tr><th style="width:130px">Date</th><th>Event</th></tr></thead>
<tbody>{logrows}</tbody></table></div>

<div class="foot">
Simulated portfolio only &mdash; no real money, no broker, no orders placed. Fractional shares assumed,
zero commission, dividends not reinvested. Prices are sourced from public delayed quotes and may differ
from any real fill. This is not investment advice; do your own research before trading.
</div>
</div></body></html>
"""

open(OUT, "w", encoding="utf-8").write(html)
print(f"wrote {OUT}  total={total:,.2f}  pl={pl:+,.2f} ({plpct:+.2f}%)  status={d['status']}")
