import asyncio
import json
import sqlite3
import os
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

LOGIN_URL = 'https://www.otodom.pl/pl/zaloguj'


def init_history_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS offer_history (
            offer_id        INTEGER PRIMARY KEY,
            fetched_at      TEXT,
            price_history   TEXT,
            views_count     INTEGER,
            days_on_market  INTEGER,
            first_listed_at TEXT,
            raw_data        TEXT
        )
    """)
    conn.commit()


def save_history(conn, offer_id, data):
    conn.execute("""
        INSERT OR REPLACE INTO offer_history
            (offer_id, fetched_at, price_history, views_count,
             days_on_market, first_listed_at, raw_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        offer_id,
        datetime.now().isoformat(timespec='seconds'),
        json.dumps(data.get('price_history'), ensure_ascii=False) if data.get('price_history') else None,
        data.get('views_count'),
        data.get('days_on_market'),
        data.get('first_listed_at'),
        json.dumps(data, ensure_ascii=False),
    ))
    conn.commit()


async def login(page, email, password):
    await page.goto(LOGIN_URL, wait_until='domcontentloaded', timeout=30000)
    try:
        await page.click('[data-testid="accept-all-cookies-button"]', timeout=5000)
    except PlaywrightTimeout:
        pass
    await page.fill('input[data-testid="login-form-login"]', email)
    await page.fill('input[data-testid="login-form-password"]', password)
    await page.click('button[data-testid="login-form-submit"]')
    await page.wait_for_load_state('networkidle', timeout=15000)


async def fetch_history(page, url):
    """Navigate to offer page and extract Historia i statystyki data."""
    await page.goto(url, wait_until='domcontentloaded', timeout=30000)

    next_data = await page.evaluate("""() => {
        const el = document.getElementById('__NEXT_DATA__');
        return el ? JSON.parse(el.textContent) : null;
    }""")

    data = {}

    if next_data:
        try:
            ad = next_data['props']['pageProps']['ad']

            history = ad.get('priceChangeHistory') or []
            if history:
                data['price_history'] = [
                    {'date': h.get('date', ''), 'price': h.get('price', {}).get('value')}
                    for h in history
                ]

            stats = ad.get('statistics') or {}
            data['views_count']     = stats.get('uniqueViews')
            data['days_on_market']  = stats.get('daysOnMarket')
            data['first_listed_at'] = ad.get('dateCreated') or ad.get('dateCreatedFirst')
            data['_source']         = 'next_data'
        except (KeyError, TypeError):
            pass

    if not data.get('price_history'):
        try:
            await page.wait_for_selector('[data-testid="price-change-history"]', timeout=8000)
            items = await page.query_selector_all('[data-testid="price-change-item"]')
            ph = []
            for item in items:
                date_el  = await item.query_selector('[data-testid="price-change-date"]')
                price_el = await item.query_selector('[data-testid="price-change-value"]')
                if date_el and price_el:
                    ph.append({
                        'date':  (await date_el.inner_text()).strip(),
                        'price': (await price_el.inner_text()).strip(),
                    })
            if ph:
                data['price_history'] = ph
                data['_source'] = 'dom'
        except PlaywrightTimeout:
            pass

    return data if (data.get('price_history') or data.get('views_count') or data.get('days_on_market')) else None


async def run(offers, db_path, email, password, job):
    """Login once, then process all offers sequentially."""
    job.update({'running': True, 'done': 0, 'total': len(offers), 'error': None})
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page    = await browser.new_page()
            await login(page, email, password)

            conn = sqlite3.connect(db_path)
            init_history_db(conn)

            for offer in offers:
                if not offer.get('url'):
                    job['done'] += 1
                    continue
                try:
                    data = await fetch_history(page, offer['url'])
                    if data:
                        save_history(conn, offer['id'], data)
                except Exception:
                    pass
                job['done'] += 1

            conn.close()
            await browser.close()
    except Exception as e:
        job['error'] = str(e)
    finally:
        job['running'] = False
