import sqlite3
import json
import os
from flask import Flask, render_template, request, redirect, url_for
import requests as http
from dotenv import load_dotenv
import scraper as sc

load_dotenv()

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'offers.db')


def get_offers():
    db_path = app.config.get('DB_PATH', DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT id, city, title, price_pln, area_m2, rooms, floor, address, url, '
        'developer, market, development, district, scraped_at FROM offers ORDER BY id'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_investments():
    db_path = app.config.get('DB_PATH', DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            'SELECT id, developer, city, district, investment_name, status, '
            'apartments_total, price_min, price_max, completion_year '
            'FROM investments ORDER BY city, developer, completion_year DESC'
        ).fetchall()
    except Exception:
        rows = []
    conn.close()
    return [dict(r) for r in rows]


def send_discord_notification(all_rows, city_counts):
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        return

    prices = [r['price_pln'] for r in all_rows if r.get('price_pln')]
    areas  = [r['area_m2']   for r in all_rows if r.get('area_m2')]
    primary = sum(1 for r in all_rows if r.get('market') == 'pierwotny')

    avg_price  = int(sum(prices) / len(prices)) if prices else None
    min_price  = min(prices) if prices else None
    max_price  = max(prices) if prices else None
    avg_area   = sum(areas) / len(areas) if areas else None
    total      = len(all_rows)

    city_line = ' | '.join(f'{city}: {n}' for city, n in city_counts)
    pct = round(primary / total * 100) if total else 0

    def fmt(n): return f'{n:,}'.replace(',', ' ') + ' zł' if n else '—'

    fields = [
        {'name': 'Pobrane oferty', 'value': f'📍 {city_line}', 'inline': False},
        {'name': 'Średnia cena',   'value': fmt(avg_price),    'inline': True},
        {'name': 'Zakres cen',     'value': f'{fmt(min_price)} – {fmt(max_price)}', 'inline': True},
        {'name': 'Rynek pierwotny','value': f'{primary} ofert ({pct}%)',            'inline': True},
        {'name': 'Śr. powierzchnia','value': f'{avg_area:.1f} m²' if avg_area else '—', 'inline': True},
    ]

    payload = {
        'embeds': [{
            'title': f'🏠 Nowe oferty z Otodom — pobrano {total} ofert',
            'color': 0x2563eb,
            'fields': fields,
            'footer': {'text': 'Otodom scraper'},
        }]
    }
    try:
        http.post(webhook_url, json=payload, timeout=10)
    except Exception:
        pass


@app.route('/')
def index():
    offers      = get_offers()
    investments = get_investments()
    status      = request.args.get('status', '')
    return render_template(
        'index.html',
        offers_json=json.dumps(offers, ensure_ascii=False),
        investments_json=json.dumps(investments, ensure_ascii=False),
        status=status,
    )


@app.route('/scrape', methods=['POST'])
def scrape():
    cities = request.form.getlist('cities')
    url_map = dict(sc.URLS)
    db_path = app.config.get('DB_PATH', DB_PATH)
    conn = sqlite3.connect(db_path)
    sc.init_db(conn)

    parts     = []
    all_rows  = []
    city_counts = []
    for city in cities:
        url = url_map.get(city)
        if not url:
            continue
        try:
            rows = sc.fetch_items(city, url)
            sc.save_rows(conn, rows)
            parts.append(f'{city} ({len(rows)})')
            all_rows.extend(rows)
            city_counts.append((city, len(rows)))
        except Exception:
            parts.append(f'{city} (błąd)')

    conn.close()

    if all_rows:
        send_discord_notification(all_rows, city_counts)

    if parts:
        status = f'Pobrano {len(all_rows)} ofert: ' + ', '.join(parts)
    else:
        status = 'Nie wybrano żadnego miasta'
    return redirect(url_for('index', status=status))


if __name__ == '__main__':
    app.run(debug=True)
