#!/usr/bin/env python3
"""Fetch prices and update every portfolio under portfolios/.

Stdlib only - no pip install needed.

Price sources, tried in order until one returns a usable daily series:
  1. Alpha Vantage      - used first if the ALPHAVANTAGE_KEY env var is set (most
                          reliable from CI runners; free key, 25 req/day is plenty
                          for 10 tickers).
  2. Stooq              - free CSV, no key. Often blocks datacenter IPs.
  3. Yahoo Finance      - chart API, seeded with real cookies. Rate-limits cloud IPs.

Every failure prints the HTTP status and a snippet of the body so the GitHub
Actions log tells you exactly which source rejected the request and why.

Usage:
    python3 update.py            # normal run (initial buy if pending, then mark-to-market)
    python3 update.py --dry-run  # fetch and report, write nothing
    python3 update.py --probe    # only test the sources against MSFT, then exit
"""
import csv
import datetime as dt
import http.cookiejar
import glob
import io
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_DIR = os.path.join(BASE, "portfolios")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
AV_KEY = os.environ.get("ALPHAVANTAGE_KEY", "").strip()

DRY = "--dry-run" in sys.argv
PROBE = "--probe" in sys.argv

_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def log(*a):
    print(*a, flush=True)


def get(url, tries=3, referer=None):
    """Return (body, error_string). Exactly one is non-None."""
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/json,text/csv,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    last = "unknown"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with _opener.open(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace"), None
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:180].replace("\n", " ")
            except Exception:  # noqa: BLE001
                pass
            last = f"HTTP {e.code} {e.reason} :: {body}"
            if e.code in (401, 403, 404, 429):
                break          # not worth retrying a hard rejection
        except Exception as e:  # noqa: BLE001
            last = f"{type(e).__name__}: {e}"
        if i < tries - 1:
            time.sleep(2 + 2 * i)
    return None, last


# ----------------------------------------------------------- Alpha Vantage

def src_alphavantage(ticker):
    if not AV_KEY:
        return None, "no ALPHAVANTAGE_KEY set"
    url = ("https://www.alphavantage.co/query?function=TIME_SERIES_DAILY"
           f"&symbol={ticker}&outputsize=compact&apikey={urllib.parse.quote(AV_KEY)}")
    txt, err = get(url, tries=2)
    if err:
        return None, err
    try:
        j = json.loads(txt)
    except json.JSONDecodeError:
        return None, f"bad JSON :: {txt[:150]}"
    if "Time Series (Daily)" not in j:
        # Alpha Vantage reports problems in Note / Information / Error Message
        msg = j.get("Note") or j.get("Information") or j.get("Error Message") or str(j)[:150]
        return None, f"api said :: {msg[:180]}"
    out = []
    for d, row in j["Time Series (Daily)"].items():
        try:
            out.append({"date": d, "open": float(row["1. open"]), "high": float(row["2. high"]),
                        "low": float(row["3. low"]), "close": float(row["4. close"])})
        except (KeyError, ValueError):
            continue
    return (out or None), (None if out else "empty series")


# ------------------------------------------------------------------ Stooq

def src_stooq(ticker):
    end = dt.date.today()
    start = end - dt.timedelta(days=400)
    urls = [
        f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d",
        f"https://stooq.pl/q/d/l/?s={ticker.lower()}.us&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d",
    ]
    errs = []
    for u in urls:
        txt, err = get(u, tries=2)
        if err:
            errs.append(err)
            continue
        if not txt or not txt.lstrip().lower().startswith("date"):
            errs.append(f"unexpected body :: {(txt or '')[:120].strip()}")
            continue
        out = []
        for row in csv.DictReader(io.StringIO(txt)):
            try:
                out.append({"date": row["Date"], "open": float(row["Open"]),
                            "high": float(row["High"]), "low": float(row["Low"]),
                            "close": float(row["Close"])})
            except (ValueError, KeyError, TypeError):
                continue
        if out:
            return out, None
        errs.append("empty series")
    return None, " | ".join(errs)


# ------------------------------------------------------------------ Yahoo

_yahoo_seeded = False


def _seed_yahoo():
    global _yahoo_seeded
    if _yahoo_seeded:
        return
    get("https://fc.yahoo.com/", tries=1)
    get("https://finance.yahoo.com/quote/MSFT/", tries=1)
    _yahoo_seeded = True


def src_yahoo(ticker):
    _seed_yahoo()
    errs = []
    for host in ("query1", "query2"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{ticker}"
               f"?range=1y&interval=1d&includePrePost=false")
        txt, err = get(url, tries=2, referer=f"https://finance.yahoo.com/quote/{ticker}/")
        if err:
            errs.append(f"{host}: {err}")
            continue
        try:
            res = json.loads(txt)["chart"]["result"][0]
            ts, q = res["timestamp"], res["indicators"]["quote"][0]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            errs.append(f"{host}: unparseable ({type(e).__name__}) :: {txt[:120]}")
            continue
        out = []
        for i, t in enumerate(ts):
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            if None in (o, c):
                continue
            out.append({"date": dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"),
                        "open": float(o), "high": float(h or o),
                        "low": float(l or o), "close": float(c)})
        if out:
            return out, None
        errs.append(f"{host}: empty series")
    return None, " | ".join(errs)


SOURCES = [("alphavantage", src_alphavantage), ("stooq", src_stooq), ("yahoo", src_yahoo)]


def _series_uncached(ticker):
    """Return (bars_ascending, source_name, [failure strings])."""
    problems = []
    for name, fn in SOURCES:
        bars, err = fn(ticker)
        if bars:
            bars.sort(key=lambda r: r["date"])
            return bars, name, problems
        problems.append(f"{name}: {err}")
    return None, None, problems


# ----------------------------------------------------------- shared cache

_CACHE = {}


def series(ticker):
    """Cached wrapper around _series_uncached.

    Several portfolios hold the same names, and Alpha Vantage's free tier allows
    only 25 requests a day, so every ticker is fetched at most once per run.
    """
    if ticker not in _CACHE:
        _CACHE[ticker] = _series_uncached(ticker)
        _CACHE[ticker] += (False,)          # first look-up, not a cache hit
    else:
        b, s, p, _ = _CACHE[ticker]
        return b, s, p, True
    b, s, p, _ = _CACHE[ticker]
    return b, s, p, False


# ---------------------------------------------------------------- portfolios

def discover():
    """Return the portfolio files to process, migrating the legacy layout if needed."""
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)
    legacy = os.path.join(BASE, "portfolio.json")
    target = os.path.join(PORTFOLIO_DIR, "sector-core.json")
    if os.path.exists(legacy) and not os.path.exists(target):
        d = json.load(open(legacy, encoding="utf-8"))
        d.setdefault("name", "Sector Core")
        d.setdefault("slug", "sector-core")
        d.setdefault("subtitle", "One large-cap leader per GICS sector, $10,000 at the open")
        # The benchmark for this one has always run from the entry date with the
        # full starting cash as its notional.
        d.setdefault("track_since", d["entry_date"])
        d.setdefault("track_base", d["start_cash"])
        with open(target, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.remove(legacy)
        log(f"Migrated portfolio.json -> {os.path.relpath(target, BASE)}\n")
    return sorted(glob.glob(os.path.join(PORTFOLIO_DIR, "*.json")))


def probe():
    log("Probing price sources with MSFT...\n")
    for name, fn in SOURCES:
        bars, err = fn("MSFT")
        if bars:
            bars.sort(key=lambda r: r["date"])
            log(f"  {name:<14} OK   {len(bars)} bars, latest {bars[-1]['date']} "
                f"close={bars[-1]['close']}")
        else:
            log(f"  {name:<14} FAIL {err}")
    log("\nIf every source failed, set an ALPHAVANTAGE_KEY repo secret "
        "(free at https://www.alphavantage.co/support/#api-key).")
    return 0


def logrets(bars):
    """{date: log return} from a list of daily bars."""
    out = {}
    for a, b in zip(bars, bars[1:]):
        if a["close"] > 0 and b["close"] > 0:
            out[b["date"]] = math.log(b["close"] / a["close"])
    return out


# A single day beyond this is almost never a real move over a 100-day window. In practice
# it means a stock split: Alpha Vantage's free TIME_SERIES_DAILY endpoint returns
# as-traded prices, so a 2-for-1 split shows up as a clean -50% day. Left in, one such
# bar wrecks the beta and volatility for that holding (CrowdStrike came back at 228%/yr).
SPLIT_GUARD = 0.35


def risk_stats(stock_bars, mkt_rets):
    """One-factor risk estimate: (beta, residual vol, total vol, days dropped).

    Regresses the stock's daily log returns on the benchmark's. Returns None when
    there is not enough overlap to say anything meaningful.
    """
    r = logrets(stock_bars)
    dates = sorted(set(r) & set(mkt_rets))
    dropped = [t for t in dates if abs(r[t]) > SPLIT_GUARD]
    dates = [t for t in dates if abs(r[t]) <= SPLIT_GUARD]
    n = len(dates)
    if n < 60:
        return None
    x = [mkt_rets[t] for t in dates]
    y = [r[t] for t in dates]
    mx, my = sum(x) / n, sum(y) / n
    vx = sum((a - mx) ** 2 for a in x) / (n - 1)
    if vx <= 0:
        return None
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y)) / (n - 1)
    beta = cov / vx
    resid = [b - my - beta * (a - mx) for a, b in zip(x, y)]
    rv = math.sqrt(sum(e * e for e in resid) / (n - 2)) * math.sqrt(252)
    tv = math.sqrt(sum((b - my) ** 2 for b in y) / (n - 1)) * math.sqrt(252)
    return round(beta, 4), round(rv, 4), round(tv, 4), len(dropped)


def backfill(d, closes, bench_bars, bench):
    """Rebuild the whole daily history from `history_from` using the fetched bars.

    Share counts never change in these portfolios, so the value on any past day is just
    shares x that day's close. That lets a portfolio mirrored from a statement show a real
    trend line immediately instead of waiting weeks to accumulate one. Benchmark shares are
    re-derived so that SPY starts from exactly the same amount on the same day.

    Rewritten from scratch on every run, so it is idempotent.
    """
    start = d["history_from"]
    spy = {b["date"]: b["close"] for b in (bench_bars or [])}
    if not spy:
        return
    common = set(spy)
    for p in d["positions"]:
        c = closes.get(p["ticker"])
        if not c:
            return                      # incomplete data: leave the old history alone
        common &= set(c)
    dates = sorted(t for t in common if t >= start)
    if len(dates) < 2:
        log(f"  backfill skipped: only {len(dates)} common trading day(s) on or after {start}")
        return

    if bench.get("entry") and d.get("track_base"):
        # Already anchored - most likely the portfolio was bought in one go at a known
        # price. Keep that anchor and only rebuild the daily series, so re-running never
        # rewrites history that was recorded correctly the first time.
        base = float(d["track_base"])
    else:
        base = sum(closes[p["ticker"]][dates[0]] * float(p["shares"] or 0)
                   for p in d["positions"]) + float(d.get("cash") or 0)
        bench["entry"] = round(spy[dates[0]], 4)
        bench["shares"] = round(base / bench["entry"], 6)
        d["track_since"] = dates[0]
        d["track_base"] = round(base, 2)

    d["history"] = [
        {"date": t,
         "value": round(sum(closes[p["ticker"]][t] * float(p["shares"] or 0)
                            for p in d["positions"]) + float(d.get("cash") or 0), 2),
         "bench": round(spy[t] * bench["shares"], 2)}
        for t in dates
    ]
    last = d["history"][-1]
    sr = (last["value"] / base - 1) * 100
    br = (last["bench"] / base - 1) * 100
    log(f"  backfilled {len(dates)} days from {dates[0]} "
        f"(base ${base:,.2f}, SPY @ {bench['entry']})")
    log(f"  -> since {dates[0]}: portfolio {sr:+.2f}%  S&P 500 {br:+.2f}%  "
        f"alpha {sr - br:+.2f} pts")


def run_one(path):
    """Update a single portfolio file. Returns True if it was fully priced."""
    d = json.load(open(path, encoding="utf-8"))
    positions = d["positions"]
    entry_date = d["entry_date"]
    start = float(d["start_cash"])
    need_entry = d.get("status") != "open"

    # Where the benchmark comparison starts. For a portfolio bought in one go this is
    # the entry date; for one mirrored from an existing account it is the day tracking
    # began, because the cost basis was accumulated over many different dates and
    # comparing that to an index would be meaningless.
    anchor = d.get("track_since") or entry_date
    bench = d.setdefault("benchmark", {
        "ticker": "SPY", "name": "S&P 500 (SPY ETF)",
        "entry": None, "shares": 0, "last": None, "prev_close": None})

    log(f"=== {d.get('name', d.get('slug', path))} "
        f"({'INITIAL BUY, entry ' + entry_date if need_entry else 'mark-to-market'}) ===")

    failures, waiting, notes = [], [], []
    latest_date = None
    closes = {}          # ticker -> {date: close}, kept for the history backfill

    # Benchmark bars are pulled up front (the cache makes this free) so that every
    # holding can be regressed against the same market series for the projection.
    bench_bars, bench_src, bench_problems, bench_hit = series(bench["ticker"])
    mkt_rets = logrets(bench_bars) if bench_bars else {}
    if bench_bars and len(mkt_rets) >= 60:
        vals = list(mkt_rets.values())
        mu = sum(vals) / len(vals)
        bench["vol"] = round(math.sqrt(sum((v - mu) ** 2 for v in vals)
                                       / (len(vals) - 1)) * math.sqrt(252), 4)
        bench["stat_days"] = len(vals)

    for p in positions:
        tk = p["ticker"]
        bars, src, problems, hit = series(tk)
        if not bars:
            failures.append(tk)
            log(f"  {tk:<6} FAILED - keeping previous values")
            for pr in problems:
                log(f"           {pr}")
            continue

        closes[tk] = {b["date"]: b["close"] for b in bars}
        last_bar = bars[-1]
        p["last"] = round(last_bar["close"], 4)
        p["prev_close"] = round(bars[-2]["close"], 4) if len(bars) > 1 else None
        latest_date = max(latest_date or last_bar["date"], last_bar["date"])

        st = risk_stats(bars, mkt_rets) if mkt_rets else None
        if st:
            p["beta"], p["resid_vol"], p["vol"], nd = st
            if nd:
                p["stat_dropped"] = nd
                log(f"           {tk}: ignored {nd} day(s) beyond "
                    f"{SPLIT_GUARD:.0%} when measuring risk (likely a split)")
            else:
                p.pop("stat_dropped", None)

        if need_entry:
            bar = next((r for r in bars if r["date"] == entry_date), None) \
                or next((r for r in bars if r["date"] >= entry_date), None)
            if bar is None:
                waiting.append(tk)
                log(f"  {tk:<6} {src:<13} no bar yet for {entry_date} "
                    f"(latest is {last_bar['date']}) - buy deferred")
                continue
            p["entry"] = round(bar["open"], 4)
            p["shares"] = round(start * p["target"] / p["entry"], 6)
            if bar["date"] != entry_date:
                notes.append(f"{tk} entry taken from {bar['date']}")
        log(f"  {tk:<6} {src + (' *' if hit else ''):<15} entry={p['entry']} "
            f"last={p['last']} ({last_bar['date']})")

    blocked = failures + waiting

    if not failures:
        kept = [e for e in d.get("log", [])
                if not str(e.get("note", "")).startswith("Price fetch failed")]
        if len(kept) != len(d.get("log", [])):
            log(f"  (cleared {len(d['log']) - len(kept)} stale fetch-failure log entries)")
        d["log"] = kept

    if need_entry and not blocked:
        cost = sum((p["entry"] or 0) * (p["shares"] or 0) for p in positions)
        d["cash"] = round(start - cost, 6)
        d["status"] = "open"
        d.setdefault("log", []).append({
            "date": entry_date,
            "note": f"Opened {len(positions)} positions at the {entry_date} market open. "
                    f"Total cost ${cost:,.2f}, residual cash ${d['cash']:,.2f}."
                    + (" " + "; ".join(notes) if notes else "")})
        d.setdefault("history", [])
        if not any(h["date"] == entry_date for h in d["history"]):
            d["history"].append({"date": entry_date, "value": round(start, 2),
                                 "bench": round(start, 2)})
        log(f"  -> BUY executed. cost={cost:,.2f} cash={d['cash']:,.2f}")
    elif need_entry:
        reason = []
        if failures:
            reason.append("fetch failed for " + ", ".join(failures))
        if waiting:
            reason.append(f"{entry_date} open not published yet for " + ", ".join(waiting))
        log("  -> buy NOT executed: " + "; ".join(reason))

    if d.get("status") == "open" and latest_date:
        total = sum((p["last"] or p["entry"] or 0) * (p["shares"] or 0)
                    for p in positions) + float(d.get("cash") or 0)

        # --- benchmark: a failure here must never affect the portfolio itself ---
        bench_bars, bench_src, bench_problems, bench_hit = series(bench["ticker"])
        if bench_bars:
            bench["last"] = round(bench_bars[-1]["close"], 4)
            bench["prev_close"] = round(bench_bars[-2]["close"], 4) if len(bench_bars) > 1 else None
            if not bench.get("entry") and not d.get("history_from"):
                bar = next((r for r in bench_bars if r["date"] == anchor), None) \
                    or next((r for r in bench_bars if r["date"] >= anchor), None)
                if bar:
                    # Notional: the starting cash for a fresh portfolio, otherwise the
                    # portfolio's own value on the day tracking started.
                    base = d.get("track_base")
                    if base is None:
                        base = round(total, 2)
                        d["track_base"] = base
                        d.setdefault("log", []).append({
                            "date": bar["date"],
                            "note": f"Benchmark tracking started at ${base:,.2f}, "
                                    f"matched into SPY at ${bar['open']:,.2f}."})
                    bench["entry"] = round(bar["open"], 4)
                    bench["shares"] = round(float(base) / bench["entry"], 6)
            log(f"  {bench['ticker']:<6} {bench_src + (' *' if bench_hit else ''):<15} "
                f"entry={bench['entry']} last={bench['last']} "
                f"({bench_bars[-1]['date']})  [benchmark]")
        else:
            log(f"  {bench['ticker']:<6} benchmark fetch failed - keeping previous values")
            for pr in bench_problems:
                log(f"           {pr}")

        bench_total = None
        if bench.get("entry") and bench.get("last"):
            bench_total = round(bench["last"] * bench["shares"], 2)

        hist = d.setdefault("history", [])
        row = next((h for h in hist if h["date"] == latest_date), None)
        if row is None:
            row = {"date": latest_date}
            hist.append(row)
        row["value"] = round(total, 2)
        if bench_total is not None:
            row["bench"] = bench_total
        hist.sort(key=lambda h: h["date"])

        d["last_price_date"] = latest_date
        pl = total - start
        log(f"  -> total={total:,.2f}  P/L vs cost={pl:+,.2f} ({pl / start * 100:+.2f}%)")
        base = d.get("track_base")
        if bench_total is not None and base and not d.get("history_from"):
            sr = (total / float(base) - 1) * 100
            br = (bench_total / float(base) - 1) * 100
            log(f"  -> since {anchor}: portfolio {sr:+.2f}%  S&P 500 {br:+.2f}%  "
                f"alpha {sr - br:+.2f} pts")

    if d.get("history_from") and d.get("status") == "open" and not failures:
        backfill(d, closes, bench_bars, bench)

    if failures:
        d.setdefault("log", []).append({
            "date": dt.date.today().isoformat(),
            "note": "Price fetch failed for: " + ", ".join(failures)
                    + " - stale values kept, see the Actions log for the reason."})

    d["last_updated"] = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if DRY:
        log("  dry-run: file NOT written\n")
        return not failures

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    log(f"  written: {os.path.relpath(path, BASE)}\n")
    return not failures


def main():
    if PROBE:
        return probe()

    log(f"Alpha Vantage key: {'present' if AV_KEY else 'NOT set'}")
    files = discover()
    if not files:
        log("No portfolios found under portfolios/.")
        return 1
    log(f"Portfolios: {', '.join(os.path.basename(f) for f in files)}\n")

    results = [run_one(f) for f in files]
    fetched = sum(1 for v in _CACHE.values() if v[0])
    log(f"Tickers fetched this run: {fetched} unique "
        f"(a '*' next to the source means the price came from this run's cache)")
    return 0 if any(results) else 1


if __name__ == "__main__":
    sys.exit(main())
