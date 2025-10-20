from db import get_zrl_db

def get_fresh_zrl_db():
    conn = get_zrl_db()
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def close_zrl_db(conn):
    if conn:
        conn.close()