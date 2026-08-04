#!/usr/bin/env python3
"""Fetch prices and update portfolio.json for the $10,000 paper-trade portfolio.

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
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "portfolio.json")
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


def series(ticker):
    """Return (bars_ascending, source_name, [failure strings])."""
    problems = []
    for name, fn in SOURCES:
        bars, err = fn(ticker)
        if bars:
            bars.sort(key=lambda r: r["date"])
            return bars, name, problems
        problems.append(f"{name}: {err}")
    return None, None, problems


# ------------------------------------------------------------------- main

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


def main():
    if PROBE:
        return probe()

    d = json.load(open(SRC, encoding="utf-8"))
    positions = d["positions"]
    entry_date = d["entry_date"]
    start = float(d["start_cash"])
    need_entry = d.get("status") != "open"

    # Benchmark: the same $10,000 put into SPY on the same day. SPY is used rather than
    # ^GSPC because the index symbol is not available on Alpha Vantage's free tier.
    bench = d.setdefault("benchmark", {
        "ticker": "SPY", "name": "S&P 500 (SPY ETF)",
        "entry": None, "shares": 0, "last": None, "prev_close": None})

    log(f"Alpha Vantage key: {'present' if AV_KEY else 'NOT set'}")
    log(f"Mode: {'INITIAL BUY (entry ' + entry_date + ')' if need_entry else 'daily mark-to-market'}\n")

    failures, waiting, notes = [], [], []
    latest_date = None

    for p in positions:
        tk = p["ticker"]
        bars, src, problems = series(tk)
        if not bars:
            failures.append(tk)
            log(f"  {tk:<6} FAILED - keeping previous values")
            for pr in problems:
                log(f"           {pr}")
            continue

        last_bar = bars[-1]
        p["last"] = round(last_bar["close"], 4)
        p["prev_close"] = round(bars[-2]["close"], 4) if len(bars) > 1 else None
        latest_date = max(latest_date or last_bar["date"], last_bar["date"])

        if need_entry:
            bar = next((r for r in bars if r["date"] == entry_date), None)
            if bar is None:
                bar = next((r for r in bars if r["date"] >= entry_date), None)
            if bar is None:
                waiting.append(tk)
                log(f"  {tk:<6} {src:<13} no bar yet for {entry_date} "
                    f"(latest is {last_bar['date']}) - buy deferred")
                continue
            p["entry"] = round(bar["open"], 4)
            p["shares"] = round(start * p["target"] / p["entry"], 6)
            if bar["date"] != entry_date:
                notes.append(f"{tk} entry taken from {bar['date']}")
        log(f"  {tk:<6} {src:<13} entry={p['entry']} last={p['last']} ({last_bar['date']})")

    # --- benchmark ------------------------------------------------------------
    # A benchmark problem must never block the portfolio itself, so its failures are
    # reported but kept out of `failures`.
    bench_bars, bench_src, bench_problems = series(bench["ticker"])
    if bench_bars:
        bench["last"] = round(bench_bars[-1]["close"], 4)
        bench["prev_close"] = round(bench_bars[-2]["close"], 4) if len(bench_bars) > 1 else None
        if not bench.get("entry"):
            bar = next((r for r in bench_bars if r["date"] == entry_date), None) \
                or next((r for r in bench_bars if r["date"] >= entry_date), None)
            if bar:
                bench["entry"] = round(bar["open"], 4)
                bench["shares"] = round(start / bench["entry"], 6)
        log(f"  {bench['ticker']:<6} {bench_src:<13} entry={bench['entry']} "
            f"last={bench['last']} ({bench_bars[-1]['date']})  [benchmark]")
    else:
        log(f"  {bench['ticker']:<6} benchmark fetch failed - keeping previous values")
        for pr in bench_problems:
            log(f"           {pr}")

    blocked = failures + waiting

    if not failures:
        # Drop stale "fetch failed" notices once everything is healthy again -
        # they are noise on the dashboard's activity log.
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
            "note": f"Opened 10 positions at the {entry_date} market open. "
                    f"Total cost ${cost:,.2f}, residual cash ${d['cash']:,.2f}."
                    + (" " + "; ".join(notes) if notes else "")})
        d.setdefault("history", [])
        if not any(h["date"] == entry_date for h in d["history"]):
            d["history"].append({"date": entry_date, "value": round(start, 2),
                                 "bench": round(start, 2)})
        log(f"\n  -> BUY executed. cost={cost:,.2f} cash={d['cash']:,.2f}")
    elif need_entry:
        reason = []
        if failures:
            reason.append("fetch failed for " + ", ".join(failures))
        if waiting:
            reason.append(f"{entry_date} open not published yet for " + ", ".join(waiting))
        log("\n  -> buy NOT executed: " + "; ".join(reason))

    if d.get("status") == "open" and latest_date:
        total = sum((p["last"] or p["entry"] or 0) * (p["shares"] or 0)
                    for p in positions) + float(d.get("cash") or 0)
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
        log(f"  -> total={total:,.2f}  P/L={pl:+,.2f} ({pl / start * 100:+.2f}%)")
        if bench_total is not None:
            bpl = bench_total - start
            log(f"  -> S&P 500 {bench_total:,.2f}  ({bpl / start * 100:+.2f}%)   "
                f"alpha {(pl - bpl) / start * 100:+.2f} pts")

    if failures:
        d.setdefault("log", []).append({
            "date": dt.date.today().isoformat(),
            "note": "Price fetch failed for: " + ", ".join(failures)
                    + " - stale values kept, see the Actions log for the reason."})

    d["last_updated"] = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if DRY:
        log("\ndry-run: portfolio.json NOT written")
        return 0

    tmp = SRC + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, SRC)
    log("\nportfolio.json updated")
    # Fail the workflow step only if literally nothing could be fetched.
    return 1 if len(failures) == len(positions) else 0


if __name__ == "__main__":
    sys.exit(main())
