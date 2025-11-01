# ============================================================
#  admin_reports.py
#  Gestione dei report amministrativi (Formazioni, Riders, Team)
# ============================================================

from flask import Blueprint, render_template, send_file
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import io
import datetime
import pandas as pd

# Import della connessione al DB centralizzata
from db import get_db

# --- Blueprint Flask ---
admin_reports_bp = Blueprint("admin_reports", __name__, url_prefix="/admin/reports")

# ============================================================
#  FUNZIONI DI UTILITÀ
# ============================================================

def make_table(data, headers):
    """Crea una tabella formattata per ReportLab"""
    table_data = [headers] + [list(row) for row in data]
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#007BFF")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))
    return table

# ============================================================
#  ROUTE: Pagina indice report
# ============================================================

@admin_reports_bp.route("/")
def index():
    """Mostra la pagina con elenco dei report disponibili"""
    now = datetime.datetime.now
    return render_template("admin/reports/index.html", now=now)

# ============================================================
#  ROUTE: Report Formazioni Confermate (PDF)
# ============================================================

@admin_reports_bp.route("/lineup/pdf")
def lineup_report_pdf():
    """Genera un report PDF elegante delle lineup, diviso per team."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            t.name AS team_name,
            r.name AS rider_name,
            r.category,
            r.zwift_power_id,
            r.country
        FROM race_lineup l
        JOIN teams t ON t.id = l.team_id
        JOIN riders r ON r.zwift_power_id = l.zwift_power_id
        ORDER BY t.name, r.name
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), title="Report Formazioni")
        styles = getSampleStyleSheet()
        elements = [
            Paragraph("Report Formazioni", styles["Title"]),
            Paragraph(f"Data generazione: {datetime.datetime.now():%d/%m/%Y %H:%M}", styles["Normal"]),
            Spacer(1, 12),
            Paragraph("Nessuna formazione presente.", styles["Normal"])
        ]
        doc.build(elements)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name="report_lineup.pdf", mimetype="application/pdf")

    from collections import defaultdict
    teams = defaultdict(list)
    for r in rows:
        teams[r["team_name"]].append(r)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), title="Report Formazioni Elegante")
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Report Formazioni per Team", styles["Title"]),
        Paragraph(f"Data generazione: {datetime.datetime.now():%d/%m/%Y %H:%M}", styles["Normal"]),
        Spacer(1, 12)
    ]

    # Funzione per creare tabelle professionali
    def make_stylish_table(data, headers):
        table_data = [headers] + [list(row) for row in data]
        table = Table(table_data, repeatRows=1, hAlign='CENTER')
        # Stile
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004080")),  # Intestazione blu scuro
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        # Alternanza colori righe
        row_colors = [colors.HexColor("#E6F0FF"), colors.white]
        for i, _ in enumerate(data):
            table.setStyle(TableStyle([("BACKGROUND", (0, i+1), (-1, i+1), row_colors[i % 2])]))
        return table

    # Creazione tabelle per ciascun team
    for team_name, riders in teams.items():
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Team: {team_name}</b>", styles["Heading2"]))
        data = [(r["rider_name"], r["category"], r["country"], r["zwift_power_id"]) for r in riders]
        headers = ["Rider", "Categoria", "Paese", "Zwift ID"]
        elements.append(make_stylish_table(data, headers))
        elements.append(Spacer(1, 12))

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="report_lineup.pdf", mimetype="application/pdf")


# ============================================================
#  ROUTE: Report Riders (CSV)
# ============================================================

@admin_reports_bp.route("/riders/csv")
def riders_csv():
    """Scarica un CSV con tutti i riders attivi"""
    import io
    import pandas as pd
    from flask import send_file
    from db import get_db

    conn = get_db()

    df = pd.read_sql_query("""
        SELECT 
            zwift_power_id, name, category, ranking,
            wkg_20min, watt_20min, wkg_15sec, watt_15sec,
            weight, ftp, age, team_id,
            available_zrl, is_captain, email, status, races, profile_url, country, created_at
        FROM riders
        WHERE active = 1
        ORDER BY category, name
    """, conn)

    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, sep=";", encoding="utf-8")
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="riders_attivi.csv", mimetype="text/csv")


# ============================================================
#  ROUTE: Report Team (PDF)
# ============================================================

@admin_reports_bp.route("/teams/pdf")
def teams_pdf():
    """Crea un report PDF con le squadre e i loro dati"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            t.name,
            t.category,
            t.division,
            COUNT(r.zwift_power_id) AS n_riders,
            c.name AS captain
        FROM teams t
       LEFT JOIN race_lineup rl ON rl.team_id = t.id
       LEFT JOIN riders r ON r.zwift_power_id = rl.zwift_power_id
       LEFT JOIN riders c ON c.zwift_power_id = t.captain_zwift_id
       GROUP BY t.id
       ORDER BY t.category, t.name

    """)
    rows = cur.fetchall()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Report Squadre")
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Report Squadre", styles["Title"]),
        Paragraph(f"Data generazione: {datetime.datetime.now():%d/%m/%Y %H:%M}", styles["Normal"]),
        Spacer(1, 12)
    ]

    if rows:
        data = [(r["name"], r["category"], r["division"], r["n_riders"], r["captain"]) for r in rows]
        headers = ["Nome Squadra", "Cat", "Divisione", "Riders", "Capitano"]
        elements.append(make_table(data, headers))
    else:
        elements.append(Paragraph("Nessuna squadra trovata.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="report_teams.pdf", mimetype="application/pdf")
