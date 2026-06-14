import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'offers.db')

INVESTMENTS = [
    # ── GDAŃSK ────────────────────────────────────────────────────────────────
    {"developer": "DOMESTA Sp. z o.o.",        "city": "Gdansk", "district": "Piecki-Migowo",     "investment_name": "Urzeka",           "status": "W sprzedaży", "apartments_total": 180, "price_min": 450000, "price_max": 650000, "completion_year": 2026},
    {"developer": "DOMESTA Sp. z o.o.",        "city": "Gdansk", "district": "Południe",           "investment_name": "Nowe Południe",    "status": "W sprzedaży", "apartments_total": 220, "price_min": 420000, "price_max": 580000, "completion_year": 2025},
    {"developer": "DOMESTA Sp. z o.o.",        "city": "Gdansk", "district": "Jasień",             "investment_name": "Botanika",         "status": "Zakończona",  "apartments_total": 150, "price_min": 340000, "price_max": 490000, "completion_year": 2022},
    {"developer": "DOMESTA Sp. z o.o.",        "city": "Gdansk", "district": "Przymorze",          "investment_name": "Kliński Park",     "status": "Zakończona",  "apartments_total": 200, "price_min": 370000, "price_max": 530000, "completion_year": 2023},
    {"developer": "DOMESTA Sp. z o.o.",        "city": "Gdansk", "district": "Morena",             "investment_name": "Morena Park",      "status": "Zakończona",  "apartments_total": 130, "price_min": 310000, "price_max": 460000, "completion_year": 2020},
    {"developer": "Hanza Grupa Inwestycyjna",  "city": "Gdansk", "district": "Chwarzno-Wiczlino",  "investment_name": "Fauna",            "status": "W sprzedaży", "apartments_total": 140, "price_min": 480000, "price_max": 700000, "completion_year": 2026},
    {"developer": "Hanza Grupa Inwestycyjna",  "city": "Gdansk", "district": "Chwarzno-Wiczlino",  "investment_name": "Stacja Chwarzno",  "status": "Zakończona",  "apartments_total": 120, "price_min": 400000, "price_max": 580000, "completion_year": 2021},
    {"developer": "Hanza Grupa Inwestycyjna",  "city": "Gdansk", "district": "Wrzeszcz",           "investment_name": "Garnizon Hanza",   "status": "Zakończona",  "apartments_total": 250, "price_min": 460000, "price_max": 780000, "completion_year": 2020},
    {"developer": "Hanza Grupa Inwestycyjna",  "city": "Gdansk", "district": "Wrzeszcz",           "investment_name": "Ogrody Hanza",     "status": "Zakończona",  "apartments_total": 190, "price_min": 430000, "price_max": 650000, "completion_year": 2019},
    {"developer": "Pomorskie Domy",            "city": "Gdansk", "district": "Jasień",             "investment_name": "Botanika IV",      "status": "W sprzedaży", "apartments_total": 90,  "price_min": 460000, "price_max": 620000, "completion_year": 2025},
    {"developer": "Pomorskie Domy",            "city": "Gdansk", "district": "Jasień",             "investment_name": "Botanika III",     "status": "Zakończona",  "apartments_total": 85,  "price_min": 380000, "price_max": 540000, "completion_year": 2023},
    {"developer": "Pomorskie Domy",            "city": "Gdansk", "district": "Jasień",             "investment_name": "Botanika II",      "status": "Zakończona",  "apartments_total": 80,  "price_min": 340000, "price_max": 490000, "completion_year": 2022},
    {"developer": "Pomorskie Domy",            "city": "Gdansk", "district": "Jasień",             "investment_name": "Botanika I",       "status": "Zakończona",  "apartments_total": 75,  "price_min": 300000, "price_max": 440000, "completion_year": 2021},
    {"developer": "Inpro",                     "city": "Gdansk", "district": "Kokoszki",           "investment_name": "Kwiatowa Dolina",  "status": "Zakończona",  "apartments_total": 310, "price_min": 380000, "price_max": 600000, "completion_year": 2022},
    {"developer": "Inpro",                     "city": "Gdansk", "district": "Orunia Górna",       "investment_name": "Gamma Park",       "status": "W sprzedaży", "apartments_total": 260, "price_min": 450000, "price_max": 680000, "completion_year": 2025},
    {"developer": "Euro Styl",                 "city": "Gdansk", "district": "Wrzeszcz",           "investment_name": "Garnizon Etapy",   "status": "Zakończona",  "apartments_total": 400, "price_min": 420000, "price_max": 720000, "completion_year": 2021},
    {"developer": "Euro Styl",                 "city": "Gdansk", "district": "Osowa",              "investment_name": "Strefa Sopocka",   "status": "W sprzedaży", "apartments_total": 180, "price_min": 520000, "price_max": 850000, "completion_year": 2026},
    {"developer": "Budlex",                    "city": "Gdansk", "district": "Chełm",              "investment_name": "Optimo",           "status": "W sprzedaży", "apartments_total": 220, "price_min": 510000, "price_max": 780000, "completion_year": 2026},
    {"developer": "Budlex",                    "city": "Gdansk", "district": "Piecki-Migowo",      "investment_name": "Osiedle Chmielna", "status": "W sprzedaży", "apartments_total": 160, "price_min": 480000, "price_max": 720000, "completion_year": 2025},
    {"developer": "Budlex",                    "city": "Gdansk", "district": "Letnica",            "investment_name": "Nowa Letnica",     "status": "Zakończona",  "apartments_total": 190, "price_min": 390000, "price_max": 580000, "completion_year": 2023},
    {"developer": "Budlex",                    "city": "Gdansk", "district": "Śródmieście",        "investment_name": "Brabank",          "status": "Zakończona",  "apartments_total": 140, "price_min": 360000, "price_max": 540000, "completion_year": 2021},
    {"developer": "Allcon",                    "city": "Gdansk", "district": "Osowa",              "investment_name": "Osiedle Beaumont", "status": "W sprzedaży", "apartments_total": 130, "price_min": 540000, "price_max": 820000, "completion_year": 2026},
    {"developer": "Allcon",                    "city": "Gdansk", "district": "Wrzeszcz",           "investment_name": "Albatross Towers", "status": "Zakończona",  "apartments_total": 110, "price_min": 480000, "price_max": 750000, "completion_year": 2022},
    {"developer": "Allcon",                    "city": "Gdansk", "district": "Śródmieście",        "investment_name": "Port Główny",      "status": "Zakończona",  "apartments_total": 95,  "price_min": 420000, "price_max": 680000, "completion_year": 2020},
    {"developer": "Invest Komfort",            "city": "Gdansk", "district": "Przymorze",          "investment_name": "Nadmorskie Tarasy","status": "W sprzedaży", "apartments_total": 280, "price_min": 560000, "price_max": 900000, "completion_year": 2025},
    {"developer": "Invest Komfort",            "city": "Gdansk", "district": "Śródmieście",        "investment_name": "Nowe Ogrody",      "status": "Zakończona",  "apartments_total": 200, "price_min": 440000, "price_max": 680000, "completion_year": 2022},
    {"developer": "Invest Komfort",            "city": "Gdansk", "district": "Jasień",             "investment_name": "Vivere Verde",     "status": "Zakończona",  "apartments_total": 170, "price_min": 400000, "price_max": 620000, "completion_year": 2021},
    {"developer": "Triton Development",        "city": "Gdansk", "district": "Żabianka",           "investment_name": "Neptun Park",      "status": "Zakończona",  "apartments_total": 150, "price_min": 350000, "price_max": 520000, "completion_year": 2019},
    {"developer": "Triton Development",        "city": "Gdansk", "district": "Letnica",            "investment_name": "Oaza Letnica",     "status": "Zakończona",  "apartments_total": 120, "price_min": 380000, "price_max": 560000, "completion_year": 2021},

    # ── WARSZAWA ───────────────────────────────────────────────────────────────
    {"developer": "Budomatex",                                 "city": "Warszawa", "district": "Praga-Południe", "investment_name": "Geometryczna",        "status": "W sprzedaży", "apartments_total": 160, "price_min": 520000, "price_max": 780000, "completion_year": 2025},
    {"developer": "Budomatex",                                 "city": "Warszawa", "district": "Praga-Północ",  "investment_name": "Praga Residence",     "status": "Zakończona",  "apartments_total": 120, "price_min": 440000, "price_max": 660000, "completion_year": 2022},
    {"developer": "Budomatex",                                 "city": "Warszawa", "district": "Wola",          "investment_name": "Wola Apartments",     "status": "Zakończona",  "apartments_total": 200, "price_min": 460000, "price_max": 700000, "completion_year": 2023},
    {"developer": "OPTYMIST 1 Grupa Inwestycyjna Sp. z o.o.", "city": "Warszawa", "district": "Białołęka",     "investment_name": "Porto Żerań",         "status": "W sprzedaży", "apartments_total": 240, "price_min": 540000, "price_max": 800000, "completion_year": 2026},
    {"developer": "OPTYMIST 1 Grupa Inwestycyjna Sp. z o.o.", "city": "Warszawa", "district": "Białołęka",     "investment_name": "Żerań Park",          "status": "Zakończona",  "apartments_total": 180, "price_min": 460000, "price_max": 680000, "completion_year": 2023},
    {"developer": "Dom Development",                           "city": "Warszawa", "district": "Targówek",      "investment_name": "Osiedle Wilno",       "status": "W sprzedaży", "apartments_total": 320, "price_min": 560000, "price_max": 920000, "completion_year": 2026},
    {"developer": "Dom Development",                           "city": "Warszawa", "district": "Wilanów",       "investment_name": "Miasteczko Wilanów",  "status": "Zakończona",  "apartments_total": 500, "price_min": 540000, "price_max": 1100000,"completion_year": 2021},
    {"developer": "Dom Development",                           "city": "Warszawa", "district": "Włochy",        "investment_name": "Osiedle Piasta",      "status": "Zakończona",  "apartments_total": 280, "price_min": 480000, "price_max": 780000, "completion_year": 2022},
    {"developer": "Atal",                                      "city": "Warszawa", "district": "Białołęka",     "investment_name": "Atal Żerań",          "status": "W sprzedaży", "apartments_total": 290, "price_min": 510000, "price_max": 860000, "completion_year": 2025},
    {"developer": "Atal",                                      "city": "Warszawa", "district": "Wola",          "investment_name": "Atal Towers Wola",    "status": "Zakończona",  "apartments_total": 350, "price_min": 520000, "price_max": 900000, "completion_year": 2023},
    {"developer": "Develia",                                   "city": "Warszawa", "district": "Ursynów",       "investment_name": "Południe Vita",       "status": "W sprzedaży", "apartments_total": 220, "price_min": 530000, "price_max": 840000, "completion_year": 2025},
    {"developer": "Develia",                                   "city": "Warszawa", "district": "Wola",          "investment_name": "Wola Libre",          "status": "Zakończona",  "apartments_total": 190, "price_min": 480000, "price_max": 760000, "completion_year": 2022},
    {"developer": "Matexi Polska",                             "city": "Warszawa", "district": "Mokotów",       "investment_name": "Bliski Mokotów",      "status": "Zakończona",  "apartments_total": 160, "price_min": 600000, "price_max": 1200000,"completion_year": 2023},
    {"developer": "Matexi Polska",                             "city": "Warszawa", "district": "Włochy",        "investment_name": "Okęcie Park",         "status": "W sprzedaży", "apartments_total": 200, "price_min": 560000, "price_max": 950000, "completion_year": 2026},

    # ── WROCŁAW ────────────────────────────────────────────────────────────────
    {"developer": "DEVELIA",            "city": "Wroclaw", "district": "Krzyki",        "investment_name": "Podhalańska Vita",    "status": "W sprzedaży", "apartments_total": 200, "price_min": 420000, "price_max": 650000, "completion_year": 2025},
    {"developer": "DEVELIA",            "city": "Wroclaw", "district": "Krzyki",        "investment_name": "Orawska Vita",        "status": "W sprzedaży", "apartments_total": 180, "price_min": 440000, "price_max": 680000, "completion_year": 2026},
    {"developer": "DEVELIA",            "city": "Wroclaw", "district": "Fabryczna",     "investment_name": "Kamienna 145",        "status": "Zakończona",  "apartments_total": 160, "price_min": 360000, "price_max": 560000, "completion_year": 2023},
    {"developer": "DEVELIA",            "city": "Wroclaw", "district": "Psie Pole",     "investment_name": "Zakrzów Park",        "status": "Zakończona",  "apartments_total": 220, "price_min": 340000, "price_max": 520000, "completion_year": 2022},
    {"developer": "DEVELIA",            "city": "Wroclaw", "district": "Śródmieście",   "investment_name": "Centralna Park",      "status": "Zakończona",  "apartments_total": 300, "price_min": 320000, "price_max": 500000, "completion_year": 2020},
    {"developer": "Arkop Deweloper",    "city": "Wroclaw", "district": "Krzyki",        "investment_name": "Parkowe Aleje 3",    "status": "W sprzedaży", "apartments_total": 120, "price_min": 450000, "price_max": 640000, "completion_year": 2025},
    {"developer": "Arkop Deweloper",    "city": "Wroclaw", "district": "Krzyki",        "investment_name": "Parkowe Aleje 2",    "status": "Zakończona",  "apartments_total": 100, "price_min": 390000, "price_max": 560000, "completion_year": 2022},
    {"developer": "Arkop Deweloper",    "city": "Wroclaw", "district": "Krzyki",        "investment_name": "Parkowe Aleje 1",    "status": "Zakończona",  "apartments_total": 90,  "price_min": 340000, "price_max": 500000, "completion_year": 2020},
    {"developer": "ROBYG Wrocław",      "city": "Wroclaw", "district": "Psie Pole",     "investment_name": "Villa Viva",          "status": "W sprzedaży", "apartments_total": 200, "price_min": 430000, "price_max": 660000, "completion_year": 2025},
    {"developer": "ROBYG Wrocław",      "city": "Wroclaw", "district": "Fabryczna",     "investment_name": "Smart City",          "status": "Zakończona",  "apartments_total": 380, "price_min": 360000, "price_max": 560000, "completion_year": 2022},
    {"developer": "ROBYG Wrocław",      "city": "Wroclaw", "district": "Fabryczna",     "investment_name": "Green Port",          "status": "Zakończona",  "apartments_total": 280, "price_min": 330000, "price_max": 520000, "completion_year": 2021},
    {"developer": "Archicom",           "city": "Wroclaw", "district": "Fabryczna",     "investment_name": "Olimpia Port",        "status": "Zakończona",  "apartments_total": 600, "price_min": 380000, "price_max": 680000, "completion_year": 2021},
    {"developer": "Archicom",           "city": "Wroclaw", "district": "Śródmieście",   "investment_name": "Przystań Śródmiejska","status": "W sprzedaży", "apartments_total": 250, "price_min": 480000, "price_max": 750000, "completion_year": 2026},
    {"developer": "Archicom",           "city": "Wroclaw", "district": "Śródmieście",   "investment_name": "City Vibe",           "status": "Zakończona",  "apartments_total": 320, "price_min": 350000, "price_max": 580000, "completion_year": 2020},
    {"developer": "Vantage Development","city": "Wroclaw", "district": "Fabryczna",     "investment_name": "Racławicka Vita",    "status": "W sprzedaży", "apartments_total": 170, "price_min": 450000, "price_max": 700000, "completion_year": 2025},
    {"developer": "Vantage Development","city": "Wroclaw", "district": "Psie Pole",     "investment_name": "Atal Bałtycka",      "status": "Zakończona",  "apartments_total": 260, "price_min": 380000, "price_max": 600000, "completion_year": 2022},
]


def seed(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investments (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            developer         TEXT NOT NULL,
            city              TEXT NOT NULL,
            district          TEXT,
            investment_name   TEXT NOT NULL,
            status            TEXT,
            apartments_total  INTEGER,
            price_min         INTEGER,
            price_max         INTEGER,
            completion_year   INTEGER,
            UNIQUE(developer, city, investment_name)
        )
    """)
    # Add district column if it doesn't exist yet
    try:
        conn.execute("ALTER TABLE investments ADD COLUMN district TEXT")
    except Exception:
        pass
    conn.executemany("""
        INSERT OR IGNORE INTO investments
            (developer, city, district, investment_name, status, apartments_total, price_min, price_max, completion_year)
        VALUES
            (:developer, :city, :district, :investment_name, :status, :apartments_total, :price_min, :price_max, :completion_year)
    """, INVESTMENTS)
    # Update district for existing rows that have it NULL
    conn.executemany("""
        UPDATE investments SET district = :district
        WHERE developer = :developer AND city = :city AND investment_name = :investment_name AND district IS NULL
    """, INVESTMENTS)
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM investments").fetchone()[0]
    conn.close()
    print(f"Investments table: {count} records in {db_path}")


if __name__ == "__main__":
    seed()
