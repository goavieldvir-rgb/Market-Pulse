#!/usr/bin/env python3
"""
The hard numbers for the Sunday Weekly Recap -> data/weekly_numbers.json

Everything here is computed from market data, never written by hand:
  - index closes and weekly % (S&P 500, Nasdaq Composite, Dow, Russell 2000)
  - equal-weight (RSP) vs cap-weight (SPY) for the week
  - all 11 SPDR sector ETFs for the week, plus semiconductors (SOXX)
  - 10-year Treasury yield (close, weekly change in basis points, week's high)
  - VIX, WTI and Brent oil, gold, bitcoin
  - the week's largest insider buys and sells from data/insiders.json

"Week" = the last completed trading week: the latest final daily close vs the
last close of the week before. Bitcoin trades every day, so it is measured
over the same calendar window (its close on the week's last trading day vs the
prior week's).

The written part of the recap (news, notable trades, calendar) is researched
separately and committed through a pull request; scripts/weekly_edition.py
copies this file into each edition so archived editions never change.

Standard library only.
"""
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (DATA_DIR, completed_bars, log, pct_change, read_json, rnd,  # noqa: E402
                    utc_now_iso, warn, write_json, yahoo_daily)

OUT = os.path.join(DATA_DIR, "weekly_numbers.json")

INDICES = [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow"), ("^RUT", "Russell 2000")]
# Approximate S&P 500 weights (%), used only to size the heatmap tiles.
SECTORS = [
    ("XLK", "Technology", 33), ("XLF", "Financials", 13), ("XLY", "Consumer Discretionary", 10),
    ("XLC", "Communication Services", 10), ("XLV", "Health Care", 9), ("XLI", "Industrials", 8),
    ("XLP", "Consumer Staples", 5), ("XLE", "Energy", 3), ("XLU", "Utilities", 2.5),
    ("XLRE", "Real Estate", 2), ("XLB", "Materials", 2),
]
OTHER = [("^VIX", "VIX"), ("CL=F", "WTI oil"), ("BZ=F", "Brent oil"), ("GC=F", "Gold"), ("BTC-USD", "Bitcoin")]


def week_window(bars):
    """(last_bar, prev_week_last_bar, this_week_bars) for the latest completed week."""
    if len(bars) < 6:
        return None, None, []
    last = bars[-1]
    d_last = date.fromisoformat(last["date"])
    monday = d_last - timedelta(days=d_last.weekday())
    this_week = [b for b in bars if date.fromisoformat(b["date"]) >= monday]
    before = [b for b in bars if date.fromisoformat(b["date"]) < monday]
    return last, (before[-1] if before else None), this_week


def weekly_block(symbol, name, ref_dates=None):
    chart = yahoo_daily(symbol, "3mo")
    if not chart:
        return None
    bars = completed_bars(chart)
    if ref_dates:  # 24/7 instruments: measure on the equity week's dates
        end_d, start_d = ref_dates
        upto = [b for b in bars if b["date"] <= end_d]
        prior = [b for b in bars if b["date"] <= start_d]
        if not upto or not prior:
            return None
        last, prev = upto[-1], prior[-1]
        this_week = [b for b in upto if b["date"] > start_d]
    else:
        last, prev, this_week = week_window(bars)
    if not last or not prev:
        return None
    return {
        "symbol": symbol, "name": name, "date": last["date"],
        "close": rnd(last["c"], 2), "prev_close": rnd(prev["c"], 2),
        "week_pct": rnd(pct_change(prev["c"], last["c"]), 2),
        "week_high": rnd(max(b["h"] for b in this_week), 2) if this_week else None,
        "week_low": rnd(min(b["l"] for b in this_week), 2) if this_week else None,
    }


def ten_year():
    chart = yahoo_daily("^TNX", "3mo")
    if not chart:
        return None
    last, prev, this_week = week_window(completed_bars(chart))
    if not last or not prev:
        return None
    # Yahoo has quoted ^TNX both as the yield (4.25) and as yield x10 (42.5).
    scale = 0.1 if last["c"] > 20 else 1.0
    return {
        "symbol": "^TNX", "name": "10-year Treasury yield", "date": last["date"],
        "close": rnd(last["c"] * scale, 3),
        "week_change_bp": rnd((last["c"] - prev["c"]) * scale * 100, 1),
        "week_high": rnd(max(b["h"] for b in this_week) * scale, 3) if this_week else None,
    }


def week_insiders(week_end):
    data = read_json(os.path.join(DATA_DIR, "insiders.json"), {}) or {}
    end = date.fromisoformat(week_end)
    start = end - timedelta(days=6)

    def in_week(t):
        f = t.get("filed") or t.get("date")
        try:
            return start <= date.fromisoformat(f[:10]) <= end + timedelta(days=2)
        except (TypeError, ValueError):
            return False

    def slim(t):
        return {k: t.get(k) for k in ("symbol", "insider", "role", "action", "value", "shares", "price", "date", "filed", "plan", "others")}

    buys = sorted([t for t in data.get("buys", []) if in_week(t)], key=lambda t: -(t.get("value") or 0))[:6]
    sells = sorted([t for t in data.get("sells", []) if in_week(t)], key=lambda t: -(t.get("value") or 0))[:6]
    return {"window": [start.isoformat(), end.isoformat()], "top_buys": [slim(t) for t in buys], "top_sells": [slim(t) for t in sells]}


def main():
    indices = [b for b in (weekly_block(s, n) for s, n in INDICES) if b]
    if not indices:
        raise SystemExit("ERROR: no index data from Yahoo; leaving the previous file in place.")
    week_end = indices[0]["date"]
    spy = weekly_block("SPY", "S&P 500 ETF")
    rsp = weekly_block("RSP", "Equal-weight S&P 500 ETF")

    sectors = []
    for sym, name, weight in SECTORS:
        b = weekly_block(sym, name)
        if b:
            b["weight"] = weight
            sectors.append(b)
        else:
            warn(f"Sector {sym} missing from this week's numbers")

    soxx = weekly_block("SOXX", "Semiconductors")
    ref = equity_week_dates()
    others = {}
    for sym, name in OTHER:
        b = weekly_block(sym, name, ref if sym == "BTC-USD" and ref else None)
        if b:
            others[sym] = b

    out = {
        "generated_at": utc_now_iso(),
        "week_ending": week_end,
        "indices": indices,
        "equal_weight": {
            "rsp_week_pct": rsp and rsp["week_pct"],
            "spy_week_pct": spy and spy["week_pct"],
        },
        "sectors": sectors,
        "semis": soxx,
        "rates": {"us10y": ten_year()},
        "vix": others.get("^VIX"),
        "commodities": [others[s] for s in ("CL=F", "BZ=F", "GC=F") if s in others],
        "crypto": others.get("BTC-USD"),
        "insiders": week_insiders(week_end),
        "notes": "Sector weights are approximate S&P 500 weights used only to size heatmap tiles.",
    }
    write_json(OUT, out)
    log(f"Wrote {OUT} for the week ending {week_end}: {len(indices)} indices, {len(sectors)} sectors")


def equity_week_dates():
    """(last trading date, prior week's last trading date) from SPY, for 24/7 instruments."""
    chart = yahoo_daily("SPY", "3mo")
    if not chart:
        return None
    last, prev, _ = week_window(completed_bars(chart))
    return (last["date"], prev["date"]) if last and prev else None


if __name__ == "__main__":
    main()
