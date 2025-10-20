from flask import Blueprint, request, redirect, url_for, flash, render_template
from datetime import datetime
from playwright.sync_api import sync_playwright
import sqlite3
import os
import re

# 🔧 Blueprint
import_wtrl_bp = Blueprint('import_wtrl', __name__)

# 🔧 Utility
def safe_float(text):
    try:
        match = re.search(r"([\d\.]+)", text.replace(",", "."))
        return float(match.group(1)) if match else 0.0
    except:
        return 0.0

def safe_int(text):
    try:
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else 0
    except:
        return 0

# 🌐 Scraping da WTRL
def fetch_race_from_url(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_selector("table", timeout=10000)

        rows = page.query_selector_all("table tr")
        races = []

        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) < 8:
                continue

            try:
                col1 = cells[0].inner_text().strip().split("\n")
                if len(col1) != 2:
                    continue

                name = col1[0].strip()
                raw_date = col1[1].strip()
                race_date = datetime.strptime(raw_date, "%d/%m/%y").strftime("%Y-%m-%d")

                format = cells[1].inner_text().strip()
                world = cells[2].inner_text().strip()
                course = cells[3].inner_text().strip()

                details = cells[4].inner_text().strip().split("\n")
                laps = safe_int(details[0]) if len(details) > 0 else 0
                distance_km = safe_float(details[1]) if len(details) > 1 else 0.0
                elevation_m = safe_float(details[2]) if len(details) > 2 else 0.0

                powerups = cells[5].inner_text().strip()
                fal_segments = cells[6].inner_text().strip()
                fts_segments = cells[7].inner_text().strip()

                races.append({
                    "name": name,
                    "race_date": race_date,
                    "format": format,
                    "world": world,
                    "course": course,
                    "laps": laps,
                    "distance_km": distance_km,
                    "elevation_m": elevation_m,
                    "powerups": powerups,
                    "fal_segments": fal_segments,
                    "fts_segments": fts_segments
                })

            except Exception as e:
                print(f"❌ Errore parsing riga: {e}")
                continue

        browser.close()
        return races

def fetch_all_category_races(url):
    from playwright.sync_api import sync_playwright
    from datetime import datetime
    import re

    def safe_float(text):
        match = re.search(r"([\d\.]+)", text.replace(",", "."))
        return float(match.group(1)) if match else 0.0

    def safe_int(text):
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else 0

    all_races = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)

        # Categorie da cliccare
        categories = ["A", "B", "C", "D"]

        for cat in categories:
            try:
                # Clicca sul pulsante della categoria
                page.click(f"text={cat}")
                page.wait_for_timeout(1000)  # aspetta che la tabella si aggiorni

                page.wait_for_selector("table", timeout=5000)
                rows = page.query_selector_all("table tr")

                for row in rows:
                    cells = row.query_selector_all("td")
                    if len(cells) < 8:
                        continue

                    col1 = cells[0].inner_text().strip().split("\n")
                    if len(col1) != 2:
                        continue

                    name = col1[0].strip()
                    raw_date = col1[1].strip()
                    try:
                        race_date = datetime.strptime(raw_date, "%d/%m/%y").strftime("%Y-%m-%d")
                    except:
                        continue

                    format = cells[1].inner_text().strip()
                    world = cells[2].inner_text().strip()
                    course = cells[3].inner_text().strip()

                    details = cells[4].inner_text().strip().split("\n")
                    laps = safe_int(details[0]) if len(details) > 0 else 0
                    distance_km = safe_float(details[1]) if len(details) > 1 else 0.0
                    elevation_m = safe_float(details[2]) if len(details) > 2 else 0.0

                    powerups = cells[5].inner_text().strip()
                    fal_segments = cells[6].inner_text().strip()
                    fts_segments = cells[7].inner_text().strip()

                    all_races.append({
                        "name": name,
                        "race_date": race_date,
                        "format": format,
                        "world": world,
                        "course": course,
                        "laps": laps,
                        "distance_km": distance_km,
                        "elevation_m": elevation_m,
                        "powerups": powerups,
                        "fal_segments": fal_segments,
                        "fts_segments": fts_segments,
                        "category": cat  # 👈 aggiunta della categoria
                    })

            except Exception as e:
                print(f"❌ Errore categoria {cat}: {e}")
                continue

        browser.close()
        return all_races


# 🚀 Route principale
@import_wtrl_bp.route('/import-wtrl-races', methods=['GET', 'POST'])
def import_wtrl_races():
    if request.method == 'POST':
        round_id = request.form.get('round_id')
        round_url = request.form.get('round_url')

        if not round_id or not round_url:
            flash("❌ Inserisci ID round e URL WTRL", "danger")
            return redirect(url_for('import_wtrl.import_wtrl_races'))

        try:
            conn = sqlite3.connect("zrl.db", isolation_level="EXCLUSIVE")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            conn.execute("BEGIN")

            # Verifica che il round esista
            cursor.execute("SELECT name FROM rounds WHERE id = ?", (round_id,))
            round_info = cursor.fetchone()
            if not round_info:
                conn.rollback()
                flash("❌ Round non trovato", "danger")
                return redirect(url_for('import_wtrl.import_wtrl_races'))

            # Scarica le gare dalla tabella visibile
            races = fetch_race_from_url(round_url)
            if not races:
                conn.rollback()
                flash("⚠️ Nessuna gara trovata", "warning")
                return redirect(url_for('import_wtrl.import_wtrl_races'))

            today = datetime.today().strftime("%Y-%m-%d")
            updated = 0
            inserted = 0
            skipped = 0

            for race in races:
                if not race["name"] or not race["race_date"]:
                    skipped += 1
                    continue

                active = 0 if race["race_date"] < today else 1

                cursor.execute("""
                    SELECT * FROM races
                    WHERE race_date = ? AND name = ?
                """, (race["race_date"], race["name"]))
                existing = cursor.fetchone()

                if existing:
                    # Confronta i campi per evitare update inutili
                    if (
                        existing["format"] == race["format"] and
                        existing["world"] == race["world"] and
                        existing["course"] == race["course"] and
                        existing["laps"] == race["laps"] and
                        existing["distance_km"] == race["distance_km"] and
                        existing["elevation_m"] == race["elevation_m"] and
                        existing["powerups"] == race["powerups"] and
                        existing["fal_segments"] == race["fal_segments"] and
                        existing["fts_segments"] == race["fts_segments"] and
                        existing["round_id"] == int(round_id) and
                        existing["active"] == active
                    ):
                        skipped += 1
                        continue

                    cursor.execute("""
                        UPDATE races SET
                            format = ?, world = ?, course = ?,
                            laps = ?, distance_km = ?, elevation_m = ?,
                            powerups = ?, fal_segments = ?, fts_segments = ?,
                            round_id = ?, active = ?
                        WHERE id = ?
                    """, (
                        race["format"], race["world"], race["course"],
                        race["laps"], race["distance_km"], race["elevation_m"],
                        race["powerups"], race["fal_segments"], race["fts_segments"],
                        round_id, active, existing["id"]
                    ))
                    updated += 1
                    print(f"🔄 Aggiornata: {race['name']}")
                else:
                    cursor.execute("""
                        INSERT INTO races (
                            name, race_date, format, world, course,
                            laps, distance_km, elevation_m,
                            powerups, fal_segments, fts_segments,
                            round_id, active
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        race["name"], race["race_date"], race["format"], race["world"], race["course"],
                        race["laps"], race["distance_km"], race["elevation_m"],
                        race["powerups"], race["fal_segments"], race["fts_segments"],
                        round_id, active
                    ))
                    inserted += 1
                    print(f"➕ Inserita: {race['name']}")

            conn.commit()
            conn.close()
            flash(f"✅ {inserted} inserite, {updated} aggiornate, {skipped} ignorate per il round '{round_info['name']}'", "success")
            return redirect(url_for('import_wtrl.import_wtrl_races'))

        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f"❌ Errore durante l'importazione: {str(e)}", "danger")
            return redirect(url_for('import_wtrl.import_wtrl_races'))

    # GET → mostra il form
    return render_template("admin/import_races.wtrl.html")