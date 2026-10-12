# Weekly Recap: how an edition is made

The Weekly Recap (`weekly.html`) is a Sunday pre-open brief. Each edition is one JSON file in
`data/weekly/`, listed in `data/weekly/index.json` (newest first). The page renders whatever edition
the index points to, and `weekly.html?week=YYYY-MM-DD` opens an archived one.

## Who does what

| Part | Made by | When |
|---|---|---|
| Numbers: index and sector moves, equal-weight vs SPY, semis, 10-year yield, VIX, oil, gold, bitcoin, the week's top insider trades | `scripts/fetch_weekly.py` via `.github/workflows/update-weekly.yml` → `data/weekly_numbers.json` | Saturday (Sunday back-up) |
| Writing: headline, TL;DR, last week's calls checked, levels, sector story, big-money trades, news, calendar, consensus, Fed odds, bitcoin levels, bottom line, sources | Researched each Sunday, committed as `data/weekly/<monday>.json` in a pull request | Sunday, before futures reopen (18:00 ET) |
| Approval | The site owner merges the pull request | Sunday |

## Publishing an edition

1. Write `data/weekly/<monday-of-the-coming-week>.json` following the format below (copy the latest edition as a template).
2. Run `python3 scripts/weekly_edition.py publish data/weekly/<date>.json`. It copies the current
   `data/weekly_numbers.json` into the edition (so archives never change later), validates everything,
   and updates `data/weekly/index.json`. It refuses to write anything if the edition is invalid.
3. Open a pull request. Merging it publishes the edition on GitHub Pages.

## Rules for the writing

- Every claim must come from a source listed in `sources` (http/https links). No invented trades, prices or quotes.
- Plain text only (no HTML, no `<` or `>`); the page escapes everything anyway.
- Politicians' trades: say when the trade happened and when it was disclosed. Amounts are the disclosed ranges.
- Do not restate numbers the script computes (index closes, sector moves) unless they come from the numbers file.
- `side`: `buy` and `sell` are disclosed trades; `short` is a bet against a stock (short sale or put options); `hold` means nothing new was reported.
- `tone` is `up` (good for stocks / buying / opportunity), `down` (pressure / selling / caution) or `neutral`.
- Not financial advice: describe conditions and what was disclosed; never tell readers to buy or sell.

## Format (schema 1)

```jsonc
{
  "schema": 1,
  "week_of": "2026-10-19",            // Monday of the coming week; also the file name
  "label": "Oct 19–23, 2026",
  "published": "2026-10-18",          // the Sunday it went out
  "title": "…",                       // ≤ 120 chars
  "deck": "…",                        // ≤ 500 chars
  "tldr": [ { "label": "What changed", "text": "…" }, { "label": "What’s next", "text": "…" }, { "label": "Who’s buying", "text": "…" } ],
  "scorecard": [ { "call": "…", "outcome": "…", "verdict": "…", "tone": "up|down|neutral" } ],   // 1–5: last edition's bottom line, checked
  "levels": { "name": "S&P 500", "now": 7811.54, "record": 7818.93, "min": 7200, "max": 8050,
              "range": [7567, 7800], "marks": [ { "value": 7250, "label": "200-day average", "tone": "neutral" } ], "note": "…" },
  "sectors": { "title": "…", "deck": "…", "flows": [ { "label": "…", "value": "…", "tone": "…", "note": "…" } ], "takeaway": "…" },
  "big_money": {
    "lag_note": "…",
    "groups": [ { "title": "Politicians", "entries": [
      { "initials": "DT", "who": "…", "role": "…", "when": "…",
        "moves": [ { "side": "buy|sell|short|hold", "text": "META $5–25M" } ], "detail": "…", "read": "…" } ] } ],
    "overlaps": [ { "name": "CoreWeave", "text": "…" } ]
  },
  "news": [ { "headline": "…", "body": "…", "tone": "…" } ],                 // 3–8
  "calendar": [ { "day": "Mon 19", "importance": 1, "title": "…", "body": "…", "key": false } ],   // 3–7
  "consensus": [ { "report": "CPI, monthly", "expected": "+0.3%", "prior": "+0.6%", "tone": "…" } ],
  "consensus_note": "…",
  "fed_odds": [ { "label": "At the Oct 27–28 meeting", "pct": 20 } ],
  "further": "…",
  "crypto": { "headline": "…", "deck": "…", "signal": "…",
              "map": { "min": 74000, "max": 90000, "marks": [ { "value": 82000, "label": "Support", "tone": "neutral" } ],
                       "zone": { "from": 86700, "to": 87300, "label": "Breakout zone" } },
              "stats": [ { "label": "…", "value": "…", "tone": "…", "note": "…" } ] },
  "bottom_line": [ { "title": "…", "body": "…" } ],                          // exactly 3
  "sources": [ { "title": "…", "url": "https://…" } ],
  "numbers": { }                                                            // added by `publish`
}
```
