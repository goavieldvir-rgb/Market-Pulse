#!/usr/bin/env python3
"""
Validate and publish a Weekly Recap edition.

    python3 scripts/weekly_edition.py validate data/weekly/2026-10-19.json
    python3 scripts/weekly_edition.py publish  data/weekly/2026-10-19.json

`publish` copies the current data/weekly_numbers.json into the edition (so an
archived edition never changes when next week's numbers land), validates the
result, and adds or updates the entry in data/weekly/index.json (newest first).
It refuses to write anything if validation fails, so a bad edition can never
reach the page. The edition format is documented in docs/weekly-recap.md.

Standard library only.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA_DIR, read_json, write_json  # noqa: E402

WEEKLY_DIR = os.path.join(DATA_DIR, "weekly")
INDEX = os.path.join(WEEKLY_DIR, "index.json")
NUMBERS = os.path.join(DATA_DIR, "weekly_numbers.json")

TONES = {"up", "down", "neutral"}
SIDES = {"buy", "sell", "short", "hold"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Invalid(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Invalid(msg)


def text(obj, key, where, max_len=900, optional=False):
    v = obj.get(key)
    if v is None and optional:
        return
    need(isinstance(v, str) and v.strip(), f"{where}.{key} must be a non-empty string")
    need(len(v) <= max_len, f"{where}.{key} is longer than {max_len} characters")
    need("<" not in v and ">" not in v, f"{where}.{key} must be plain text (no < or >)")


def tone(obj, key, where):
    v = obj.get(key, "neutral")
    need(v in TONES, f"{where}.{key} must be one of {sorted(TONES)}")


def items(obj, key, where, lo=1, hi=12):
    v = obj.get(key)
    need(isinstance(v, list) and lo <= len(v) <= hi, f"{where}.{key} must be a list of {lo}-{hi} items")
    return v


def number(obj, key, where, optional=False):
    v = obj.get(key)
    if v is None and optional:
        return
    need(isinstance(v, (int, float)) and not isinstance(v, bool), f"{where}.{key} must be a number")


def validate(ed):
    need(isinstance(ed, dict), "edition must be a JSON object")
    need(ed.get("schema") == 1, "schema must be 1")
    need(isinstance(ed.get("week_of"), str) and DATE_RE.match(ed["week_of"]), "week_of must be YYYY-MM-DD (the Monday)")
    need(isinstance(ed.get("published"), str) and DATE_RE.match(ed["published"]), "published must be YYYY-MM-DD")
    for k, n in (("label", 60), ("title", 120), ("deck", 500)):
        text(ed, k, "edition", n)

    for i, t in enumerate(items(ed, "tldr", "edition", 3, 3)):
        text(t, "label", f"tldr[{i}]", 40); text(t, "text", f"tldr[{i}]", 300)

    for i, s in enumerate(items(ed, "scorecard", "edition", 1, 5)):
        text(s, "call", f"scorecard[{i}]", 60); text(s, "outcome", f"scorecard[{i}]", 400)
        text(s, "verdict", f"scorecard[{i}]", 40); tone(s, "tone", f"scorecard[{i}]")

    lv = ed.get("levels")
    need(isinstance(lv, dict), "levels must be an object")
    text(lv, "name", "levels", 40)
    for k in ("now", "min", "max"):
        number(lv, k, "levels")
    number(lv, "record", "levels", optional=True)
    need(lv["min"] < lv["max"], "levels.min must be below levels.max")
    rng = lv.get("range")
    need(isinstance(rng, list) and len(rng) == 2 and all(isinstance(x, (int, float)) for x in rng), "levels.range must be [low, high]")
    for i, m in enumerate(items(lv, "marks", "levels", 1, 6)):
        number(m, "value", f"levels.marks[{i}]"); text(m, "label", f"levels.marks[{i}]", 40); tone(m, "tone", f"levels.marks[{i}]")
        need(lv["min"] <= m["value"] <= lv["max"], f"levels.marks[{i}].value is outside min..max")
    text(lv, "note", "levels", 400, optional=True)

    sec = ed.get("sectors")
    need(isinstance(sec, dict), "sectors must be an object")
    text(sec, "title", "sectors", 80); text(sec, "deck", "sectors", 400)
    for i, f in enumerate(items(sec, "flows", "sectors", 1, 5)):
        text(f, "label", f"sectors.flows[{i}]", 60); text(f, "value", f"sectors.flows[{i}]", 30)
        text(f, "note", f"sectors.flows[{i}]", 300); tone(f, "tone", f"sectors.flows[{i}]")
    text(sec, "takeaway", "sectors", 400, optional=True)

    bm = ed.get("big_money")
    need(isinstance(bm, dict), "big_money must be an object")
    text(bm, "lag_note", "big_money", 400)
    for gi, g in enumerate(items(bm, "groups", "big_money", 1, 3)):
        text(g, "title", f"big_money.groups[{gi}]", 40)
        for ei, e in enumerate(items(g, "entries", f"big_money.groups[{gi}]", 1, 8)):
            w = f"big_money.groups[{gi}].entries[{ei}]"
            text(e, "who", w, 60); text(e, "role", w, 60); text(e, "when", w, 80)
            text(e, "initials", w, 3)
            for mi, m in enumerate(items(e, "moves", w, 1, 6)):
                need(m.get("side") in SIDES, f"{w}.moves[{mi}].side must be one of {sorted(SIDES)}")
                text(m, "text", f"{w}.moves[{mi}]", 50)
            text(e, "detail", w, 300); text(e, "read", w, 300)
    for i, o in enumerate(bm.get("overlaps") or []):
        text(o, "name", f"big_money.overlaps[{i}]", 40); text(o, "text", f"big_money.overlaps[{i}]", 160)

    for i, n in enumerate(items(ed, "news", "edition", 3, 8)):
        text(n, "headline", f"news[{i}]", 90); text(n, "body", f"news[{i}]", 400); tone(n, "tone", f"news[{i}]")

    for i, c in enumerate(items(ed, "calendar", "edition", 3, 7)):
        text(c, "day", f"calendar[{i}]", 20); text(c, "title", f"calendar[{i}]", 80)
        text(c, "body", f"calendar[{i}]", 300, optional=True)
        need(c.get("importance") in (1, 2, 3), f"calendar[{i}].importance must be 1, 2 or 3")
    for i, c in enumerate(ed.get("consensus") or []):
        text(c, "report", f"consensus[{i}]", 40); text(c, "expected", f"consensus[{i}]", 16)
        text(c, "prior", f"consensus[{i}]", 16); tone(c, "tone", f"consensus[{i}]")
    text(ed, "consensus_note", "edition", 300, optional=True)
    for i, f in enumerate(ed.get("fed_odds") or []):
        text(f, "label", f"fed_odds[{i}]", 60); number(f, "pct", f"fed_odds[{i}]")
        need(0 <= f["pct"] <= 100, f"fed_odds[{i}].pct must be 0-100")
    text(ed, "further", "edition", 300, optional=True)

    cr = ed.get("crypto")
    need(isinstance(cr, dict), "crypto must be an object")
    text(cr, "headline", "crypto", 80); text(cr, "deck", "crypto", 300); text(cr, "signal", "crypto", 300)
    mp = cr.get("map")
    need(isinstance(mp, dict), "crypto.map must be an object")
    number(mp, "min", "crypto.map"); number(mp, "max", "crypto.map")
    for i, m in enumerate(items(mp, "marks", "crypto.map", 1, 5)):
        number(m, "value", f"crypto.map.marks[{i}]"); text(m, "label", f"crypto.map.marks[{i}]", 30); tone(m, "tone", f"crypto.map.marks[{i}]")
    z = mp.get("zone")
    if z is not None:
        number(z, "from", "crypto.map.zone"); number(z, "to", "crypto.map.zone"); text(z, "label", "crypto.map.zone", 30)
    for i, s in enumerate(items(cr, "stats", "crypto", 1, 4)):
        text(s, "label", f"crypto.stats[{i}]", 60); text(s, "value", f"crypto.stats[{i}]", 24, optional=True)
        text(s, "note", f"crypto.stats[{i}]", 300); tone(s, "tone", f"crypto.stats[{i}]")

    for i, b in enumerate(items(ed, "bottom_line", "edition", 3, 3)):
        text(b, "title", f"bottom_line[{i}]", 40); text(b, "body", f"bottom_line[{i}]", 300)

    for i, s in enumerate(items(ed, "sources", "edition", 3, 40)):
        text(s, "title", f"sources[{i}]", 140)
        need(isinstance(s.get("url"), str) and re.match(r"^https?://[^\s<>\"']+$", s["url"]), f"sources[{i}].url must be an http(s) URL")

    nb = ed.get("numbers")
    need(isinstance(nb, dict) and isinstance(nb.get("indices"), list) and nb["indices"], "numbers must hold indices (run publish to copy them in)")
    need(isinstance(nb.get("sectors"), list) and len(nb["sectors"]) >= 9, "numbers.sectors must hold the sector ETFs")
    return True


def publish(path):
    ed = read_json(path)
    if ed is None:
        raise SystemExit(f"ERROR: cannot read {path}")
    nums = read_json(NUMBERS)
    if nums:
        ed["numbers"] = nums
    validate(ed)
    expect = os.path.join(WEEKLY_DIR, f"{ed['week_of']}.json")
    if os.path.abspath(path) != os.path.abspath(expect):
        raise SystemExit(f"ERROR: an edition for the week of {ed['week_of']} must be saved as {expect}")
    write_json(path, ed)
    idx = read_json(INDEX, {"editions": []}) or {"editions": []}
    entries = [e for e in idx.get("editions", []) if e.get("week_of") != ed["week_of"]]
    entries.append({"week_of": ed["week_of"], "label": ed["label"], "title": ed["title"],
                    "published": ed["published"], "file": f"data/weekly/{ed['week_of']}.json"})
    entries.sort(key=lambda e: e["week_of"], reverse=True)
    write_json(INDEX, {"editions": entries})
    print(f"Published {path} and updated {INDEX} ({len(entries)} editions).")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("validate", "publish"):
        raise SystemExit(__doc__)
    cmd, path = sys.argv[1], sys.argv[2]
    try:
        if cmd == "validate":
            ed = read_json(path)
            validate(ed)
            print(f"OK: {path} is a valid edition.")
        else:
            publish(path)
    except Invalid as e:
        raise SystemExit(f"INVALID: {e}")


if __name__ == "__main__":
    main()
