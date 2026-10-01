"""
Shared helpers for the data scripts (standard library only):
  - HTTP GET with retries + gzip
  - Yahoo Finance daily bars (open/high/low/close/volume + quote metadata)
  - exchange-session helpers: is the latest daily bar final? is the market open?
  - small JSON read/write helpers
"""
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# A daily bar is treated as final this long after the official close, so the
# closing auction print has landed before we count the day as "done".
FINAL_BUFFER_SECONDS = 10 * 60

SP500_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
NASDAQ100_URL = "https://yfiua.github.io/index-constituents/constituents-nasdaq100.csv"


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def warn(msg):
    # "::warning::" lines show up as yellow annotations on the GitHub Actions run page.
    print(f"::warning::{msg}", flush=True)


# ---------------------------------------------------------------- HTTP ----

RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def http_get(url, headers=None, timeout=20, retries=2, backoff=2.0):
    hdrs = {"User-Agent": BROWSER_UA, "Accept-Encoding": "gzip"}
    if headers:
        hdrs.update(headers)
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
                if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                    body = gzip.decompress(body)
                return body
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code not in RETRYABLE_HTTP or attempt == retries:
                raise
        except Exception as e:  # timeouts, resets, TLS hiccups
            last_err = e
            if attempt == retries:
                raise
        time.sleep(backoff * (attempt + 1))
    raise last_err  # pragma: no cover


def http_json(url, **kw):
    return json.loads(http_get(url, **kw).decode("utf-8"))


def http_text(url, **kw):
    return http_get(url, **kw).decode("utf-8", errors="replace")


# ---------------------------------------------------------------- JSON ----

def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if compact:
            json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
        else:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso_from_ts(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds")


def rnd(v, digits=2):
    return None if v is None else round(v, digits)


def pct_change(frm, to):
    if frm in (0, None) or to is None:
        return None
    return (to - frm) / frm * 100.0


# ------------------------------------------------------------- Yahoo ------

def _at(arr, i):
    try:
        v = arr[i]
    except (TypeError, IndexError):
        return None
    return v if isinstance(v, (int, float)) else None


def parse_yahoo_chart(payload):
    """Turns a v8 chart response into {"meta", "tz", "bars"}. Bars carry the
    session date in exchange time (America/New_York for US listings), not UTC."""
    try:
        res = payload["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        return None
    meta = res.get("meta") or {}
    try:
        tz = ZoneInfo(meta.get("exchangeTimezoneName") or "America/New_York")
    except Exception:
        tz = ET
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0] or {}
    closes, highs, lows = q.get("close"), q.get("high"), q.get("low")
    opens, vols = q.get("open"), q.get("volume")
    by_date = {}
    for i, ts in enumerate(res.get("timestamp") or []):
        c = _at(closes, i)
        if c is None or c <= 0:
            continue
        d = datetime.fromtimestamp(ts, tz).date().isoformat()
        h, lo = _at(highs, i), _at(lows, i)
        by_date[d] = {  # a repeated date (Yahoo sometimes re-sends the live bar) keeps the latest
            "t": ts, "date": d, "o": _at(opens, i),
            "h": max(h, c) if h else c, "l": min(lo, c) if lo else c,
            "c": float(c), "v": _at(vols, i) or 0,
        }
    bars = [by_date[d] for d in sorted(by_date)]
    return {"meta": meta, "tz": tz, "bars": bars}


def yahoo_daily(symbol, range_="1y"):
    """Daily bars for one symbol, or None. Tries both Yahoo hosts."""
    enc = urllib.parse.quote(symbol, safe="")
    last_err = None
    for host in ("query1", "query2"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{enc}"
               f"?range={range_}&interval=1d&includePrePost=false")
        try:
            chart = parse_yahoo_chart(http_json(url, timeout=15, retries=1))
            if chart and chart["bars"]:
                return chart
            last_err = "empty response"
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 404:
                break
        except Exception as e:
            last_err = e
    log(f"WARN: Yahoo {symbol}: {last_err}")
    return None


# ------------------------------------------------------ Market session ----

def regular_period(meta):
    reg = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    start, end = reg.get("start"), reg.get("end")
    if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
        return int(start), int(end)
    return None, None


def _default_close_ts(day_iso, tz, symbol):
    d = date.fromisoformat(day_iso)
    hh, mm = (16, 15) if symbol == "^VIX" else (16, 0)  # VIX settles at 4:15pm ET
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz).timestamp()


def last_bar_is_final(chart, now=None):
    """True when the newest daily bar belongs to a session that has already
    closed (plus a short buffer). Mid-session, or pre-market for instruments
    that print early (e.g. VIX), the newest bar is still moving."""
    now = time.time() if now is None else now
    bars = chart.get("bars") or []
    if not bars:
        return True
    meta, tz = chart.get("meta") or {}, chart.get("tz") or ET
    last_day = bars[-1]["date"]
    start, end = regular_period(meta)
    if start and datetime.fromtimestamp(start, tz).date().isoformat() == last_day:
        close_ts = end
    else:
        close_ts = _default_close_ts(last_day, tz, meta.get("symbol"))
    return now >= close_ts + FINAL_BUFFER_SECONDS


def completed_bars(chart, now=None):
    bars = chart.get("bars") or []
    return bars if last_bar_is_final(chart, now) else bars[:-1]


def market_state(chart, now=None):
    """('open' | 'pre' | 'closed', session_start_ts, session_end_ts) for the
    US session, judged from a US-listed instrument's quote metadata. Falls
    back to the clock (Mon-Fri 9:30-16:00 ET) if Yahoo omits the periods."""
    now = time.time() if now is None else now
    meta = (chart or {}).get("meta") or {}
    start, end = regular_period(meta)
    if not start:
        local = datetime.fromtimestamp(now, ET)
        start = local.replace(hour=9, minute=30, second=0, microsecond=0).timestamp()
        end = local.replace(hour=16, minute=0, second=0, microsecond=0).timestamp()
        if local.weekday() >= 5:
            return "closed", start, end
    if now < start:
        return ("pre" if start - now <= 6 * 3600 else "closed"), start, end
    if now < end:
        last_trade = meta.get("regularMarketTime")
        # Holiday guard: the calendar says "open" but nothing has traded since the bell.
        if isinstance(last_trade, (int, float)) and last_trade < start and now - start > 300:
            return "closed", start, end
        return "open", start, end
    return "closed", start, end


# ------------------------------------------------------------ Universe ----

def normalize_symbol(sym):
    return sym.strip().upper().replace(".", "-")


def _csv_symbols(text):
    import csv
    import io
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        sym = (row.get("Symbol") or row.get("symbol") or row.get("Ticker")
               or row.get("ticker") or row.get("code") or row.get("Code"))
        if sym and sym.strip():
            out.append(normalize_symbol(sym))
    return out


def fetch_universe():
    """(sp500_list, nasdaq100_list) - either may be empty if its source failed."""
    sp500, ndx = [], []
    try:
        sp500 = _csv_symbols(http_text(SP500_URL))
    except Exception as e:
        log(f"WARN: could not fetch S&P 500 list: {e}")
    try:
        ndx = _csv_symbols(http_text(NASDAQ100_URL))
    except Exception as e:
        log(f"WARN: could not fetch Nasdaq-100 list: {e}")
    return sp500, ndx
