import sqlite3
from db import get_zrl_db

def get_next_race_date():
    conn = get_zrl_db()
    cur = conn.cursor()
    result = cur.execute("""
        SELECT race_date
        FROM races
        WHERE race_date >= DATE('now')
        ORDER BY race_date ASC
        LIMIT 1
    """).fetchone()
    conn.close()
    return result[0] if result else None

def validate_race_selection(team_id, race_date):
    conn = get_zrl_db()
    cur = conn.cursor()
    delegate = cur.execute("""
        SELECT zwift_power_id
        FROM race_delegates
        WHERE team_id = ? AND race_date = ?
    """, (team_id, race_date)).fetchone()
    conn.close()
    return delegate is not None

def save_race_selection(team_id, race_date, rider_ids):
    conn = get_zrl_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM race_lineup WHERE team_id = ? AND race_date = ?", (team_id, race_date))
    for zwift_power_id in rider_ids:
        cur.execute("""
            INSERT INTO race_lineup (team_id, race_date, zwift_power_id)
            VALUES (?, ?, ?)
        """, (team_id, race_date, zwift_power_id))
    conn.commit()
    conn.close()