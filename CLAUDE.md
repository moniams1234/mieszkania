# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

A real estate scraper + viewer for apartment listings from Otodom.pl. It scrapes offers from Gdańsk, Warszawa, and Wrocław (up to 10 per city), stores them in a local SQLite database (`offers.db`), and serves them through a Flask web UI with filtering and sorting.

## Commands

**Run the scraper** (fetches fresh data into offers.db):
```
python scraper.py
```

**Run the web app**:
```
python app.py
```
Then open http://127.0.0.1:5000

**Run tests**:
```
pytest tests/
```

**Run a single test**:
```
pytest tests/test_app.py::test_index_returns_200
```

## Commands (new)

**Fetch NBP currency rates (last 18 months, one-time seeding):**
```
python currency_fetcher.py
```

**Apply DB migrations manually in Supabase SQL Editor:**
Run files in order: `migrations/001_*.sql`, `002_*.sql`, `003_*.sql`, `004_*.sql`

## Architecture

- `scraper.py` — hits Otodom listing pages, parses `__NEXT_DATA__` JSON, upserts rows.
- `app.py` — Flask app. Routes: `/`, `/offer/<id>` (detail+notes+tags), `/search/notes`, `/currency/set`, `/currency/fetch`, `/qr/generate`, `/qr/scan/<token>`.
- `currency_fetcher.py` — fetches NBP Table A rates, saves to Supabase `currency_rates`.
- `templates/index.html` — main dashboard with currency selector per user, detail links.
- `templates/offer_detail.html` — per-offer page: price in PLN/EUR/USD/GBP, price history chart, notes history, tags history.
- `templates/search_notes.html` — search offers by note content.
- `templates/qr_login.html` — QR code scan-to-login for mobile (5-min token, polling).
- `migrations/` — SQL migration files (apply manually in Supabase).
- `vercel.json` — Vercel config + daily cron at 07:00 UTC (`/currency/fetch`).
- `offers.db` — SQLite file for local dev.

## New env variables (.env)

```
DISCORD_ERRORS_WEBHOOK_URL=https://discord.com/api/webhooks/...   # kanał #błędy
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...           # kanał ogólny
```

## Testing

Tests in `tests/test_app.py` use Flask's test client and the real `offers.db`.
