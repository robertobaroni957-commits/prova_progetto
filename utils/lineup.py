# utils/lineup.py
from db import get_zrl_db

def save_lineup(team_id, race_date, rider_ids):
    conn = get_zrl_db()
    cur = conn.cursor()

    cur.execute("DELETE FROM lineup WHERE team_id = ? AND race_date = ?", (team_id, race_date))

    for rider_id in rider_ids:
        cur.execute("""
            INSERT INTO lineup (team_id, rider_id, race_date)
            VALUES (?, ?, ?)
        """, (team_id, rider_id, race_date))

    conn.commit()
def save_race_selection(cur, team_id, rider_ids, race_date):
    """
    Salva la formazione per una gara specifica usando SQLite diretto.
    """
    # Cancella la formazione esistente
    cur.execute("""
        DELETE FROM race_selection 
        WHERE team_id = ? AND race_date = ?
    """, (team_id, race_date))

    # Inserisci i nuovi rider
    for rider_id in rider_ids:
        cur.execute("""
            INSERT INTO race_selection (team_id, rider_id, race_date)
            VALUES (?, ?, ?)
        """, (team_id, rider_id, race_date))