from flask import Blueprint, request, redirect, url_for, flash
import sqlite3
import os
from utils.seasons import get_or_create_season  # Assicurati che esista

seasons_bp = Blueprint("seasons", __name__)

@seasons_bp.route("/create", methods=["POST"])
def create_season():
    name = request.form.get("name")
    try:
        start_year = int(request.form.get("start_year"))
        end_year = int(request.form.get("end_year"))
    except (TypeError, ValueError):
        flash("⚠️ Anni non validi", "danger")
        return redirect(url_for("main.dashboard"))

    # Costruzione percorso assoluto del database
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    DB_PATH = os.path.join(BASE_DIR, "zrl.db")

    # Connessione sicura al database
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        get_or_create_season(cursor, name, start_year, end_year)
        conn.commit()

    flash("✅ Stagione creata o già esistente", "success")
    return redirect(url_for("main.dashboard"))