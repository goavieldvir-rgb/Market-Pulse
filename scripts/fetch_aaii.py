#!/usr/bin/env python3
"""
AAII publishes its weekly Bullish/Neutral/Bearish sentiment survey numbers
for free, publicly, on aaii.com. Scraped best-effort - fails soft if their
page layout changes.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "aaii.json")
URL = "https://www.aaii.com/sentimentsurvey"


def fetch_html(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")


def extract_pct(html, label):
    patterns = [
        rf"{label}[^0-9%]{{0,40}}?(\d{{1,2}}\.\d)\s*%",
        rf"(\d{{1,2}}\.\d)\s*%[^a-zA-Z]{{0,10}}{label}",
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return None


def main():
    try:
        html = fetch_html(URL)
    except Exception as e:
        print(f"WARN: could not fetch AAII page: {e}", file=sys.stderr)
        sys.exit(0)

    bullish = extract_pct(html, "Bullish")
    neutral = extract_pct(html, "Neutral")
    bearish = extract_pct(html, "Bearish")

    if bullish is None or bearish is None:
        print("WARN: could not parse AAII numbers - site layout may have changed", file=sys.stderr)
        sys.exit(0)

    spread = round(bullish - bearish, 1) if (bullish is not None and bearish is not None) else None

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bullish_pct": bullish,
        "neutral_pct": neutral,
        "bearish_pct": bearish,
        "bull_bear_spread": spread,
        "source": URL,
        "note": "AAII updates this survey weekly (Thursdays). Scraped best-effort from AAII's public page.",
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT_PATH}: bullish={bullish} bearish={bearish} spread={spread}")


if __name__ == "__main__":
    main()
