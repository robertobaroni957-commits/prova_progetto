from flask import Blueprint, render_template, session, redirect, url_for, flash
from utils.auth import require_captain
import sqlite3
import os

def get_zrl_db():
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DB_PATH = os.path.join(BASE_DIR, "zrl.db")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

dashboard_bp = Blueprint("dashboard_captain", __name__)

@dashboard_bp.route("/dashboard")
@require_captain
def captain_dashboard():
    zwift_id = session.get("zwift_id")
    if not zwift_id:
        flash("❌ Accesso non autorizzato", "danger")
        return redirect(url_for("auth.login_captain"))

    conn = get_zrl_db()
    cur = conn.cursor()

    # Esempio di query (puoi adattarla)
    # races = cur.execute("SELECT * FROM races WHERE zwift_id = ?", (zwift_id,)).fetchall()
    # conn.close()
    # return render_template("captain/captain_dashboard.html", races=races)

    return render_template("captain/captain_dashboard.html")
    captain = cur.execute("SELECT * FROM captains WHERE zwift_power_id = ?", (zwift_id,)).fetchone()
    team_id = captain["team_id"] if captain else None
    team_assigned = bool(team_id)

    team_name = "—"
    if team_assigned:
        team = cur.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
        if team:
            team_name = team["name"]

    race = cur.execute("""
        SELECT * FROM races
        WHERE race_date >= DATE('now')
        ORDER BY race_date
        LIMIT 1
    """).fetchone()
    race_date = race["race_date"] if race else None

    lineup_ids = []
    if team_assigned and race:
        lineup = cur.execute("""
            SELECT rider_id FROM lineup
            WHERE team_id = ? AND race_id = ?
        """, (team_id, race["id"])).fetchall()
        lineup_ids = [r["rider_id"] for r in lineup]

    riders = []
    if team_assigned:
        riders = cur.execute("""
            SELECT id, name, category
            FROM riders
            WHERE team_id = ? AND active = 1
        """, (team_id,)).fetchall()
    return render_template("captain/captain_dashboard.html",
        page_title="Dashboard Capitano",
        team_assigned=team_assigned,
        team_name=team_name,
        race=race,
        race_date=race_date,
        lineup_ids=lineup_ids,
        riders=riders
    )