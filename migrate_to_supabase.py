"""
Migracja danych z lokalnego SQLite do Supabase.

Uruchom lokalnie po ustawieniu zmiennych:
    set SUPABASE_URL=https://ptzbavstceawstdevbda.supabase.co
    set SUPABASE_KEY=sb_secret_...
    python migrate_to_supabase.py
"""
import os
import sqlite3
from supabase import create_client

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://ptzbavstceawstdevbda.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'offers.db')

if not SUPABASE_KEY:
    raise SystemExit('Ustaw zmienną SUPABASE_KEY przed uruchomieniem skryptu.')

supa = create_client(SUPABASE_URL, SUPABASE_KEY)
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row


def migrate(table, on_conflict='id', batch=100):
    try:
        rows = conn.execute(f'SELECT * FROM {table}').fetchall()
    except Exception as e:
        print(f'  {table}: pominięto ({e})')
        return
    data = [dict(r) for r in rows]
    if not data:
        print(f'  {table}: brak danych')
        return
    for i in range(0, len(data), batch):
        supa.table(table).upsert(data[i:i + batch], on_conflict=on_conflict).execute()
    print(f'  {table}: {len(data)} wierszy OK')


print('=== Migracja SQLite → Supabase ===')
migrate('offers',        on_conflict='id')
migrate('investments',   on_conflict='id')
migrate('offer_history', on_conflict='offer_id')

conn.close()
print('Gotowe!')
