import os
import sqlite3
import logging
from flask import g, has_app_context
from werkzeug.security import generate_password_hash, check_password_hash

# 📁 Percorsi assoluti dei database (ora nella root)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ZRL_DB_PATH = os.path.join(BASE_DIR, "zrl.db") 
ZWIFT_DB_PATH = os.path.join(BASE_DIR, "zwift.db")

# ===============================================================
# 🔌 CONNESSIONE DATABASE
# ===============================================================

def _connect_db(db_path, attr_name):
    """Crea o riusa una connessione SQLite."""
    if has_app_context():
        if not hasattr(g, attr_name):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            setattr(g, attr_name, conn)
            logging.info(f"📂 Connessione Flask attiva → {db_path}")
        return getattr(g, attr_name)

    # Esecuzione standalone
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    logging.info(f"📂 Connessione diretta → {db_path}")
    return conn

def get_zrl_db():
    """Connessione al database ZRL."""
    return _connect_db(ZRL_DB_PATH, "zrl_db")

def get_zwift_db():
    """Connessione al database Zwift."""
    return _connect_db(ZWIFT_DB_PATH, "zwift_db")

def close_db(e=None):
    """Chiude la connessione ZRL se esiste."""
    db = g.pop("zrl_db", None)
    if db is not None:
        db.close()

# Alias comodo
get_db = get_zrl_db

# ===============================================================
# 👤 GESTIONE ADMIN
# ===============================================================

def get_admin_by_username(username):
    """Recupera un admin dal database per username."""
    conn = get_zrl_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM admins WHERE username = ?", (username,))
    admin = cur.fetchone()
    print("🔍 Admin trovato:", dict(admin) if admin else "Nessuno")
    return admin

def create_admin(username, password, email=None):
    """Crea un nuovo admin (se non esiste già)."""
    conn = get_zrl_db()
    hashed_pw = generate_password_hash(password)
    try:
        with conn:
            conn.execute("""
                INSERT INTO admins (username, password, email)
                VALUES (?, ?, ?)
            """, (username, hashed_pw, email))
        print(f"✅ Admin '{username}' creato con successo")
    except sqlite3.IntegrityError:
        print(f"⚠️ Admin '{username}' già esistente")

def verify_admin_password(admin_row, password):
    """Verifica la password di un admin."""
    if not admin_row:
        print("⚠️ Nessun admin da verificare")
        return False
    result = check_password_hash(admin_row["password"], password)
    print("🔐 Verifica password:", result)
    return result