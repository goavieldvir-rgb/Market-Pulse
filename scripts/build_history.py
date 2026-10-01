#!/usr/bin/env python3
"""
Rebuilds data/daily_history.json: one row per completed session for the past
~year with the raw reading of every scored signal on that day's close.

The dashboard turns these readings into scores with the SAME JavaScript that
scores the live cards, so the trend line can never drift from the gauge, and
a change to the scoring automatically applies to the whole history.

Sources:
  - Yahoo daily closes: SPY, RSP, ^VIX, XLU, XLP, XLY (computed exactly like fast.json)
  - data/breadth.json "series" (written by fetch_breadth.py earlier in the job)
  - CNN Fear & Greed daily history
  - data/aaii.json weekly history (each reading applies from the day after its survey week)

Run after fetch_breadth.py and fetch_aaii.py.
"""
import bisect
import os
from datetime import date, datetime, timedelta, timezone

from common import (DATA_DIR, completed_bars, http_json, log, read_json, rnd,
                    utc_now_iso, warn, write_json, yahoo_daily)
from fetch_fast import CNN_HEADERS, CNN_URL

OUT_PATH = os.path.join(DATA_DIR, "daily_history.json")
SESSIONS = 260


def closes_by_date(symbol):
    chart = yahoo_daily(symbol, "2y")
    if not chart:
        return None
    return {b["date"]: b["c"] for b in completed_bars(chart)}


def fear_greed_by_date():
    start = (datetime.now(timezone.utc) - timedelta(days=400)).strftime("%Y-%m-%d")
    try:
        data = http_json(CNN_URL.format(start=start), headers=CNN_HEADERS, timeout=20)
    except Exception as e:
        log(f"WARN: Fear & Greed history unavailable: {e}")
        return {}
    out = {}
    for p in ((data.get("fear_and_greed_historical") or {}).get("data")) or []:
        x, y = p.get("x"), p.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and 0 <= y <= 100:
            out[datetime.fromtimestamp(x / 1000, timezone.utc).date().isoformat()] = round(float(y), 1)
    return out


def aaii_lookup():
    """Function date -> bull-bear spread in force on that date (or None)."""
    hist = (read_json(os.path.join(DATA_DIR, "aaii.json"), {}) or {}).get("history") or []
    points = []
    for h in hist:
        try:
            effective = (date.fromisoformat(h["date"]) + timedelta(days=1)).isoformat()
            points.append((effective, round(h["bullish"] - h["bearish"], 1)))
        except (KeyError, TypeError, ValueError):
            continue
    points.sort()
    keys = [p[0] for p in points]

    def lookup(d):
        i = bisect.bisect_right(keys, d) - 1
        if i < 0:
            return None
        # a reading goes stale if AAII skipped a couple of weeks
        if (date.fromisoformat(d) - date.fromisoformat(keys[i])).days > 14:
            return None
        return points[i][1]
    return lookup


def main():
    series = {}
    for sym in ("SPY", "RSP", "^VIX", "XLU", "XLP", "XLY"):
        s = closes_by_date(sym)
        if s is None:
            if sym in ("SPY", "^VIX"):
                warn(f"History: {sym} unavailable - keeping the previous daily_history.json")
                return
            s = {}
        series[sym] = s

    spy_dates = sorted(series["SPY"])
    spy = [series["SPY"][d] for d in spy_dates]
    breadth = {p["d"]: p["v"] for p in
               ((read_json(os.path.join(DATA_DIR, "breadth.json"), {}) or {}).get("series") or [])}
    fear_greed = fear_greed_by_date()
    aaii_at = aaii_lookup()

    def ret(sym, i, n):
        """n-session return of `sym` ending on spy_dates[i] (aligned on SPY's calendar)."""
        if i - n < 0:
            return None
        a, b = series[sym].get(spy_dates[i - n]), series[sym].get(spy_dates[i])
        return (b - a) / a * 100 if a and b else None

    rows = []
    for i in range(max(0, len(spy_dates) - SESSIONS), len(spy_dates)):
        d = spy_dates[i]
        sma150 = sum(spy[i - 149:i + 1]) / 150 if i >= 149 else None
        rsp20, spy20 = ret("RSP", i, 20), ret("SPY", i, 20)
        xlu20, xlp20, xly20 = ret("XLU", i, 20), ret("XLP", i, 20), ret("XLY", i, 20)
        row = {
            "d": d,
            "trend": rnd((spy[i] - sma150) / sma150 * 100) if sma150 else None,
            "vix": rnd(series["^VIX"].get(d)),
            "participation": rnd(rsp20 - spy20) if rsp20 is not None and spy20 is not None else None,
            "rotation": (rnd((xlu20 + xlp20) / 2 - xly20)
                         if None not in (xlu20, xlp20, xly20) else None),
            "breadth": breadth.get(d),
            "feargreed": fear_greed.get(d),
            "aaii": aaii_at(d),
        }
        rows.append(row)

    write_json(OUT_PATH, {
        "generated_at": utc_now_iso(),
        "note": "Raw daily readings on each session's close; the dashboard scores them with the live scoring rules.",
        "days": rows,
    }, compact=True)
    filled = {k: sum(1 for r in rows if r[k] is not None) for k in rows[0] if k != "d"} if rows else {}
    log(f"Wrote {OUT_PATH}: {len(rows)} sessions ({rows[0]['d'] if rows else '-'} .. {rows[-1]['d'] if rows else '-'}); "
        f"filled per signal: {filled}")


if __name__ == "__main__":
    main()
