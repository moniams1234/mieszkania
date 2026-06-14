import requests
import re
import json
import sqlite3
import time
from datetime import datetime

URLS = [
    ("Gdansk", "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/pomorskie/gdansk/gdansk/gdansk?limit=36&ownerTypeSingleSelect=ALL&priceMax=600000&floorsNumberMax=5&by=DEFAULT&direction=DESC"),
    ("Warszawa", "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/mazowieckie/warszawa/warszawa/warszawa?limit=36&ownerTypeSingleSelect=ALL&priceMax=600000&floorsNumberMax=5&by=DEFAULT&direction=DESC"),
    ("Wroclaw", "https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/dolnoslaskie/wroclaw/wroclaw/wroclaw?limit=36&ownerTypeSingleSelect=ALL&priceMax=600000&floorsNumberMax=5&by=DEFAULT&direction=DESC"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

ROOMS_MAP = {
    "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5,
    "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9, "TEN": 10,
    "MORE_THAN_TEN": 11,
}

FLOOR_MAP = {
    "GROUND": 0, "FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4,
    "FIFTH": 5, "SIXTH": 6, "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9,
    "TENTH": 10, "ABOVE_TENTH": 11, "GARRET": -1,
}


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id          INTEGER PRIMARY KEY,
            city        TEXT NOT NULL,
            title       TEXT,
            price_pln   INTEGER,
            area_m2     REAL,
            rooms       INTEGER,
            floor       INTEGER,
            address     TEXT,
            url         TEXT,
            scraped_at  TEXT,
            developer   TEXT,
            market      TEXT,
            development TEXT,
            district    TEXT
        )
    """)
    # Add new columns to existing tables that predate this schema
    for col, typ in [("developer","TEXT"),("market","TEXT"),("development","TEXT"),("district","TEXT")]:
        try:
            conn.execute(f"ALTER TABLE offers ADD COLUMN {col} {typ}")
        except Exception:
            pass
    conn.commit()


def fetch_items(city, url):
    print(f"  Fetching {city}...")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    if not m:
        raise ValueError(f"No __NEXT_DATA__ found for {city}")

    data = json.loads(m.group(1))
    items = data["props"]["pageProps"]["data"]["searchAds"]["items"]
    print(f"  Found {len(items)} raw items")

    rows = []
    for item in items:
        if len(rows) >= 10:
            break

        # Skip investment placeholders with no price (they're groupings, real flats are in relatedAds)
        if item.get("estate") == "INVESTMENT" and item.get("relatedAds"):
            for sub in item["relatedAds"]:
                if len(rows) >= 10:
                    break
                rows.append(extract_row(sub, city))
        else:
            rows.append(extract_row(item, city))

    return rows[:10]


def extract_row(item, city):
    price = None
    if item.get("totalPrice") and item["totalPrice"].get("value"):
        price = int(item["totalPrice"]["value"])

    area = item.get("areaInSquareMeters")

    rooms_raw = item.get("roomsNumber")
    rooms = ROOMS_MAP.get(rooms_raw) if rooms_raw else None

    floor_raw = item.get("floorNumber")
    floor = FLOOR_MAP.get(floor_raw) if floor_raw else None

    loc = item.get("location") or {}
    addr = loc.get("address") or {}
    street = (addr.get("street") or {}).get("name", "")
    city_name = (addr.get("city") or {}).get("name", "")
    district = (addr.get("district") or {}).get("name", "") or None
    address = f"{street}, {city_name}".strip(", ")

    slug = item.get("slug", "")
    offer_url = f"https://www.otodom.pl/pl/oferta/{slug}" if slug else ""

    # Developer / agency
    agency_data = item.get("agency") or {}
    developer = agency_data.get("name") or None
    if not developer:
        developer = "Właściciel prywatny" if item.get("isPrivateOwner") else None

    # Market type: primary if linked to a development project
    dev_title = item.get("developmentTitle") or None
    development = dev_title
    market = "pierwotny" if (dev_title or item.get("developmentId")) else "wtórny"

    return {
        "id": item.get("id"),
        "city": city,
        "title": item.get("title", ""),
        "price_pln": price,
        "area_m2": area,
        "rooms": rooms,
        "floor": floor,
        "address": address,
        "url": offer_url,
        "scraped_at": datetime.now().isoformat(timespec="seconds"),
        "developer": developer,
        "market": market,
        "development": development,
        "district": district,
    }


def save_rows(conn, rows):
    conn.executemany("""
        INSERT OR REPLACE INTO offers
            (id, city, title, price_pln, area_m2, rooms, floor, address, url, scraped_at,
             developer, market, development, district)
        VALUES
            (:id, :city, :title, :price_pln, :area_m2, :rooms, :floor, :address, :url, :scraped_at,
             :developer, :market, :development, :district)
    """, rows)
    conn.commit()


def main():
    db_path = "offers.db"
    conn = sqlite3.connect(db_path)
    init_db(conn)

    total = 0
    for city, url in URLS:
        try:
            rows = fetch_items(city, url)
            save_rows(conn, rows)
            print(f"  Saved {len(rows)} offers for {city}")
            total += len(rows)
        except Exception as e:
            print(f"  ERROR for {city}: {e}")
        time.sleep(1)

    conn.close()
    print(f"\nDone. Total offers saved: {total}")
    print(f"Database: {db_path}")


if __name__ == "__main__":
    main()
