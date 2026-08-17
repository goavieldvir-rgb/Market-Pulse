#!/usr/bin/env python3
"""
Computes an approximation of the "S5FI" style breadth reading: the percentage
of S&P 500 constituents trading above their 50-day moving average.
 
There is no free, direct API for this exact figure, so we compute it ourselves:
  1. Pull the current S&P 500 constituent list from a public, community-maintained
     dataset (github.com/datasets/s-and-p-500-companies).
  2. For each ticker, pull ~4 months of daily closes from Yahoo Finance's public
     CHART endpoint (v8/finance/chart) - the same endpoint fetch_fast.py uses
     successfully. We deliberately avoid the v7/finance/quote endpoint: Yahoo
     added a crumb/cookie requirement to it, so unauthenticated batch requests
     silently return nothing.
  3. Compute each stock's 50-day SMA ourselves from those closes.
  4. % above 50DMA = count(price > sma50) / count(valid tickers) * 100
 
Run once a day - breadth doesn't swing meaningfully within a day, and this
keeps ~500 sequential requests well clear of any informal rate limits.
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
 
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "breadth.json")
CONSTITUENTS_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
 
 
def fetch_constituents():
    req = urllib.request.Request(CONSTITUENTS_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        text = r.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    tickers = []
    for row in reader:
        sym = row.get("Symbol") or row.get("symbol")
        if sym:
            # Yahoo uses '-' instead of '.' for share classes, e.g. BRK.B -> BRK-B
            tickers.append(sym.strip().replace(".", "-"))
    return tickers
 
 
def price_vs_sma50(symbol, retries=2):
    """Returns (price, sma50) or None using the public chart endpoint."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=4mo&interval=1d"
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            result = data["chart"]["result"][0]
            closes = [c for c in result["indicators"]["quote"][0]["close"] if c is not None]
            if len(closes) < 50:
                return None
            price = closes[-1]
            sma50 = sum(closes[-50:]) / 50
            return price, sma50
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except Exception:
            return None
    return None
 
 
def main():
    try:
        tickers = fetch_constituents()
    except Exception as e:
        print(f"ERROR: could not fetch constituent list: {e}", file=sys.stderr)
        sys.exit(0)  # fail soft - keep previous breadth.json rather than crash the workflow
 
    if not tickers:
        print("ERROR: empty constituent list", file=sys.stderr)
        sys.exit(0)
 
    above = 0
    matched = 0
    failed = []
    for i, sym in enumerate(tickers):
        res = price_vs_sma50(sym)
        if res is None:
            failed.append(sym)
            continue
        price, sma50 = res
        matched += 1
        if price > sma50:
            above += 1
        # brief pause to stay well clear of informal rate limits over ~500 requests
        time.sleep(0.15)
        if (i + 1) % 100 == 0:
            print(f"...{i + 1}/{len(tickers)} processed", file=sys.stderr)
 
    pct_above = round((above / matched) * 100, 1) if matched else None
 
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe_size_requested": len(tickers),
        "universe_size_matched": matched,
        "pct_above_sma50": pct_above,
        "count_above_sma50": above,
        "note": (
            "Approximation of the 'S5FI'-style breadth reading (% of S&P 500 "
            "constituents above their 50-day moving average), computed from a "
            "community-maintained constituent list and Yahoo Finance chart data. "
            "Not an official index value."
        ),
    }
 
    if failed:
        print(f"WARN: {len(failed)} tickers failed to fetch (sample: {failed[:10]})", file=sys.stderr)
 
    # Only overwrite if we got a reasonably complete read - a mostly-failed run
    # (e.g. transient blocking) shouldn't clobber a good prior value with junk.
    if matched < len(tickers) * 0.5:
        print(f"ERROR: only matched {matched}/{len(tickers)} tickers - skipping write to avoid a bad overwrite", file=sys.stderr)
        sys.exit(0)
 
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT_PATH}: {pct_above}% above 50DMA ({above}/{matched})")
 
 
if __name__ == "__main__":
    main()
