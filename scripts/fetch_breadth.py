#!/usr/bin/env python3
"""
Daily scan of the S&P 500 + Nasdaq-100 (deduplicated), one Yahoo request per
ticker, producing two files:

1. data/breadth.json - % of S&P 500 members above their 50-day SMA (an
   S5FI-style reading), plus the same reading for each of the past ~260
   sessions so the dashboard can show where today sits in the past year.
2. data/opportunities.json - per-ticker stats for the Opportunity Scanner:
   SMAs, 52-week high/low (intraday), last session's volume vs its 20-day
   average and last session's % change. Thresholds are applied in the browser.

Only completed sessions are used, so a manual run during market hours does
not mix a half-finished day into the stats.
"""
import os
import sys
import time

from common import (DATA_DIR, completed_bars, fetch_universe, log, pct_change,
                    rnd, utc_now_iso, warn, write_json, yahoo_daily)

BREADTH_OUT = os.path.join(DATA_DIR, "breadth.json")
OPP_OUT = os.path.join(DATA_DIR, "opportunities.json")

SMA_PERIODS = [10, 20, 50, 100, 150, 200]
SERIES_SESSIONS = 260          # ~1 year of daily breadth readings
REQUEST_PAUSE = 0.15           # be polite to Yahoo


def analyze(symbol, bars):
    """Scanner stats from completed daily bars (oldest first)."""
    if len(bars) < 60:
        return None
    closes = [b["c"] for b in bars]
    vols = [b["v"] for b in bars]
    price = closes[-1]
    out = {"symbol": symbol, "price": round(price, 2), "sma": {}}
    for p in SMA_PERIODS:
        if len(closes) >= p:
            out["sma"][str(p)] = round(sum(closes[-p:]) / p, 2)
    window = bars[-252:]
    hi52 = max(b["h"] for b in window)
    lo52 = min(b["l"] for b in window)
    out["hi52"] = round(hi52, 2)
    out["lo52"] = round(lo52, 2)
    out["dist_hi52_pct"] = rnd((hi52 - price) / hi52 * 100) if hi52 else None
    out["dist_lo52_pct"] = rnd((price - lo52) / lo52 * 100) if lo52 else None
    out["chg_1d_pct"] = rnd(pct_change(closes[-2], closes[-1]))
    base = vols[-21:-1]
    avg_vol = sum(base) / len(base) if len(base) == 20 else 0
    out["volume_ratio"] = rnd(vols[-1] / avg_vol) if avg_vol > 0 and vols[-1] > 0 else None
    out["as_of"] = bars[-1]["date"]
    return out


def above_sma50_by_date(bars):
    """{date: bool} - was the close above its own 50-day SMA on that date?"""
    closes = [b["c"] for b in bars]
    out, running = {}, 0.0
    for i, c in enumerate(closes):
        running += c
        if i >= 50:
            running -= closes[i - 50]
        if i >= 49:
            out[bars[i]["date"]] = c > running / 50
    return out


def main():
    sp500, ndx = fetch_universe()
    sp500_set = set(sp500)
    universe = sorted(sp500_set | set(ndx))
    if not universe:
        warn("Empty universe (both constituent lists failed) - nothing scanned")
        return

    results, flags_by_symbol, failed = {}, {}, 0
    for i, sym in enumerate(universe):
        chart = yahoo_daily(sym, "2y")
        time.sleep(REQUEST_PAUSE)
        if not chart:
            failed += 1
            continue
        bars = completed_bars(chart)
        stats = analyze(sym, bars)
        if not stats:
            failed += 1
            continue
        results[sym] = stats
        if sym in sp500_set:
            flags_by_symbol[sym] = above_sma50_by_date(bars)
        if (i + 1) % 100 == 0:
            log(f"...{i + 1}/{len(universe)} scanned")

    matched = len(results)
    log(f"Scanned {matched}/{len(universe)} tickers ({failed} failed)")
    if matched < len(universe) * 0.5:
        warn(f"Only {matched}/{len(universe)} tickers returned data - keeping the previous scan")
        return

    # The session the scan describes = the most common latest date.
    dates = [r["as_of"] for r in results.values()]
    as_of = max(set(dates), key=dates.count)

    # ---- breadth.json
    sp_ok = [s for s in sp500 if s in results and "50" in results[s]["sma"]]
    if sp500 and len(sp_ok) >= 0.8 * len(sp500):
        above = sum(1 for s in sp_ok if results[s]["price"] > results[s]["sma"]["50"])
        per_date_total, per_date_above = {}, {}
        for flags in flags_by_symbol.values():
            for d, is_above in flags.items():
                per_date_total[d] = per_date_total.get(d, 0) + 1
                per_date_above[d] = per_date_above.get(d, 0) + (1 if is_above else 0)
        full = max(per_date_total.values()) if per_date_total else 0
        series = [{"d": d, "v": round(per_date_above[d] / per_date_total[d] * 100, 1)}
                  for d in sorted(per_date_total)
                  if per_date_total[d] >= 0.9 * full and d <= as_of][-SERIES_SESSIONS:]
        write_json(BREADTH_OUT, {
            "generated_at": utc_now_iso(),
            "as_of": as_of,
            "universe_size_requested": len(sp500),
            "universe_size_matched": len(sp_ok),
            "pct_above_sma50": round(above / len(sp_ok) * 100, 1),
            "count_above_sma50": above,
            "series": series,
            "note": ("Approximation of the S5FI reading (% of S&P 500 members above their "
                     "50-day moving average) from a community-maintained constituent list and "
                     "Yahoo Finance daily closes. Not an official index value."),
        })
        log(f"Wrote {BREADTH_OUT}: {above}/{len(sp_ok)} above 50DMA as of {as_of}; {len(series)} days of history")
    else:
        warn(f"Only {len(sp_ok)}/{len(sp500)} S&P 500 members scanned - breadth not updated")

    # ---- opportunities.json
    stocks = [results[s] for s in sorted(results)]
    write_json(OPP_OUT, {
        "generated_at": utc_now_iso(),
        "as_of": as_of,
        "universe_size": matched,
        "universe_sources": {"sp500": len(sp500), "nasdaq100": len(ndx)},
        "sma_periods": SMA_PERIODS,
        "stocks": stocks,
        "note": "S&P 500 + Nasdaq-100 (deduplicated), completed sessions only. Not stock advice.",
    }, compact=True)
    log(f"Wrote {OPP_OUT}: {len(stocks)} stocks as of {as_of}")


if __name__ == "__main__":
    sys.exit(main())
