import sqlite3
import json
import os
from flask import Flask, render_template, request, redirect, url_for
import scraper as sc

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

    parts = []
    total = 0
    for city in cities:
        url = url_map.get(city)
        if not url:
            continue
        try:
            rows = sc.fetch_items(city, url)
            sc.save_rows(conn, rows)
            parts.append(f'{city} ({len(rows)})')
            total += len(rows)
        except Exception:
            parts.append(f'{city} (błąd)')

    conn.close()
    if parts:
        status = f'Pobrano {total} ofert: ' + ', '.join(parts)
    else:
        status = 'Nie wybrano żadnego miasta'
    return redirect(url_for('index', status=status))


if __name__ == '__main__':
    app.run(debug=True)
