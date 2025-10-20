def save_race_selection(cur, team_id, rider_ids, race_date):
    cur.execute("DELETE FROM race_selection WHERE team_id = ? AND race_date = ?", (team_id, race_date))
    for rider_id in rider_ids:
        cur.execute("""
            INSERT INTO race_selection (team_id, rider_id, race_date)
            VALUES (?, ?, ?)
        """, (team_id, rider_id, race_date))