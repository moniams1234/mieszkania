import sqlite3
import json
import os
import asyncio
import threading
import time as _time
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import requests as http
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import scraper as sc
import history_scraper as hs

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'otodom-scraper-dev-secret')
DB_PATH = os.path.join(os.path.dirname(__file__), 'offers.db')

_IS_VERCEL = bool(os.environ.get('VERCEL'))
_VERCEL_DB = '/tmp/offers.db'


def get_db_path():
    if _IS_VERCEL:
        # Vercel filesystem is read-only except /tmp; copy bundled DB on first use
        if not os.path.exists(_VERCEL_DB) and os.path.exists(DB_PATH):
            import shutil
            shutil.copy2(DB_PATH, _VERCEL_DB)
        return _VERCEL_DB
    return app.config.get('DB_PATH', DB_PATH)


def get_offers():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT id, city, title, price_pln, area_m2, rooms, floor, address, url, '
        'developer, market, development, district, scraped_at, first_scraped_at '
        'FROM offers ORDER BY id'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_investments():
    conn = sqlite3.connect(get_db_path())
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


def init_users_db():
    conn = sqlite3.connect(get_db_path())
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            login         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id   INTEGER NOT NULL,
            offer_id  INTEGER NOT NULL,
            added_at  TEXT NOT NULL,
            PRIMARY KEY (user_id, offer_id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()


CITY_COLORS = {'Gdansk': 0x2563eb, 'Warszawa': 0xd97706, 'Wroclaw': 0x059669}
_history_job = {'running': False, 'done': 0, 'total': 0, 'error': None}
CITY_LABELS = {'Gdansk': 'Gdańsk', 'Warszawa': 'Warszawa', 'Wroclaw': 'Wrocław'}


def send_discord_notification(all_rows, city_counts):
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        return

    def fmt(n): return f'{n:,}'.replace(',', ' ') + ' zł' if n else '—'

    for city, count in city_counts:
        rows    = [r for r in all_rows if r.get('city') == city]
        prices  = [r['price_pln'] for r in rows if r.get('price_pln')]
        areas   = [r['area_m2']   for r in rows if r.get('area_m2')]
        primary = sum(1 for r in rows if r.get('market') == 'pierwotny')
        pct     = round(primary / count * 100) if count else 0

        avg_price = int(sum(prices) / len(prices)) if prices else None
        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None
        avg_area  = sum(areas) / len(areas) if areas else None

        fields = [
            {'name': 'Średnia cena',     'value': fmt(avg_price),  'inline': True},
            {'name': 'Zakres cen',       'value': f'{fmt(min_price)} – {fmt(max_price)}', 'inline': True},
            {'name': 'Rynek pierwotny',  'value': f'{primary} ofert ({pct}%)', 'inline': True},
            {'name': 'Śr. powierzchnia', 'value': f'{avg_area:.1f} m²' if avg_area else '—', 'inline': True},
        ]

        payload = {
            'embeds': [{
                'title': f'🏠 {CITY_LABELS.get(city, city)} — pobrano {count} ofert',
                'color': CITY_COLORS.get(city, 0x2563eb),
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

    favorite_ids = []
    if 'user_id' in session:
        conn = sqlite3.connect(get_db_path())
        rows = conn.execute(
            'SELECT offer_id FROM favorites WHERE user_id = ?', (session['user_id'],)
        ).fetchall()
        conn.close()
        favorite_ids = [r[0] for r in rows]

    return render_template(
        'index.html',
        offers_json=json.dumps(offers, ensure_ascii=False),
        investments_json=json.dumps(investments, ensure_ascii=False),
        status=status,
        username=session.get('username'),
        favorite_ids=json.dumps(favorite_ids),
    )


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if request.method == 'POST':
        login_val = request.form.get('login', '').strip()
        password  = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        if not login_val or not password:
            return render_template('register.html', error='Uzupełnij wszystkie pola')
        if password != password2:
            return render_template('register.html', error='Hasła nie są zgodne')
        if len(password) < 4:
            return render_template('register.html', error='Hasło musi mieć co najmniej 4 znaki')
        conn = sqlite3.connect(get_db_path())
        try:
            conn.execute(
                'INSERT INTO users (login, password_hash, created_at) VALUES (?, ?, ?)',
                (login_val, generate_password_hash(password), datetime.now().isoformat(timespec='seconds'))
            )
            conn.commit()
            conn.close()
            return redirect(url_for('login_page', registered=1))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error='Ta nazwa użytkownika jest już zajęta')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        login_val = request.form.get('login', '').strip()
        password  = request.form.get('password', '')
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        user = conn.execute('SELECT * FROM users WHERE login = ?', (login_val,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id']  = user['id']
            session['username'] = user['login']
            return redirect(url_for('index'))
        return render_template('login.html', error='Nieprawidłowy login lub hasło')
    return render_template('login.html', registered=request.args.get('registered'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/favorites/add', methods=['POST'])
def favorites_add():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'error': 'not logged in'}), 401
    data     = request.get_json()
    offer_id = data.get('offer_id') if data else None
    if not offer_id:
        return jsonify({'ok': False}), 400
    conn = sqlite3.connect(get_db_path())
    conn.execute(
        'INSERT OR IGNORE INTO favorites (user_id, offer_id, added_at) VALUES (?, ?, ?)',
        (session['user_id'], offer_id, datetime.now().isoformat(timespec='seconds'))
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/favorites/remove', methods=['POST'])
def favorites_remove():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'error': 'not logged in'}), 401
    data     = request.get_json()
    offer_id = data.get('offer_id') if data else None
    if not offer_id:
        return jsonify({'ok': False}), 400
    conn = sqlite3.connect(get_db_path())
    conn.execute(
        'DELETE FROM favorites WHERE user_id = ? AND offer_id = ?',
        (session['user_id'], offer_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/scrape', methods=['POST'])
def scrape():
    cities  = request.form.getlist('cities')
    url_map = dict(sc.URLS)
    conn    = sqlite3.connect(get_db_path())
    sc.init_db(conn)

    parts       = []
    all_rows    = []
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

    status = (f'Pobrano {len(all_rows)} ofert: ' + ', '.join(parts)) if parts else 'Nie wybrano żadnego miasta'
    return redirect(url_for('index', status=status))


def _auto_scrape_task():
    while True:
        try:
            conn = sqlite3.connect(get_db_path())
            sc.init_db(conn)
            all_rows, city_counts = [], []
            for city, url in sc.URLS:
                try:
                    rows = sc.fetch_items(city, url)
                    sc.save_rows(conn, rows)
                    all_rows.extend(rows)
                    city_counts.append((city, len(rows)))
                except Exception:
                    pass
            conn.close()
            if all_rows:
                send_discord_notification(all_rows, city_counts)
        except Exception:
            pass
        _time.sleep(15 * 60)


@app.route('/history/fetch', methods=['POST'])
def history_fetch():
    email    = os.getenv('OTODOM_EMAIL')
    password = os.getenv('OTODOM_PASSWORD')
    if not email or not password:
        return jsonify({'ok': False, 'error': 'Brak OTODOM_EMAIL lub OTODOM_PASSWORD w pliku .env'}), 400
    if _history_job['running']:
        return jsonify({'ok': False, 'error': 'Pobieranie już trwa'}), 409

    offers = [o for o in get_offers() if o.get('url')]

    def _run():
        asyncio.run(hs.run(offers, get_db_path(), email, password, _history_job))

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({'ok': True, 'total': len(offers)})


@app.route('/history/status')
def history_status():
    return jsonify(_history_job)


@app.route('/history/<int:offer_id>')
def history_data(offer_id):
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    hs.init_history_db(conn)
    row = conn.execute(
        'SELECT * FROM offer_history WHERE offer_id = ?', (offer_id,)
    ).fetchone()
    conn.close()
    if not row:
        return jsonify(None)
    d = dict(row)
    if d.get('price_history'):
        d['price_history'] = json.loads(d['price_history'])
    return jsonify(d)


init_users_db()

# Start background scraper only locally (Vercel serverless can't run persistent threads)
if not _IS_VERCEL and (not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'):
    threading.Thread(target=_auto_scrape_task, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
