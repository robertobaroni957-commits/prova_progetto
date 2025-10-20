import os
import sqlite3
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from utils.auth import require_captain

def get_zrl_db():
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DB_PATH = os.path.join(BASE_DIR, "zrl.db")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

availability_bp = Blueprint("availability_captain", __name__)

@availability_bp.route("/view_availability", methods=["GET", "POST"])
@require_captain
def view_availability():
    zwift_id = session.get("zwift_id")
    if not zwift_id:
        flash("❌ Accesso non autorizzato", "danger")
        return redirect(url_for("auth.login_captain"))

    conn = get_zrl_db()
    cur = conn.cursor()

    # 🔄 Aggiorna stato gare
    cur.execute("UPDATE races SET active = 0 WHERE race_date < DATE('now')")
    cur.execute("UPDATE races SET active = 0 WHERE race_date >= DATE('now')")
    cur.execute("""
        UPDATE races SET active = 1
        WHERE race_date = (
            SELECT MIN(race_date) FROM races WHERE race_date >= DATE('now')
        )
    """)

    captain = cur.execute("SELECT * FROM captains WHERE zwift_power_id = ?", (zwift_id,)).fetchone()
    if not captain:
        flash("❌ Capitano non trovato", "danger")
        return redirect(url_for("auth.login_captain"))

    team_id = captain["team_id"]
    if not team_id:
        flash("⚠️ Nessun team assegnato. Contatta l'amministratore.", "warning")
        return redirect(url_for("dashboard_captain.captain_dashboard"))

    race = cur.execute("SELECT * FROM races WHERE active = 1").fetchone()

    riders = cur.execute("""
        SELECT r.zwift_power_id, r.name, r.category, a.status AS availability
        FROM riders r
        LEFT JOIN availability a ON r.zwift_power_id = a.zwift_power_id AND a.race_id = ?
        WHERE r.team_id = ? AND r.active = 1
    """, (race["id"] if race else 0, team_id)).fetchall()

    if request.method == 'POST' and race:
        for rider in riders:
            status = request.form.get(f"availability_{rider['id']}")
            cur.execute("DELETE FROM availability WHERE rider_id = ? AND race_id = ?", (rider["id"], race["id"]))
            cur.execute("INSERT INTO availability (rider_id, race_id, status) VALUES (?, ?, ?)",
                        (rider["id"], race["id"], status))
        conn.commit()
        flash("✅ Disponibilità aggiornata", "success")
        return redirect(url_for("availability_captain.view_availability"))

    return render_template("captain/view_availability.html",
        page_title="Disponibilità Corridori",
        race=race,
        riders=riders
    )