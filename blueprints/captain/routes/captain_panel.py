from flask import Blueprint, render_template, session

captain_panel = Blueprint("captain_panel", __name__, url_prefix="/captain")

@captain_panel.route("/dashboard", endpoint="captain_dashboard")
def captain_dashboard():
    # Esempio dati fittizi
    team_assigned = session.get("team_id") is not None
    race = None  # oppure carica la prossima gara
    race_date = None
    riders = []  # carica rider disponibili
    lineup_ids = []  # rider selezionati

    return render_template("captain/captain_dashboard.html",
                           team_assigned=team_assigned,
                           race=race,
                           race_date=race_date,
                           riders=riders,
                           lineup_ids=lineup_ids)