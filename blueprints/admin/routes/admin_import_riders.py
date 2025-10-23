from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
import datetime
import os
import shutil
import pandas as pd

admin_import_riders_bp = Blueprint("admin_import_riders", __name__, url_prefix="/admin/import")

# 🔹 Percorsi corretti rispetto alla root del progetto
# punta sempre alla root del progetto

# ROOT del progetto
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CSV_FILE = os.path.join(DATA_DIR, "riders.csv")
JSON_FILE = os.path.join(DATA_DIR, "riders.json")
ZRL_DB_FILE = os.path.join(PROJECT_ROOT, "zrl.db")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")

if os.path.exists(CSV_FILE):
    print(f"✅ Trovato CSV: {CSV_FILE}")
elif os.path.exists(JSON_FILE):
    print(f"✅ Trovato JSON: {JSON_FILE}")
else:
    print("❌ Nessun file riders.csv o riders.json trovato.")

# --- Helper ---
def backup_db():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"zrl_backup_{timestamp}.db")
    shutil.copy2(ZRL_DB_FILE, backup_file)
    return backup_file

def get_zrl_conn():
    conn = sqlite3.connect(ZRL_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def read_riders_file():
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
    elif os.path.exists(JSON_FILE):
        df = pd.read_json(JSON_FILE)
    else:
        return None
    return df

# --- ROUTE: aggiorna tutti i rider esistenti ---
@admin_import_riders_bp.route("/update_all", methods=["GET"])
def update_all_riders():
    df = read_riders_file()
    if df is None:
        flash("❌ Nessun file riders.csv o riders.json trovato.", "danger")
        return redirect(url_for("admin_import_riders.import_zrl_riders"))

    backup_file = backup_db()
    conn = get_zrl_conn()
    cur = conn.cursor()

    updated = 0
    for _, row in df.iterrows():
        existing = cur.execute("SELECT 1 FROM riders WHERE zwift_power_id=?", (row["zwift_power_id"],)).fetchone()
        if existing:
            cur.execute("""
                UPDATE riders SET
                    name=?, category=?, ranking=?,
                    wkg_20min=?, watt_20min=?, wkg_15sec=?, watt_15sec=?,
                    status=?, races=?, weight=?, ftp=?, age=?, country=?, profile_url=?
                WHERE zwift_power_id=?
            """, (
                row.get("name"), row.get("category"), row.get("ranking"),
                row.get("wkg_20min"), row.get("watt_20min"), row.get("wkg_15sec"), row.get("watt_15sec"),
                row.get("status"), row.get("races"), row.get("weight"), row.get("ftp"), row.get("age"),
                row.get("country"), row.get("profile_url"), row.get("zwift_power_id")
            ))
            updated += 1

    conn.commit()
    conn.close()
    flash(f"✅ Rider aggiornati: {updated}. Backup DB: {backup_file}", "success")
    return redirect(url_for("admin_import_riders.import_zrl_riders"))

# --- ROUTE: import selettivo nuovi rider ---
@admin_import_riders_bp.route("/zrl_riders", methods=["GET", "POST"])
def import_zrl_riders():
    conn = get_zrl_conn()
    cur = conn.cursor()

    # POST: import selezionati
    if request.method == "POST":
        selected_ids = request.form.getlist("rider_ids")
        new_riders = 0
        updated_riders = 0

        df = read_riders_file()
        if df is None:
            flash("❌ Nessun file riders.csv o riders.json trovato.", "danger")
            return redirect(url_for("admin_import_riders.import_zrl_riders"))

        for zwid in selected_ids:
            rider_row = df[df["zwift_power_id"] == zwid]
            if rider_row.empty:
                continue
            rider = rider_row.iloc[0]

            existing = cur.execute("SELECT 1 FROM riders WHERE zwift_power_id=?", (zwid,)).fetchone()
            if existing:
                # Aggiorna esistente
                cur.execute("""
                    UPDATE riders SET
                        name=?, category=?, ranking=?,
                        wkg_20min=?, watt_20min=?, wkg_15sec=?, watt_15sec=?,
                        status=?, races=?, weight=?, ftp=?, age=?, country=?, profile_url=?, available_zrl=1
                    WHERE zwift_power_id=?
                """, (
                    rider["name"], rider["category"], rider["ranking"],
                    rider["wkg_20min"], rider["watt_20min"], rider["wkg_15sec"], rider["watt_15sec"],
                    rider["status"], rider["races"], rider["weight"], rider["ftp"], rider["age"],
                    rider.get("country",""), rider.get("profile_url",""), zwid
                ))
                updated_riders += 1
            else:
                # Inserisci nuovo
                cur.execute("""
                    INSERT INTO riders (
                        zwift_power_id, name, category, ranking,
                        wkg_20min, watt_20min, wkg_15sec, watt_15sec,
                        status, races, weight, ftp, age, country, profile_url,
                        team_id, available_zrl, is_captain, email, password,
                        active, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rider["zwift_power_id"], rider["name"], rider["category"], rider["ranking"],
                    rider["wkg_20min"], rider["watt_20min"], rider["wkg_15sec"], rider["watt_15sec"],
                    rider["status"], rider["races"], rider["weight"], rider["ftp"], rider["age"],
                    rider.get("country",""), rider.get("profile_url",""),
                    None, 1, 0, "", "", 1, datetime.datetime.now().strftime("%Y-%m-%d")
                ))
                new_riders += 1

        conn.commit()
        conn.close()
        flash(f"✅ Rider importati: {new_riders}, Rider aggiornati: {updated_riders}", "success")
        return redirect(url_for("admin_import_riders.import_zrl_riders"))

    # GET: filtri
    selected_category = request.args.get("category", "")
    df = read_riders_file()
    if df is None:
        flash("❌ Nessun file riders.csv o riders.json trovato.", "danger")
        return render_template("admin/import_zrl_riders.html", zwift_riders=[], selected_category=selected_category)

    # Filtra per categoria
    if selected_category:
        cat = selected_category.upper()
        if cat == "A":
            df = df[df["category"].isin(["A","A+"])]
        elif cat == "NESSUNA":
            df = df[df["category"].isna() | (df["category"]=="")]
        else:
            df = df[df["category"]==cat]

    zwift_riders = df.to_dict(orient="records")
    return render_template("admin/import_zrl_riders.html",
                           zwift_riders=zwift_riders,
                           selected_category=selected_category)
