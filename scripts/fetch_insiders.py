#!/usr/bin/env python3
"""
Insider trades for S&P 500 + Nasdaq-100 companies, from official SEC Form 4
filings (officers, directors and 10%+ owners must report trades within two
business days) -> data/insiders.json. Free public SEC data, no API key.

Coverage: a rolling 30-day window, built from two official sources:
  - EDGAR's daily form index (complete list of each day's filings), and
  - EDGAR's "latest filings" feed (same-day freshness between index updates).
Every run adds what is new, so a skipped or late scheduled run loses nothing.

Accuracy:
  - only open-market purchases (code P) and sales (code S); grants, option
    exercises, gifts and tax withholding are excluded; amendments (4/A) too;
  - one row per filing per direction: multiple lines of the same filing are
    summed (shares, value, volume-weighted price);
  - the same trade reported by several people (e.g. co-trustees of a family
    trust) is shown once, with the other reporting people listed;
  - sales/purchases made under a pre-arranged Rule 10b5-1 plan are flagged,
    since those are scheduled in advance and say less about the insider's view.

The SEC asks automated tools to identify themselves with a contact address in
the User-Agent: https://www.sec.gov/os/webmaster-faq#developers
"""
import json
import os
import re
import time
import urllib.error
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

from common import (DATA_DIR, ET as NY, fetch_universe, http_get, log,
                    normalize_symbol, read_json, utc_now_iso, warn, write_json)

CONTACT = "market-pulse-dashboard go.avieldvir+marketpulse@gmail.com"
SEC_HEADERS = {"User-Agent": CONTACT}

OUT_PATH = os.path.join(DATA_DIR, "insiders.json")
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
FEED_URL = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb="
            "&owner=include&count=100&output=atom&start={start}")
DAILY_INDEX_URL = "https://www.sec.gov/Archives/edgar/daily-index/{y}/QTR{q}/form.{ymd}.idx"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}.txt"

WINDOW_DAYS = 30
KEEP_SELLS = 100           # the largest sales in the window (smaller ones are mostly routine)
KEEP_BUYS = 300            # purchases are rare - keep them all (safety cap only)
MAX_DOCS_PER_RUN = 2000    # the first run back-fills over a few runs
FEED_MAX_PAGES = 15
SEC_PAUSE = 0.12           # stays well under the SEC's 10 requests/second limit


class SecBlocked(Exception):
    pass


def sec_get(url, timeout=25):
    time.sleep(SEC_PAUSE)
    try:
        return http_get(url, headers=SEC_HEADERS, timeout=timeout, retries=2, backoff=3.0)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise SecBlocked(url)
        raise


# ------------------------------------------------------------ parsing ----

def truthy(v):
    return (v or "").strip().lower() in ("1", "true", "yes", "y")


def _text(node, path):
    el = node.find(path)
    return el.text.strip() if el is not None and el.text and el.text.strip() else None


PARTICLES = {"van", "von", "de", "del", "della", "der", "den", "di", "da", "du", "la", "le", "st", "st.", "ter", "ten"}
SUFFIXES = {"JR", "SR", "II", "III", "IV", "V", "MD", "PHD", "ESQ", "CPA"}
ENTITY = re.compile(
    r"\b(INC|LLC|L\.L\.C|LP|L\.P|LLP|LTD|LIMITED|CORP|CORPORATION|COMPANY|CO|TRUST|FUNDS?|PARTNERS(HIP)?|"
    r"HOLDINGS?|CAPITAL|MANAGEMENT|GROUP|ADVIS[OE]RS?|FOUNDATION|BANK|PLC|AG|SA|NV|GMBH|INVESTMENTS?|"
    r"VENTURES?|ASSOCIATES|ENTERPRISES?|SECURITIES|MASTER|OFFSHORE|INTERNATIONAL|GLOBAL|FINANCIAL|"
    r"BERKSHIRE|HATHAWAY|ENDOWMENT|PENSION|RETIREMENT)\b\.?", re.I)


def _smart_case(s):
    words = []
    for w in s.split():
        bare = w.strip(".,").upper()
        if bare in {"II", "III", "IV", "LLC", "LP", "L.P", "LLP", "PLC", "AG", "SA", "NV", "USA", "US"} or len(bare) == 1:
            words.append(w.upper())
        elif bare.startswith("MC") and len(bare) > 3:
            words.append("Mc" + w[2:].capitalize())
        else:
            words.append(w.capitalize() if "'" not in w and "-" not in w else w.title())
    return " ".join(words)


def display_name(raw):
    """SEC lists people as 'Last First Middle' - show them as 'First Middle Last'.
    Company and fund names are left alone (just de-shouted)."""
    name = " ".join((raw or "").split())
    if not name:
        return "Unknown"
    if ENTITY.search(name) or any(ch.isdigit() for ch in name):
        return _smart_case(name) if name.isupper() else name
    if "," in name:
        last, _, rest = name.partition(",")
        tokens = rest.split() + [last.strip()]
    else:
        parts = name.split()
        if len(parts) == 1:
            return _smart_case(name) if name.isupper() else name
        i = 0
        while i < len(parts) - 1 and parts[i].lower() in PARTICLES:
            i += 1
        last = parts[:i + 1]
        rest = parts[i + 1:]
        suffix = [p for p in rest if p.upper().strip(".,") in SUFFIXES]
        given = [p for p in rest if p.upper().strip(".,") not in SUFFIXES]
        tokens = given + last + suffix
    out = " ".join(t.strip(",") for t in tokens if t.strip(","))
    return _smart_case(out) if out.isupper() else out


GENERIC_TITLES = {"see remarks", "see remarks below", "see remarks.", "officer", "see footnote", "see explanation"}


def owner_role(rel):
    is_officer, is_director = truthy(_text(rel, "isOfficer")), truthy(_text(rel, "isDirector"))
    is_ten, is_other = truthy(_text(rel, "isTenPercentOwner")), truthy(_text(rel, "isOther"))
    title = " ".join((_text(rel, "officerTitle") or "").split())
    other = " ".join((_text(rel, "otherText") or "").split())
    if is_officer:
        role = title if title and title.lower() not in GENERIC_TITLES else "Officer"
        rank = 0
    elif is_director:
        role, rank = "Director", 1
    elif is_ten:
        role, rank = "10% Owner", 2
    elif is_other and other:
        role, rank = other, 3
    else:
        role, rank = "Insider", 4
    return (role[:48] + "…") if len(role) > 49 else role, rank


PLAN_NEGATED = re.compile(r"not\s+(?:\w+\s+){0,3}pursuant\s+to\s+(?:a\s+)?(?:rule\s+)?10b5-1", re.I)


def parse_submission(txt):
    """Parses a full EDGAR submission (.txt) holding a Form 4. Returns a dict or None."""
    header = txt[:6000]
    form = re.search(r"CONFORMED SUBMISSION TYPE:\s*(\S+)", header)
    if not form or form.group(1).upper() != "4":
        return None
    acc = re.search(r"ACCESSION NUMBER:\s*([\d-]+)", header)
    filed = re.search(r"FILED AS OF DATE:\s*(\d{8})", header)
    accepted = re.search(r"<ACCEPTANCE-DATETIME>\s*(\d{14})", header)
    xml = None
    for m in re.finditer(r"<XML>(.*?)</XML>", txt, re.S | re.I):
        if "<ownershipDocument" in m.group(1):
            xml = m.group(1).strip()
            break
    if not xml:
        return None
    root = None
    for candidate in (xml, xml.encode("utf-8")):
        try:
            root = ET.fromstring(candidate)
            break
        except (ET.ParseError, ValueError):
            continue
    if root is None:
        return None

    owners = []
    for ro in root.findall("reportingOwner"):
        rel = ro.find("reportingOwnerRelationship")
        role, rank = owner_role(rel) if rel is not None else ("Insider", 4)
        owners.append({"name": display_name(_text(ro, "reportingOwnerId/rptOwnerName")),
                       "role": role, "rank": rank})
    owners.sort(key=lambda o: o["rank"])

    footnotes = " ".join(" ".join(f.itertext()) for f in root.findall("footnotes/footnote"))
    aff = root.find("aff10b5One")
    if aff is not None and aff.text is not None:
        plan = truthy(aff.text)
    else:  # filings from before the 2023 checkbox: look for the plan in the footnotes
        plan = bool(re.search(r"10b5-1", footnotes, re.I)) and not PLAN_NEGATED.search(footnotes)

    lines = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        code = (_text(tx, "transactionCoding/transactionCode") or "").upper()
        if code not in ("P", "S"):
            continue
        try:
            shares = float(_text(tx, "transactionAmounts/transactionShares/value") or 0)
            price = float(_text(tx, "transactionAmounts/transactionPricePerShare/value") or 0)
        except ValueError:
            continue
        if shares <= 0 or price <= 0:
            continue
        lines.append({"code": code, "shares": shares, "price": price,
                      "date": _text(tx, "transactionDate/value")})

    filed_iso = None
    if filed:
        f = filed.group(1)
        filed_iso = f"{f[:4]}-{f[4:6]}-{f[6:]}"
    accepted_iso = None
    if accepted:
        a = accepted.group(1)
        accepted_iso = datetime(int(a[:4]), int(a[4:6]), int(a[6:8]), int(a[8:10]), int(a[10:12]),
                                int(a[12:14]), tzinfo=NY).isoformat()
    return {
        "accession": acc.group(1) if acc else None,
        "filed": filed_iso,
        "accepted": accepted_iso,
        "issuer_cik": int(_text(root, "issuer/issuerCik") or 0) or None,
        "symbol": normalize_symbol(_text(root, "issuer/issuerTradingSymbol") or ""),
        "owners": owners or [{"name": "Unknown", "role": "Insider", "rank": 4}],
        "plan": plan,
        "lines": lines,
    }


def filing_rows(doc, ticker):
    """One row per direction (buy/sell) for a parsed filing."""
    rows = []
    for code, action in (("P", "Buy"), ("S", "Sell")):
        lines = [ln for ln in doc["lines"] if ln["code"] == code]
        if not lines:
            continue
        shares = sum(ln["shares"] for ln in lines)
        value = sum(ln["shares"] * ln["price"] for ln in lines)
        dates = sorted(ln["date"] for ln in lines if ln["date"])
        primary, others = doc["owners"][0], doc["owners"][1:]
        rows.append({
            "symbol": ticker,
            "cik": doc["issuer_cik"],
            "insider": primary["name"],
            "role": primary["role"],
            "rank": primary["rank"],
            "others": [o["name"] for o in others],
            "action": action,
            "transaction_code": code,
            "shares": round(shares),
            "price": round(value / shares, 2),
            "value": round(value),
            "date": dates[-1] if dates else doc["filed"],
            "date_first": dates[0] if dates else doc["filed"],
            "filed": doc["filed"],
            "plan": doc["plan"],
            "lines": len(lines),
            "accession": doc["accession"],
            "accessions": [doc["accession"]],
        })
    return rows


def merge_joint(rows):
    """Collapse the same trade reported in separate filings by different people."""
    groups = {}
    for r in rows:
        key = (r["symbol"], r["transaction_code"], r["date"], r["shares"], r["price"])
        groups.setdefault(key, []).append(r)
    out = []
    for group in groups.values():
        group.sort(key=lambda r: (r.get("rank", 4), r.get("filed") or "", r["accession"]))
        base = dict(group[0])
        names, accs = [], []
        for r in group:
            for n in [r["insider"], *r.get("others", [])]:
                if n not in names:
                    names.append(n)
            for a in r.get("accessions") or [r["accession"]]:
                if a not in accs:
                    accs.append(a)
        base["insider"], base["others"], base["accessions"] = names[0], names[1:], accs
        base["plan"] = any(r.get("plan") for r in group)
        out.append(base)
    return out


# ---------------------------------------------------------- collection ----

def build_cik_map(universe):
    data = json.loads(sec_get(TICKER_MAP_URL).decode("utf-8"))
    out = {}
    for row in data.values():
        t = normalize_symbol(str(row.get("ticker", "")))
        if t in universe:
            out.setdefault(int(row["cik_str"]), t)
    return out


def index_accessions(day, cik_map):
    q = (day.month - 1) // 3 + 1
    url = DAILY_INDEX_URL.format(y=day.year, q=q, ymd=day.strftime("%Y%m%d"))
    text = sec_get(url, timeout=40).decode("latin-1")
    found = {}
    for line in text.splitlines():
        if not line.startswith("4 "):       # exactly "4" - amendments ("4/A") are skipped
            continue
        parts = line.split()
        if len(parts) < 5 or not parts[-3].isdigit():
            continue
        cik = int(parts[-3])
        if cik in cik_map:
            acc = parts[-1].rsplit("/", 1)[-1].replace(".txt", "")
            found.setdefault(acc, cik)
    return found


def feed_entries(max_pages, stop_before):
    """Latest Form 4 filings (issuer side) newer than `stop_before` (ISO) - newest first."""
    out, newest = [], None
    for page in range(max_pages):
        xml = sec_get(FEED_URL.format(start=page * 100)).decode("utf-8", errors="replace")
        entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
        if not entries:
            break
        oldest_on_page = None
        for block in entries:
            title = re.search(r"<title>(.*?)</title>", block, re.S)
            acc = re.search(r"accession-number=([\d-]+)", block)
            link = re.search(r'href="[^"]*/data/(\d+)/', block)
            upd = re.search(r"<updated>(.*?)</updated>", block)
            if not (title and acc and link and upd):
                continue
            t = title.group(1)
            updated = upd.group(1).strip()
            if newest is None or _cmp_iso(updated) > _cmp_iso(newest):
                newest = updated
            if oldest_on_page is None or _cmp_iso(updated) < _cmp_iso(oldest_on_page):
                oldest_on_page = updated
            if t.split(" - ", 1)[0].strip() != "4" or "(Issuer)" not in t:
                continue
            out.append({"accession": acc.group(1), "cik": int(link.group(1)), "updated": updated})
        if stop_before and oldest_on_page and _cmp_iso(oldest_on_page) < _cmp_iso(stop_before):
            break
        if len(entries) < 100:
            break
    return out, newest


def _cmp_iso(s):
    try:
        return datetime.fromisoformat(s).timestamp()
    except ValueError:
        return 0


def business_days(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def main():
    today = datetime.now(NY).date()
    window_start = today - timedelta(days=WINDOW_DAYS)
    previous = read_json(OUT_PATH, {}) or {}
    state = previous.get("state") or {}
    stored = [r for r in (previous.get("buys") or []) + (previous.get("sells") or [])
              if r.get("accession") and r.get("filed") and r["filed"] >= window_start.isoformat()]
    known = {a for r in stored for a in (r.get("accessions") or [r["accession"]])}
    indexed = {d for d in state.get("indexed_days", []) if d >= window_start.isoformat()}

    sp500, ndx = fetch_universe()
    universe = set(sp500) | set(ndx)
    if len(universe) < 400:
        warn(f"Insiders: universe lists incomplete ({len(universe)} tickers) - skipping this run")
        return
    try:
        cik_map = build_cik_map(universe)
    except Exception as e:
        warn(f"Insiders: could not load the SEC ticker map ({e}) - skipping this run")
        return

    new_rows, budget, blocked, processed = [], MAX_DOCS_PER_RUN, False, 0
    seen_this_run = set()

    def process(acc, cik):
        nonlocal budget, processed
        if acc in seen_this_run:
            return
        seen_this_run.add(acc)
        budget -= 1
        try:
            txt = sec_get(DOC_URL.format(cik=cik, acc=acc)).decode("utf-8", errors="replace")
        except SecBlocked:
            raise
        except Exception as e:
            log(f"WARN: {acc}: {e}")
            return
        processed += 1
        doc = parse_submission(txt)
        if not doc or not doc["lines"]:
            return
        ticker = doc["symbol"] if doc["symbol"] in universe else cik_map.get(cik)
        if ticker:
            new_rows.extend(filing_rows(doc, ticker))
        known.add(acc)

    # 1) Completeness: every business day in the window, from EDGAR's daily index.
    try:
        for day in sorted(business_days(window_start, today - timedelta(days=1)), reverse=True):
            key = day.isoformat()
            if key in indexed:
                continue
            try:
                accs = index_accessions(day, cik_map)
            except urllib.error.HTTPError as e:
                if e.code == 404 and (today - day).days > 3:
                    indexed.add(key)            # market holiday - no index will ever appear
                continue                        # otherwise: not published yet, try next run
            todo = [(a, c) for a, c in accs.items() if a not in known]
            if len(todo) > budget and processed:
                break
            for acc, cik in todo:
                process(acc, cik)
            indexed.add(key)
            log(f"Indexed {key}: {len(accs)} Form 4s for our companies, {len(todo)} fetched")
            if budget <= 0:
                break

        # 2) Freshness: today's filings from the live feed.
        entries, newest = feed_entries(FEED_MAX_PAGES, state.get("feed_watermark"))
        feed_done = True
        for e in entries:
            if e["cik"] in cik_map and e["accession"] not in known:
                if budget <= 0:
                    feed_done = False       # finish these next run - don't move the bookmark past them
                    break
                process(e["accession"], e["cik"])
        if newest and feed_done:
            state["feed_watermark"] = newest
    except SecBlocked as e:
        warn(f"SEC refused a request ({e}) - saving what was collected and stopping")
        blocked = True

    rows = merge_joint(stored + new_rows)
    rows = [r for r in rows if (r.get("filed") or "") >= window_start.isoformat()]
    buys = sorted((r for r in rows if r["action"] == "Buy"),
                  key=lambda r: (r["filed"], r["value"]), reverse=True)[:KEEP_BUYS]
    sells = sorted((r for r in rows if r["action"] == "Sell"),
                   key=lambda r: r["value"], reverse=True)[:KEEP_SELLS]

    covered_from = None
    for day in sorted(business_days(window_start, today - timedelta(days=1)), reverse=True):
        if day.isoformat() not in indexed:
            break
        covered_from = day.isoformat()

    state["indexed_days"] = sorted(indexed)
    out = {
        "generated_at": utc_now_iso(),
        "window_days": WINDOW_DAYS,
        "covered_from": covered_from,
        "latest_filing": state.get("feed_watermark"),
        "buys": buys,
        "sells": sells,
        "state": state,
        "note": ("Official SEC Form 4 filings: open-market purchases (P) and sales (S) by officers, "
                 "directors and 10%+ owners of S&P 500 + Nasdaq-100 companies. Grants, option "
                 "exercises, gifts, tax withholding and amendments are excluded. Not stock advice."),
    }
    # Only commit when something a reader would see changed (or the feed bookmark is
    # a few hours stale), not on every run - keeps the repository history small.
    def meaningful(d):
        return json.loads(json.dumps({k: v for k, v in d.items()
                                      if k not in ("generated_at", "latest_filing", "state")}))
    old_mark = (previous.get("state") or {}).get("feed_watermark")
    mark_moved = (_cmp_iso(state.get("feed_watermark") or "") - _cmp_iso(old_mark or "")) > 3 * 3600
    if (meaningful(previous) == meaningful(out)
            and sorted((previous.get("state") or {}).get("indexed_days", [])) == state["indexed_days"]
            and not mark_moved):
        log(f"No new insider data ({processed} filings checked).")
        return
    write_json(OUT_PATH, out, compact=True)
    log(f"Wrote {OUT_PATH}: {len(buys)} buys, {len(sells)} sells in the last {WINDOW_DAYS} days "
        f"(covered from {covered_from}); {processed} filings fetched this run{' - stopped early' if blocked else ''}")


if __name__ == "__main__":
    main()
