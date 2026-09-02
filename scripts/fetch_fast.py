#!/usr/bin/env python3
"""
Fetches the "fast" indicators that can meaningfully change intraday:
  - SPY / QQQ price, distance from SMA150, win/loss streak
  - VIX level
  - Sector rotation ratios (XLU/XLP vs XLY) - defensive vs cyclical
  - All 11 SPDR sector ETFs, ranked by momentum (breakout leaderboard)
  - Market participation proxy (RSP equal-weight vs SPY cap-weight)
  - CNN Fear & Greed Index (unofficial public endpoint)

Writes data/fast.json. Designed to run every ~15 minutes via GitHub Actions.
No API key required - uses Yahoo Finance's public chart endpoint and CNN's
public (unofficial) Fear & Greed data endpoint.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fast.json")


def get_json(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_history(symbol, range_="1y", interval="1d"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={range_}&interval={interval}")
    try:
        data = get_json(url)
    except Exception as e:
        print(f"WARN: failed to fetch {symbol}: {e}", file=sys.stderr)
        return []
    try:
        result = data["chart"]["result"][0]
        timestamps = result["timestamp"]
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, TypeError, IndexError):
        print(f"WARN: unexpected shape for {symbol}", file=sys.stderr)
        return []
    out = []
    for ts, c in zip(timestamps, closes):
        if c is None:
            continue
        d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        out.append((d, c))
    return out


def sma(values, window):
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def streak(closes):
    if len(closes) < 2:
        return None, 0
    diffs = []
    for i in range(1, len(closes)):
        diffs.append(1 if closes[i] > closes[i - 1] else (-1 if closes[i] < closes[i - 1] else 0))
    direction = diffs[-1]
    if direction == 0:
        return "flat", 0
    count = 0
    for d in reversed(diffs):
        if d == direction:
            count += 1
        else:
            break
    return ("green" if direction == 1 else "red"), count


def pct_change(a, b):
    if a in (0, None) or b is None:
        return None
    return (b - a) / a * 100.0


def build_symbol_block(symbol):
    hist = fetch_history(symbol)
    if not hist:
        return None
    closes = [c for _, c in hist]
    last_date, last_close = hist[-1]
    sma150 = sma(closes, 150)
    dist_pct = pct_change(sma150, last_close) if sma150 else None
    dirn, cnt = streak(closes)
    ret_5d = pct_change(closes[-6], last_close) if len(closes) >= 6 else None
    ret_20d = pct_change(closes[-21], last_close) if len(closes) >= 21 else None
    return {
        "symbol": symbol,
        "date": last_date,
        "close": round(last_close, 2),
        "sma150": round(sma150, 2) if sma150 else None,
        "distance_from_sma150_pct": round(dist_pct, 2) if dist_pct is not None else None,
        "streak_direction": dirn,
        "streak_count": cnt,
        "return_5d_pct": round(ret_5d, 2) if ret_5d is not None else None,
        "return_20d_pct": round(ret_20d, 2) if ret_20d is not None else None,
    }


def fetch_fear_greed():
    from datetime import timedelta
    start_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    url = f"https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{start_date}"
    cnn_headers = dict(HEADERS)
    cnn_headers["Referer"] = "https://www.cnn.com/markets/fear-and-greed"
    cnn_headers["Accept"] = "application/json"
    try:
        req = urllib.request.Request(url, headers=cnn_headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))

        fg = data.get("fear_and_greed")
        if fg and fg.get("score") is not None:
            return {"score": round(float(fg["score"]), 1), "rating": fg.get("rating")}

        hist = data.get("fear_and_greed_historical", {}).get("data", [])
        if hist:
            latest = hist[-1]
            return {"score": round(float(latest["y"]), 1), "rating": latest.get("rating")}

        print("WARN: fear & greed response had neither current nor historical data", file=sys.stderr)
        return None
    except Exception as e:
        print(f"WARN: fear & greed fetch failed: {e}", file=sys.stderr)
        return None


def main():
    all_sectors = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLRE", "XLC", "XLU"]
    symbols = ["SPY", "QQQ", "^VIX", "RSP"] + all_sectors
    blocks = {}
    for s in symbols:
        b = build_symbol_block(s)
        if b:
            blocks[s] = b

    sector_names = {
        "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care",
        "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", "XLE": "Energy",
        "XLI": "Industrials", "XLB": "Materials", "XLRE": "Real Estate",
        "XLC": "Communication Services", "XLU": "Utilities",
    }

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spy": blocks.get("SPY"),
        "qqq": blocks.get("QQQ"),
        "vix": blocks.get("^VIX"),
        "sectors": {
            "XLP": blocks.get("XLP"),
            "XLU": blocks.get("XLU"),
            "XLY": blocks.get("XLY"),
        },
        "participation": {
            "RSP": blocks.get("RSP"),
            "SPY": blocks.get("SPY"),
        },
        "fear_greed": fetch_fear_greed(),
    }

    sector_rows = []
    for sym in all_sectors:
        b = blocks.get(sym)
        if not b:
            continue
        sector_rows.append({
            "symbol": sym,
            "name": sector_names.get(sym, sym),
            "close": b.get("close"),
            "return_5d_pct": b.get("return_5d_pct"),
            "return_20d_pct": b.get("return_20d_pct"),
            "distance_from_sma150_pct": b.get("distance_from_sma150_pct"),
        })
    sector_rows.sort(key=lambda r: (r["return_5d_pct"] if r["return_5d_pct"] is not None else -999), reverse=True)
    out["sector_breakout"] = sector_rows

    xlu = blocks.get("XLU")
    xlp = blocks.get("XLP")
    xly = blocks.get("XLY")
    if xlu and xlp and xly:
        defensive_avg_5d = None
        vals = [v["return_5d_pct"] for v in (xlu, xlp) if v.get("return_5d_pct") is not None]
        if vals:
            defensive_avg_5d = sum(vals) / len(vals)
        cyclical_5d = xly.get("return_5d_pct")
        spread = None
        if defensive_avg_5d is not None and cyclical_5d is not None:
            spread = round(defensive_avg_5d - cyclical_5d, 2)
        out["sector_rotation"] = {
            "defensive_avg_return_5d_pct": round(defensive_avg_5d, 2) if defensive_avg_5d is not None else None,
            "cyclical_return_5d_pct": cyclical_5d,
            "defensive_minus_cyclical_5d_pct": spread,
        }

    rsp = blocks.get("RSP")
    spy = blocks.get("SPY")
    if rsp and spy and rsp.get("return_20d_pct") is not None and spy.get("return_20d_pct") is not None:
        out["participation"]["rsp_minus_spy_20d_pct"] = round(
            rsp["return_20d_pct"] - spy["return_20d_pct"], 2
        )

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
