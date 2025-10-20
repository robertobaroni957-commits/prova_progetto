from flask import Blueprint, request, redirect, url_for, flash
from datetime import datetime
from playwright.sync_api import sync_playwright
import sqlite3
import os
import re

# 🔧 Utility
def safe_float(text):
    try:
        match = re.search(r"([\d\.]+)", text.replace(",", "."))
        return float(match.group(1)) if match else 0.0
    except Exception:
        return 0.0

def safe_int(text):
    try:
        match = re.search(r"(\d+)", text)
        return int(match.group(1)) if match else 0
    except Exception:
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
                # Colonna 1: nome gara + data
                col1 = cells[0].inner_text().strip().split("\n")

                if len(col1) == 2:
                    name = col1[0].strip()
                    raw_date = col1[1].strip()

                    try:
                       race_date = datetime.strptime(raw_date, "%d/%m/%y").strftime("%d-%m-%Y")
                    except Exception as e:
                       print(f"❌ Data non valida: '{raw_date}' → {e}")
                    continue
                else:
                    print(f"⚠️ Colonna 1 non valida: {cells[0].inner_text().strip()}")
                    continue

                # Colonne 2–4
                format = cells[1].inner_text().strip()
                world = cells[2].inner_text().strip()
                course = cells[3].inner_text().strip()

                # Colonna 5: laps, distanza, dislivello
                details = cells[4].inner_text().strip().split("\n")
                laps = safe_int(details[0]) if len(details) > 0 else 0
                distance_km = safe_float(details[1]) if len(details) > 1 else 0.0
                elevation_m = safe_float(details[2]) if len(details) > 2 else 0.0

                # Colonne 6–8
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

# 🚀 Route Flask
import_wtrl_bp = Blueprint('import_wtrl', __name__)

@import_wtrl_bp.route('/import-wtrl-races', methods=['POST'])
def import_wtrl_races():
    season_id = request.form.get('season_id')
    round_name = request.form.get('round_name')
    round_url = request.form.get('round_url')

    if not season_id or not round_name or not round_url:
        flash("❌ Tutti i campi sono obbligatori.", "danger")
        return redirect(url_for('main.index'))

    try:
        db_path = os.path.abspath("zrl.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 🔧 Crea la tabella races se non esiste
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS races (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            race_date TEXT NOT NULL,
            format TEXT,
            world TEXT,
            course TEXT,
            laps INTEGER,
            distance_km REAL,
            elevation_m REAL,
            powerups TEXT,
            fal_segments TEXT,
            fts_segments TEXT,
            round_id INTEGER,
            active INTEGER DEFAULT 1,
            UNIQUE(race_date, name)
        )
        """)

        # 🔍 Verifica che la stagione esista
        cursor.execute("SELECT id FROM seasons WHERE id = ?", (season_id,))
        season = cursor.fetchone()
        if not season:
            flash("❌ Stagione non trovata.", "danger")
            conn.close()
            return redirect(url_for('main.index'))

        # 🔍 Cerca il round esistente
        cursor.execute("""
            SELECT id FROM rounds WHERE season_id = ? AND name = ?
        """, (season_id, round_name))
        round = cursor.fetchone()

        if not round:
            flash("❌ Round non trovato. Inseriscilo manualmente prima di importare le gare.", "danger")
            conn.close()
        return redirect(url_for('main.index'))

        round_id = round["id"]

        # 🌐 Scarica le gare
        races = fetch_race_from_url(round_url)
        if not races:
            flash("⚠️ Nessuna gara trovata nel link fornito.", "warning")
            conn.close()
            return redirect(url_for('main.index'))

        # 💾 Inserisci le gare
        inserted = 0
        for race in races:
            if not race.get("race_date") or not race.get("name"):
                print(f"⚠️ Gara ignorata: dati mancanti → {race}")
                continue

            cursor.execute("SELECT COUNT(*) FROM races WHERE race_date = ? AND name = ?", (race["race_date"], race["name"]))
            if cursor.fetchone()[0] > 0:
                continue

            cursor.execute("""
                INSERT INTO races (
                    name, race_date, format, world, course,
                    laps, distance_km, elevation_m,
                    powerups, fal_segments, fts_segments,
                    round_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                race["name"], race["race_date"], race["format"], race["world"], race["course"],
                race["laps"], race["distance_km"], race["elevation_m"],
                race["powerups"], race["fal_segments"], race["fts_segments"],
                round_id
            ))
            inserted += 1

        conn.commit()
        conn.close()
        flash(f"✅ Importate {inserted} gare nel round '{round_name}'.", "success")

    except Exception as e:
        flash(f"❌ Errore durante l'importazione: {str(e)}", "danger")

    return redirect(url_for('main.index'))