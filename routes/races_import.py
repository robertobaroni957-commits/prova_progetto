from flask import Blueprint, request, redirect, url_for, flash
import sqlite3
from utils.wtrl_import_rounds import import_rounds
from utils.wtrl_import_races import import_races

races_bp = Blueprint("races_import", __name__, url_prefix="/races")

DB_PATH = "zrl.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_or_create_round(cursor, season_id, round_name):
    cursor.execute("""
        SELECT id FROM rounds WHERE season_id = ? AND name = ?
    """, (season_id, round_name))
    row = cursor.fetchone()
    if row:
        return row["id"]
    cursor.execute("""
        INSERT INTO rounds (season_id, name)
        VALUES (?, ?)
    """, (season_id, round_name))
    return cursor.lastrowid

@races_bp.route("/import_round", methods=["POST"])
def import_round():
    season_id = int(request.form.get("season_id"))
    round_name = request.form.get("round_name")
    round_url = request.form.get("round_url")

    if not season_id or not round_name or not round_url:
        flash("❌ Dati mancanti per l'importazione del round.", "danger")
        return redirect(url_for("main.dashboard"))

    try:
        conn = get_db()
        cursor = conn.cursor()

        round_id = get_or_create_round(cursor, season_id, round_name)
        races = wtrl_import(round_url)

        inserted = 0
        for race in races:
            cursor.execute("""
                SELECT COUNT(*) FROM races WHERE race_date = ? AND name = ?
            """, (race["race_date"], race["name"]))
            if cursor.fetchone()[0] > 0:
                continue

            cursor.execute("""
                INSERT INTO races (
                    round_id, name, race_date, format, world, course,
                    laps, distance_km, elevation_m,
                    powerups, fal_segments, fts_segments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                round_id, race["name"], race["race_date"], race["format"], race["world"], race["course"],
                race["laps"], race["distance_km"], race["elevation_m"],
                race["powerups"], race["fal_segments"], race["fts_segments"]
            ))
            inserted += 1

        conn.commit()
        flash(f"✅ {inserted} gare importate per il round '{round_name}'", "success")

    except Exception as e:
        flash(f"❌ Errore durante l'importazione: {e}", "danger")

    

    return redirect(url_for("main.dashboard"))