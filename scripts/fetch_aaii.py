#!/usr/bin/env python3
"""
AAII Investor Sentiment Survey (weekly, published Thursdays) -> data/aaii.json

The old scraper matched the first "Bullish ... %" on AAII's page, which turned
out to be the all-time record (75.0% bullish, Jan 2000) and "Bearish 70.3%"
(Mar 2009) rather than this week's survey. This version:

  - reads the dated results table (one row per week: bullish/neutral/bearish),
  - accepts a row only if the three shares add up to ~100%,
  - records the survey week, and keeps a weekly history for the trend chart,
  - never overwrites good data with a failed or implausible parse.
"""
import html as htmllib
import os
import re
from datetime import date

from common import DATA_DIR, http_text, log, read_json, utc_now_iso, warn, write_json

OUT_PATH = os.path.join(DATA_DIR, "aaii.json")
RESULTS_URL = "https://www.aaii.com/sentimentsurvey/sent_results"
MAIN_URL = "https://www.aaii.com/sentimentsurvey"
HISTORY_WEEKS = 104
HISTORICAL_AVG = {"bullish": 37.5, "neutral": 31.5, "bearish": 31.0}  # AAII's long-run averages

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
PCT = r"(\d{1,2}(?:\.\d{1,2})?)\s*%"
ROW_NUMERIC = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\s+" + PCT + r"\s+" + PCT + r"\s+" + PCT)
ROW_MONTH = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})"
                       r"(?:,?\s+(\d{4}))?\s+" + PCT + r"\s+" + PCT + r"\s+" + PCT, re.I)
WEEK_ENDING = re.compile(r"week\s+ending\s+([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", re.I)


def html_to_text(page):
    page = re.sub(r"(?is)<(script|style|noscript)\b.*?</\1>", " ", page)
    page = re.sub(r"(?s)<!--.*?-->", " ", page)
    page = re.sub(r"<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", htmllib.unescape(page)).strip()


def plausible(bull, neu, bear):
    vals = (bull, neu, bear)
    return all(0 < v < 100 for v in vals) and abs(sum(vals) - 100) <= 1.0


def parse_rows(text, today):
    """All weekly rows found in the text, newest first: [(iso_date, bull, neu, bear)]."""
    rows = []
    for m in ROW_NUMERIC.finditer(text):
        mo, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        vals = tuple(float(m.group(i)) for i in (4, 5, 6))
        try:
            d = date(yy, mo, dd)
        except ValueError:
            continue
        if plausible(*vals) and d <= today:
            rows.append((d, *vals))

    # "Sep 23  32.7%  19.2%  48.1%" - table rows without a year, newest first.
    year, prev = today.year, None
    for m in ROW_MONTH.finditer(text):
        mon = MONTHS.get(m.group(1)[:3].lower())
        vals = tuple(float(m.group(i)) for i in (4, 5, 6))
        if not mon or not plausible(*vals):
            continue
        if m.group(3):
            year = int(m.group(3))
        try:
            d = date(year, mon, int(m.group(2)))
            if not m.group(3):
                if prev is None and d > today:
                    d = date(year - 1, mon, int(m.group(2)))
                elif prev is not None and d > prev:     # crossed into the previous year
                    d = date(d.year - 1, mon, int(m.group(2)))
                year = d.year
        except ValueError:
            continue
        if d <= today:
            rows.append((d, *vals))
            prev = d

    unique = {}
    for d, b, n, r in rows:
        unique.setdefault(d, (b, n, r))
    return [(d.isoformat(), *unique[d]) for d in sorted(unique, reverse=True)]


def parse_headline(text, today):
    """Fallback: 'Bullish 32.7% ... Neutral 19.2% ... Bearish 48.1%' near 'week ending'.
    Tries every nearby combination and keeps only one that adds up to ~100%."""
    week = WEEK_ENDING.search(text)
    survey_date = None
    if week:
        mon = MONTHS.get(week.group(1)[:3].lower())
        try:
            survey_date = date(int(week.group(3)), mon, int(week.group(2))) if mon else None
        except ValueError:
            survey_date = None
    start = week.start() if week else 0
    window = text[start:start + 1500]

    def candidates(label):
        return [float(m.group(1)) for m in re.finditer(label + r"\D{0,40}?" + PCT, window, re.I)][:3]

    for b in candidates("Bullish"):
        for n in candidates("Neutral"):
            for r in candidates("Bearish"):
                if plausible(b, n, r):
                    d = survey_date if survey_date and survey_date <= today else None
                    return [(d.isoformat() if d else None, b, n, r)]
    return []


def fetch_rows(today):
    rows, sources = [], []
    for url in (MAIN_URL, RESULTS_URL):
        try:
            text = html_to_text(http_text(url, timeout=25))
        except Exception as e:
            log(f"WARN: could not fetch {url}: {e}")
            continue
        found = parse_rows(text, today)
        if not found:
            found = [r for r in parse_headline(text, today) if r[0]]
        if found:
            rows.extend(found)
            sources.append(url)
    merged = {}
    for d, b, n, r in rows:
        merged.setdefault(d, (b, n, r))
    return [(d, *merged[d]) for d in sorted(merged, reverse=True)], sources


def main(today=None):
    today = today or date.today()
    rows, sources = fetch_rows(today)
    if not rows:
        warn("AAII: no plausible survey rows found (page layout may have changed) - keeping the previous file")
        return

    previous = read_json(OUT_PATH, {}) or {}
    history = {h["date"]: h for h in previous.get("history", [])
               if h.get("date") and plausible(h.get("bullish", 0), h.get("neutral", 0), h.get("bearish", 0))}
    for d, b, n, r in rows:
        history[d] = {"date": d, "bullish": b, "neutral": n, "bearish": r}
    ordered = [history[d] for d in sorted(history)][-HISTORY_WEEKS:]

    latest = ordered[-1]
    out = {
        "generated_at": utc_now_iso(),
        "survey_date": latest["date"],
        "bullish_pct": latest["bullish"],
        "neutral_pct": latest["neutral"],
        "bearish_pct": latest["bearish"],
        "bull_bear_spread": round(latest["bullish"] - latest["bearish"], 1),
        "historical_avg": HISTORICAL_AVG,
        "history": ordered,
        "source": sources[0] if sources else MAIN_URL,
        "note": "AAII Investor Sentiment Survey, published weekly (Thursdays). Rows are checked to add up to 100%.",
    }
    write_json(OUT_PATH, out)
    log(f"Wrote {OUT_PATH}: week of {latest['date']} bull {latest['bullish']} / neutral {latest['neutral']} "
        f"/ bear {latest['bearish']} (spread {out['bull_bear_spread']}); {len(ordered)} weeks of history")


if __name__ == "__main__":
    main()
