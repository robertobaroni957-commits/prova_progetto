from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.auth_decorators import require_admin
from db import get_zrl_db
import sqlite3

admin_riders_bp = Blueprint("admin_riders", __name__, url_prefix="/admin/riders")

@admin_riders_bp.route("/available", methods=["GET", "POST"])
@require_admin
def manage_available_riders():
    conn = get_zrl_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 🔄 Gestione POST: attiva/disattiva rider
    if request.method == "POST":
        rider_ids = request.form.getlist("rider_ids")
        action = request.form.get("action")

        if not rider_ids:
            flash("⚠️ Nessun rider selezionato", "warning")
            return redirect(url_for("admin_riders.manage_available_riders"))

        for rider_id in rider_ids:
            cur.execute("UPDATE riders SET active = ? WHERE zwift_power_id = ?", 
                        (1 if action == "activate" else 0, rider_id))

        conn.commit()
        flash(f"{len(rider_ids)} rider {'attivati' if action == 'activate' else 'disattivati'}", "success")
        return redirect(url_for("admin_riders.manage_available_riders"))

    # 🔍 Gestione GET: filtri categoria e team
    selected_category = request.args.get("category")
    selected_team = request.args.get("team_id")

    query = """
        SELECT r.zwift_power_id, r.name, r.active, r.category, r.age, r.ftp,
               rt.team_id
        FROM riders r
        LEFT JOIN rider_teams rt ON r.zwift_power_id = rt.zwift_power_id
        WHERE 1=1
    """
    params = []

    if selected_category:
        query += " AND r.category = ?"
        params.append(selected_category)

    if selected_team:
        query += " AND rt.team_id = ?"
        params.append(selected_team)

    query += " ORDER BY r.name"

    riders = cur.execute(query, params).fetchall()

    # 📦 Recupero categorie e team per i filtri
    categories = cur.execute(
        "SELECT DISTINCT category FROM riders WHERE category IS NOT NULL ORDER BY category"
    ).fetchall()
    
    teams = cur.execute(
        """SELECT t.id, t.name
           FROM teams t
           JOIN rider_teams rt ON t.id = rt.team_id
           GROUP BY t.id, t.name
           ORDER BY t.name"""
    ).fetchall()

    conn.close()
    return render_template(
        "admin/manage_available_riders.html",
        riders=riders,
        categories=categories,
        teams=teams,
        selected_category=selected_category,
        selected_team=selected_team
    )
