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

## Architecture

- `scraper.py` — hits Otodom listing pages, parses the embedded `__NEXT_DATA__` JSON, and upserts rows into `offers.db`. The `INVESTMENT` estate type wraps multiple real listings in `relatedAds`; these are expanded before saving. Enum-string values for rooms and floor are translated via `ROOMS_MAP` / `FLOOR_MAP`.
- `app.py` — minimal Flask app with a single route (`/`). Reads all offers from SQLite and passes them as a JSON blob to the template.
- `templates/index.html` — self-contained single-page UI. Offers are injected server-side as `offersData` JS variable; all filtering, sorting, and rendering happen client-side in vanilla JS.
- `offers.db` — SQLite file, schema defined in `scraper.init_db()`. Primary key is the Otodom listing `id`.

## Testing

Tests in `tests/test_app.py` use Flask's test client and the real `offers.db`. The `DB_PATH` app config key lets tests point to a different database if needed.
