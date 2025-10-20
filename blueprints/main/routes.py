from flask import Blueprint, render_template
import sqlite3
import os

main_bp = Blueprint("main", __name__)

@main_bp.route("/", endpoint="home")
def home():
    return render_template("home.html")

@main_bp.route("/import")
def import_links():
    # Costruzione percorso assoluto del database
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DB_PATH = os.path.join(BASE_DIR, "zrl.db")  # ← percorso unificato

    # Connessione al database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query stagioni
    seasons = cursor.execute("SELECT * FROM seasons ORDER BY start_year DESC").fetchall()
    conn.close()

    # Render template con dati
    return render_template("import_links.html", seasons=seasons)
