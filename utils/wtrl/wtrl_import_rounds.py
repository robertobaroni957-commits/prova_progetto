import sqlite3
from datetime import datetime
from db import get_zrl_db

def carica_rounds_manuali():
    return [
        {
            "number": 1,
            "name": "Round 1",
            "start_date": "2025-09-16",
            "end_date": "2025-10-07",
            "link": None
        },
        {
            "number": 2,
            "name": "Round 2",
            "start_date": "2025-11-04",
            "end_date": "2025-12-09",
            "link": None
        },
        {
            "number": 3,
            "name": "Round 3",
            "start_date": "2026-01-06",
            "end_date": "2026-02-10",
            "link": None
        },
        {
            "number": 4,
            "name": "Round 4",
            "start_date": "2026-04-07",
            "end_date": "2026-04-28",
            "link": None
        }
    ]

def importa_stagione_e_rounds():
    print("🚀 Importazione manuale dei round avviata")
    rounds_data = carica_rounds_manuali()
    print("📦 Round caricati:", rounds_data)

    start_dates = [datetime.strptime(r["start_date"], "%Y-%m-%d").date() for r in rounds_data]
    end_dates = [datetime.strptime(r["end_date"], "%Y-%m-%d").date() for r in rounds_data]

    season_start = min(start_dates)
    season_end = max(end_dates)
    season_name = f"ZRL {season_start.year}/{season_end.year}"

    conn = get_zrl_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Verifica colonne
    columns = [col[1] for col in cur.execute("PRAGMA table_info(rounds)").fetchall()]
    if "start_date" not in columns:
        cur.execute("ALTER TABLE rounds ADD COLUMN start_date TEXT")
    if "end_date" not in columns:
        cur.execute("ALTER TABLE rounds ADD COLUMN end_date TEXT")
    if "active" not in columns:
        cur.execute("ALTER TABLE rounds ADD COLUMN active INTEGER DEFAULT 0")
    if "link" not in columns:
        cur.execute("ALTER TABLE rounds ADD COLUMN link TEXT")

    # Inserimento stagione
    cur.execute("SELECT id FROM seasons WHERE name = ?", (season_name,))
    season = cur.fetchone()
    if season:
        season_id = season["id"]
    else:
        cur.execute("""
            INSERT INTO seasons (name, start_year, end_year)
            VALUES (?, ?, ?)
        """, (season_name, season_start.year, season_end.year))
        season_id = cur.lastrowid

    # Inserimento round
    inserted = 0
    for r in rounds_data:
        cur.execute("""
            SELECT id FROM rounds WHERE season_id = ? AND round_number = ?
        """, (season_id, r["number"]))
        existing = cur.fetchone()

        active = 1 if r["start_date"] and r["end_date"] else 0

        if not existing:
            cur.execute("""
                INSERT INTO rounds (season_id, round_number, name, start_date, end_date, active, link)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (season_id, r["number"], r["name"], r["start_date"], r["end_date"], active, r["link"]))
            inserted += 1

    conn.commit()
    conn.close()
    print(f"✅ {inserted} round importati per la stagione {season_name}")

import re
from datetime import datetime

def parse_rounds_from_text(text):
    lines = text.splitlines()
    rounds = []
    current_round = None

    for line in lines:
        line = line.strip()
        if re.match(r"(?i)^round\s+\d+", line):
            match = re.search(r"(\d+)", line)
            if match:
                current_round = int(match.group(1))
        elif re.search(r"\d{1,2}(st|nd|rd|th)?\s+\w+\s*[-–]\s*\d{1,2}(st|nd|rd|th)?\s+\w+", line):
            parts = re.split(r"[-–]", line)
            start = parse_date(parts[0].strip())
            end = parse_date(parts[1].strip())
            rounds.append({
                "number": current_round,
                "name": f"Round {current_round}",
                "start_date": start.isoformat() if start else None,
                "end_date": end.isoformat() if end else None,
                "link": None
            })

    return rounds

def parse_date(text):
    text = text.strip().replace("–", "-")
    text = re.sub(r"(st|nd|rd|th)", "", text)
    try:
        return datetime.strptime(f"{text} 2025", "%d %b %Y").date()
    except Exception:
        try:
            return datetime.strptime(f"{text} 2026", "%d %b %Y").date()
        except Exception:
            return None

# Alias esportabile
import_rounds = importa_stagione_e_rounds