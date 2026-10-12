# Security

Market Pulse is a static site: no accounts, no server code and no secrets. Pages render only
data files from this repository, and every value from those files is escaped before display.

## Reporting a problem

Please report anything that could run code in a visitor's browser, alter published data, or
misuse the repository's automation privately through GitHub's
**Security → Report a vulnerability** form on this repository, not in a public issue.

## How the site protects itself

- All text from data files (prices, SEC filings, weekly editions) is HTML-escaped before display;
  links are rendered only for `http`/`https` URLs.
- Weekly editions must pass `scripts/weekly_edition.py validate` and are published only by
  merging a reviewed pull request.
- Workflows run only on a schedule or by hand (never on pull requests from forks), declare the
  minimum permissions they need, and use no repository secrets.
- Secret scanning and push protection are enabled.
