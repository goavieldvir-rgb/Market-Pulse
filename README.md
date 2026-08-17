# Market Pulse

A shareable, installable dashboard summarizing SPY/QQQ market health across
trend, sentiment, breadth, volatility, and sector rotation — built as a static
site + GitHub Actions, so it needs no server, login, or paid API keys.

## What it shows

1. **Trend** — SPY/QQQ distance from the 150-day SMA
2. **Momentum streak** — consecutive green/red days for SPY & QQQ
3. **AAII sentiment** — weekly bull/bear survey spread
4. **VIX** — CBOE volatility index
5. **Market participation** — equal-weight (RSP) vs cap-weight (SPY), a proxy for how broad the rally is
6. **Breadth** — % of S&P 500 stocks above their 50-day SMA (a free approximation of the S5FI-style reading)
7. **Defensive sector rotation** — Utilities/Staples (XLU/XLP) vs Discretionary (XLY)
8. **CNN Fear & Greed Index**

...plus a composite "contrarian gauge" that blends all of the above into one read.

## How it stays "live" without a backend or API keys

Two scheduled **GitHub Actions** workflows do the data fetching server-side
(no CORS or browser rate-limit issues) and commit small JSON files back into
the repo. The static page just reads those files.

- `.github/workflows/update-fast.yml` — runs every **15 minutes**, all day,
  weekdays. Refreshes price/SMA/VIX/sector/Fear&Greed data
  (`data/fast.json`). Yahoo's free quote data is itself typically ~15 minutes
  delayed, so this is roughly the practical ceiling for "real-time" without a
  paid feed (Finnhub, Polygon, etc.).
- `.github/workflows/update-slow.yml` — runs **once a day** after the close.
  Refreshes S&P 500 breadth and AAII sentiment (`data/breadth.json`,
  `data/aaii.json`) — both are inherently slow-moving (breadth barely shifts
  intraday; AAII only publishes weekly, on Thursdays).

All data sources are free and public, with no API key:
- Yahoo Finance's public chart/quote endpoints (price history, VIX, sectors, 50-day averages)
- CNN's Fear & Greed Index — an **unofficial** public endpoint (CNN doesn't offer
  a documented API; this can break if they change their site, in which case
  the fast workflow just logs a warning and leaves the field blank rather than failing)
- AAII.com's public sentiment survey page — scraped best-effort (same caveat as above)
- A community-maintained S&P 500 constituent list (`github.com/datasets/s-and-p-500-companies`)

If a source changes shape, the affected script fails soft — it prints a
warning to the workflow log and leaves the previous value in place rather
than breaking the whole dashboard.

## Deploying this yourself

1. Create a new **public** GitHub repo and push this folder to it.
2. In the repo, go to **Settings → Actions → General → Workflow permissions**
   and select **"Read and write permissions"**. This lets the scheduled
   workflows commit the refreshed JSON files back to the repo.
3. Go to **Settings → Pages**, set Source to **"Deploy from a branch"**,
   branch `main`, folder `/ (root)`. Save.
4. Your dashboard will be live at `https://<your-username>.github.io/<repo-name>/`.
5. Optionally, go to the **Actions** tab and manually run "Update fast market
   data" and "Update slow market data" once each (via "Run workflow") so the
   page has real data immediately instead of waiting for the next scheduled run.
6. Share the Pages URL. Anyone can open it and "Add to Home Screen" — no
   login or account needed.

### Notes / things you may want to tweak
- Public repos get free, effectively unlimited GitHub Actions minutes for
  this kind of light job — a private repo would eventually hit the free
  minutes cap given a 15-minute schedule.
- GitHub's scheduled workflows are "best effort" and can be delayed a few
  minutes during high load on GitHub's side — don't expect second-perfect timing.
- The composite gauge's scoring thresholds (in `index.html`, near the bottom)
  are simple linear heuristics you set yourself — tune them if you disagree
  with where "caution" vs "opportunity" should kick in.
- `scripts/fetch_breadth.py` pulls the full S&P 500 list fresh each run, so
  it stays current with index changes automatically.
