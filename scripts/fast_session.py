#!/usr/bin/env python3
"""
Keeps data/fast.json fresh through the US trading session.

Why a loop: GitHub runs scheduled workflows on a best-effort basis. In
practice a "*/15" schedule fired about five times a day, hours apart. So the
workflow's schedule entries are only wake-up calls. The first one that fires
on a trading day starts this loop, which:

  1. fetches and publishes fast.json right away,
  2. waits for the opening bell if it woke up shortly before it,
  3. refreshes every INTERVAL_MIN minutes while the market is open,
  4. takes one last snapshot a few minutes after the close (official close), and
  5. before GitHub's 6-hour job limit, starts a fresh run of this workflow to
     carry on (workflow_dispatch is allowed to trigger itself).

Only one loop runs at a time: a run exits straight away if an older run of
this workflow is already in progress (the wake-up calls that land during a
session therefore finish in seconds and cost nothing).
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_fast  # noqa: E402
from common import log, read_json, write_json  # noqa: E402
from publish import publish  # noqa: E402

INTERVAL_MIN = 10            # ~6 commits/hour keeps GitHub Pages well under its build limit
WAIT_FOR_OPEN_MIN = 45       # if the bell is this close, stay and wait for it
FINAL_SNAPSHOT_MIN = 12      # take the closing snapshot this long after 4:00pm
HANDOFF_AFTER_MIN = 5 * 60 + 15   # hand over before the 6h job limit
WORKFLOW_FILE = "update-fast.yml"

RUN_ID = int(os.environ.get("GITHUB_RUN_ID") or 0)
PARENT_ID = (os.environ.get("PARENT_RUN_ID") or "").strip()


def gh(*args, timeout=60):
    return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)


def older_loop_running():
    """True if an older run of this workflow is in progress (it owns the session)."""
    if not RUN_ID:
        return False
    try:
        res = gh("run", "list", "--workflow", WORKFLOW_FILE, "--status", "in_progress",
                 "--limit", "20", "--json", "databaseId")
        if res.returncode != 0:
            log(f"WARN: could not list runs ({res.stderr.strip()[:200]}) - continuing")
            return False
        ids = [r["databaseId"] for r in json.loads(res.stdout or "[]")]
    except Exception as e:
        log(f"WARN: run check failed ({e}) - continuing")
        return False
    return any(i < RUN_ID and str(i) != PARENT_ID for i in ids)


def hand_off():
    ref = os.environ.get("GITHUB_REF_NAME") or "main"
    res = gh("workflow", "run", WORKFLOW_FILE, "--ref", ref, "-f", f"parent={RUN_ID}")
    if res.returncode == 0:
        log("Handed the session over to a fresh run.")
    else:
        log(f"WARN: hand-off failed ({res.stderr.strip()[:300]}); the next scheduled wake-up will resume.")


def fetch_and_publish():
    path = fetch_fast.OUT_PATH
    try:
        out = fetch_fast.build(read_json(path, {}) or {})
    except Exception as e:  # a malformed upstream response shouldn't kill the whole session
        log(f"WARN: fetch failed unexpectedly: {e!r}")
        return None
    if out is None:
        return None
    write_json(path, out)
    spy = out["spy"]
    log(f"{time.strftime('%H:%M:%S')} UTC  market={out['market']['state']}  SPY={spy['close']}  "
        f"VIX={out['vix']['close']}  F&G={(out.get('fear_greed') or {}).get('score')}")
    try:
        publish([path], "chore: update fast market data [skip ci]")
    except SystemExit as e:
        log(f"WARN: {e}")
    return out


def sleep_until(ts):
    delay = ts - time.time()
    if delay > 0:
        time.sleep(delay)


def main():
    started = time.time()
    if older_loop_running():
        log("Another run is already keeping the data fresh - nothing to do.")
        return
    final_snapshot_taken = False
    failing_since = None
    while True:
        out = fetch_and_publish()
        now = time.time()

        if out is None:
            # Yahoo hiccup: retry every 2 minutes for up to half an hour, then
            # give up and let the next scheduled wake-up try again.
            failing_since = failing_since or now
            if now - failing_since > 30 * 60 or now - started > HANDOFF_AFTER_MIN * 60:
                return
            time.sleep(120)
            continue
        failing_since = None

        market = out.get("market") or {}
        state = market.get("state")
        opens = _ts(market.get("session_open"))
        closes = _ts(market.get("session_close"))

        if state == "open":
            next_tick = now + INTERVAL_MIN * 60
            if closes and next_tick > closes:
                next_tick = closes + FINAL_SNAPSHOT_MIN * 60   # land the closing snapshot
                final_snapshot_taken = True
            if next_tick - started > HANDOFF_AFTER_MIN * 60:
                hand_off()
                return
            sleep_until(next_tick)
        elif state == "pre" and opens and opens - now <= WAIT_FOR_OPEN_MIN * 60:
            if opens + 120 - started > HANDOFF_AFTER_MIN * 60:
                return
            sleep_until(opens + 120)
        elif (state == "closed" and closes and not final_snapshot_taken
              and 0 <= now - closes < FINAL_SNAPSHOT_MIN * 60):
            final_snapshot_taken = True
            sleep_until(closes + FINAL_SNAPSHOT_MIN * 60)
        else:
            return   # market closed: one snapshot is all we need

        if older_loop_running():
            log("An older run took over - stopping this one.")
            return


def _ts(iso):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return None


if __name__ == "__main__":
    main()
