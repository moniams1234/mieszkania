import sqlite3
import json
import os
import uuid
import asyncio
import threading
import time as _time
import io
import base64
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
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

# ── Supabase ──────────────────────────────────────────────────────
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

_supa_client = None

DISCORD_ERRORS_WEBHOOK = os.getenv('DISCORD_ERRORS_WEBHOOK_URL', '')


def supa():
    global _supa_client
    if _supa_client is None:
        from supabase import create_client
        _supa_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supa_client


# ── Discord powiadomienia o błędach ──────────────────────────────
def send_discord_error(message: str):
    """Wysyła błąd na kanał #błędy Discord."""
    webhook = DISCORD_ERRORS_WEBHOOK or os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook:
        return
    payload = {
        'embeds': [{
            'title': '🚨 Błąd aplikacji mieszkania',
            'description': message,
            'color': 0xf87171,
            'footer': {'text': 'Otodom scraper'},
            'timestamp': datetime.utcnow().isoformat(),
        }]
    }
    try:
        http.post(webhook, json=payload, timeout=10)
    except Exception:
        pass


# ── SQLite fallback (gdy brak Supabase) ──────────────────────────
if _IS_VERCEL and not USE_SUPABASE and not os.path.exists(_VERCEL_DB):
    import shutil
    _bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'offers.db')
    if os.path.exists(_bundled):
        shutil.copy2(_bundled, _VERCEL_DB)


def get_db_path():
    if _IS_VERCEL:
        return _VERCEL_DB
    return app.config.get('DB_PATH', DB_PATH)


# ── Pobieranie ofert / inwestycji ────────────────────────────────
def get_offers():
    if USE_SUPABASE:
        res = supa().table('offers').select(
            'id,city,title,price_pln,area_m2,rooms,floor,'
            'address,url,developer,market,development,district,'
            'scraped_at,first_scraped_at'
        ).order('id').execute()
        return res.data or []
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
    if USE_SUPABASE:
        res = supa().table('investments').select(
            'id,developer,city,district,investment_name,status,'
            'apartments_total,price_min,price_max,completion_year'
        ).order('city').order('developer').order('completion_year', desc=True).execute()
        return res.data or []
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


# ── Init bazy (SQLite lokalnie) ───────────────────────────────────
def init_users_db():
    if USE_SUPABASE:
        return
    conn = sqlite3.connect(get_db_path())
    sc.init_db(conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            login             TEXT UNIQUE NOT NULL,
            password_hash     TEXT NOT NULL,
            created_at        TEXT NOT NULL,
            preferred_currency TEXT NOT NULL DEFAULT 'PLN'
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS currency_rates (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            currency       TEXT NOT NULL,
            currency_name  TEXT NOT NULL,
            rate           REAL NOT NULL,
            effective_date TEXT NOT NULL,
            table_no       TEXT,
            fetched_at     TEXT NOT NULL,
            UNIQUE(currency, effective_date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS offer_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            offer_id   INTEGER NOT NULL,
            note_text  TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS offer_tags (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            offer_id   INTEGER NOT NULL,
            tag        TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qr_login_tokens (
            token      TEXT PRIMARY KEY,
            user_id    INTEGER,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used       INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


# ── Kursy walut ──────────────────────────────────────────────────
def get_latest_rates(currencies=None):
    """Zwraca {KOD: kurs_PLN} dla najnowszych dostępnych kursów."""
    if USE_SUPABASE:
        query = supa().table('currency_rates').select(
            'currency, rate, effective_date'
        ).order('effective_date', desc=True).limit(500)
        if currencies:
            query = query.in_('currency', currencies)
        res = query.execute()
        seen = {}
        for row in (res.data or []):
            code = row['currency']
            if code not in seen:
                seen[code] = float(row['rate'])
        return seen
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    q = 'SELECT currency, rate, effective_date FROM currency_rates ORDER BY effective_date DESC'
    rows = conn.execute(q).fetchall()
    conn.close()
    seen = {}
    for row in rows:
        code = row['currency']
        if currencies and code not in currencies:
            continue
        if code not in seen:
            seen[code] = float(row['rate'])
    return seen


CITY_COLORS = {'Gdansk': 0x2563eb, 'Warszawa': 0xd97706, 'Wroclaw': 0x059669}
_history_job = {'running': False, 'done': 0, 'total': 0, 'error': None}
CITY_LABELS = {'Gdansk': 'Gdańsk', 'Warszawa': 'Warszawa', 'Wroclaw': 'Wrocław'}

POPULAR_CURRENCIES = ['EUR', 'USD', 'GBP', 'CHF', 'CZK', 'NOK', 'SEK']


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


# ── Strona główna ────────────────────────────────────────────────
@app.route('/')
def index():
    offers      = get_offers()
    investments = get_investments()
    status      = request.args.get('status', '')

    favorite_ids = []
    preferred_currency = 'PLN'
    rates = {}

    if 'user_id' in session:
        if USE_SUPABASE:
            res = supa().table('favorites').select('offer_id').eq(
                'user_id', session['user_id']
            ).execute()
            favorite_ids = [r['offer_id'] for r in (res.data or [])]
            u_res = supa().table('users').select('preferred_currency').eq(
                'id', session['user_id']
            ).execute()
            if u_res.data:
                preferred_currency = u_res.data[0].get('preferred_currency', 'PLN')
        else:
            conn = sqlite3.connect(get_db_path())
            rows = conn.execute(
                'SELECT offer_id FROM favorites WHERE user_id = ?', (session['user_id'],)
            ).fetchall()
            u_row = conn.execute(
                'SELECT preferred_currency FROM users WHERE id = ?', (session['user_id'],)
            ).fetchone()
            conn.close()
            favorite_ids = [r[0] for r in rows]
            if u_row:
                preferred_currency = u_row[0] or 'PLN'

        if preferred_currency != 'PLN':
            rates = get_latest_rates([preferred_currency])

    return render_template(
        'index.html',
        offers_json=json.dumps(offers, ensure_ascii=False),
        investments_json=json.dumps(investments, ensure_ascii=False),
        status=status,
        username=session.get('username'),
        favorite_ids=json.dumps(favorite_ids),
        preferred_currency=preferred_currency,
        currency_rates=json.dumps(rates),
        popular_currencies=POPULAR_CURRENCIES,
    )


# ── Rejestracja / logowanie ──────────────────────────────────────
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
        if USE_SUPABASE:
            try:
                supa().table('users').insert({
                    'login':              login_val,
                    'password_hash':      generate_password_hash(password),
                    'created_at':         datetime.now().isoformat(timespec='seconds'),
                    'preferred_currency': 'PLN',
                }).execute()
                return redirect(url_for('login_page', registered=1))
            except Exception as e:
                if 'duplicate' in str(e).lower() or '23505' in str(e):
                    return render_template('register.html', error='Ta nazwa użytkownika jest już zajęta')
                raise
        conn = sqlite3.connect(get_db_path())
        try:
            conn.execute(
                'INSERT INTO users (login, password_hash, created_at, preferred_currency) VALUES (?, ?, ?, ?)',
                (login_val, generate_password_hash(password),
                 datetime.now().isoformat(timespec='seconds'), 'PLN')
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
        if USE_SUPABASE:
            res  = supa().table('users').select('*').eq('login', login_val).execute()
            user = res.data[0] if res.data else None
        else:
            conn = sqlite3.connect(get_db_path())
            conn.row_factory = sqlite3.Row
            row  = conn.execute('SELECT * FROM users WHERE login = ?', (login_val,)).fetchone()
            conn.close()
            user = dict(row) if row else None

        if user and check_password_hash(user['password_hash'], password):
            session['user_id']  = user['id']
            session['username'] = user['login']
            return redirect(url_for('index'))

        send_discord_error(
            f'❌ Nieudane logowanie dla użytkownika `{login_val}` '
            f'o {datetime.now().isoformat(timespec="seconds")}'
        )
        return render_template('login.html', error='Nieprawidłowy login lub hasło')
    return render_template('login.html', registered=request.args.get('registered'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


# ── Waluta użytkownika ────────────────────────────────────────────
@app.route('/currency/set', methods=['POST'])
def set_currency():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'error': 'not logged in'}), 401
    data     = request.get_json()
    currency = (data.get('currency') or 'PLN').upper()
    if len(currency) > 3:
        return jsonify({'ok': False, 'error': 'invalid currency'}), 400

    if USE_SUPABASE:
        supa().table('users').update({'preferred_currency': currency}).eq(
            'id', session['user_id']
        ).execute()
    else:
        conn = sqlite3.connect(get_db_path())
        conn.execute(
            'UPDATE users SET preferred_currency = ? WHERE id = ?',
            (currency, session['user_id'])
        )
        conn.commit()
        conn.close()
    return jsonify({'ok': True, 'currency': currency})


@app.route('/currency/rates')
def currency_rates():
    """Zwraca aktualne kursy dla podanych walut (query param: codes=EUR,USD)."""
    codes_param = request.args.get('codes', '')
    codes = [c.strip().upper() for c in codes_param.split(',') if c.strip()] or None
    rates = get_latest_rates(codes)
    return jsonify(rates)


# ── Strona szczegółów ogłoszenia ──────────────────────────────────
@app.route('/offer/<int:offer_id>')
def offer_detail(offer_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    offer = None
    if USE_SUPABASE:
        res = supa().table('offers').select('*').eq('id', offer_id).execute()
        if res.data:
            offer = res.data[0]
    else:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM offers WHERE id = ?', (offer_id,)).fetchone()
        conn.close()
        offer = dict(row) if row else None

    if not offer:
        return 'Ogłoszenie nie znalezione', 404

    # Historia cenowa
    price_history = []
    if USE_SUPABASE:
        res = supa().table('offer_history').select('price_history').eq(
            'offer_id', offer_id
        ).execute()
        if res.data and res.data[0].get('price_history'):
            price_history = json.loads(res.data[0]['price_history'])
    else:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            'SELECT price_history FROM offer_history WHERE offer_id = ?', (offer_id,)
        ).fetchone()
        conn.close()
        if row and row['price_history']:
            price_history = json.loads(row['price_history'])

    # Kursy 3 walut (PLN + EUR + USD)
    display_currencies = ['EUR', 'USD', 'GBP']
    rates = get_latest_rates(display_currencies)

    # Notatki użytkownika
    notes = _get_notes(session['user_id'], offer_id)
    tags  = _get_tags(session['user_id'], offer_id)

    # Preferowana waluta usera
    preferred_currency = 'PLN'
    if USE_SUPABASE:
        u_res = supa().table('users').select('preferred_currency').eq(
            'id', session['user_id']
        ).execute()
        if u_res.data:
            preferred_currency = u_res.data[0].get('preferred_currency', 'PLN')
    else:
        conn = sqlite3.connect(get_db_path())
        u_row = conn.execute(
            'SELECT preferred_currency FROM users WHERE id = ?', (session['user_id'],)
        ).fetchone()
        conn.close()
        preferred_currency = (u_row[0] if u_row else None) or 'PLN'

    return render_template(
        'offer_detail.html',
        offer=offer,
        price_history=json.dumps(price_history, ensure_ascii=False),
        rates=json.dumps(rates),
        display_currencies=display_currencies,
        notes=notes,
        tags=tags,
        username=session.get('username'),
        preferred_currency=preferred_currency,
    )


# ── Notatki ──────────────────────────────────────────────────────
def _get_notes(user_id, offer_id):
    if USE_SUPABASE:
        res = supa().table('offer_notes').select('*').eq(
            'user_id', user_id
        ).eq('offer_id', offer_id).order('created_at', desc=True).execute()
        return res.data or []
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM offer_notes WHERE user_id=? AND offer_id=? ORDER BY created_at DESC',
        (user_id, offer_id)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _get_tags(user_id, offer_id):
    if USE_SUPABASE:
        res = supa().table('offer_tags').select('*').eq(
            'user_id', user_id
        ).eq('offer_id', offer_id).order('created_at', desc=True).execute()
        return res.data or []
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT * FROM offer_tags WHERE user_id=? AND offer_id=? ORDER BY created_at DESC',
        (user_id, offer_id)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.route('/offer/<int:offer_id>/notes', methods=['POST'])
def add_note(offer_id):
    if 'user_id' not in session:
        return jsonify({'ok': False}), 401
    data = request.get_json()
    note_text = (data.get('note') or '').strip()
    if not note_text:
        return jsonify({'ok': False, 'error': 'Treść notatki jest pusta'}), 400
    now = datetime.now().isoformat(timespec='seconds')
    if USE_SUPABASE:
        res = supa().table('offer_notes').insert({
            'user_id': session['user_id'],
            'offer_id': offer_id,
            'note_text': note_text,
            'created_at': now,
        }).execute()
        note = res.data[0] if res.data else {}
    else:
        conn = sqlite3.connect(get_db_path())
        cur = conn.execute(
            'INSERT INTO offer_notes (user_id, offer_id, note_text, created_at) VALUES (?, ?, ?, ?)',
            (session['user_id'], offer_id, note_text, now)
        )
        conn.commit()
        note = {'id': cur.lastrowid, 'note_text': note_text, 'created_at': now}
        conn.close()
    return jsonify({'ok': True, 'note': note})


@app.route('/offer/<int:offer_id>/tags', methods=['POST'])
def add_tag(offer_id):
    if 'user_id' not in session:
        return jsonify({'ok': False}), 401
    data = request.get_json()
    tag = (data.get('tag') or '').strip().lower()
    if not tag or len(tag) > 50:
        return jsonify({'ok': False, 'error': 'Nieprawidłowy tag'}), 400
    now = datetime.now().isoformat(timespec='seconds')
    if USE_SUPABASE:
        res = supa().table('offer_tags').insert({
            'user_id': session['user_id'],
            'offer_id': offer_id,
            'tag': tag,
            'created_at': now,
        }).execute()
        tag_obj = res.data[0] if res.data else {}
    else:
        conn = sqlite3.connect(get_db_path())
        cur = conn.execute(
            'INSERT INTO offer_tags (user_id, offer_id, tag, created_at) VALUES (?, ?, ?, ?)',
            (session['user_id'], offer_id, tag, now)
        )
        conn.commit()
        tag_obj = {'id': cur.lastrowid, 'tag': tag, 'created_at': now}
        conn.close()
    return jsonify({'ok': True, 'tag': tag_obj})


# ── Wyszukiwanie po notatkach ────────────────────────────────────
@app.route('/search/notes')
def search_by_notes():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    q = request.args.get('q', '').strip()
    results = []
    if q:
        if USE_SUPABASE:
            notes_res = supa().table('offer_notes').select(
                'offer_id, note_text, created_at'
            ).eq('user_id', session['user_id']).ilike('note_text', f'%{q}%').execute()
            offer_ids = list({r['offer_id'] for r in (notes_res.data or [])})
            if offer_ids:
                offers_res = supa().table('offers').select(
                    'id, city, title, price_pln, url'
                ).in_('id', offer_ids).execute()
                results = offers_res.data or []
        else:
            conn = sqlite3.connect(get_db_path())
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                '''SELECT DISTINCT o.id, o.city, o.title, o.price_pln, o.url
                   FROM offers o
                   JOIN offer_notes n ON o.id = n.offer_id
                   WHERE n.user_id = ? AND n.note_text LIKE ?''',
                (session['user_id'], f'%{q}%')
            ).fetchall()
            conn.close()
            results = [dict(r) for r in rows]

    return render_template(
        'search_notes.html',
        query=q,
        results=results,
        username=session.get('username'),
    )


# ── Ulubione ────────────────────────────────────────────────────
@app.route('/favorites/add', methods=['POST'])
def favorites_add():
    if 'user_id' not in session:
        return jsonify({'ok': False, 'error': 'not logged in'}), 401
    data     = request.get_json()
    offer_id = data.get('offer_id') if data else None
    if not offer_id:
        return jsonify({'ok': False}), 400
    if USE_SUPABASE:
        try:
            supa().table('favorites').insert({
                'user_id':  session['user_id'],
                'offer_id': offer_id,
                'added_at': datetime.now().isoformat(timespec='seconds'),
            }).execute()
        except Exception:
            pass
    else:
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
    if USE_SUPABASE:
        supa().table('favorites').delete().eq(
            'user_id', session['user_id']
        ).eq('offer_id', offer_id).execute()
    else:
        conn = sqlite3.connect(get_db_path())
        conn.execute(
            'DELETE FROM favorites WHERE user_id = ? AND offer_id = ?',
            (session['user_id'], offer_id)
        )
        conn.commit()
        conn.close()
    return jsonify({'ok': True})


# ── Scraping ────────────────────────────────────────────────────
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


# ── Historia cen ────────────────────────────────────────────────
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


# ── Kursy walut — endpoint do odświeżania ────────────────────────
@app.route('/currency/fetch', methods=['POST'])
def currency_fetch():
    """Endpoint wywoływany przez Vercel Cron lub ręcznie."""
    if not USE_SUPABASE:
        return jsonify({'ok': False, 'error': 'Wymaga Supabase'}), 400
    try:
        import currency_fetcher
        n = currency_fetcher.fetch_today()
        return jsonify({'ok': True, 'saved': n})
    except Exception as e:
        msg = f'Błąd pobierania kursów walut: {e}'
        send_discord_error(msg)
        return jsonify({'ok': False, 'error': str(e)}), 500


@app.route('/currency/fetch-history', methods=['POST'])
def currency_fetch_history():
    """Pobiera kursy za ostatnie 18 miesięcy (jednorazowe seeding)."""
    if not USE_SUPABASE:
        return jsonify({'ok': False, 'error': 'Wymaga Supabase'}), 400
    try:
        import currency_fetcher
        n = currency_fetcher.fetch_last_18_months()
        return jsonify({'ok': True, 'saved': n})
    except Exception as e:
        msg = f'Błąd pobierania historii kursów walut: {e}'
        send_discord_error(msg)
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── QR Code Login ────────────────────────────────────────────────
@app.route('/qr/generate')
def qr_generate():
    """
    Generuje QR kod do zalogowania się przez telefon.
    Token ważny 5 minut. Użytkownik musi być zalogowany.
    """
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    try:
        import qrcode
    except ImportError:
        return 'Zainstaluj bibliotekę qrcode: pip install qrcode[pil]', 500

    token = str(uuid.uuid4())
    now   = datetime.now()
    exp   = now + timedelta(minutes=5)

    if USE_SUPABASE:
        supa().table('qr_login_tokens').insert({
            'token':      token,
            'user_id':    session['user_id'],
            'created_at': now.isoformat(timespec='seconds'),
            'expires_at': exp.isoformat(timespec='seconds'),
            'used':       False,
        }).execute()
    else:
        conn = sqlite3.connect(get_db_path())
        conn.execute(
            'INSERT INTO qr_login_tokens (token, user_id, created_at, expires_at, used) '
            'VALUES (?, ?, ?, ?, 0)',
            (token, session['user_id'],
             now.isoformat(timespec='seconds'), exp.isoformat(timespec='seconds'))
        )
        conn.commit()
        conn.close()

    base_url = request.host_url.rstrip('/')
    scan_url = f'{base_url}/qr/scan/{token}'

    img = qrcode.make(scan_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    return render_template(
        'qr_login.html',
        qr_b64=img_b64,
        token=token,
        expires_in=5,
        username=session.get('username'),
    )


@app.route('/qr/scan/<token>')
def qr_scan(token):
    """
    Endpoint otwarty przez telefon po zeskanowaniu QR kodu.
    Tworzy sesję zalogowanego użytkownika.
    """
    now = datetime.now().isoformat(timespec='seconds')

    if USE_SUPABASE:
        res = supa().table('qr_login_tokens').select('*').eq('token', token).execute()
        row = res.data[0] if res.data else None
    else:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            'SELECT * FROM qr_login_tokens WHERE token = ?', (token,)
        ).fetchone()
        conn.close()
        row = dict(row) if row else None

    if not row:
        return render_template('qr_result.html', success=False, error='Token nie istnieje')
    if row.get('used'):
        return render_template('qr_result.html', success=False, error='Token już użyty')
    if row.get('expires_at', '') < now:
        return render_template('qr_result.html', success=False, error='Token wygasł')

    user_id = row['user_id']
    if USE_SUPABASE:
        u_res = supa().table('users').select('id, login').eq('id', user_id).execute()
        user = u_res.data[0] if u_res.data else None
        supa().table('qr_login_tokens').update({'used': True}).eq('token', token).execute()
    else:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        u_row = conn.execute('SELECT id, login FROM users WHERE id = ?', (user_id,)).fetchone()
        user  = dict(u_row) if u_row else None
        conn.execute('UPDATE qr_login_tokens SET used = 1 WHERE token = ?', (token,))
        conn.commit()
        conn.close()

    if not user:
        return render_template('qr_result.html', success=False, error='Użytkownik nie znaleziony')

    session['user_id']  = user['id']
    session['username'] = user['login']
    return render_template('qr_result.html', success=True, username=user['login'])


@app.route('/qr/status/<token>')
def qr_status(token):
    """Sprawdza czy token został już użyty (polling ze strony desktopowej)."""
    if USE_SUPABASE:
        res = supa().table('qr_login_tokens').select('used, expires_at').eq(
            'token', token
        ).execute()
        row = res.data[0] if res.data else None
    else:
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            'SELECT used, expires_at FROM qr_login_tokens WHERE token = ?', (token,)
        ).fetchone()
        conn.close()
        row = dict(row) if row else None

    if not row:
        return jsonify({'status': 'invalid'})
    now = datetime.now().isoformat(timespec='seconds')
    if row.get('expires_at', '') < now:
        return jsonify({'status': 'expired'})
    if row.get('used'):
        return jsonify({'status': 'used'})
    return jsonify({'status': 'pending'})


# ── Symulacja błędów (punkt 12b) ─────────────────────────────────
@app.route('/debug/simulate-errors', methods=['POST'])
def simulate_errors():
    """
    Symuluje błędy i wysyła je na Discord (punkt 12b zadania).
    Tylko do testów — nie używać na produkcji.
    """
    scenario = request.get_json(silent=True) or {}
    sent = []

    if scenario.get('login_failure'):
        send_discord_error(
            '❌ [SYMULACJA] Nieudane logowanie dla użytkownika `test_user` '
            f'o {datetime.now().isoformat(timespec="seconds")}'
        )
        sent.append('login_failure')

    if scenario.get('currency_fetch_error'):
        send_discord_error(
            '💱 [SYMULACJA] Błąd pobierania kursów walut z NBP API: '
            'ConnectionError — timeout po 30s'
        )
        sent.append('currency_fetch_error')

    return jsonify({'ok': True, 'simulated': sent})


# ── Init & uruchomienie ──────────────────────────────────────────
init_users_db()

if not _IS_VERCEL and (not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'):
    threading.Thread(target=_auto_scrape_task, daemon=True).start()

if __name__ == '__main__':
    app.run(debug=True)
