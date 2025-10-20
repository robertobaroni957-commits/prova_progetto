from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_zrl_db
from utils.race_utils import get_next_race_date
from utils.auth import require_roles
import sqlite3

admin_lineup_bp = Blueprint("admin_lineup", __name__, url_prefix="/admin")

# ================================
# Gestione formazione team
# ================================
@admin_lineup_bp.route("/manage_riders", methods=["GET", "POST"], endpoint="manage_riders")
@require_roles(["admin", "captain"])
def manage_riders():
    conn = get_zrl_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    team_id = request.args.get("team_id") or request.form.get("team_id")
    race_date = request.args.get("race_date") or request.form.get("race_date")

    if not team_id:
        flash("❌ Team non specificato", "danger")
        return redirect(url_for("admin_panel.admin_dashboard"))

    if not race_date:
        race_date = get_next_race_date(team_id)
        if not race_date:
            flash("⛔ Nessuna gara disponibile per questo team", "warning")
            return redirect(url_for("admin_panel.admin_dashboard"))

    # 🔹 POST actions
    if request.method == "POST":
        action = request.form.get("action")
        selected_riders = request.form.getlist("riders")

        if action == "save_lineup":
            # Controllo massimo 6 rider
            if len(selected_riders) > 6:
                flash("⚠️ Puoi selezionare al massimo 6 rider", "warning")
                return redirect(url_for("admin_lineup.manage_riders", team_id=team_id, race_date=race_date))

            # Controllo conflitti
            conflicting_riders = []
            for zwift_power_id in selected_riders:
                conflict = cur.execute("""
                    SELECT rl.team_id
                    FROM race_lineup rl
                    WHERE rl.zwift_power_id = ?
                      AND rl.race_date = ?
                      AND rl.team_id != ?
                """, (zwift_power_id, race_date, team_id)).fetchone()
                if conflict:
                    rider_name = cur.execute("SELECT name FROM riders WHERE zwift_power_id = ?", (zwift_power_id,)).fetchone()["name"]
                    conflicting_riders.append(rider_name)

            if conflicting_riders:
                flash(f"❌ I seguenti rider sono già assegnati a un'altra gara in questa data: {', '.join(conflicting_riders)}", "danger")
                return redirect(url_for("admin_lineup.manage_riders", team_id=team_id, race_date=race_date))

            # Salvataggio lineup
            cur.execute("DELETE FROM race_lineup WHERE team_id = ? AND race_date = ?", (team_id, race_date))
            for zwift_power_id in selected_riders:
                cur.execute(
                    "INSERT INTO race_lineup (team_id, race_date, zwift_power_id) VALUES (?, ?, ?)",
                    (team_id, race_date, zwift_power_id)
                )
            conn.commit()
            flash("✅ Formazione salvata", "success")

        elif action == "remove_rider":
            remove_id = request.form.get("remove_id")
            if remove_id:
                cur.execute("DELETE FROM race_lineup WHERE team_id = ? AND race_date = ? AND zwift_power_id = ?",
                            (team_id, race_date, remove_id))
                conn.commit()
                rider_name = cur.execute("SELECT name FROM riders WHERE zwift_power_id = ?", (remove_id,)).fetchone()["name"]
                flash(f"🗑️ Rider {rider_name} rimosso dalla formazione", "success")

        return redirect(url_for("admin_lineup.manage_riders", team_id=team_id, race_date=race_date))

    # 🔹 GET: dati per il template
    riders = cur.execute("""
        SELECT r.zwift_power_id, r.name, r.category, r.available_zrl, r.is_captain, r.email
        FROM riders r
        JOIN rider_teams rt ON r.zwift_power_id = rt.zwift_power_id
        WHERE rt.team_id = ? AND r.active = 1
        ORDER BY r.name ASC
    """, (team_id,)).fetchall()

    # Rider già selezionati
    selected_ids = [row["zwift_power_id"] for row in cur.execute(
        "SELECT zwift_power_id FROM race_lineup WHERE team_id = ? AND race_date = ?", (team_id, race_date)).fetchall()]

    # Capitano assegnato
    assigned_captain = cur.execute("""
        SELECT r.name
        FROM teams t
        JOIN riders r ON t.captain_zwift_id = r.zwift_power_id
        WHERE t.id = ? AND r.active = 1
    """, (team_id,)).fetchone()
    assigned_captain = assigned_captain["name"] if assigned_captain else None

    team_name = cur.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()["name"]

    # Controllo rider impegnati in altre gare lo stesso giorno
    busy_riders = {row["zwift_power_id"] for row in cur.execute(
        "SELECT zwift_power_id FROM race_lineup WHERE race_date = ? AND team_id != ?", (race_date, team_id)).fetchall()
    }

    conn.close()

    return render_template("admin/manage_riders.html",
                           team_id=team_id,
                           race_date=race_date,
                           team_name=team_name,
                           riders=riders,
                           selected_ids=selected_ids,
                           assigned_captain=assigned_captain,
                           busy_riders=busy_riders)


# ================================
# Report formazioni admin
# ================================
@admin_lineup_bp.route("/lineup_report", endpoint="lineup_report_all")
@require_roles(["admin"])
def lineup_report_all():
    conn = get_zrl_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    next_race_row = cur.execute("SELECT MIN(race_date) as race_date FROM races WHERE race_date >= DATE('now')").fetchone()
    race_date = next_race_row["race_date"] if next_race_row else None

    team_id = request.args.get("team_id")
    category = request.args.get("category")

    all_teams = cur.execute("SELECT id, name FROM teams ORDER BY name ASC").fetchall()
    all_categories = [row["category"] for row in cur.execute("""
        SELECT DISTINCT r.category
        FROM riders r
        JOIN race_lineup rl ON r.zwift_power_id = rl.zwift_power_id
        WHERE rl.race_date = ?
        ORDER BY r.category ASC
    """, (race_date,)).fetchall()]

    # Filtra team se richiesto
    teams_query = "SELECT id, name FROM teams"
    params = []
    if team_id:
        teams_query += " WHERE id = ?"
        params.append(team_id)
    teams_query += " ORDER BY name ASC"
    teams = cur.execute(teams_query, params).fetchall()

    report = []
    for team in teams:
        query = """
            SELECT r.name, r.category, r.is_captain
            FROM riders r
            JOIN race_lineup rl ON r.zwift_power_id = rl.zwift_power_id
            WHERE rl.team_id = ? AND rl.race_date = ?
        """
        query_params = [team["id"], race_date]
        if category:
            query += " AND r.category = ?"
            query_params.append(category)
        query += " ORDER BY r.name ASC"

        selected_riders = cur.execute(query, query_params).fetchall()
        report.append({
            "team_name": team["name"],
            "selected_riders": selected_riders
        })

    category_colors = {
        "A": "bg-danger text-white",
        "B": "bg-success text-white",
        "C": "bg-primary text-white",
        "D": "bg-warning text-dark"
    }

    conn.close()
    return render_template("admin/lineup_report_all.html",
                           race_date=race_date,
                           report=report,
                           all_teams=all_teams,
                           all_categories=all_categories,
                           category_colors=category_colors)
