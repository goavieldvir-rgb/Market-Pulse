#!/usr/bin/env python3
"""
Appends today's composite contrarian score and breadth reading to a rolling
history file (data/history.json), so the dashboard can show:
  - a small trend sparkline for the composite score over the last ~30-90 days
  - a percentile for today's breadth reading ("today is higher than X% of
    the last N days") once enough history has accumulated

Run once a day (as part of update-slow.yml, after fast/breadth/aaii are all
fresh) so each day gets exactly one snapshot, taken at a consistent point
after the market close.

IMPORTANT: the composite-score formula here must be kept in sync with the
one in index.html's client-side JS (search for "scores.push" in index.html).
This is unavoidable duplication for a static site with no shared backend -
if you change the weighting in one place, mirror it here too, or the
sparkline will silently drift from what the gauge actually shows "live".
"""
import json
import os
import sys
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
MAX_HISTORY_DAYS = 120


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def load_json(name):
    path = os.path.join(DATA_DIR, name)
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"WARN: could not read {name}: {e}", file=sys.stderr)
        return None


def compute_composite(fast, breadth, aaii):
    """Mirrors the per-card scoring logic in index.html's JS. Returns None
    if there isn't enough data to compute a meaningful score."""
    scores = []

    spy = (fast or {}).get("spy") or {}
    d = spy.get("distance_from_sma150_pct")
    if d is not None:
        scores.append(clamp(-d * 6, -100, 100))

    spread = (aaii or {}).get("bull_bear_spread")
    if spread is not None:
        scores.append(clamp(-spread * 3, -100, 100))

    vix = (fast or {}).get("vix") or {}
    vix_close = vix.get("close")
    if vix_close is not None:
        scores.append(clamp((vix_close - 18) * 5, -100, 100))

    rel = ((fast or {}).get("participation") or {}).get("rsp_minus_spy_20d_pct")
    if rel is not None:
        scores.append(clamp(rel * 12, -100, 100))

    pct = (breadth or {}).get("pct_above_sma50")
    if pct is not None:
        scores.append(clamp((45 - pct) * 3, -100, 100))

    fg = ((fast or {}).get("fear_greed") or {}).get("score")
    if fg is not None:
        scores.append(clamp((50 - fg) * 2.2, -100, 100))

    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def main():
    fast = load_json("fast.json")
    breadth = load_json("breadth.json")
    aaii = load_json("aaii.json")

    composite = compute_composite(fast, breadth, aaii)
    breadth_pct = (breadth or {}).get("pct_above_sma50")
    vix_close = ((fast or {}).get("vix") or {}).get("close")

    if composite is None and breadth_pct is None:
        print("WARN: no usable data yet - skipping history snapshot", file=sys.stderr)
        sys.exit(0)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        with open(HISTORY_PATH) as f:
            history = json.load(f)
            if not isinstance(history, list):
                history = []
    except Exception:
        history = []

    # Overwrite today's entry if this runs more than once in a day, rather
    # than appending duplicates.
    history = [h for h in history if h.get("date") != today]
    history.append({
        "date": today,
        "composite": composite,
        "breadth_pct": breadth_pct,
        "vix": vix_close,
    })
    history.sort(key=lambda h: h["date"])
    history = history[-MAX_HISTORY_DAYS:]

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)
    print(f"Wrote {HISTORY_PATH}: {len(history)} days of history, today's composite={composite}")


if __name__ == "__main__":
    main()
