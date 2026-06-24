"""
Pobiera kursy walut z NBP API (tabela A – wszystkie waluty)
za ostatnie 18 miesięcy i zapisuje do Supabase.

Uruchomienie ręczne:
    python currency_fetcher.py

Wywołane też przez Vercel Cron co dzień (patrz vercel.json).
"""

import os
import time
import requests
from datetime import date, timedelta, datetime
from dotenv import load_dotenv

load_dotenv()

NBP_BASE = "https://api.nbp.pl/api/exchangerates/tables/A"
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")


def _supa():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_rates_for_period(date_from: date, date_to: date) -> list[dict]:
    """Pobiera kursy z NBP dla zadanego okresu. Zwraca listę rekordów."""
    url = f"{NBP_BASE}/{date_from.isoformat()}/{date_to.isoformat()}/?format=json"
    resp = requests.get(url, timeout=30)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    tables = resp.json()

    records = []
    fetched_at = datetime.now().isoformat(timespec="seconds")
    for table in tables:
        table_no = table.get("no", "")
        eff_date = table.get("effectiveDate", "")
        for rate in table.get("rates", []):
            records.append({
                "currency":      rate["code"],
                "currency_name": rate["currency"],
                "rate":          float(rate["mid"]),
                "effective_date": eff_date,
                "table_no":      table_no,
                "fetched_at":    fetched_at,
            })
    return records


def fetch_last_18_months() -> int:
    """
    Pobiera kursy za ostatnie 18 miesięcy w kawałkach ≤93 dni
    (ograniczenie API NBP) i zapisuje do Supabase.
    Zwraca łączną liczbę wstawionych/zaktualizowanych rekordów.
    """
    client = _supa()
    today = date.today()
    start = today - timedelta(days=548)  # ~18 miesięcy

    total = 0
    chunk_days = 90
    current = start
    while current <= today:
        chunk_end = min(current + timedelta(days=chunk_days - 1), today)
        records = fetch_rates_for_period(current, chunk_end)
        if records:
            client.table("currency_rates").upsert(
                records,
                on_conflict="currency,effective_date"
            ).execute()
            total += len(records)
        current = chunk_end + timedelta(days=1)
        time.sleep(0.5)  # nie zalewamy API

    return total


def fetch_today() -> int:
    """Pobiera kursy na dziś (wywoływane przez cron codzienny)."""
    client = _supa()
    today = date.today()
    records = fetch_rates_for_period(today, today)
    if not records:
        yesterday = today - timedelta(days=1)
        records = fetch_rates_for_period(yesterday, today)
    if records:
        client.table("currency_rates").upsert(
            records,
            on_conflict="currency,effective_date"
        ).execute()
    return len(records)


def get_latest_rates(currencies: list[str] | None = None) -> dict[str, float]:
    """
    Zwraca słownik {KOD: kurs_do_PLN} dla najnowszych dostępnych kursów.
    Jeśli currencies=None, zwraca wszystkie waluty.
    """
    client = _supa()
    query = client.table("currency_rates").select(
        "currency, rate, effective_date"
    ).order("effective_date", desc=True).limit(500)

    if currencies:
        query = query.in_("currency", currencies)

    res = query.execute()
    seen = {}
    for row in (res.data or []):
        code = row["currency"]
        if code not in seen:
            seen[code] = float(row["rate"])
    return seen


if __name__ == "__main__":
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Brak SUPABASE_URL lub SUPABASE_KEY w .env")
        raise SystemExit(1)
    print("Pobieram kursy walut za ostatnie 18 miesięcy…")
    n = fetch_last_18_months()
    print(f"Zapisano {n} rekordów kursów walut.")
