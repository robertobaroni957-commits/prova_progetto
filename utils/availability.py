from db import get_zwift_db

def activate_rider_availability(rider_ids):
    conn = get_zwift_db()
    cur = conn.cursor()

    for rider_id in rider_ids:
        cur.execute("""
            UPDATE riders SET available_zrl = 1 WHERE id = ?
        """, (rider_id,))

    conn.commit()