import discord
from discord import app_commands
import sqlite3
import os
import asyncio
from dotenv import load_dotenv
import scraper as sc

load_dotenv()

DB_PATH    = os.path.join(os.path.dirname(__file__), 'offers.db')
BOT_TOKEN  = os.getenv('DISCORD_BOT_TOKEN')

CITY_LABELS = {'Gdansk': 'Gdańsk', 'Warszawa': 'Warszawa', 'Wroclaw': 'Wrocław'}
CITY_COLORS = {'Gdansk': 0x3b82f6, 'Warszawa': 0xf59e0b, 'Wroclaw': 0x22d3a5}

intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)


def fmt(n):
    return f'{n:,}'.replace(',', ' ') + ' zł' if n else '—'


def scrape_cities(cities: list) -> list:
    url_map = dict(sc.URLS)
    conn    = sqlite3.connect(DB_PATH)
    sc.init_db(conn)

    results = []
    for city in cities:
        url = url_map.get(city)
        if not url:
            continue
        try:
            rows = sc.fetch_items(city, url)
            sc.save_rows(conn, rows)
            results.append((city, rows, None))
        except Exception as e:
            results.append((city, [], str(e)))

    conn.close()
    return results


def build_embed(city: str, rows: list, error: str | None) -> discord.Embed:
    label = CITY_LABELS.get(city, city)
    color = CITY_COLORS.get(city, 0xc9a84c)

    if error:
        embed = discord.Embed(title=f'🏠 {label} — błąd', color=0xf87171)
        embed.description = f'Błąd: {error}'
        return embed

    prices  = [r['price_pln'] for r in rows if r.get('price_pln')]
    areas   = [r['area_m2']   for r in rows if r.get('area_m2')]
    primary = sum(1 for r in rows if r.get('market') == 'pierwotny')
    count   = len(rows)
    pct     = round(primary / count * 100) if count else 0

    avg_price = int(sum(prices) / len(prices)) if prices else None
    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None
    avg_area  = sum(areas)  / len(areas)  if areas  else None

    embed = discord.Embed(title=f'🏠 {label} — pobrano {count} ofert', color=color)
    embed.add_field(name='Średnia cena',      value=fmt(avg_price),                         inline=True)
    embed.add_field(name='Zakres cen',        value=f'{fmt(min_price)} – {fmt(max_price)}', inline=True)
    embed.add_field(name='Rynek pierwotny',   value=f'{primary} ofert ({pct}%)',            inline=True)
    embed.add_field(name='Śr. powierzchnia',  value=f'{avg_area:.1f} m²' if avg_area else '—', inline=True)
    embed.set_footer(text='Otodom scraper')
    return embed


async def run_scrape(interaction: discord.Interaction, cities: list):
    await interaction.response.defer(thinking=True)
    city_results = await asyncio.to_thread(scrape_cities, cities)
    embeds = [build_embed(city, rows, err) for city, rows, err in city_results]
    await interaction.followup.send(embeds=embeds)


@tree.command(name='gdansk', description='Pobierz nowe oferty dla Gdańska')
async def cmd_gdansk(interaction: discord.Interaction):
    await run_scrape(interaction, ['Gdansk'])


@tree.command(name='warszawa', description='Pobierz nowe oferty dla Warszawy')
async def cmd_warszawa(interaction: discord.Interaction):
    await run_scrape(interaction, ['Warszawa'])


@tree.command(name='wroclaw', description='Pobierz nowe oferty dla Wrocławia')
async def cmd_wroclaw(interaction: discord.Interaction):
    await run_scrape(interaction, ['Wroclaw'])


@tree.command(name='wszystkie', description='Pobierz nowe oferty dla wszystkich 3 miast')
async def cmd_wszystkie(interaction: discord.Interaction):
    await run_scrape(interaction, ['Gdansk', 'Warszawa', 'Wroclaw'])


@client.event
async def on_ready():
    await tree.sync()
    print(f'✅ Bot {client.user} gotowy')
    print('   Komendy: /gdansk  /warszawa  /wroclaw  /wszystkie')


if not BOT_TOKEN:
    print('❌ Brak DISCORD_BOT_TOKEN w pliku .env')
else:
    client.run(BOT_TOKEN)
