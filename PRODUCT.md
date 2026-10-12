# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

A public audience the owner wants to grow: retail traders and market-curious investors who follow the S&P 500 and Nasdaq-100 (SPY/QQQ). They mostly check it on a phone around the US open — often in the evening in Israel, where the owner lives — to answer "how healthy is the market right now, and is anything worth a closer look?" A share-worthy first impression matters because growth comes from people passing the link along.

## Product Purpose

Market Pulse turns scattered market-health signals into one contrarian read: seven scored signals (trend vs the 150-day average, AAII sentiment, VIX, equal-weight participation, % of S&P 500 above the 50-day, defensive sector rotation, CNN Fear & Greed) averaged into a −100 (caution) to +100 (opportunity) composite. A second page, the Opportunity Scanner, screens the S&P 500 + Nasdaq-100 for insider buying/selling (SEC Form 4), sector leadership, 52-week highs/lows, unusual volume and moving-average tests. A third page, the Weekly Recap, is a Sunday pre-open brief: the week's moves, sector rotation, notable trades by politicians, famous investors and insiders, news, and the week-ahead calendar. Success: a visitor knows the market's state within seconds on a phone and comes back before each open.

## Positioning

A contrarian composite built from real, cited data and refreshed every ~10 minutes while the market is open, with every number stating how fresh it is; plus a human-readable Sunday brief that is checked against last week's calls. Free, no account, installable as a home-screen app.

## Operating Context

- Static site on GitHub Pages (`goavieldvir-rgb.github.io/Market-Pulse`), plain HTML/CSS/JS, no build step, installable PWA (manifest + service worker).
- Data is JSON in `data/`, produced by Python scripts in `scripts/` run by GitHub Actions: fast prices during the session, daily scans after the close, insider filings every ~2 hours, the weekly recap on Sundays.
- Sources: Yahoo Finance, CNN Fear & Greed (unofficial endpoint), AAII, SEC EDGAR, a community S&P 500 constituent list; the Weekly Recap's written content is researched each Sunday and approved by the owner via pull request.

## Capabilities and Constraints

- Every reading must show its as-of time; stale data is excluded from the composite with a visible notice.
- Scanner settings and the watchlist are stored per device (localStorage); no accounts.
- Must stay framework-free and fast on mobile networks; data files are fetched network-first.
- "Not financial advice" disclosure is required on every page.

## Brand Commitments

- The name "Market Pulse" is binding. Everything else about the current look (colors, gauge-as-hero, dark theme, fonts, logo mark) is open to replacement.

## Evidence on Hand

- Real live data files in `data/` (fast.json, breadth.json, aaii.json, daily_history.json, insiders.json, opportunities.json).
- No testimonials, user counts or press exist; none may be invented.

## Product Principles

1. The state of the market in one glance, then the evidence one tap deeper.
2. Honest freshness: every number says how old it is; stale beats invisible, wrong beats nothing never.
3. Contrarian, not predictive: frame readings as conditions, never as buy/sell signals.
4. Phone first: the evening check before the open is the main moment.
5. Free and open: no account walls, nothing that makes sharing awkward.

## Accessibility & Inclusion

Up/down and caution/opportunity must never rely on red/green hue alone (common color-vision deficiency); WCAG AA contrast; respects reduced motion.
