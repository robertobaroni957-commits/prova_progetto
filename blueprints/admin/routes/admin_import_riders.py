from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
import datetime
from urllib.parse import unquote

admin_import_riders_bp = Blueprint("admin_import_riders", __name__, url_prefix="/admin/import")

def get_zwift_db():
    conn = sqlite3.connect("zwift.db")
    conn.row_factory = sqlite3.Row
    return conn

def get_zrl_db():
    conn = sqlite3.connect("zrl.db")
    conn.row_factory = sqlite3.Row
    return conn

@admin_import_riders_bp.route("/zrl_riders", methods=["GET", "POST"])
def import_zrl_riders():
    zwift_conn = get_zwift_db()
    zwift_cur = zwift_conn.cursor()
    zrl_conn = get_zrl_db()
    zrl_cur = zrl_conn.cursor()

    # --- POST: import selezionati ---
    if request.method == "POST":
        selected_ids = request.form.getlist("rider_ids")
        new_riders = 0
        updated_riders = 0

        for zwid in selected_ids:
            rider = zwift_cur.execute(
                "SELECT * FROM zwift_power_riders WHERE zwift_power_id=?", (zwid,)
            ).fetchone()
            if rider:
                existing = zrl_cur.execute(
                    "SELECT 1 FROM riders WHERE zwift_power_id=?", (zwid,)
                ).fetchone()

                if existing:
                    # Aggiorna rider esistente
                    zrl_cur.execute(
                        """
                        UPDATE riders SET
                            name=?, category=?, ranking=?,
                            wkg_20min=?, watt_20min=?, wkg_15sec=?, watt_15sec=?,
                            status=?, races=?, weight=?, ftp=?, age=?,
                            available_zrl=1
                        WHERE zwift_power_id=?
                        """,
                        (
                            rider["name"], rider["category"], rider["ranking"],
                            rider["wkg_20min"], rider["watt_20min"], rider["wkg_15sec"], rider["watt_15sec"],
                            rider["status"], rider["races"], rider["weight"], rider["ftp"], rider["age"],
                            rider["zwift_power_id"]
                        )
                    )
                    updated_riders += 1
                else:
                    # Inserisci nuovo rider
                    zrl_cur.execute(
                        """
                        INSERT INTO riders (
                            zwift_power_id, name, category, ranking,
                            wkg_20min, watt_20min, wkg_15sec, watt_15sec,
                            status, races, weight, ftp, age,
                            team_id, available_zrl, is_captain, email, password,
                            active, profile_url, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            rider["zwift_power_id"], rider["name"], rider["category"], rider["ranking"],
                            rider["wkg_20min"], rider["watt_20min"], rider["wkg_15sec"], rider["watt_15sec"],
                            rider["status"], rider["races"], rider["weight"], rider["ftp"], rider["age"],
                            None, 1, 0, "", "", 1, "", datetime.datetime.now().strftime("%Y-%m-%d")
                        )
                    )
                    new_riders += 1

        zrl_conn.commit()
        flash(f"✅ Rider importati: {new_riders}, Rider aggiornati: {updated_riders}", "success")
        return redirect(url_for("admin_import_riders.import_zrl_riders"))

    # --- GET: filtri ---
    selected_category = unquote(request.args.get("category", ""))
    query = "SELECT * FROM zwift_power_riders WHERE 1=1"
    params = []

    if selected_category:
        cat = selected_category.upper()
        if cat == "A":
            query += " AND (category='A' OR category='A+')"
        elif cat == "NESSUNA":
            query += " AND (category IS NULL OR category='')"
        else:
            query += " AND category=?"
            params.append(cat)

    query += " ORDER BY name"
    zwift_riders = zwift_cur.execute(query, params).fetchall()

    zwift_conn.close()
    zrl_conn.close()

    return render_template(
        "admin/import_zrl_riders.html",
        zwift_riders=zwift_riders,
        selected_category=selected_category
    )
