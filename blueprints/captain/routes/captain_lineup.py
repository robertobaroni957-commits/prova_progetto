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

lineup_bp = Blueprint("lineup_captain", __name__)
@lineup_bp.route("/save_lineup", methods=["POST"])
@require_captain
def save_lineup():
    zwift_id = session.get("zwift_id")
    race_id = request.form.get("race_id")
    selected_riders = request.form.getlist("rider_ids")

    conn = get_zrl_db()
    cur = conn.cursor()

    captain = cur.execute("SELECT * FROM captains WHERE zwift_power_id = ?", (int(zwift_id),)).fetchone()
    if not captain:
        flash("❌ Capitano non trovato", "danger")
        return redirect(url_for("auth.login_captain"))

    team_id = captain["team_id"]
    cur.execute("DELETE FROM lineup WHERE team_id = ? AND race_id = ?", (team_id, race_id))

    for rider_id in selected_riders[:12]:
        cur.execute("""
            INSERT INTO lineup (team_id, rider_id, race_id)
            VALUES (?, ?, ?)
        """, (team_id, rider_id, race_id))

    conn.commit()
    flash("✅ Formazione salvata", "success")
    return redirect(url_for("dashboard_captain.captain_dashboard"))

@lineup_bp.route("/lineup/<int:team_id>/<int:race_id>", methods=["GET", "POST"])
@require_captain
def manage_lineup(team_id, race_id):
    zwift_id = session.get("zwift_id")
    if not zwift_id:
        flash("❌ Accesso non autorizzato", "danger")
        return redirect(url_for("auth.login_captain"))

    conn = get_zrl_db()
    cur = conn.cursor()

    captain = cur.execute("SELECT * FROM captains WHERE zwift_power_id = ?", (int(zwift_id),)).fetchone()
    if not captain or captain["team_id"] != team_id:
        flash("❌ Non puoi gestire la formazione di un altro team", "danger")
        return redirect(url_for("dashboard_captain.captain_dashboard"))

    race = cur.execute("SELECT * FROM races WHERE id = ?", (race_id,)).fetchone()
    if not race:
        flash("⚠️ Gara non trovata.", "danger")
        return redirect(url_for("dashboard_captain.captain_dashboard"))

    riders = cur.execute("""
        SELECT id AS rider_id, name, zwift_power_id
        FROM riders
        WHERE team_id = ? AND active = 1
    """, (team_id,)).fetchall()

    blocked_ids = [r["rider_id"] for r in cur.execute("""
        SELECT rider_id FROM lineup
        WHERE race_id = ? AND team_id != ?
    """, (race_id, team_id)).fetchall()]

    selected_ids = [r["rider_id"] for r in cur.execute("""
        SELECT rider_id FROM lineup
        WHERE race_id = ? AND team_id = ?
    """, (race_id, team_id)).fetchall()]

    if request.method == "POST":
        try:
            new_selection = [int(rid) for rid in request.form.getlist("rider_ids")]
        except ValueError:
            flash("❌ Selezione non valida.", "danger")
            return redirect(url_for("lineup_captain.manage_lineup", team_id=team_id, race_id=race_id))

        if len(new_selection) > 6:
            flash("⚠️ Puoi selezionare al massimo 6 corridori.", "warning")
            return redirect(url_for("lineup_captain.manage_lineup", team_id=team_id, race_id=race_id))

        valid_selection = [rid for rid in new_selection if rid not in blocked_ids]

        cur.execute("DELETE FROM lineup WHERE race_id = ? AND team_id = ?", (race_id, team_id))
        for rider_id in valid_selection:
            cur.execute("""
                INSERT INTO lineup (race_id, rider_id, team_id)
                VALUES (?, ?, ?)
            """, (race_id, rider_id, team_id))

        conn.commit()
        flash("✅ Formazione aggiornata con successo.", "success")
        return redirect(url_for("lineup_captain.manage_lineup", team_id=team_id, race_id=race_id))

    return render_template("captain/manage_lineup.html",
        page_title="Gestione Formazione",
        team_id=team_id,
        team_name=session.get("team_name"),
        race_date=race["race_date"],
        race=race,
        riders=riders,
        selected_ids=selected_ids,
        blocked_ids=blocked_ids
    )