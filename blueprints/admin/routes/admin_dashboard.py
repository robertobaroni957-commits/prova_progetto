from flask import Blueprint, render_template, session, redirect, url_for, flash
from db import get_zrl_db
import sqlite3
from datetime import date

# 🔹 Blueprint dashboard amministratore
admin_panel_bp = Blueprint("admin_panel", __name__, url_prefix="/admin")

@admin_panel_bp.route("/dashboard", endpoint="admin_dashboard")
def admin_dashboard():
    """Pagina principale della dashboard amministratore"""

    # ✅ Controllo accesso
    if session.get("user_role") != "admin":
        flash("⛔ Accesso riservato agli amministratori", "danger")
        return redirect(url_for("auth.login_admin"))

    # ✅ Pagina di benvenuto solo la prima volta
    if not session.get("welcome_shown"):
        session["welcome_shown"] = True
        return redirect(url_for("admin_panel.welcome"))

    # ✅ Connessione DB
    conn = get_zrl_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    today = date.today()

    # 🔹 Aggiorna round scaduti
    cur.execute("UPDATE rounds SET is_active = 0 WHERE end_date < ?", (today,))
    conn.commit()

    # 🔹 Round attuale
    current_round = cur.execute("""
        SELECT id, name
        FROM rounds
        WHERE end_date >= ?
        ORDER BY end_date ASC
        LIMIT 1
    """, (today,)).fetchone()

    # 🔹 Gare del round attuale
    races = []
    if current_round:
        races_raw = cur.execute("""
            SELECT * FROM races
            WHERE round_id = ?
            ORDER BY race_date ASC
        """, (current_round["id"],)).fetchall()
        races = [dict(row) for row in races_raw]

    # 🔹 Dati squadre
    teams_raw = cur.execute("""
        SELECT t.id, t.name, t.category, t.division, t.captain_zwift_id,
               COUNT(rt.zwift_power_id) AS rider_count
        FROM teams t
        LEFT JOIN rider_teams rt ON t.id = rt.team_id
        GROUP BY t.id
        ORDER BY t.name ASC
    """).fetchall()

    # 🔹 Prossima data gara
    race_date_row = cur.execute("""
        SELECT MIN(race_date)
        FROM races
        WHERE race_date >= DATE('now')
    """).fetchone()
    race_date = race_date_row[0] if race_date_row and race_date_row[0] else None

    # 🔹 Costruzione lista squadre
    teams = []
    for team in teams_raw:
        captain_name = None
        if team["captain_zwift_id"]:
            rider = cur.execute("SELECT name FROM riders WHERE zwift_power_id = ?", (team["captain_zwift_id"],)).fetchone()
            if rider:
                captain_name = rider["name"]

        has_lineup = False
        if race_date:
            result = cur.execute("""
                SELECT 1 FROM race_lineup
                WHERE team_id = ? AND race_date = ?
                LIMIT 1
            """, (team["id"], race_date)).fetchone()
            has_lineup = result is not None

        teams.append({
            "id": team["id"],
            "name": team["name"],
            "category": team["category"],
            "division": team["division"],
            "captain_name": captain_name,
            "rider_count": team["rider_count"],
            "has_lineup": has_lineup
        })

    # 🔹 Riempie fino a 16 card per layout
    while len(teams) < 16:
        teams.append({"empty": True})

    conn.close()

    return render_template(
        "admin/admin_dashboard.html",
        teams=teams,
        races=races,
        current_round=current_round,
        current_time=today,
        race_date=race_date
    )

@admin_panel_bp.route("/welcome", endpoint="welcome")
def welcome():
    return render_template("admin/welcome.html")
