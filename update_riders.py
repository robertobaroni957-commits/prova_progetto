#!/usr/bin/env python3
import os
import sqlite3
import pandas as pd
from datetime import datetime

# Percorsi
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(REPO_DIR, "data")  # <-- cartella dove ci sono riders.json / riders.csv
CSV_FILE = os.path.join(DATA_DIR, "riders.csv")
JSON_FILE = os.path.join(DATA_DIR, "riders.json")
DB_FILE = os.path.join(REPO_DIR, "zrl.db")

def update_and_import_riders():
    # 1️⃣ Legge i dati dai file (CSV preferito)
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
    elif os.path.exists(JSON_FILE):
        df = pd.read_json(JSON_FILE)
    else:
        print("❌ Nessun file riders.csv o riders.json trovato.")
        return

    print(f"ℹ️ Totale riders nel file: {len(df)}")

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # 2️⃣ Crea la tabella se non esiste
    cur.execute("""
    CREATE TABLE IF NOT EXISTS riders (
        zwift_power_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        ranking REAL,
        wkg_20min REAL,
        watt_20min REAL,
        wkg_15sec REAL,
        watt_15sec REAL,
        status TEXT,
        races INTEGER,
        weight REAL,
        ftp REAL,
        age INTEGER,
        country TEXT,
        profile_url TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 3️⃣ Aggiorna o inserisce i riders
    updated = 0
    inserted = 0
    for _, row in df.iterrows():
        cur.execute("SELECT * FROM riders WHERE zwift_power_id=?", (row["zwift_power_id"],))
        existing = cur.fetchone()

        if existing:
            # Aggiorna i campi modificabili
            cur.execute("""
            UPDATE riders SET
                name=?,
                category=?,
                ranking=?,
                wkg_20min=?,
                watt_20min=?,
                wkg_15sec=?,
                watt_15sec=?,
                status=?,
                races=?,
                weight=?,
                ftp=?,
                age=?,
                country=?,
                profile_url=?
            WHERE zwift_power_id=?
            """, (
                row.get("name"),
                row.get("category"),
                row.get("ranking"),
                row.get("wkg_20min"),
                row.get("watt_20min"),
                row.get("wkg_15sec"),
                row.get("watt_15sec"),
                row.get("status"),
                row.get("races"),
                row.get("weight"),
                row.get("ftp"),
                row.get("age"),
                row.get("country"),
                row.get("profile_url"),
                row.get("zwift_power_id")
            ))
            updated += 1
        else:
            # Inserisce nuovo rider
            cur.execute("""
            INSERT INTO riders (
                zwift_power_id, name, category, ranking, wkg_20min, watt_20min,
                wkg_15sec, watt_15sec, status, races, weight, ftp, age, country,
                profile_url, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row.get("zwift_power_id"),
                row.get("name"),
                row.get("category"),
                row.get("ranking"),
                row.get("wkg_20min"),
                row.get("watt_20min"),
                row.get("wkg_15sec"),
                row.get("watt_15sec"),
                row.get("status"),
                row.get("races"),
                row.get("weight"),
                row.get("ftp"),
                row.get("age"),
                row.get("country"),
                row.get("profile_url"),
                datetime.now().isoformat()
            ))
            inserted += 1

    conn.commit()
    conn.close()

    print(f"✅ Aggiornati: {updated} riders")
    print(f"✅ Inseriti nuovi: {inserted} riders")
