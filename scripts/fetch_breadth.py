#!/usr/bin/env python3
"""
One scan, two outputs:
1. data/breadth.json - % of S&P 500 above 50-day SMA (S5FI-style approximation).
2. data/opportunities.json - scans S&P 500 + Nasdaq 100 (deduplicated) for:
   near_sma20 / near_sma150, volume_surge, near_52w_high / near_52w_low.
Both come from the SAME pass of Yahoo Finance chart data per ticker.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import csv
import io
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

BREADTH_OUT = os.path.join(os.path.dirname(__file__), "..", "data", "breadth.json")
OPP_OUT = os.path.join(os.path.dirname(__file__), "..", "data", "opportunities.json")

SP500_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
NASDAQ100_URL = "https://yfiua.github.io/index-constituents/constituents-nasdaq100.csv"

NEAR_MA_PCT = 2.0
NEAR_52W_PCT = 3.0
VOLUME_SURGE_RATIO = 2.0
MAX_LIST_SIZE = 30


def normalize_symbol(sym):
    return sym.strip().upper().replace(".", "-")


def fetch_sp500():
    req = urllib.request.Request(SP500_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        text = r.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for row in reader:
        sym = row.get("Symbol") or row.get("symbol")
        if sym:
            out.append(normalize_symbol(sym))
    return out


def fetch_nasdaq100():
    req = urllib.request.Request(NASDAQ100_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        text = r.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for row in reader:
        sym = (row.get("Symbol") or row.get("symbol") or row.get("Ticker")
               or row.get("ticker") or row.get("code") or row.get("Code"))
        if sym:
            out.append(normalize_symbol(sym))
    return out


def fetch_history(symbol, retries=2):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1y&interval=1d"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            result = data["chart"]["result"][0]
            quote = result["indicators"]["quote"][0]
            closes_raw = quote["close"]
            volumes_raw = quote.get("volume", [])
            closes, volumes = [], []
            for c, v in zip(closes_raw, volumes_raw):
                if c is None:
                    continue
                closes.append(c)
                volumes.append(v or 0)
            if len(closes) < 20:
                return None
            return closes, volumes
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except Exception:
            return None
    return None


def analyze(symbol, closes, volumes):
    price = closes[-1]
    out = {"symbol": symbol, "price": round(price, 2)}

    if len(closes) >= 20:
        sma20 = sum(closes[-20:]) / 20
        out["sma20"] = sma20
        out["dist_sma20_pct"] = (price - sma20) / sma20 * 100
    if len(closes) >= 50:
        sma50 = sum(closes[-50:]) / 50
        out["sma50"] = sma50
    if len(closes) >= 150:
        sma150 = sum(closes[-150:]) / 150
        out["sma150"] = sma150
        out["dist_sma150_pct"] = (price - sma150) / sma150 * 100

    hist_window = closes[-252:] if len(closes) >= 252 else closes
    hi52, lo52 = max(hist_window), min(hist_window)
    out["hi52"] = hi52
    out["lo52"] = lo52
    out["dist_hi52_pct"] = (hi52 - price) / hi52 * 100 if hi52 else None
    out["dist_lo52_pct"] = (price - lo52) / lo52 * 100 if lo52 else None

    if len(volumes) >= 21:
        vol_today = volumes[-1]
        avg_vol20 = sum(volumes[-21:-1]) / 20
        out["volume_today"] = vol_today
        out["avg_volume_20d"] = avg_vol20
        out["volume_ratio"] = (vol_today / avg_vol20) if avg_vol20 > 0 else None

    return out


def main():
    try:
        sp500 = fetch_sp500()
    except Exception as e:
        print(f"ERROR: could not fetch S&P 500 list: {e}", file=sys.stderr)
        sp500 = []
    try:
        nasdaq100 = fetch_nasdaq100()
    except Exception as e:
        print(f"WARN: could not fetch Nasdaq 100 list, continuing with S&P 500 only: {e}", file=sys.stderr)
        nasdaq100 = []

    sp500_set = set(sp500)
    universe = sorted(sp500_set | set(nasdaq100))

    if not universe:
        print("ERROR: empty universe, nothing to scan", file=sys.stderr)
        sys.exit(0)

    results = {}
    failed = 0
    for i, sym in enumerate(universe):
        hist = fetch_history(sym)
        if hist is None:
            failed += 1
            continue
        closes, volumes = hist
        results[sym] = analyze(sym, closes, volumes)
        time.sleep(0.15)
        if (i + 1) % 100 == 0:
            print(f"...{i + 1}/{len(universe)} processed", file=sys.stderr)

    matched = len(results)
    print(f"Scanned {matched}/{len(universe)} tickers ({failed} failed)", file=sys.stderr)

    if matched < len(universe) * 0.5:
        print("ERROR: too many failures this run - skipping writes to avoid clobbering good data", file=sys.stderr)
        sys.exit(0)

    sp500_results = [r for sym, r in results.items() if sym in sp500_set and "sma50" in r]
    above = sum(1 for r in sp500_results if r["price"] > r["sma50"])
    total_sp = len(sp500_results)
    pct_above = round((above / total_sp) * 100, 1) if total_sp else None

    breadth_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe_size_requested": len(sp500),
        "universe_size_matched": total_sp,
        "pct_above_sma50": pct_above,
        "count_above_sma50": above,
        "note": (
            "Approximation of the 'S5FI'-style breadth reading (% of S&P 500 "
            "constituents above their 50-day moving average), computed from a "
            "community-maintained constituent list and Yahoo Finance chart data. "
            "Not an official index value."
        ),
    }
    os.makedirs(os.path.dirname(BREADTH_OUT), exist_ok=True)
    with open(BREADTH_OUT, "w") as f:
        json.dump(breadth_out, f, indent=2)
    print(f"Wrote {BREADTH_OUT}: {pct_above}% above 50DMA ({above}/{total_sp})")

    near_sma20 = [r for r in results.values() if "dist_sma20_pct" in r and abs(r["dist_sma20_pct"]) <= NEAR_MA_PCT]
    near_sma150 = [r for r in results.values() if "dist_sma150_pct" in r and abs(r["dist_sma150_pct"]) <= NEAR_MA_PCT]
    vol_surge = [r for r in results.values() if r.get("volume_ratio") and r["volume_ratio"] >= VOLUME_SURGE_RATIO]
    near_hi52 = [r for r in results.values() if r.get("dist_hi52_pct") is not None and r["dist_hi52_pct"] <= NEAR_52W_PCT]
    near_lo52 = [r for r in results.values() if r.get("dist_lo52_pct") is not None and r["dist_lo52_pct"] <= NEAR_52W_PCT]

    opp_out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe_size": matched,
        "universe_sources": {"sp500": len(sp500), "nasdaq100": len(nasdaq100)},
        "near_sma20": sorted(
            [{"symbol": r["symbol"], "price": r["price"], "dist_pct": round(r["dist_sma20_pct"], 2)} for r in near_sma20],
            key=lambda r: abs(r["dist_pct"])
        )[:MAX_LIST_SIZE],
        "near_sma150": sorted(
            [{"symbol": r["symbol"], "price": r["price"], "dist_pct": round(r["dist_sma150_pct"], 2)} for r in near_sma150],
            key=lambda r: abs(r["dist_pct"])
        )[:MAX_LIST_SIZE],
        "volume_surge": sorted(
            [{"symbol": r["symbol"], "price": r["price"], "ratio": round(r["volume_ratio"], 2)} for r in vol_surge],
            key=lambda r: r["ratio"], reverse=True
        )[:MAX_LIST_SIZE],
        "near_52w_high": sorted(
            [{"symbol": r["symbol"], "price": r["price"], "dist_pct": round(r["dist_hi52_pct"], 2)} for r in near_hi52],
            key=lambda r: r["dist_pct"]
        )[:MAX_LIST_SIZE],
        "near_52w_low": sorted(
            [{"symbol": r["symbol"], "price": r["price"], "dist_pct": round(r["dist_lo52_pct"], 2)} for r in near_lo52],
            key=lambda r: r["dist_pct"]
        )[:MAX_LIST_SIZE],
        "note": "Scanned from S&P 500 + Nasdaq 100 (deduplicated). Not stock advice - a starting point for your own research.",
    }
    with open(OPP_OUT, "w") as f:
        json.dump(opp_out, f, indent=2)
    print(f"Wrote {OPP_OUT}: {len(opp_out['near_sma20'])} near SMA20, "
          f"{len(opp_out['volume_surge'])} volume surges, "
          f"{len(opp_out['near_52w_high'])} near 52w high")


if __name__ == "__main__":
    main()
