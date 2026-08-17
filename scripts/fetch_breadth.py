#!/usr/bin/env python3
"""
Computes an approximation of the "S5FI" style breadth reading: the percentage
of S&P 500 constituents trading above their 50-day moving average.

There is no free, direct API for this exact figure, so we compute it ourselves:
  1. Pull the current S&P 500 constituent list from a public, community-maintained
     dataset (github.com/datasets/s-and-p-500-companies).
  2. Batch-query Yahoo Finance's public quote endpoint, which conveniently returns
     `fiftyDayAverage` directly alongside the live price - no need to pull full
     history per ticker.
  3. % above 50DMA = count(price > fiftyDayAverage) / count(valid tickers) * 100

This is run once a day (breadth doesn't swing meaningfully within a day) to stay
well clear of any informal rate limits on the public endpoints.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
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


def chunked(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch_quotes(symbols):
    """Batch quote lookup. Returns dict symbol -> {price, fiftyDayAverage}."""
    out = {}
    for batch in chunked(symbols, 40):
        qs = urllib.parse.urlencode({"symbols": ",".join(batch)})
        url = f"https://query1.finance.yahoo.com/v7/finance/quote?{qs}"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            for item in data.get("quoteResponse", {}).get("result", []):
                sym = item.get("symbol")
                price = item.get("regularMarketPrice")
                sma50 = item.get("fiftyDayAverage")
                if sym and price is not None and sma50 is not None:
                    out[sym] = {"price": price, "sma50": sma50}
        except Exception as e:
            print(f"WARN: batch quote failed ({batch[0]}..{batch[-1]}): {e}", file=sys.stderr)
        time.sleep(1)  # be polite between batches
    return out


def main():
    try:
        tickers = fetch_constituents()
    except Exception as e:
        print(f"ERROR: could not fetch constituent list: {e}", file=sys.stderr)
        sys.exit(0)  # fail soft - keep previous breadth.json rather than crash the workflow

    if not tickers:
        print("ERROR: empty constituent list", file=sys.stderr)
        sys.exit(0)

    quotes = fetch_quotes(tickers)
    total = len(quotes)
    above = sum(1 for v in quotes.values() if v["price"] > v["sma50"])
    pct_above = round((above / total) * 100, 1) if total else None

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "universe_size_requested": len(tickers),
        "universe_size_matched": total,
        "pct_above_sma50": pct_above,
        "count_above_sma50": above,
        "note": (
            "Approximation of the 'S5FI'-style breadth reading (% of S&P 500 "
            "constituents above their 50-day moving average), computed from a "
            "community-maintained constituent list and Yahoo Finance quote data. "
            "Not an official index value."
        ),
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT_PATH}: {pct_above}% above 50DMA ({above}/{total})")


if __name__ == "__main__":
    main()
