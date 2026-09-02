#!/usr/bin/env python3
"""
Tracks corporate insider stock transactions via SEC Form 4 filings - the
disclosure every officer, director, or 10%+ owner of a US public company is
legally required to file within 2 business days of trading their own
company's stock (Section 16 of the Securities Exchange Act).

Entirely official, free, public SEC data - no API key.

IMPORTANT: the SEC asks that automated tools identify themselves with a real
contact in the User-Agent header - see https://www.sec.gov/os/webmaster-faq#developers.
Replace the email below with a real contact before deploying this yourself.
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# --- IMPORTANT: replace with a real contact before you deploy this ---
CONTACT = "market-pulse-dashboard go.avieldvir+marketpulse@gmail.com"
HEADERS = {"User-Agent": CONTACT}

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "insiders.json")

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
CURRENT_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=include&count=100&output=atom"

MAX_ITEMS = 40


def get_json(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_text(url, timeout=15):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def fetch_full_universe():
    """Same S&P 500 + Nasdaq 100 source lists used by fetch_breadth.py."""
    import csv
    import io
    tickers = set()
    try:
        req = urllib.request.Request(
            "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
            headers=HEADERS,
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode("utf-8")
        for row in csv.DictReader(io.StringIO(text)):
            sym = row.get("Symbol") or row.get("symbol")
            if sym:
                tickers.add(sym.strip().upper().replace(".", "-"))
    except Exception as e:
        print(f"WARN: could not load S&P 500 list: {e}", file=sys.stderr)
    try:
        req = urllib.request.Request(
            "https://yfiua.github.io/index-constituents/constituents-nasdaq100.csv",
            headers=HEADERS,
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode("utf-8")
        for row in csv.DictReader(io.StringIO(text)):
            sym = (row.get("Symbol") or row.get("symbol") or row.get("Ticker")
                   or row.get("ticker") or row.get("code") or row.get("Code"))
            if sym:
                tickers.add(sym.strip().upper().replace(".", "-"))
    except Exception as e:
        print(f"WARN: could not load Nasdaq 100 list: {e}", file=sys.stderr)
    return tickers


def build_cik_to_ticker(universe_tickers):
    data = get_json(TICKER_MAP_URL)
    out = {}
    for _, row in data.items():
        ticker = row.get("ticker", "").upper()
        if ticker in universe_tickers:
            cik = str(row.get("cik_str")).zfill(10)
            out[cik] = ticker
    return out


def parse_current_feed():
    xml_text = get_text(CURRENT_FEED_URL)
    entries = []
    for m in re.finditer(r"<entry>(.*?)</entry>", xml_text, re.S):
        block = m.group(1)
        id_m = re.search(r"accession-number=([\d\-]+)", block)
        link_m = re.search(r'href="([^"]+)"', block)
        if not id_m or not link_m:
            continue
        accession_dashed = id_m.group(1)
        cik_m = re.search(r"CIK=(\d{10})", link_m.group(1)) or re.search(r"/data/(\d+)/", link_m.group(1))
        cik = cik_m.group(1).zfill(10) if cik_m else None
        entries.append({"accession": accession_dashed, "cik": cik})
    return entries


def fetch_form4_details(cik, accession_dashed):
    accession_nodashes = accession_dashed.replace("-", "")
    index_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodashes}/index.json"
    try:
        idx = get_json(index_url)
    except Exception:
        return []
    xml_file = None
    for item in idx.get("directory", {}).get("item", []):
        name = item.get("name", "")
        if name.endswith(".xml") and "form4" not in name.lower() and not name.startswith("R"):
            xml_file = name
            break
    if not xml_file:
        for item in idx.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name.endswith(".xml"):
                xml_file = name
                break
    if not xml_file:
        return []

    doc_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodashes}/{xml_file}"
    try:
        xml_text = get_text(doc_url)
        root = ET.fromstring(xml_text)
    except Exception:
        return []

    def find_text(elem, path):
        node = elem.find(path)
        return node.text.strip() if node is not None and node.text else None

    issuer_symbol = find_text(root, ".//issuer/issuerTradingSymbol")
    owner_name = find_text(root, ".//reportingOwner/reportingOwnerId/rptOwnerName")
    is_officer = find_text(root, ".//reportingOwnerRelationship/isOfficer") == "1"
    is_director = find_text(root, ".//reportingOwnerRelationship/isDirector") == "1"
    officer_title = find_text(root, ".//reportingOwnerRelationship/officerTitle")
    role = officer_title if (is_officer and officer_title) else ("Director" if is_director else "Insider")

    transactions = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        code = find_text(tx, ".//transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        shares_s = find_text(tx, ".//transactionAmounts/transactionShares/value")
        price_s = find_text(tx, ".//transactionAmounts/transactionPricePerShare/value")
        date_s = find_text(tx, ".//transactionDate/value")
        try:
            shares = float(shares_s) if shares_s else None
            price = float(price_s) if price_s else None
        except ValueError:
            shares, price = None, None
        if not shares or not price:
            continue
        transactions.append({
            "symbol": issuer_symbol,
            "insider": owner_name,
            "role": role,
            "transaction_code": code,
            "action": "Buy" if code == "P" else "Sell",
            "shares": shares,
            "price": round(price, 2),
            "value": round(shares * price, 0),
            "date": date_s,
        })
    return transactions


def main():
    try:
        universe = fetch_full_universe()
    except Exception as e:
        print(f"ERROR: could not build universe: {e}", file=sys.stderr)
        sys.exit(0)

    if not universe:
        print("ERROR: empty universe", file=sys.stderr)
        sys.exit(0)

    try:
        cik_map = build_cik_to_ticker(universe)
    except Exception as e:
        print(f"ERROR: could not build CIK map: {e}", file=sys.stderr)
        sys.exit(0)

    try:
        feed_entries = parse_current_feed()
    except Exception as e:
        print(f"ERROR: could not fetch current Form 4 feed: {e}", file=sys.stderr)
        sys.exit(0)

    all_transactions = []
    checked = 0
    for entry in feed_entries:
        cik = entry.get("cik")
        if not cik or cik not in cik_map:
            continue
        checked += 1
        txs = fetch_form4_details(cik, entry["accession"])
        all_transactions.extend(txs)
        time.sleep(0.2)

    if checked == 0 and len(feed_entries) > 0:
        print("WARN: none of this run's filings matched our universe - writing empty-but-valid result", file=sys.stderr)

    all_transactions.sort(key=lambda t: t["value"], reverse=True)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checked_filings": checked,
        "feed_size": len(feed_entries),
        "buys": [t for t in all_transactions if t["action"] == "Buy"][:MAX_ITEMS],
        "sells": [t for t in all_transactions if t["action"] == "Sell"][:MAX_ITEMS],
        "note": (
            "Official SEC Form 4 filings (Section 16 disclosures) for open-market "
            "buy/sell transactions by officers, directors, and 10%+ owners, filtered "
            "to S&P 500 + Nasdaq 100 companies. Grants, option exercises, gifts, and "
            "tax-withholding transactions are excluded. Not stock advice."
        ),
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {OUT_PATH}: {len(out['buys'])} buys, {len(out['sells'])} sells "
          f"({checked} matching filings out of {len(feed_entries)} in feed)")


if __name__ == "__main__":
    main()
