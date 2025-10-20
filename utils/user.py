import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = "zrl.db"

def create_user(email, password, zwift_power_id, role='admin', team_id=None, active=1):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Verifica che la tabella 'users' esista
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cur.fetchone():
            print("❌ Tabella 'users' non trovata nel database.")
            return

        # Verifica se l'email è già registrata
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            print(f"⚠️ Utente con email '{email}' già esistente.")
            return

        hashed_pw = generate_password_hash(password)

        cur.execute("""
            INSERT INTO users (email, password, zwift_power_id, role, team_id, active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (email, hashed_pw, zwift_power_id, role, team_id, active))

        conn.commit()
        print(f"✅ Utente '{email}' creato con ruolo '{role}' e ZwiftPower ID '{zwift_power_id}'")

    except Exception as e:
        print(f"❌ Errore durante la creazione dell'utente: {e}")

    finally:
        conn.close()

# Esempio di utilizzo
if __name__ == "__main__":
    create_user(
        email="admin@example.com",
        password="secure123",
        zwift_power_id="123456",
        role="admin"
    )