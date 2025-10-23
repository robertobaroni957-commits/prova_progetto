# blueprints/ai_lineup/routes.py
from flask import Blueprint, render_template, request
from .ai_engine import genera_lineup

ai_lineup_bp = Blueprint('ai_lineup', __name__)

# ⚠️ Dati fittizi d’esempio (poi li prenderemo dal database)
riders = [
    {"nome": "Mario Rossi", "ftp": 300, "peso": 70, "ruolo": "climber", "form": 0.9, "disponibile": True},
    {"nome": "Luca Verdi", "ftp": 285, "peso": 75, "ruolo": "rouleur", "form": 0.8, "disponibile": True},
    {"nome": "Giorgio Neri", "ftp": 310, "peso": 78, "ruolo": "sprinter", "form": 0.7, "disponibile": False},
    {"nome": "Andrea Blu", "ftp": 270, "peso": 68, "ruolo": "climber", "form": 0.95, "disponibile": True},
    {"nome": "Pietro Gialli", "ftp": 260, "peso": 80, "ruolo": "rouleur", "form": 0.85, "disponibile": True},
    {"nome": "Simone Rosa", "ftp": 280, "peso": 73, "ruolo": "all-rounder", "form": 0.75, "disponibile": True},
]

@ai_lineup_bp.route('/ai-lineup', methods=['GET', 'POST'])
def ai_lineup():
    lineup = None
    race_type = None

    if request.method == 'POST':
        race_type = request.form.get('race_type')
        lineup = genera_lineup(riders, race_type)

    return render_template('ai_lineup.html', lineup=lineup, race_type=race_type)
