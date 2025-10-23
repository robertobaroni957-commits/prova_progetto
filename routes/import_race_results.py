import sqlite3
import csv
from datetime import datetime

# Percorsi relativi al progetto
DB_PATH = r"C:\Progetti\gestioneZRL\data\gestioneZRL.db"  # Aggiorna con il tuo DB reale
CSV_FILE = r"C:\Progetti\gestioneZRL\data\race_results.csv"  # CSV generato dall'OCR

def get_team_id(team_name, conn):
    """Recupera team_id dalla tabella teams usando il nome del team."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM teams WHERE name = ?", (team_name,))
    row = cur.fetchone()
    if row:
        return row[0]
    else:
        print(f"⚠ Team non trovato: {team_name}")
        return None

def import_race_results(csv_file, race_date):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            team_name = row['Team'].strip()
            team_id = get_team_id(team_name, conn)
            if not team_id:
                continue

            cursor.execute("""
                INSERT OR REPLACE INTO race_results_team
                (race_date, team_id, riders_count, fal_points, fts_points, fin_points, pbt_points, total_points)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                race_date,
                team_id,
                int(row['Riders']),
                float(row.get('FAL', 0)),
                float(row.get('FTS', 0)),
                float(row.get('FIN', 0)),
                float(row.get('PBT', 0)),
                float(row.get('POINTS', 0))
            ))

    conn.commit()
    conn.close()
    print("✅ Import completato")

if __name__ == "__main__":
    # Modifica qui la data della gara da importare
    race_date = '2025-11-04'
    import_race_results(CSV_FILE, race_date)
