#!/usr/bin/env python3
"""
The "fast" indicators - everything that moves intraday:
  - SPY / QQQ price, distance from the 150-day SMA, up/down-day streak
  - VIX level and where it sits in its 1-year range
  - Participation: equal-weight RSP vs cap-weight SPY over 20 sessions
  - Defensive rotation: Utilities + Staples vs Discretionary over 20 sessions
  - All 11 SPDR sector ETFs for the Opportunity Scanner leaderboard
  - CNN Fear & Greed

Writes data/fast.json. Run once with `python3 scripts/fetch_fast.py`, or let
scripts/fast_session.py call build() every few minutes through the session.

Accuracy notes:
  - Dates are exchange-local (New York), not UTC.
  - Streaks count completed sessions only; while the market is open, today's
    move is reported separately (change_pct / in_session).
  - Prices, SMA distance and 5/20-day returns use the live price mid-session.
"""
import os
import time
from datetime import datetime, timedelta, timezone

from common import (DATA_DIR, http_json, iso_from_ts, last_bar_is_final, log,
                    market_state, pct_change, read_json, rnd, utc_now_iso,
                    warn, write_json, yahoo_daily)

OUT_PATH = os.path.join(DATA_DIR, "fast.json")

SECTOR_NAMES = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care",
    "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", "XLE": "Energy",
    "XLI": "Industrials", "XLB": "Materials", "XLRE": "Real Estate",
    "XLC": "Communication Services", "XLU": "Utilities",
}
SECTORS = list(SECTOR_NAMES)
SYMBOLS = ["SPY", "QQQ", "^VIX", "RSP"] + SECTORS
REQUIRED = ("SPY", "^VIX")  # without these the file would be misleading - keep the old one

CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{start}"
CNN_HEADERS = {"Referer": "https://www.cnn.com/markets/fear-and-greed", "Accept": "application/json"}


def streak(closes):
    """(direction, count) of consecutive up or down closes at the end of the series."""
    if len(closes) < 2:
        return None, 0
    diffs = [1 if b > a else (-1 if b < a else 0) for a, b in zip(closes, closes[1:])]
    direction = diffs[-1]
    if direction == 0:
        return "flat", 0
    count = 0
    for d in reversed(diffs):
        if d != direction:
            break
        count += 1
    return ("green" if direction == 1 else "red"), count


def percentile_rank(values, current):
    """% of values that are <= current (current included)."""
    if not values or current is None:
        return None
    return round(sum(1 for v in values if v <= current) / len(values) * 100, 1)


def symbol_block(symbol, chart, now):
    bars = chart["bars"]
    if len(bars) < 22:
        return None
    meta = chart["meta"]
    final = last_bar_is_final(chart, now)
    closes = [b["c"] for b in bars]
    live = meta.get("regularMarketPrice")
    if not final and isinstance(live, (int, float)) and live > 0:
        closes[-1] = float(live)
    completed = closes if final else closes[:-1]
    price, prev_close = closes[-1], closes[-2]
    sma150 = sum(closes[-150:]) / 150 if len(closes) >= 150 else None
    direction, count = streak(completed)
    as_of = meta.get("regularMarketTime")
    return {
        "symbol": symbol,
        "date": bars[-1]["date"],
        "close": round(price, 2),              # live price while the session is open
        "prev_close": round(prev_close, 2),
        "change_pct": rnd(pct_change(prev_close, price)),
        "in_session": not final,
        "as_of": iso_from_ts(as_of) if isinstance(as_of, (int, float)) else None,
        "sma150": rnd(sma150),
        "distance_from_sma150_pct": rnd(pct_change(sma150, price)),
        "streak_direction": direction,
        "streak_count": count,
        "streak_through": bars[-1]["date"] if final else bars[-2]["date"],
        "return_5d_pct": rnd(pct_change(closes[-6], price)),
        "return_20d_pct": rnd(pct_change(closes[-21], price)),
        "percentile_1y": percentile_rank(closes[-252:], price),
    }


def fetch_fear_greed():
    start = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    try:
        data = http_json(CNN_URL.format(start=start), headers=CNN_HEADERS, timeout=15)
    except Exception as e:
        log(f"WARN: Fear & Greed fetch failed: {e}")
        return None
    fg = data.get("fear_and_greed") or {}
    score, rating, ts = fg.get("score"), fg.get("rating"), fg.get("timestamp")
    if score is None:
        hist = ((data.get("fear_and_greed_historical") or {}).get("data")) or []
        if not hist:
            return None
        score, rating, ts = hist[-1].get("y"), hist[-1].get("rating"), hist[-1].get("x")
    if isinstance(ts, (int, float)):  # epoch milliseconds
        ts = iso_from_ts(ts / 1000)
    try:
        score = round(float(score), 1)
    except (TypeError, ValueError):
        return None
    if not 0 <= score <= 100:
        return None
    return {"score": score, "rating": rating, "as_of": ts,
            "previous_close": rnd(fg.get("previous_close"), 1),
            "previous_1_week": rnd(fg.get("previous_1_week"), 1)}


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def build(previous=None, now=None):
    """Returns the fast.json payload, or None if the core symbols failed."""
    now = time.time() if now is None else now
    previous = previous or {}
    charts, blocks = {}, {}
    for sym in SYMBOLS:
        chart = yahoo_daily(sym, "1y")
        if chart:
            charts[sym] = chart
            block = symbol_block(sym, chart, now)
            if block:
                blocks[sym] = block
    missing = [s for s in REQUIRED if s not in blocks]
    if missing:
        warn(f"Yahoo returned no usable data for {', '.join(missing)} - keeping the previous fast.json")
        return None

    state, start, end = market_state(charts["SPY"], now)

    fear_greed = fetch_fear_greed()
    if fear_greed is None and previous.get("fear_greed"):
        fear_greed = dict(previous["fear_greed"], carried_forward=True)
        log("Fear & Greed unavailable this run - carrying the previous reading forward")

    out = {
        "generated_at": utc_now_iso(),
        "market": {
            "state": state,
            "session_open": iso_from_ts(start),
            "session_close": iso_from_ts(end),
            "as_of": blocks["SPY"]["as_of"],
            "session_date": blocks["SPY"]["date"],
        },
        "spy": blocks.get("SPY"),
        "qqq": blocks.get("QQQ"),
        "vix": blocks.get("^VIX"),
        "sectors": {s: blocks.get(s) for s in ("XLP", "XLU", "XLY")},
        "participation": {"RSP": blocks.get("RSP"), "SPY": blocks.get("SPY")},
        "fear_greed": fear_greed,
    }

    rows = []
    for sym in SECTORS:
        b = blocks.get(sym)
        if b:
            rows.append({
                "symbol": sym, "name": SECTOR_NAMES[sym], "close": b["close"],
                "change_pct": b["change_pct"],
                "return_5d_pct": b["return_5d_pct"], "return_20d_pct": b["return_20d_pct"],
                "distance_from_sma150_pct": b["distance_from_sma150_pct"],
            })
    rows.sort(key=lambda r: r["return_5d_pct"] if r["return_5d_pct"] is not None else -999, reverse=True)
    out["sector_breakout"] = rows

    rot = {}
    for days in (5, 20):
        key = f"return_{days}d_pct"
        defensive = _avg([(blocks.get(s) or {}).get(key) for s in ("XLU", "XLP")])
        cyclical = (blocks.get("XLY") or {}).get(key)
        rot[f"defensive_avg_return_{days}d_pct"] = rnd(defensive)
        rot[f"cyclical_return_{days}d_pct"] = rnd(cyclical)
        rot[f"defensive_minus_cyclical_{days}d_pct"] = (
            rnd(defensive - cyclical) if defensive is not None and cyclical is not None else None)
    out["sector_rotation"] = rot

    rsp, spy = blocks.get("RSP"), blocks.get("SPY")
    if rsp and spy and rsp["return_20d_pct"] is not None and spy["return_20d_pct"] is not None:
        out["participation"]["rsp_minus_spy_20d_pct"] = rnd(rsp["return_20d_pct"] - spy["return_20d_pct"])

    failed = [s for s in SYMBOLS if s not in blocks]
    if failed:
        out["missing_symbols"] = failed
        log(f"WARN: no data this run for {', '.join(failed)}")
    return out


def main():
    previous = read_json(OUT_PATH, {}) or {}
    out = build(previous)
    if out is None:
        return
    write_json(OUT_PATH, out)
    spy = out["spy"]
    log(f"Wrote {OUT_PATH}: market {out['market']['state']}, SPY {spy['close']} "
        f"({spy['distance_from_sma150_pct']}% vs SMA150), VIX {out['vix']['close']}")


if __name__ == "__main__":
    main()
