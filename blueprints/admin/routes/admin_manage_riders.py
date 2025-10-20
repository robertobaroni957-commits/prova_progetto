from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from db import get_zrl_db
from utils.auth import require_roles
import sqlite3

# Blueprint
admin_lineup_bp = Blueprint("admin_lineup", __name__, url_prefix="/admin")

@admin_lineup_bp.route("/manage_riders", methods=["GET", "POST"])
@require_roles(["admin", "captain"])
def manage_riders():
    """
    Gestione rider per un team e una gara specifica.
    Mostra i rider già registrati nel team (rider_teams).
    """
    conn = get_zrl_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Parametri
    team_id = request.args.get("team_id") or request.form.get("team_id")
    race_date = request.args.get("race_date") or request.form.get("race_date")

    if not team_id:
        flash("❌ Team non specificato", "danger")
        return redirect(url_for("admin_panel.admin_dashboard"))

    if not race_date:
        flash("❌ Data gara non specificata", "warning")
        return redirect(url_for("admin_panel.admin_dashboard"))

    # 🔹 Salvataggio lineup
    if request.method == "POST":
        selected_riders = request.form.getlist("riders")
        if len(selected_riders) > 6:
            flash("⚠️ Puoi selezionare al massimo 6 rider", "warning")
            return redirect(url_for("admin_lineup.manage_riders", team_id=team_id, race_date=race_date))

        cur.execute("DELETE FROM race_lineup WHERE team_id = ? AND race_date = ?", (team_id, race_date))
        for zwift_power_id in selected_riders:
            cur.execute("""
                INSERT INTO race_lineup (team_id, race_date, zwift_power_id)
                VALUES (?, ?, ?)
            """, (team_id, race_date, zwift_power_id))

        conn.commit()
        flash("✅ Formazione salvata", "success")
        return redirect(url_for("admin_lineup.manage_riders", team_id=team_id, race_date=race_date))

    # 🔹 Rider attivi del team tramite rider_teams
    riders = cur.execute("""
        SELECT r.zwift_power_id, r.name, r.category, r.available_zrl, r.is_captain, r.email
        FROM riders r
        JOIN rider_teams rt ON r.zwift_power_id = rt.zwift_power_id
        WHERE rt.team_id = ? AND r.active = 1
        ORDER BY r.name ASC
    """, (team_id,)).fetchall()

    # 🔹 Rider già selezionati per la gara
    selected_ids = [
        row["zwift_power_id"]
        for row in cur.execute("""
            SELECT zwift_power_id
            FROM race_lineup
            WHERE team_id = ? AND race_date = ?
        """, (team_id, race_date)).fetchall()
    ]

    # 🔹 Capitano del team
    assigned_captain = cur.execute("""
        SELECT r.name
        FROM teams t
        JOIN riders r ON t.captain_zwift_id = r.zwift_power_id
        WHERE t.id = ?
    """, (team_id,)).fetchone()
    assigned_captain = assigned_captain["name"] if assigned_captain else None

    # 🔹 Nome del team
    team_name_row = cur.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
    team_name = team_name_row["name"] if team_name_row else "—"

    conn.close()

    return render_template(
        "admin/manage_riders.html",
        team_id=team_id,
        race_date=race_date,
        team_name=team_name,
        riders=riders,
        selected_ids=selected_ids,
        assigned_captain=assigned_captain
    )
