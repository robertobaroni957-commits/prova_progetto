from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
import datetime
import os
import shutil
import pandas as pd

admin_import_riders_bp = Blueprint("admin_import_riders", __name__, url_prefix="/admin/import")

# 🔹 Percorsi principali
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CSV_FILE = os.path.join(DATA_DIR, "riders.csv")
JSON_FILE = os.path.join(DATA_DIR, "riders.json")
ZRL_DB_FILE = os.path.join(PROJECT_ROOT, "zrl.db")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")

# 🔹 Verifica file
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
    # Forza zwift_power_id come stringa per compatibilità
    df["zwift_power_id"] = df["zwift_power_id"].astype(str)
    return df

# --- ROUTE: aggiorna tutti i rider ---
@admin_import_riders_bp.route("/update_all", methods=["GET"])
def update_all_riders():
    df = read_riders_file()
    if df is None:
        flash("❌ Nessun file riders.csv o riders.json trovato.", "danger")
        return redirect(url_for("admin_import_riders.import_zrl_riders"))

    backup_file = backup_db()
    conn = get_zrl_conn()
    cur = conn.cursor()

    # Dizionario per accesso veloce
    df_dict = {row["zwift_power_id"]: row for _, row in df.iterrows()}

    cur.execute("SELECT zwift_power_id FROM riders")
    db_riders = [str(row["zwift_power_id"]) for row in cur.fetchall()]

    updated = 0
    not_found = 0

    for zwid in db_riders:
        if zwid not in df_dict:
            not_found += 1
            continue

        r = df_dict[zwid]
        cur.execute("""
            UPDATE riders SET
                name=?, category=?, ranking=?,
                wkg_20min=?, watt_20min=?, wkg_15sec=?, watt_15sec=?,
                status=?, races=?, weight=?, ftp=?, age=?, country=?, profile_url=?
            WHERE zwift_power_id=?
        """, (
            r.get("name"), r.get("category"), r.get("ranking"),
            r.get("wkg_20min"), r.get("watt_20min"), r.get("wkg_15sec"), r.get("watt_15sec"),
            r.get("status"), r.get("races"), r.get("weight"), r.get("ftp"), r.get("age"),
            r.get("country"), r.get("profile_url"), zwid
        ))
        updated += 1

    conn.commit()
    conn.close()

    flash(f"✅ Aggiornamento completato. Rider aggiornati: {updated}, non trovati nei file: {not_found}. Backup: {backup_file}", "success")
    return redirect(url_for("admin_import_riders.import_zrl_riders"))

# --- ROUTE: import selettivo nuovi rider ---
@admin_import_riders_bp.route("/zrl_riders", methods=["GET", "POST"])
def import_zrl_riders():
    conn = get_zrl_conn()
    cur = conn.cursor()

    df = read_riders_file()
    if df is None:
        flash("❌ Nessun file riders.csv o riders.json trovato.", "danger")
        return render_template("admin/import_zrl_riders.html", zwift_riders=[], selected_category="")

    if request.method == "POST":
        selected_ids = request.form.getlist("rider_ids")
        new_riders = 0
        updated_riders = 0

        # Filtra DataFrame solo ai selezionati (compatibilità stringa)
        df["zwift_power_id"] = df["zwift_power_id"].astype(str)

        for zwid in selected_ids:
            rider_row = df[df["zwift_power_id"] == zwid]
            if rider_row.empty:
                continue
            rider = rider_row.iloc[0]

            existing = cur.execute("SELECT 1 FROM riders WHERE zwift_power_id=?", (zwid,)).fetchone()
            if existing:
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
                cur.execute("""
                INSERT INTO riders (
                    zwift_power_id, name, category, ranking,
                    wkg_20min, watt_20min, wkg_15sec, watt_15sec,
                    status, races, weight, ftp, age, country, profile_url,
                    available_zrl, is_captain, email, password,
                    active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rider["zwift_power_id"], rider["name"], rider["category"], rider["ranking"],
                rider["wkg_20min"], rider["watt_20min"], rider["wkg_15sec"], rider["watt_15sec"],
                rider["status"], rider["races"], rider["weight"], rider["ftp"], rider["age"],
                rider.get("country",""), rider.get("profile_url",""),
                1, 0, "", "", 1, datetime.datetime.now().strftime("%Y-%m-%d")
            ))
            new_riders += 1

        conn.commit()
        conn.close()
        flash(f"✅ Rider importati: {new_riders}, Rider aggiornati: {updated_riders}", "success")
        return redirect(url_for("admin_import_riders.import_zrl_riders"))

    # --- GET: filtri categoria ---
    selected_category = request.args.get("category", "").upper()
    if selected_category:
        if selected_category == "A":
            df = df[df["category"].isin(["A","A+"])]
        elif selected_category == "NESSUNA":
            df = df[df["category"].isna() | (df["category"]=="")]
        else:
            df = df[df["category"] == selected_category]

    zwift_riders = df.to_dict(orient="records")
    return render_template("admin/import_zrl_riders.html",
                           zwift_riders=zwift_riders,
                           selected_category=selected_category)
