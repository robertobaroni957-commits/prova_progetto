
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db, get_zrl_db
from utils.auth import require_roles, require_admin
from datetime import datetime
import json
import sqlite3

admin_races_bp = Blueprint("admin_races", __name__, url_prefix="/admin")


@admin_races_bp.route("/placeholder")
@require_admin
def placeholder():
    return render_template("admin/placeholder.html")


# ===========================
# Visualizza stagioni e round
# ===========================

@admin_races_bp.route("/import_races", methods=["GET"])
@require_admin
def import_races():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Stagioni disponibili
    seasons_raw = cur.execute("SELECT id, start_year, end_year FROM seasons ORDER BY start_year DESC").fetchall()
    seasons = [{"id": s["id"], "label": f"{s['start_year']}/{str(s['end_year'])[-2:]}", "id_str": s["id"]} for s in seasons_raw]

    # Round già registrati con label stagione
    existing_rounds = cur.execute("""
        SELECT r.*, s.start_year, s.end_year,
               s.start_year || '/' || substr(s.end_year, -2) AS season_label
        FROM rounds r
        JOIN seasons s ON r.season_id = s.id
        ORDER BY r.start_date ASC
    """).fetchall()

    conn.close()
    return render_template("admin/import_rounds.html", seasons=seasons, existing_rounds=existing_rounds)


@admin_races_bp.route("/create_season", methods=["POST"])
@require_admin
def create_season():
    start_year = request.form.get("start_year", type=int)
    end_year = request.form.get("end_year", type=int)

    if not start_year or not end_year or end_year <= start_year:
        flash("⚠️ Anni non validi", "warning")
        return redirect(url_for("admin_races.import_races"))

    conn = get_db()
    cur = conn.cursor()

    # Evita duplicati
    existing = cur.execute("SELECT id FROM seasons WHERE start_year = ? AND end_year = ?", (start_year, end_year)).fetchone()
    if existing:
        flash("⚠️ Stagione già esistente", "warning")
    else:
        cur.execute("INSERT INTO seasons (start_year, end_year) VALUES (?, ?)", (start_year, end_year))
        conn.commit()
        flash("✅ Stagione creata correttamente", "success")

    conn.close()
    return redirect(url_for("admin_races.import_races"))

@admin_races_bp.route("/bulk_insert_rounds", methods=["POST"])
@require_admin
def bulk_insert_rounds():
    raw_data = request.form.get("rounds_json")
    if not raw_data:
        flash("⚠️ Nessun round da registrare", "warning")
        return redirect(url_for("admin_races.import_races"))
    try:
        rounds = json.loads(raw_data)
    except Exception as e:
        flash("❌ Errore nel parsing dei dati", "danger")
        print("❌ Errore:", e)
        return redirect(url_for("admin_races.import_races"))

    conn = get_db()
    cur = conn.cursor()

    for r in rounds:
        season_id = int(r["season_id"])
        name = r["name"]
        start_date = r["start_date"]
        end_date = r["end_date"]

        # Calcola round_number progressivo per quella stagione
        cur.execute("SELECT MAX(round_number) FROM rounds WHERE season_id = ?", (season_id,))
        max_round = cur.fetchone()[0] or 0
        next_round_number = max_round + 1

        cur.execute("""
            INSERT INTO rounds (season_id, round_number, name, start_date, end_date, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (season_id, next_round_number, name, start_date, end_date))

    conn.commit()
    conn.close()
    flash(f"✅ {len(rounds)} round registrati correttamente", "success")
    return redirect(url_for("admin_races.import_races"))


@admin_races_bp.route("/insert_round", methods=["POST"])
@require_admin
def insert_round():
    conn = get_db()
    cur = conn.cursor()

    round_number = request.form.get("round_number")
    name = request.form.get("name")
    season_id = request.form.get("season_id")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")

    today = datetime.today().strftime("%Y-%m-%d")
    is_active = 1 if end_date >= today else 0

    cur.execute("""
        INSERT INTO rounds (round_number, name, season_id, start_date, end_date, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (round_number, name, season_id, start_date, end_date, is_active))

    conn.commit()
    conn.close()
    flash("✅ Round inserito correttamente", "success")
    return redirect(url_for("admin_races.import_races"))


@admin_races_bp.route("/edit_round/<int:round_id>", methods=["POST"])
@require_admin
def edit_round(round_id):
    conn = get_db()
    cur = conn.cursor()

    name = request.form.get("name")
    round_number = request.form.get("round_number")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    is_active = 1 if request.form.get("is_active") == "1" else 0

    cur.execute("""
        UPDATE rounds
        SET name = ?, round_number = ?, start_date = ?, end_date = ?, is_active = ?
        WHERE id = ?
    """, (name, round_number, start_date, end_date, is_active, round_id))

    conn.commit()
    conn.close()
    flash("✅ Round aggiornato correttamente", "success")
    return redirect(url_for("admin_races.import_races"))


@admin_races_bp.route("/delete_round/<int:round_id>", methods=["POST"])
@require_admin
def delete_round(round_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM rounds WHERE id = ?", (round_id,))
    conn.commit()
    conn.close()

    flash("🗑️ Round eliminato correttamente", "info")
    return redirect(url_for("admin_races.import_races"))


@admin_races_bp.route("/seasons", methods=["GET"])
@require_admin
def view_seasons():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    season = conn.execute("SELECT * FROM seasons ORDER BY start_year DESC LIMIT 1").fetchone()
    rounds = []
    if season:
        rounds = conn.execute("""
            SELECT id, name, start_date, end_date
            FROM rounds
            WHERE season_id = ?
            ORDER BY start_date ASC
        """, (season["id"],)).fetchall()
    conn.close()
    return render_template("races/manage_seasons.html", season=season, rounds=rounds)


@admin_races_bp.route("/rounds/<int:season_id>", methods=["GET"])
@require_admin
def view_rounds(season_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    season = conn.execute("SELECT * FROM seasons WHERE id = ?", (season_id,)).fetchone()
    rounds = conn.execute("""
        SELECT * FROM rounds
        WHERE season_id = ?
        ORDER BY round_number
    """, (season_id,)).fetchall()
    conn.close()
    return render_template("races/view_rounds.html", season=season, rounds=rounds)
# ===========================
# Visualizza gare per round
# ===========================
@admin_races_bp.route("/races/round/<int:round_id>", methods=["GET"])
@require_admin
def view_races_by_round(round_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    round = conn.execute("SELECT * FROM rounds WHERE id = ?", (round_id,)).fetchone()
    races = conn.execute("SELECT * FROM races WHERE round_id = ? ORDER BY race_date", (round_id,)).fetchall()
    conn.close()
    if not round:
        flash("⚠️ Round non trovato.", "danger")
        return redirect(url_for("admin_races.view_seasons"))
    return render_template("races/view_races_by_round.html", round=round, races=races)

# ===========================
# Modifica / Elimina gare
# ===========================
@admin_races_bp.route("/races/edit/<int:race_id>", methods=["GET", "POST"])
@require_admin
def edit_race(race_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    race = cur.execute("SELECT * FROM races WHERE id = ?", (race_id,)).fetchone()
    if request.method == "POST":
        # aggiornamento dati gara qui se necessario
        flash("💾 Modifiche salvate", "success")
        round_id = race["round_id"]
        conn.close()
        return redirect(url_for("admin_races.view_races_by_round", round_id=round_id))
    conn.close()
    return render_template("races/edit_race.html", race=race)

@admin_races_bp.route("/races/delete/<int:race_id>", methods=["POST"])
@require_admin
def delete_race(race_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    race = cur.execute("SELECT round_id FROM races WHERE id = ?", (race_id,)).fetchone()
    round_id = race["round_id"] if race else None
    cur.execute("DELETE FROM races WHERE id = ?", (race_id,))
    conn.commit()
    conn.close()
    flash("🗑️ Gara eliminata con successo.", "info")
    if round_id:
        return redirect(url_for("admin_races.view_races_by_round", round_id=round_id))
    else:
        return redirect(url_for("admin_races.view_seasons"))

# ===========================
# Gestione riders per round
# ===========================
@admin_races_bp.route("/manage_riders", methods=["GET", "POST"])
@require_roles(["admin", "captain"])
def manage_riders():
    conn = get_db()
    cur = conn.cursor()

    team_id = request.args.get("team_id") or request.form.get("team_id")
    race_date = request.args.get("race_date") or request.form.get("race_date")
    if not team_id or not race_date:
        flash("❌ Parametri mancanti", "danger")
        return redirect(url_for("admin_races.view_seasons"))

    # 🔐 Controllo delegato se ruolo è "captain"
    if session.get("user_role") == "captain":
        rider_email = session.get("user_email")
        delegate = cur.execute("""
            SELECT r.zwift_power_id
            FROM race_delegates rd
            JOIN riders r ON rd.zwift_power_id = r.zwift_power_id
            WHERE rd.team_id = ? AND rd.race_date = ? AND r.email = ?
        """, (team_id, race_date, rider_email)).fetchone()
        if not delegate:
            flash("⛔ Non sei il delegato per questo team in questa gara", "danger")
            return redirect(url_for("admin_races.view_seasons"))

    # 📝 Gestione POST
    if request.method == "POST":
        action = request.form.get("action")

        if action == "save_lineup":
            selected_riders = request.form.getlist("riders")
            if len(selected_riders) > 6:
                flash("⚠️ Puoi selezionare al massimo 6 rider", "warning")
                return redirect(url_for("admin_races.manage_riders", team_id=team_id, race_date=race_date))

            cur.execute("DELETE FROM race_lineup WHERE team_id = ? AND race_date = ?", (team_id, race_date))
            for zwift_power_id in selected_riders:
                cur.execute("""
                    INSERT INTO race_lineup (team_id, race_date, zwift_power_id)
                    VALUES (?, ?, ?)
                """, (team_id, race_date, zwift_power_id))
            flash("✅ Formazione salvata", "success")

    conn.commit()

    # 📋 Dati per il rendering
    riders = cur.execute("""
        SELECT zwift_power_id, name, category, available_zrl, is_captain, email
        FROM riders
        WHERE team_id = ? AND active = 1
        ORDER BY name ASC

    """, (team_id,)).fetchall()

    selected_ids = [row["zwift_power_id"] for row in cur.execute("""
        SELECT zwift_power_id FROM race_lineup
        WHERE team_id = ? AND race_date = ?
    """, (team_id, race_date)).fetchall()]

    assigned_captain = cur.execute("""
        SELECT r.name FROM teams t
        JOIN riders r ON t.captain_zwift_id = r.zwift_power_id
        WHERE t.id = ?
    """, (team_id,)).fetchone()
    assigned_captain = assigned_captain["name"] if assigned_captain else None

    team_name = cur.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()["name"]

    conn.close()
    return render_template("admin/manage_riders.html",
                       team_id=team_id,
                       race_date=race_date,
                       team_name=team_name,
                       riders=riders,
                       selected_ids=selected_ids,
                       assigned_captain=assigned_captain)


@admin_races_bp.route("/manage_captains", methods=["GET", "POST"])
@require_admin
def manage_captains():
    conn = get_zrl_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Recupero la gara selezionata (ad esempio la prossima)
    selected_race = cur.execute("""
        SELECT * FROM races
        WHERE active = 1
        ORDER BY race_date ASC
        LIMIT 1
    """).fetchone()
    selected_race_date = selected_race["race_date"] if selected_race else "N/D"

    if request.method == "POST":
        action = request.form.get("action")
        team_id = request.form.get("team_id")
        zwift_power_id = request.form.get("zwift_power_id")

        if action == "assign_captain" and team_id and zwift_power_id:
            # Rimuovo eventuale capitano precedente del team
            cur.execute("""
                UPDATE riders
                SET is_captain = 0
                WHERE zwift_power_id IN (
                    SELECT zwift_power_id FROM rider_teams WHERE team_id = ?
                )
            """, (team_id,))
            
            # Imposto nuovo capitano
            cur.execute("UPDATE riders SET is_captain = 1 WHERE zwift_power_id = ?", (zwift_power_id,))
            cur.execute("UPDATE teams SET captain_zwift_id = ? WHERE id = ?", (zwift_power_id, team_id))

            # 🔹 Inserimento o aggiornamento nella tabella captains
            cur.execute("""
                INSERT INTO captains (team_id, zwift_power_id, active)
                VALUES (?, ?, 1)
                ON CONFLICT(team_id, zwift_power_id)
                DO UPDATE SET active = 1
            """, (team_id, zwift_power_id))

            flash("🧢 Capitano assegnato con successo!", "success")

        elif action == "remove_captain" and zwift_power_id:
            cur.execute("UPDATE riders SET is_captain = 0 WHERE zwift_power_id = ?", (zwift_power_id,))
            cur.execute("UPDATE teams SET captain_zwift_id = NULL WHERE captain_zwift_id = ?", (zwift_power_id,))
            cur.execute("UPDATE captains SET active = 0 WHERE zwift_power_id = ?", (zwift_power_id,))
            flash("🧢 Capitano rimosso", "info")

        conn.commit()
        return redirect(url_for("admin_races.manage_captains"))

    # GET: selezione team per filtro
    selected_team_id = request.args.get("team_id", type=int)

    # Teams disponibili
    available_teams = cur.execute("""
        SELECT t.id, t.name
        FROM teams t
        ORDER BY t.name
    """).fetchall()

    # Rider disponibili solo per il team selezionato e non ancora capitani
    if selected_team_id:
        unassigned_riders = cur.execute("""
            SELECT r.zwift_power_id, r.name
            FROM riders r
            JOIN rider_teams rt ON r.zwift_power_id = rt.zwift_power_id
            WHERE r.is_captain = 0 AND rt.team_id = ?
            ORDER BY r.name
        """, (selected_team_id,)).fetchall()
    else:
        unassigned_riders = []

    # Capitani attuali
    current_captains = cur.execute("""
        SELECT t.name AS team_name, r.name AS rider_name, r.zwift_power_id
        FROM teams t
        JOIN riders r ON t.captain_zwift_id = r.zwift_power_id
        ORDER BY t.name
    """).fetchall()

    conn.close()

    return render_template(
        "admin/manage_captains.html",
        selected_race_date=selected_race_date,
        available_teams=available_teams,
        unassigned_riders=unassigned_riders,
        current_captains=current_captains,
        selected_team_id=selected_team_id
    )
