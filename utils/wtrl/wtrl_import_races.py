from db import get_zrl_db
from datetime import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re

def import_races():
    """Importa le gare del round attivo o imminente da WTRL."""
    try:
        conn = get_zrl_db()
        cur = conn.cursor()

        # Trova il round attivo
        cur.execute("""
            SELECT r.*, s.start_year AS season_start
            FROM rounds r
            JOIN seasons s ON r.season_id = s.id
            WHERE date('now') BETWEEN date(r.start_date) AND date(r.end_date)
            ORDER BY date(r.start_date)
            LIMIT 1
        """)
        round_row = cur.fetchone()
        print("🔍 Round trovato:", round_row)
        if not round_row:
            print("📭 Nessun round attivo o imminente trovato.")
            return

        round_id = round_row["id"]
        round_number = round_row["round_number"]
        season_start = round_row["season_start"]
        year = int(season_start)

        url = f"https://www.wtrl.racing/zwift-racing-league/schedule/{year}/r{round_number}/"
        print(f"🌍 Import gare dal round {round_number} → {url}")

        # Scarica HTML
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url)
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()

        # Parsing HTML
        soup = BeautifulSoup(html, "html.parser")
        blocks = soup.select(".schedule-block")
        print("🔍 Blocchi gara trovati:", len(blocks))
        if not blocks:
            print("⚠️ Nessun blocco gara trovato.")
            return

        imported = 0
        for block in blocks:
            try:
                date_str = block.select_one(".schedule-date").text.strip()
                race_date = datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")

                name = block.select_one(".schedule-title").text.strip()
                format_ = block.select_one(".schedule-format").text.strip()
                world = block.select_one(".schedule-world").text.strip()
                course = block.select_one(".schedule-course").text.strip()

                distance_text = block.select_one(".schedule-distance").text.strip()
                elevation_text = block.select_one(".schedule-elevation").text.strip()
                distance_km = float(re.search(r"([\d.]+)", distance_text).group(1))
                elevation_m = float(re.search(r"([\d.]+)", elevation_text).group(1))

                laps = 1  # default

                powerup_icons = block.select(".schedule-powerups img")
                powerups = " ".join(img["alt"] for img in powerup_icons if img.has_attr("alt"))

                fal = block.select_one(".schedule-fal")
                fts = block.select_one(".schedule-fts")
                fal_segments = fal.get_text(separator="\n", strip=True) if fal else ""
                fts_segments = fts.get_text(separator="\n", strip=True) if fts else ""

                active = 1 if datetime.strptime(race_date, "%Y-%m-%d") >= datetime.today() else 0

                cur.execute("""
                    SELECT id FROM races WHERE round_id = ? AND name = ? AND race_date = ?
                """, (round_id, name, race_date))
                existing = cur.fetchone()

                if existing:
                    cur.execute("""
                        UPDATE races SET format=?, world=?, course=?, laps=?, distance_km=?, elevation_m=?,
                            powerups=?, fal_segments=?, fts_segments=?, active=?
                        WHERE id=?
                    """, (
                        format_, world, course, laps, distance_km, elevation_m,
                        powerups, fal_segments, fts_segments, active, existing["id"]
                    ))
                else:
                    cur.execute("""
                        INSERT INTO races (name, race_date, format, world, course, laps,
                            distance_km, elevation_m, powerups, fal_segments, fts_segments, active, round_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name, race_date, format_, world, course, laps,
                        distance_km, elevation_m, powerups, fal_segments,
                        fts_segments, active, round_id
                    ))

                imported += 1

            except Exception as e:
                print(f"❌ Errore nel parsing o salvataggio gara: {e}")
                continue

        conn.commit()
        print(f"✅ Importazione completata: {imported} gare salvate per Round {round_number}")

    except Exception as e:
        print(f"❌ Errore durante l'importazione: {e}")