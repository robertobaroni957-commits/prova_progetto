# blueprints/ai_lineup/ai_engine.py
import random

def match_role_score(ruolo, race_type):
    """Compatibilità tra ruolo e tipo di percorso."""
    mappa = {
        "climber": {"montagna": 1.0, "pianura": 0.6, "cronosquadre": 0.8},
        "rouleur": {"montagna": 0.7, "pianura": 1.0, "cronosquadre": 0.9},
        "sprinter": {"montagna": 0.4, "pianura": 1.0, "cronosquadre": 0.7},
        "all-rounder": {"montagna": 0.8, "pianura": 0.8, "cronosquadre": 0.8},
    }
    return mappa.get(ruolo, {}).get(race_type, 0.7)

def calcola_score(rider, race_type):
    """Calcola un punteggio finale per ogni rider."""
    ftp_weight_ratio = rider["ftp"] / rider["peso"]
    compatibilita = match_role_score(rider["ruolo"], race_type)
    form = rider["form"]
    casuale = random.uniform(0.0, 0.05)
    score = (0.5 * ftp_weight_ratio) + (0.3 * compatibilita) + (0.2 * form) + casuale
    return round(score, 3)

def genera_lineup(riders, race_type, n=6):
    """Restituisce la formazione migliore basata su AI euristica."""
    disponibili = [r for r in riders if r.get("disponibile")]
    for r in disponibili:
        r["score"] = calcola_score(r, race_type)
    lineup = sorted(disponibili, key=lambda x: x["score"], reverse=True)[:n]
    return lineup
