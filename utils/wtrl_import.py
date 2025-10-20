from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from datetime import datetime
import re
from flask import flash
from db_utils import get_fresh_zrl_db, close_zrl_db

def parse_races_from_html(html, round_number):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tblschedule")
    if not table:
        return []

    races = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 8:
            continue

        race_info = cells[0].get_text(separator="\n", strip=True).split("\n")
        name = race_info[0]
        date_str = race_info[1]

        try:
            race_date = datetime.strptime(date_str, "%d/%m/%y")
        except ValueError:
            continue

        format = cells[1].get_text(strip=True)
        world = cells[2].get_text(strip=True)
        course = cells[3].get_text(strip=True)

        duration_text = cells[4].get_text(separator="\n", strip=True)
        laps_match = re.search(r"(\d+)\s+lap", duration_text)
        laps = int(laps_match.group(1)) if laps_match else 1
        distance_match = re.search(r"([\d.]+)km", duration_text)
        elevation_match = re.search(r"([\d.]+)m", duration_text)
        distance_km = float(distance_match.group(1)) if distance_match else 0
        elevation_m = float(elevation_match.group(1)) if elevation_match else 0

        powerups = cells[5].get_text(separator=" ", strip=True)
        if "none" not in powerups.lower() and "%" not in powerups:
            powerups = ""

        fal_segments = cells[6].get_text(separator="\n", strip=True)
        fts_segments = cells[7].get_text(separator="\n", strip=True)

        races.append({
            "name": name,
            "race_date": date_str,
            "format": format,
            "world": world,
            "course": course,
            "laps": laps,
            "distance_km": distance_km,
            "elevation_m": elevation_m,
            "powerups": powerups,
            "fal_segments": fal_segments,
            "fts_segments": fts_segments,
            "round_number": round_number
        })
    return races


def wtrl_import():
    try:
        close_zrl_db()

        season_name = "ZRL 2025/26"
        season_start = "2025-09-16"
        season_end = "2026-04-28"
        start_year = "2025"
        total_rounds = 4

        rounds = []
        races = []

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            for round_number in range(1, total_rounds + 1):
                url = f"https://www.wtrl.racing/zwift-racing-league/schedule/{start_year}/r{round_number}/"
                page.goto(url)
                page.wait_for_timeout(3000)

                html = page.content()
                header_text = page.inner_text("body")
                date_match = re.search(r"\((\d{4}-\d{2}-\d{2})\s*→\s*(\d{4}-\d{2}-\d{2})\)", header_text)
                start_date = date_match.group(1) if date_match else None
                end_date = date_match.group(2) if date_match else None

                rounds.append({
                    "round_number": round_number,
                    "name": f"Round {round_number}",
                    "start_date": start_date,
                    "end_date": end_date
                })

                races += parse_races_from_html(html, round_number)

            browser.close()

        if not races:
            flash("📭 Nessuna gara trovata da importare.", "info")
            return

        conn = get_fresh_zrl_db()
        cur = conn.cursor()

        cur.execute("SELECT id FROM seasons WHERE name = ?", (season_name,))
        row = cur.fetchone()
        if row:
            season_id = row["id"]
            cur.execute("UPDATE seasons SET start = ?, end = ? WHERE id = ?", (season_start, season_end, season_id))
        else:
            cur.execute("INSERT INTO seasons (name, start_year, end_year) VALUES (?, ?, ?)",
                        (season_name, season_start[:4], season_end[:4]))
            season_id = cur.lastrowid

        for r in rounds:
            cur.execute("SELECT id FROM rounds WHERE season_id = ? AND round_number = ?", (season_id, r["round_number"]))
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE rounds SET name = ?, start_date = ?, end_date = ? WHERE id = ?",
                            (r["name"], r["start_date"], r["end_date"], row["id"]))
            else:
                cur.execute("INSERT INTO rounds (season_id, round_number, name, start_date, end_date) VALUES (?, ?, ?, ?, ?)",
                            (season_id, r["round_number"], r["name"], r["start_date"], r["end_date"]))

        cur.execute("SELECT id, round_number FROM rounds WHERE season_id = ?", (season_id,))
        round_map = {row["round_number"]: row["id"] for row in cur.fetchall()}

        imported = 0
        for race in races:
            round_id = round_map.get(race["round_number"])
            if not round_id:
                continue

            race_day = datetime.strptime(race["race_date"], "%d/%m/%y")
            active = 1 if race_day >= datetime.today() else 0

            cur.execute("SELECT id FROM races WHERE round_id = ? AND name = ? AND race_date = ?",
                        (round_id, race["name"], race["race_date"]))
            row = cur.fetchone()
            if row:
                cur.execute("""
                    UPDATE races SET format = ?, world = ?, course = ?, laps = ?, distance_km = ?, elevation_m = ?,
                    powerups = ?, fal_segments = ?, fts_segments = ?, active = ? WHERE id = ?
                """, (
                    race["format"], race["world"], race["course"], race["laps"], race["distance_km"], race["elevation_m"],
                    race["powerups"], race["fal_segments"], race["fts_segments"], active, row["id"]
                ))
            else:
                cur.execute("""
                    INSERT INTO races (
                        name, race_date, format, world, course, laps,
                        distance_km, elevation_m, powerups,
                        fal_segments, fts_segments, active, round_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    race["name"], race["race_date"], race["format"], race["world"], race["course"],
                    race["laps"], race["distance_km"], race["elevation_m"], race["powerups"],
                    race["fal_segments"], race["fts_segments"], active, round_id
                ))
            imported += 1

        conn.commit()
        conn.close()

        flash(f"✅ Importazione completata.\n🏁 {imported} gare salvate nel database.", "success")

    except Exception as e:
        flash(f"❌ Errore durante l'importazione WTRL: {str(e)}", "danger")
        print("❌ Dettaglio errore:", e)