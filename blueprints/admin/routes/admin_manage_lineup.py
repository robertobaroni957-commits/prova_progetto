from flask import Blueprint, render_template, request, session, flash
from db import get_zrl_db
from utils.auth import require_roles

admin_lineup_bp = Blueprint("admin_lineup", __name__, url_prefix="/admin")

@admin_lineup_bp.route("/view_lineup", methods=["GET"])
@require_roles(["admin", "captain"])
def view_lineup():
    """
    Visualizza le formazioni salvate per un team e una gara.
    """
    conn = get_zrl_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Parametri opzionali: team e data gara
    team_id = request.args.get("team_id")
    race_date = request.args.get("race_date")

    # Lista dei team
    teams = cur.execute("SELECT id, name FROM teams ORDER BY name").fetchall()

    # Se team_id e race_date sono forniti, mostra la formazione
    lineup = []
    team_name = None
    if team_id and race_date:
        team_row = cur.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
        team_name = team_row["name"] if team_row else "—"

        lineup = cur.execute("""
            SELECT r.name, r.category, r.is_captain, r.available_zrl
            FROM race_lineup rl
            JOIN riders r ON rl.zwift_power_id = r.zwift_power_id
            WHERE rl.team_id = ? AND rl.race_date = ?
            ORDER BY r.name ASC
        """, (team_id, race_date)).fetchall()

    conn.close()
    return render_template(
        "admin/view_lineup.html",
        teams=teams,
        selected_team_id=team_id,
        race_date=race_date,
        lineup=lineup,
        team_name=team_name
    )
