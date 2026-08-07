#!/usr/bin/env python3
"""Render the dashboards from portfolios/*.json.

Writes one page per portfolio (<slug>.html) plus an index.html overview.
Pure stdlib, no network. Usage:  python3 build.py
"""
import datetime
import glob
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_DIR = os.path.join(BASE, "portfolios")

PAL = ["#4f8ff7", "#f7a34f", "#5ecb9e", "#e26d8a", "#a98bf0", "#4fc7d8",
       "#f2d05a", "#8fb84f", "#ef7b5c", "#9aa4b2", "#6ea8fe", "#d98cc4"]


def money(v, dp=2):
    return f"${v:,.{dp}f}"


def signed(v, dp=2, pct=False):
    return f"{'+' if v >= 0 else '−'}{abs(v):,.{dp}f}{'%' if pct else ''}"


def cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "flat")


CSS = """
:root{--bg:#0e1116;--card:#161b23;--line:#242c38;--tx:#e6edf3;--mut:#8b98a8;
--up:#3fb950;--down:#f85149;--acc:#4f8ff7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,sans-serif;padding:28px 20px 60px}
.wrap{max-width:1180px;margin:0 auto}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
h1{font-size:23px;margin:0 0 4px}
.meta{color:var(--mut);font-size:13px;margin-bottom:22px}
.nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:22px}
.nav a{padding:7px 14px;border:1px solid var(--line);border-radius:99px;font-size:13px;
background:var(--card);color:var(--tx)}
.nav a:hover{border-color:var(--acc);text-decoration:none}
.nav a.on{background:var(--acc);border-color:var(--acc);color:#08111f;font-weight:600}
.banner{background:rgba(79,143,247,.1);border:1px solid rgba(79,143,247,.4);
border-radius:10px;padding:13px 16px;margin-bottom:20px;font-size:14px;color:#c8dcff}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:14px;margin-bottom:22px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.kpi .l{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.kpi .v{font-size:25px;font-weight:650;margin-top:6px;font-variant-numeric:tabular-nums}
.kpi.hl{border-color:rgba(79,143,247,.45);background:linear-gradient(180deg,rgba(79,143,247,.09),var(--card))}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:18px 20px;margin-bottom:20px}
.card h2{font-size:14px;text-transform:uppercase;letter-spacing:.07em;
color:var(--mut);margin:0 0 14px;font-weight:600}
.bar{display:flex;height:16px;border-radius:8px;overflow:hidden;gap:1px}
.seg{height:100%}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th{text-align:left;color:var(--mut);font-size:11px;text-transform:uppercase;
letter-spacing:.06em;font-weight:600;padding:0 12px 10px;border-bottom:1px solid var(--line)}
th.n,td.n{text-align:right}
td{padding:13px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
.sub{color:var(--mut);font-size:12px;margin-top:3px;font-weight:400}
.drv{max-width:260px}
.sec{font-size:13px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}
.up{color:var(--up)} .down{color:var(--down)} .flat,.pend{color:var(--mut)}
.legend{display:flex;flex-wrap:wrap;gap:18px;align-items:center;margin:-4px 0 14px;font-size:13px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:7px;vertical-align:-1px}
.legend .note{color:var(--mut);font-size:12px}
.alpha{margin-top:14px;padding-top:13px;border-top:1px solid var(--line);font-size:16px;font-weight:600}
.alpha .sub{display:inline;font-weight:400}
.mcctl{display:flex;flex-wrap:wrap;gap:22px;align-items:center;margin:-2px 0 16px;font-size:13px}
.mcctl label{display:flex;flex-direction:column;gap:5px;color:var(--mut)}
.mcctl label b{color:var(--tx)}
.mcctl input[type=range]{width:190px;accent-color:var(--acc)}
.mcctl .note{color:var(--mut);font-size:12px;max-width:340px;line-height:1.5}
.presets{display:flex;gap:7px;flex-wrap:wrap;align-self:flex-end}
.presets button{background:var(--bg);border:1px solid var(--line);color:var(--tx);
border-radius:99px;padding:6px 13px;font-size:12px;cursor:pointer;font-family:inherit}
.presets button:hover{border-color:var(--acc);color:var(--acc)}
tr.sep td{border-top:2px solid var(--line);padding-top:15px}
.mcout{margin-top:16px}
.mcout table{font-size:14px}
.mcout td,.mcout th{padding:9px 12px}
.mcnote{color:var(--mut);font-size:12px;line-height:1.65;margin-top:14px;
padding-top:13px;border-top:1px solid var(--line)}
.movers{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.movers h3{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin:0 0 8px}
.movers ul{list-style:none;margin:0;padding:0}
.movers li{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--line)}
.pcard{display:block;background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:20px 22px;margin-bottom:14px;color:var(--tx)}
.pcard:hover{border-color:var(--acc);text-decoration:none}
.pcard .top{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap}
.pcard .nm{font-size:18px;font-weight:650}
.pcard .val{font-size:22px;font-weight:650;font-variant-numeric:tabular-nums}
.pcard .row{display:flex;gap:26px;flex-wrap:wrap;margin-top:12px;font-size:13px;color:var(--mut)}
.pcard .row b{color:var(--tx);font-weight:600;font-variant-numeric:tabular-nums}
.foot{color:var(--mut);font-size:12px;line-height:1.7;margin-top:26px;
border-top:1px solid var(--line);padding-top:16px}
canvas{max-height:220px}
@media(max-width:760px){.drv{display:none}.movers{grid-template-columns:1fr}}
"""

FOOT = """<div class="foot">
Simulated portfolios only &mdash; no real money, no broker, no orders placed. Fractional shares
assumed, zero commission, no rebalancing, dividends not reinvested. Prices come from public
end-of-day sources and may differ from any real fill. Not investment advice.
</div>"""


def page(title, body, extra_head=""):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{CSS}</style>{extra_head}</head><body><div class="wrap">
{body}
{FOOT}
</div></body></html>
"""


def nav(portfolios, current):
    items = ['<a href="index.html"%s>Overview</a>' % ("" if current else ' class="on"')]
    for p in portfolios:
        on = ' class="on"' if current == p["slug"] else ""
        items.append(f'<a href="{p["slug"]}.html"{on}>{p["name"]}</a>')
    return '<div class="nav">' + "".join(items) + "</div>"


def compute(d):
    """Derive every number a page needs, and attach per-position figures."""
    pos = d["positions"]
    live = d.get("status") == "open"
    start = float(d["start_cash"])
    cash = float(d.get("cash") or 0)

    for p in pos:
        e, l, s = p.get("entry"), p.get("last"), float(p.get("shares") or 0)
        p["_cost"] = (e or 0) * s
        p["_mv"] = (l if l is not None else (e or 0)) * s
        p["_pl"] = p["_mv"] - p["_cost"]
        p["_plpct"] = (p["_pl"] / p["_cost"] * 100) if p["_cost"] else 0.0
        pc = p.get("prev_close")
        p["_day"] = ((l - pc) / pc * 100) if (l is not None and pc) else None

    mv = sum(p["_mv"] for p in pos)
    total = mv + cash
    for p in pos:
        p["_w"] = (p["_mv"] / total * 100) if total else 0.0

    pl = total - start
    plpct = pl / start * 100 if start else 0.0

    bm = d.get("benchmark") or {}
    bm_live = bool(bm.get("entry") and bm.get("last"))
    bm_total = (bm["last"] * bm["shares"]) if bm_live else None

    base = float(d["track_base"]) if d.get("track_base") else None
    since_ret = (total / base - 1) * 100 if base else None
    bm_ret = (bm_total / base - 1) * 100 if (bm_live and base) else None
    alpha = (since_ret - bm_ret) if (since_ret is not None and bm_ret is not None) else None

    port_day = None
    if live and all(p.get("prev_close") for p in pos):
        prev = sum(p["prev_close"] * float(p["shares"] or 0) for p in pos) + cash
        if prev:
            port_day = (total - prev) / prev * 100
    bm_day = None
    if bm_live and bm.get("prev_close"):
        bm_day = (bm["last"] - bm["prev_close"]) / bm["prev_close"] * 100

    return dict(d=d, pos=pos, live=live, start=start, cash=cash, mv=mv, total=total,
                pl=pl, plpct=plpct, bm=bm, bm_live=bm_live, bm_total=bm_total,
                base=base, since_ret=since_ret, bm_ret=bm_ret, alpha=alpha,
                port_day=port_day, bm_day=bm_day,
                # "since tracking" only differs from total return for a mirrored
                # portfolio, where the cost basis predates the tracking start.
                split=bool(base) and abs(base - float(d["start_cash"])) > 0.01)


def holdings_table(c):
    rows = []
    for i, p in enumerate(c["pos"]):
        colour = PAL[i % len(PAL)]
        if c["live"]:
            day = (f'<span class="{cls(p["_day"])}">{signed(p["_day"],2,True)}</span>'
                   if p["_day"] is not None else '<span class="flat">&mdash;</span>')
            rows.append(f"""<tr>
  <td><span class="dot" style="background:{colour}"></span><b>{p['ticker']}</b><div class="sub">{p['name']}</div></td>
  <td class="sec">{p['sector']}<div class="sub drv">{p['driver']}</div></td>
  <td class="n">{p['shares']:.4f}</td>
  <td class="n">{money(p['entry'])}</td>
  <td class="n">{money(p['last']) if p['last'] is not None else '&mdash;'}<div class="sub">{day}</div></td>
  <td class="n">{money(p['_mv'])}<div class="sub">{p['_w']:.1f}%</div></td>
  <td class="n {cls(p['_pl'])}">{signed(p['_pl'])}<div class="sub {cls(p['_pl'])}">{signed(p['_plpct'],2,True)}</div></td>
</tr>""")
        else:
            rows.append(f"""<tr>
  <td><span class="dot" style="background:{colour}"></span><b>{p['ticker']}</b><div class="sub">{p['name']}</div></td>
  <td class="sec">{p['sector']}<div class="sub drv">{p['driver']}</div></td>
  <td class="n pend">pending</td><td class="n pend">pending</td><td class="n pend">&mdash;</td>
  <td class="n">{money(c['start'] * p['target'])}<div class="sub">{p['target']*100:.1f}%</div></td>
  <td class="n pend">&mdash;</td>
</tr>""")
    return f"""<div class="card"><h2>Holdings</h2>
<table><thead><tr><th>Ticker</th><th>Sector / driver</th><th class="n">Shares</th>
<th class="n">Entry</th><th class="n">Last</th><th class="n">Value</th><th class="n">P/L</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""


def montecarlo(d, c):
    """A one-factor forward simulation, run in the browser so the assumptions are live.

    Each holding is modelled as  r_i = beta_i * market + idiosyncratic noise, with beta and
    residual volatility measured from the trailing daily bars. Expected returns come from
    CAPM off a market-return assumption the reader sets -- deliberately NOT from each
    stock's own trailing return, because extrapolating a holding that has tripled would
    manufacture a forecast rather than describe risk.
    """
    ok = [p for p in c["pos"] if p.get("beta") is not None
          and p.get("resid_vol") is not None and p.get("last")]
    mvol = (d.get("benchmark") or {}).get("vol")
    if not c["live"] or not mvol or not ok or len(ok) < len(c["pos"]):
        return ""

    tot = sum(p["_mv"] for p in ok)
    tpl = TPL_MC
    for k, v in {
        "@@ASSETS@@": json.dumps([{"t": p["ticker"], "v": round(p["_mv"], 2),
                                   "b": p["beta"], "r": p["resid_vol"]} for p in ok]),
        "@@MVOL@@": f"{mvol:.4f}",
        "@@PATHS@@": "4000",
        "@@BETA@@": f"{sum(p['beta'] * p['_mv'] for p in ok) / tot:.2f}",
        "@@VOL@@": f"{sum(p.get('vol', 0) * p['_mv'] for p in ok) / tot * 100:.0f}",
        "@@DAYS@@": str((d.get("benchmark") or {}).get("stat_days", 0)),
        "@@FLAG@@": _statflag(ok),
    }.items():
        tpl = tpl.replace(k, v)
    return tpl


def _statflag(positions):
    """Note which holdings had bars discarded as split artifacts."""
    bad = [p for p in positions if p.get("stat_dropped")]
    if not bad:
        return ""
    names = ", ".join(f"{p['ticker']} ({p['stat_dropped']})" for p in bad)
    return (" &middot; split-like days excluded for " + names)


TPL_MC = """<div class="card"><h2>Projection &mdash; Monte Carlo</h2>
<div class="mcctl">
  <label>Horizon <b><span id="mcY">8</span> yr</b>
    <input type="range" id="mcYr" min="1" max="15" step="1" value="8"></label>
  <label>Assumed market return <b><span id="mcM">8.0</span>%/yr</b>
    <input type="range" id="mcMk" min="0" max="14" step="0.5" value="8"></label>
  <span class="note">@@PATHS@@ paths &middot; portfolio beta @@BETA@@ &middot;
  weighted volatility @@VOL@@%/yr &middot; estimated from @@DAYS@@ trading days@@FLAG@@</span>
</div>
<canvas id="mc" height="95"></canvas>
<div id="mcOut" class="mcout"></div>
<div class="mcnote">Holdings are simulated as <i>beta &times; market + own noise</i>, with no
rebalancing. Each stock's expected return follows CAPM from the slider above, so
<b>no stock-picking skill is assumed</b> &mdash; the spread below is volatility, not a forecast
about these particular companies. A real multi-year path also brings takeovers, dilution,
regime changes and outright business failure, none of which a lognormal model captures.
Read the fan as a rough sense of scale, nothing more.</div>
</div>
<script>
(function(){
const A = @@ASSETS@@, MV = @@MVOL@@, RF = 0.04, PATHS = @@PATHS@@;
const V0 = A.reduce(function(s,a){return s+a.v;},0);
let sp = null;
function nrm(){
  let u=0,v=0;
  while(u===0) u=Math.random();
  while(v===0) v=Math.random();
  return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);
}
function pct(sorted,q){
  const i=(sorted.length-1)*q, lo=Math.floor(i), hi=Math.ceil(i);
  return lo===hi ? sorted[lo] : sorted[lo]+(sorted[hi]-sorted[lo])*(i-lo);
}
function run(years, mu){
  const drift=[], bs=[], rs=[];
  for(const a of A){
    const sig2 = Math.pow(a.b*MV,2) + a.r*a.r;
    const er   = RF + a.b*(mu-RF);
    drift.push(Math.log(1+er) - 0.5*sig2);
    bs.push(a.b*MV);
    rs.push(a.r);
  }
  const byYear = Array.from({length:years}, function(){return [];});
  for(let p=0;p<PATHS;p++){
    const cur = A.map(function(a){return a.v;});
    for(let y=0;y<years;y++){
      const zm = nrm();
      let tot = 0;
      for(let i=0;i<A.length;i++){
        cur[i] *= Math.exp(drift[i] + bs[i]*zm + rs[i]*nrm());
        tot += cur[i];
      }
      byYear[y].push(tot);
    }
  }
  byYear.forEach(function(a){a.sort(function(x,y){return x-y;});});
  return byYear;
}
const fmt = function(v){return '$'+Math.round(v).toLocaleString();};
function draw(){
  const years = +document.getElementById('mcYr').value;
  const mu = +document.getElementById('mcMk').value/100;
  document.getElementById('mcY').textContent = years;
  document.getElementById('mcM').textContent = (mu*100).toFixed(1);
  const by = run(years, mu);
  const labels = ['now'].concat(Array.from({length:years}, function(_,i){return 'y'+(i+1);}));
  const q = function(k){return [V0].concat(by.map(function(a){return pct(a,k);}));};
  const band = function(data,col,fill,dash){
    return {data:data,borderColor:col,backgroundColor:fill||'transparent',
            fill:fill?'-1':false,borderWidth:fill?1:2,pointRadius:0,
            tension:.2,borderDash:dash||[]};
  };
  const ds=[band(q(0.10),'rgba(79,143,247,.35)',null,[4,3]),
            band(q(0.25),'rgba(79,143,247,.5)','rgba(79,143,247,.10)'),
            band(q(0.50),'#4f8ff7',null),
            band(q(0.75),'rgba(79,143,247,.5)','rgba(79,143,247,.10)'),
            band(q(0.90),'rgba(79,143,247,.35)',null,[4,3])];
  if(sp) sp.destroy();
  sp = new Chart(document.getElementById('mc'), {type:'line',
    data:{labels:labels,datasets:ds},
    options:{plugins:{legend:{display:false},
      tooltip:{mode:'index',intersect:false,callbacks:{
        title:function(c){return c[0].label;},
        label:function(c){return ['10th','25th','median','75th','90th'][c.datasetIndex]
          +': '+fmt(c.parsed.y);}}}},
      scales:{y:{ticks:{callback:function(v){return '$'+(v/1000).toFixed(0)+'k';}}}},
      responsive:true,maintainAspectRatio:false}});
  const f = by[years-1];
  const loss = f.filter(function(v){return v<V0;}).length/f.length*100;
  const cagr = function(v){return ((Math.pow(v/V0,1/years)-1)*100).toFixed(1)+'%/yr';};
  const rows=[['Bad case (10th pct)',pct(f,.10)],['25th percentile',pct(f,.25)],
              ['Median',pct(f,.50)],['75th percentile',pct(f,.75)],
              ['Good case (90th pct)',pct(f,.90)]];
  document.getElementById('mcOut').innerHTML =
    '<table><thead><tr><th>Outcome</th><th class="n">Value after '+years+' yr</th>'
    +'<th class="n">Multiple</th><th class="n">Implied CAGR</th></tr></thead><tbody>'
    + rows.map(function(r){
        return '<tr><td>'+r[0]+'</td><td class="n">'+fmt(r[1])+'</td><td class="n">'
             +(r[1]/V0).toFixed(2)+'x</td><td class="n">'+cagr(r[1])+'</td></tr>';
      }).join('')
    + '</tbody></table><div class="alpha flat">Chance of ending below today&rsquo;s '
    + fmt(V0)+': <b>'+loss.toFixed(0)+'%</b></div>';
}
document.getElementById('mcYr').addEventListener('input', draw);
document.getElementById('mcMk').addEventListener('input', draw);
draw();
})();
</script>"""


def stresstest(d, c):
    """What a market-wide drawdown would do to this portfolio, via each holding's beta."""
    ok = [p for p in c["pos"] if p.get("beta") is not None
          and p.get("resid_vol") is not None and p.get("last")]
    if not c["live"] or not ok or len(ok) < len(c["pos"]):
        return ""
    tpl = TPL_STRESS
    for k, v in {
        "@@ASSETS@@": json.dumps([{"t": p["ticker"], "v": round(p["_mv"], 2),
                                   "b": p["beta"], "r": p["resid_vol"]} for p in ok]),
    }.items():
        tpl = tpl.replace(k, v)
    return tpl


TPL_STRESS = """<div class="card"><h2>Stress test &mdash; market drawdown</h2>
<div class="mcctl">
  <label>S&amp;P 500 falls <b><span id="stD">30</span>%</b>
    <input type="range" id="stDd" min="5" max="60" step="1" value="30"></label>
  <label>Over <b><span id="stM">6</span> months</b>
    <input type="range" id="stMo" min="1" max="30" step="1" value="6"></label>
  <div class="presets">
    <button data-d="34" data-m="1">COVID 2020</button>
    <button data-d="25" data-m="9">2022 bear</button>
    <button data-d="57" data-m="17">GFC 2007-09</button>
    <button data-d="49" data-m="31">Dot-com 2000-02</button>
  </div>
</div>
<div id="stOut"></div>
<div class="mcnote">Each holding is moved by <i>its beta &times; the market fall</i>, plus its own
noise scaled to the length of the shock. Two things this cannot capture: in a real crash
correlations converge toward 1, so diversification helps less than the model suggests; and beta
is measured on ordinary days, then tends to run higher in a panic. <b>Treat these as an
optimistic floor, not a worst case.</b> Historical presets are peak-to-trough S&amp;P 500 closes,
rounded.</div>
</div>
<script>
(function(){
const A = @@ASSETS@@;
const V0 = A.reduce(function(s,a){return s+a.v;},0);
function nrm(){
  let u=0,v=0;
  while(u===0) u=Math.random();
  while(v===0) v=Math.random();
  return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v);
}
const fmt=function(v){return '$'+Math.round(v).toLocaleString();};
const sg=function(v){return (v>=0?'+':'\u2212')+Math.abs(v).toFixed(1)+'%';};
const cl=function(v){return v>0?'up':(v<0?'down':'flat');};
function draw(){
  const dd = +document.getElementById('stDd').value/100;
  const mo = +document.getElementById('stMo').value;
  document.getElementById('stD').textContent=(dd*100).toFixed(0);
  document.getElementById('stM').textContent=mo;
  const Lm = Math.log(1-dd), T = mo/12;
  let central=0;
  const rows=A.map(function(a){
    const mv = a.v*Math.exp(a.b*Lm);
    central += mv;
    return {t:a.t, b:a.b, mv:mv, ch:(Math.exp(a.b*Lm)-1)*100, loss:mv-a.v};
  });
  const N=4000, out=[];
  for(let p=0;p<N;p++){
    let tot=0;
    for(let i=0;i<A.length;i++)
      tot += A[i].v*Math.exp(A[i].b*Lm + A[i].r*Math.sqrt(T)*nrm());
    out.push(tot);
  }
  out.sort(function(x,y){return x-y;});
  const q=function(k){return out[Math.round((out.length-1)*k)];};
  rows.sort(function(x,y){return x.loss-y.loss;});
  document.getElementById('stOut').innerHTML =
    '<div class="kpis" style="margin-bottom:18px">'
    +'<div class="kpi"><div class="l">Portfolio after the fall</div><div class="v down">'
      +fmt(central)+'</div><div class="sub">from '+fmt(V0)+'</div></div>'
    +'<div class="kpi"><div class="l">Portfolio drawdown</div><div class="v down">'
      +sg((central/V0-1)*100)+'</div><div class="sub">market '+sg(-dd*100)+'</div></div>'
    +'<div class="kpi"><div class="l">Amount lost</div><div class="v down">'
      +fmt(V0-central)+'</div></div>'
    +'<div class="kpi"><div class="l">Likely range</div><div class="v">'
      +fmt(q(0.10))+' &ndash; '+fmt(q(0.90))+'</div>'
      +'<div class="sub">10th&ndash;90th pct incl. stock-specific moves</div></div>'
    +'</div>'
    +'<table><thead><tr><th>Ticker</th><th class="n">Beta</th><th class="n">Move</th>'
    +'<th class="n">Value after</th><th class="n">Loss</th></tr></thead><tbody>'
    + rows.map(function(r){
        return '<tr><td><b>'+r.t+'</b></td><td class="n">'+r.b.toFixed(2)+'</td>'
        +'<td class="n '+cl(r.ch)+'">'+sg(r.ch)+'</td>'
        +'<td class="n">'+fmt(r.mv)+'</td>'
        +'<td class="n '+cl(r.loss)+'">'+(r.loss<0?'\u2212':'')+fmt(Math.abs(r.loss)).replace('$','$')+'</td></tr>';
      }).join('')
    +'</tbody></table>';
}
document.getElementById('stDd').addEventListener('input',draw);
document.getElementById('stMo').addEventListener('input',draw);
Array.prototype.forEach.call(document.querySelectorAll('.presets button'),function(b){
  b.addEventListener('click',function(){
    document.getElementById('stDd').value=b.dataset.d;
    document.getElementById('stMo').value=b.dataset.m;
    draw();
  });
});
draw();
})();
</script>"""


def render_portfolio(d, portfolios):
    c = compute(d)
    pos, live = c["pos"], c["live"]
    total, pl, plpct = c["total"], c["pl"], c["plpct"]

    basis_label = "vs cost basis" if c["split"] else f"vs {money(c['start'], 0)} start"
    kpis = [
        f'<div class="kpi"><div class="l">Total value</div><div class="v">{money(total)}</div></div>',
        f'<div class="kpi"><div class="l">Total P/L</div><div class="v {cls(pl)}">{signed(pl)}</div>'
        f'<div class="sub">{basis_label}</div></div>',
        f'<div class="kpi"><div class="l">Total return</div><div class="v {cls(pl)}">{signed(plpct,2,True)}</div></div>',
    ]
    if c["split"]:
        sr = c["since_ret"]
        kpis.append(
            f'<div class="kpi"><div class="l">Since tracking</div>'
            f'<div class="v {cls(sr) if sr is not None else "flat"}">'
            f'{signed(sr,2,True) if sr is not None else "&mdash;"}</div>'
            f'<div class="sub">from {d.get("track_since")}</div></div>')
    a = c["alpha"]
    kpis.append(
        f'<div class="kpi{" hl" if a is not None else ""}"><div class="l">vs S&amp;P 500</div>'
        f'<div class="v {cls(a) if a is not None else "flat"}">'
        f'{signed(a,2)+" pts" if a is not None else "&mdash;"}</div>'
        f'<div class="sub">{"S&amp;P " + signed(c["bm_ret"],2,True) if c["bm_ret"] is not None else "benchmark pending"}</div></div>')

    alloc = "".join(
        f'<div class="seg" style="width:{(p["_w"] if live else p["target"]*100):.4f}%;'
        f'background:{PAL[i%len(PAL)]}" title="{p["ticker"]}"></div>'
        for i, p in enumerate(pos))

    vs = ""
    if live and c["bm_live"] and c["base"]:
        pv, bv = c["total"], c["bm_total"]
        # A mirrored portfolio carries gains banked before tracking began. Showing them in
        # the same table is useful, but they are NOT comparable to the S&P row above, which
        # only covers the tracked window - so the row is separated and labelled as such.
        cost_row = ""
        cost_note = ""
        if c["split"]:
            cost_note = (
                '<div class="mcnote">The bottom row measures against what these shares cost, '
                'which was paid on many dates before tracking started. It answers "how is the '
                'position doing overall", not "did it beat the index" &mdash; only the top two '
                'rows cover the same window and can be compared to each other.</div>')
            cost_row = (
                f'<tr class="sep"><td><b>Since cost basis</b>'
                f'<div class="sub">what was actually paid for these shares</div></td>'
                f'<td class="n">{money(c["start"])}</td><td class="n">{money(pv)}</td>'
                f'<td class="n {cls(c["pl"])}">{signed(c["plpct"], 2, True)}</td>'
                f'<td class="n flat">&mdash;</td></tr>')
        vs = f"""<div class="card"><h2>Head to head &mdash; since {d.get('track_since')}</h2>
<table><thead><tr><th></th><th class="n">Started at</th><th class="n">Now</th>
<th class="n">Return</th><th class="n">Today</th></tr></thead><tbody>
<tr><td><span class="dot" style="background:#4f8ff7"></span><b>{d['name']}</b></td>
    <td class="n">{money(c['base'])}</td><td class="n">{money(pv)}</td>
    <td class="n {cls(c['since_ret'])}">{signed(c['since_ret'],2,True)}</td>
    <td class="n {cls(c['port_day'] or 0)}">{signed(c['port_day'],2,True) if c['port_day'] is not None else '&mdash;'}</td></tr>
<tr><td><span class="dot" style="background:#f7a34f"></span><b>S&amp;P 500</b>
    <div class="sub">{c['bm'].get('shares',0):.4f} SPY @ {money(c['bm']['entry'])}</div></td>
    <td class="n">{money(c['base'])}</td><td class="n">{money(bv)}</td>
    <td class="n {cls(c['bm_ret'])}">{signed(c['bm_ret'],2,True)}</td>
    <td class="n {cls(c['bm_day'] or 0)}">{signed(c['bm_day'],2,True) if c['bm_day'] is not None else '&mdash;'}</td></tr>
{cost_row}</tbody></table>
<div class="alpha {cls(a)}">{signed(a,2)} pts {'ahead of' if a >= 0 else 'behind'} the S&amp;P 500
<span class="sub">&nbsp;&middot;&nbsp; {money(abs(pv - bv))} difference</span></div>
{cost_note}</div>"""

    mc = montecarlo(d, c)
    stress = stresstest(d, c)

    hist = d.get("history", [])
    chart = ""
    if len(hist) >= 2:
        hj = json.dumps([{"d": h["date"], "v": round(h["value"], 2),
                          "b": (round(h["bench"], 2) if h.get("bench") else None)} for h in hist])
        two = "true" if sum(1 for h in hist if h.get("bench")) >= 2 else "false"
        chart = """<div class="card"><h2>Portfolio vs S&amp;P 500</h2>
<div class="legend"><span><i style="background:#4f8ff7"></i>%s</span>
<span><i style="background:#f7a34f"></i>S&amp;P 500 (SPY)</span>
<span class="note">both starting from the same amount on %s</span></div>
<canvas id="eq" height="90"></canvas></div>
<script>
const H = %s;
const ds=[{label:'%s',data:H.map(x=>x.v),borderColor:'#4f8ff7',
 backgroundColor:'rgba(79,143,247,.13)',fill:true,tension:.25,pointRadius:2,borderWidth:2}];
if(%s) ds.push({label:'S&P 500',data:H.map(x=>x.b),borderColor:'#f7a34f',fill:false,
 tension:.25,pointRadius:2,borderWidth:2,borderDash:[5,4],spanGaps:true});
new Chart(document.getElementById('eq'),{type:'line',data:{labels:H.map(x=>x.d),datasets:ds},
 options:{plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>c.dataset.label+': $'+
  c.parsed.y.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}}},
 interaction:{mode:'index',intersect:false},
 scales:{y:{ticks:{callback:v=>'$'+v.toLocaleString()}}},
 responsive:true,maintainAspectRatio:false}});
</script>""" % (d["name"], d.get("track_since", ""), hj, d["name"], two)

    movers = ""
    ranked = sorted([p for p in pos if p["_cost"]], key=lambda x: -x["_plpct"])
    if live and len(ranked) >= 6:
        mk = lambda arr: "".join(
            f'<li><b>{p["ticker"]}</b><span class="{cls(p["_pl"])}">{signed(p["_plpct"],2,True)}</span></li>'
            for p in arr)
        movers = ('<div class="card"><h2>Movers</h2><div class="movers">'
                  f'<div><h3>Top 3</h3><ul>{mk(ranked[:3])}</ul></div>'
                  f'<div><h3>Bottom 3</h3><ul>{mk(ranked[-3:][::-1])}</ul></div></div></div>')

    logrows = "".join(f"<tr><td>{e.get('date','')}</td><td>{e.get('note','')}</td></tr>"
                      for e in reversed(d.get("log", []))) \
        or "<tr><td colspan='2' class='pend'>No entries yet.</td></tr>"

    banner = "" if live else (
        '<div class="banner">Orders staged &mdash; not yet filled. Entry price will be the '
        f'official <b>market open on {d["entry_date"]}</b> (09:30 ET).</div>')

    body = f"""{nav(portfolios, d['slug'])}
<h1>{d['name']}</h1>
<div class="meta">{d.get('subtitle','')} &nbsp;&middot;&nbsp; Entry basis: {d['price_basis']}
&nbsp;&middot;&nbsp; Prices as of {d.get('last_price_date') or '&mdash;'}
&nbsp;&middot;&nbsp; Updated {d.get('last_updated') or '&mdash;'}</div>
{banner}
<div class="kpis">{''.join(kpis)}</div>
<div class="card"><h2>Allocation</h2><div class="bar">{alloc}</div></div>
{holdings_table(c)}
{vs}
{chart}
{mc}
{stress}
{movers}
<div class="card"><h2>Activity log</h2>
<table><thead><tr><th style="width:130px">Date</th><th>Event</th></tr></thead>
<tbody>{logrows}</tbody></table></div>"""
    head = ('<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>'
            if (chart or mc) else "")
    return page(f"{d['name']} &mdash; Paper Trade", body, head), c


def render_index(cards, portfolios):
    blocks = []
    for d, c in cards:
        a = c["alpha"]
        extra = ""
        if c["split"] and c["since_ret"] is not None:
            extra = (f'<span>Since {d.get("track_since")} '
                     f'<b class="{cls(c["since_ret"])}">{signed(c["since_ret"],2,True)}</b></span>')
        blocks.append(f"""<a class="pcard" href="{d['slug']}.html">
<div class="top"><div><div class="nm">{d['name']}</div>
<div class="sub">{d.get('subtitle','')}</div></div>
<div class="val {cls(c['pl'])}">{money(c['total'])}</div></div>
<div class="row">
  <span>Total return <b class="{cls(c['pl'])}">{signed(c['plpct'],2,True)}</b></span>
  <span>P/L <b class="{cls(c['pl'])}">{signed(c['pl'])}</b></span>
  {extra}
  <span>vs S&amp;P 500 <b class="{cls(a) if a is not None else 'flat'}">
    {signed(a,2)+' pts' if a is not None else '&mdash;'}</b></span>
  <span>{len(d['positions'])} holdings</span>
</div></a>""")

    grand = sum(c["total"] for _, c in cards)
    gcost = sum(c["start"] for _, c in cards)
    gpl = grand - gcost
    body = f"""{nav(portfolios, None)}
<h1>Paper Trade</h1>
<div class="meta">Simulated portfolios, refreshed automatically after every US close
&nbsp;&middot;&nbsp; Built {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
<div class="kpis">
  <div class="kpi"><div class="l">Combined value</div><div class="v">{money(grand)}</div></div>
  <div class="kpi"><div class="l">Combined P/L</div><div class="v {cls(gpl)}">{signed(gpl)}</div></div>
  <div class="kpi"><div class="l">Combined return</div>
    <div class="v {cls(gpl)}">{signed(gpl/gcost*100 if gcost else 0,2,True)}</div></div>
  <div class="kpi"><div class="l">Portfolios</div><div class="v">{len(cards)}</div></div>
</div>
{''.join(blocks)}"""
    return page("Paper Trade &mdash; Overview", body)


def main():
    files = sorted(glob.glob(os.path.join(PORTFOLIO_DIR, "*.json")))
    if not files:
        raise SystemExit("No portfolios found under portfolios/")
    data = []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        d.setdefault("slug", os.path.splitext(os.path.basename(f))[0])
        d.setdefault("name", d["slug"])
        data.append(d)
    meta = [{"slug": d["slug"], "name": d["name"]} for d in data]

    cards = []
    for d in data:
        html, c = render_portfolio(d, meta)
        out = os.path.join(BASE, f"{d['slug']}.html")
        open(out, "w", encoding="utf-8").write(html)
        cards.append((d, c))
        print(f"wrote {d['slug']}.html   value={c['total']:,.2f}  "
              f"return={c['plpct']:+.2f}%  alpha="
              f"{('%+.2f pts' % c['alpha']) if c['alpha'] is not None else 'n/a'}")

    open(os.path.join(BASE, "index.html"), "w", encoding="utf-8").write(
        render_index(cards, meta))
    print(f"wrote index.html    {len(cards)} portfolios")


if __name__ == "__main__":
    main()
