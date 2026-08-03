#!/usr/bin/env python3
"""Fetch prices and update portfolio.json for the $10,000 paper-trade portfolio.

Stdlib only - no pip install needed.
Sources: Stooq (primary, CSV) -> Yahoo Finance chart API (fallback).

Usage:
    python3 update.py            # normal daily mark-to-market (+ initial buy if pending)
    python3 update.py --dry-run  # print what it would do, write nothing
"""
import csv
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "portfolio.json")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
DRY = "--dry-run" in sys.argv


def log(*a):
    print(*a, flush=True)


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                log(f"    ! fetch failed {url} -> {e}")
                return None
            time.sleep(2 + 2 * i)
    return None


# ---------------------------------------------------------------- Stooq

def stooq_daily(ticker, days=400):
    """Return list of {date, open, high, low, close} ascending, or None."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    url = (f"https://stooq.com/q/d/l/?s={ticker.lower()}.us"
           f"&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d")
    txt = get(url)
    if not txt or "Date" not in txt[:60]:
        return None
    out = []
    for row in csv.DictReader(io.StringIO(txt)):
        try:
            out.append({"date": row["Date"], "open": float(row["Open"]),
                        "high": float(row["High"]), "low": float(row["Low"]),
                        "close": float(row["Close"])})
        except (ValueError, KeyError, TypeError):
            continue
    return out or None


# ---------------------------------------------------------------- Yahoo

def yahoo_daily(ticker, rng="1y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?range={rng}&interval=1d&includePrePost=false")
    txt = get(url)
    if not txt:
        return None
    try:
        res = json.loads(txt)["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None
    out = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, c):
            continue
        d = dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d")
        out.append({"date": d, "open": float(o), "high": float(h or o),
                    "low": float(l or o), "close": float(c)})
    return out or None


def series(ticker):
    s = stooq_daily(ticker)
    src = "stooq"
    if not s:
        s = yahoo_daily(ticker)
        src = "yahoo"
    if not s:
        return None, None
    s.sort(key=lambda r: r["date"])
    return s, src


# ---------------------------------------------------------------- main

def main():
    d = json.load(open(SRC, encoding="utf-8"))
    positions = d["positions"]
    entry_date = d["entry_date"]
    start = float(d["start_cash"])
    need_entry = d.get("status") != "open"

    failures, notes = [], []
    latest_date = None

    for p in positions:
        tk = p["ticker"]
        s, src = series(tk)
        if not s:
            failures.append(tk)
            log(f"  {tk:<6} FAILED - keeping previous values")
            continue

        last_bar = s[-1]
        p["last"] = round(last_bar["close"], 4)
        p["prev_close"] = round(s[-2]["close"], 4) if len(s) > 1 else None
        latest_date = max(latest_date or last_bar["date"], last_bar["date"])

        if need_entry:
            bar = next((r for r in s if r["date"] == entry_date), None)
            if bar is None:
                # entry_date not a trading day / not published yet -> first bar on or after it
                bar = next((r for r in s if r["date"] >= entry_date), None)
            if bar is None:
                failures.append(tk)
                log(f"  {tk:<6} no bar for entry date {entry_date}")
                continue
            p["entry"] = round(bar["open"], 4)
            p["shares"] = round(start * p["target"] / p["entry"], 6)
            if bar["date"] != entry_date:
                notes.append(f"{tk} entry taken from {bar['date']}")
        log(f"  {tk:<6} {src:<6} entry={p['entry']} last={p['last']} ({last_bar['date']})")

    if need_entry and not failures:
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
            d["history"].append({"date": entry_date, "value": round(start, 2)})
        log(f"  -> BUY executed. cost={cost:,.2f} cash={d['cash']:,.2f}")
    elif need_entry:
        log(f"  -> buy NOT executed, missing data for: {', '.join(failures)}")

    if d.get("status") == "open" and latest_date:
        total = sum((p["last"] or p["entry"] or 0) * (p["shares"] or 0)
                    for p in positions) + float(d.get("cash") or 0)
        hist = d.setdefault("history", [])
        for h in hist:
            if h["date"] == latest_date:
                h["value"] = round(total, 2)
                break
        else:
            hist.append({"date": latest_date, "value": round(total, 2)})
        hist.sort(key=lambda h: h["date"])
        d["last_price_date"] = latest_date
        pl = total - start
        log(f"  -> total={total:,.2f}  P/L={pl:+,.2f} ({pl / start * 100:+.2f}%)")

    if failures:
        d.setdefault("log", []).append({
            "date": dt.date.today().isoformat(),
            "note": "Price fetch failed for: " + ", ".join(failures) + " (stale values kept)."})

    d["last_updated"] = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if DRY:
        log("dry-run: portfolio.json NOT written")
        return 0

    tmp = SRC + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, SRC)
    log("portfolio.json updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
