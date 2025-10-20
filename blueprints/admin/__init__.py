import os
import sqlite3

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "..", "zrl.db")  # ← risale alla root

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS riders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    available_zrl INTEGER DEFAULT 0,
    is_captain INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    division TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS captains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    team_id INTEGER,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS rider_team (
    rider_id INTEGER,
    team_id INTEGER,
    PRIMARY KEY (rider_id, team_id),
    FOREIGN KEY (rider_id) REFERENCES riders(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);
""")

conn.commit()
conn.close()
print("✅ Database inizializzato")