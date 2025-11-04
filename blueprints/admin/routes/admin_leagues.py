from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.auth_decorators import require_admin
from db import get_zrl_db
import sqlite3

admin_leagues_bp = Blueprint("admin_leagues", __name__, url_prefix="/admin/leagues")

@admin_leagues_bp.route("/manage", methods=["GET", "POST"])
@require_admin
def manage_leagues():
    """Gestione delle leghe (crea, aggiorna, elimina)."""
    conn = get_zrl_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == "POST":
        action = request.form.get("action")
        league_id = request.form.get("league_id")
        name = request.form.get("name").strip()
        type_ = request.form.get("type").strip()
        region = request.form.get("region").strip()

        if action == "create":
            cur.execute("""
                INSERT INTO leagues (name, type, region)
                VALUES (?, ?, ?)
            """, (name, type_, region))
            conn.commit()
            flash("✅ Lega creata correttamente", "success")

        elif action == "update":
            cur.execute("""
                UPDATE leagues
                SET name = ?, type = ?, region = ?
                WHERE id = ?
            """, (name, type_, region, league_id))
            conn.commit()
            flash("💾 Modifiche salvate", "success")

        elif action == "delete":
            cur.execute("DELETE FROM leagues WHERE id = ?", (league_id,))
            conn.commit()
            flash("🗑️ Lega eliminata", "warning")

        conn.close()
        return redirect(url_for("admin_leagues.manage_leagues"))

    leagues = cur.execute("""
        SELECT * FROM leagues ORDER BY type, region, name
    """).fetchall()

    conn.close()
    return render_template("admin/manage_leagues.html", leagues=leagues)
