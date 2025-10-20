import os
import sqlite3
import re
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash

admin_imports_bp = Blueprint("admin_imports", __name__)

DB_PATH = os.path.abspath(r"C:\Progetti\gestioneZRL\istances\zrl.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

def parse_date(date_str, default_year):
    m = re.search(r"(\d+)(?:st|nd|rd|th)? (\w+)", date_str)
    if m:
        day, mon = int(m.group(1)), m.group(2)
        month_num = MONTHS.get(mon, 1)
        return datetime(default_year, month_num, day).date()
    return None

def extract_round_number(name):
    match = re.search(r"(\d+)", name)
    return int(match.group(1)) if match else 0

def extract_rounds(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    rounds = []
    current_year = datetime.now().year
    i = 0
    while i < len(lines):
        name = lines[i]
        start, end = None, None
        if i + 1 < len(lines):
            dates = lines[i + 1].split("-")
            if len(dates) == 2:
                start = parse_date(dates[0], current_year)
                end = parse_date(dates[1], current_year)
                if start and end and end < start:
                    end = parse_date(dates[1], current_year + 1)
        if start and end:
            rounds.append((name, start.isoformat(), end.isoformat()))
        i += 2
    return rounds

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@admin_imports_bp.route("/import_rounds", methods=["GET", "POST"], endpoint="import_rounds")
def import_rounds_view():
    conn = get_connection()
    cursor = conn.cursor()

    # Mostra i round esistenti
    existing_rounds = cursor.execute(
        "SELECT * FROM rounds ORDER BY season_id, round_number"
    ).fetchall()

    if request.method == "POST":
        try:
            season = int(request.form.get("season"))
        except (TypeError, ValueError):
            flash("⚠️ Inserisci una stagione valida", "warning")
            return redirect(url_for("admin_imports.import_rounds"))

        raw_text = request.form.get("rounds_text")
        rounds = extract_rounds(raw_text)

        if not rounds:
            flash("⚠️ Nessun round valido trovato nel testo", "warning")
            return redirect(url_for("admin_imports.import_rounds"))

        inserted, skipped = 0, 0
        for name, start, end in rounds:
            round_number = extract_round_number(name)
            cursor.execute(
                "SELECT id FROM rounds WHERE season_id = ? AND name = ?",
                (season, name)
            )
            exists = cursor.fetchone()
            if exists:
                skipped += 1
                continue
            cursor.execute("""
                INSERT INTO rounds (season_id, round_number, name, start_date, end_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (season, round_number, name, start, end, 1))
            inserted += 1

        conn.commit()
        flash(f"✅ Importati {inserted} nuovi round. ⏩ {skipped} già presenti.", "success")
        conn.close()
        return redirect(url_for("admin_imports.import_rounds"))

    conn.close()
    return render_template("admin/import_rounds.html", existing_rounds=existing_rounds)

@admin_imports_bp.route("/update_round/<int:round_id>", methods=["POST"])
def update_round(round_id):
    name = request.form.get("name")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    is_active = 1 if request.form.get("is_active") == "on" else 0

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE rounds
        SET name = ?, start_date = ?, end_date = ?, is_active = ?
        WHERE id = ?
    """, (name, start_date, end_date, is_active, round_id))
    conn.commit()
    conn.close()

    flash("✅ Round aggiornato con successo.", "success")
    return redirect(url_for("admin_imports.import_rounds"))

@admin_imports_bp.route("/delete_round/<int:round_id>", methods=["POST"])
def delete_round(round_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rounds WHERE id = ?", (round_id,))
    conn.commit()
    conn.close()

    flash("🗑️ Round eliminato con successo.", "info")
    return redirect(url_for("admin_imports.import_rounds"))