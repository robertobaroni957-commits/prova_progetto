from flask import Blueprint, render_template, request, send_file, flash, redirect
from db import get_db
import pandas as pd
import io
import datetime
import locale
import sqlite3


# Imposta la localizzazione italiana per la data, con fallback sicuro
try:
    locale.setlocale(locale.LC_TIME, "it_IT.UTF-8")
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, "it_IT")
    except locale.Error:
        locale.setlocale(locale.LC_TIME, "")  # fallback al locale di default

admin_reports_bp = Blueprint("admin_reports", __name__, url_prefix="/admin/reports")

@admin_reports_bp.route("/")
def index():
    report_type = (request.args.get("report_type") or "riders_compact").strip()
    category_filter = (request.args.get("category") or "").strip().upper()
    team_filter = (request.args.get("team") or "").strip()

    # Valid report types
    valid_reports = ["riders_compact", "riders", "teams", "lineup", "team_composition"]
    if report_type not in valid_reports:
        flash("Tipo di report non valido", "danger")
        report_type = "riders_compact"

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ---------------------
    # Categorie e Teams
    # ---------------------
    categories = [r["category"] for r in cursor.execute(
        "SELECT DISTINCT category FROM riders WHERE active=1 AND category IS NOT NULL"
    ).fetchall()]
    teams_list = [r["name"] for r in cursor.execute(
        "SELECT DISTINCT name FROM teams WHERE name IS NOT NULL"
    ).fetchall()]

    rows, columns, lineup_per_team = [], [], {}
    race_date = None
    team_categories = {}

    # ---------------------
    # Report Riders / Riders Compact
    # ---------------------
    if report_type in ["riders", "riders_compact"]:
        query = """
            SELECT 
                r.zwift_power_id,
                r.name,
                TRIM(UPPER(r.category)) AS category,
                COALESCE(GROUP_CONCAT(DISTINCT t.name), '') AS teams
            FROM riders r
            LEFT JOIN rider_teams rt ON r.zwift_power_id = rt.zwift_power_id
            LEFT JOIN teams t ON t.id = rt.team_id
            WHERE r.active = 1
        """
        params = []
        if category_filter:
            query += " AND TRIM(UPPER(r.category)) = ?"
            params.append(category_filter)

        query += " GROUP BY r.zwift_power_id, r.name, r.category ORDER BY r.category, r.name"
        df = pd.read_sql_query(query, conn, params=params)

        # Gestione valori nulli
        for col in ["zwift_power_id", "name", "category", "teams"]:
            df[col] = df[col].fillna("").astype(str).str.strip()

        # Split team1 e team2
        split_teams = df["teams"].str.split(",", n=1, expand=True)
        df["team1"] = split_teams[0].fillna("").str.strip()
        df["team2"] = split_teams[1].fillna("").str.strip() if 1 in split_teams.columns else ""

        df = df[["zwift_power_id", "name", "category", "team1", "team2"]]
        rows = df.to_dict(orient="records")
        columns = list(df.columns)

    # ---------------------
    # Report Teams
    # ---------------------
    elif report_type == "teams":
        query = """
            SELECT 
                t.name AS team,
                t.category,
                COUNT(r.zwift_power_id) AS n_riders,
                COALESCE(r2.name, '') AS captain
            FROM teams t
            LEFT JOIN rider_teams rt ON rt.team_id = t.id
            LEFT JOIN riders r ON r.zwift_power_id = rt.zwift_power_id AND r.active = 1
            LEFT JOIN riders r2 ON r2.zwift_power_id = t.captain_zwift_id
            GROUP BY t.id, t.name, t.category, r2.name
            ORDER BY t.category ASC, t.name ASC
        """
        rows = [dict(r) for r in cursor.execute(query).fetchall()]
        columns = ["team", "category", "n_riders", "captain"]

    # ---------------------
    # Report Lineup
    # ---------------------
    elif report_type == "lineup":
        query = """
            SELECT 
                t.name AS team,
                r.name AS rider_name,
                TRIM(UPPER(r.category)) AS category,
                rl.race_date,
                COALESCE(rc.name, '') AS captain
            FROM race_lineup rl
            JOIN riders r ON r.zwift_power_id = rl.zwift_power_id
            JOIN teams t ON t.id = rl.team_id
            LEFT JOIN riders rc ON rc.zwift_power_id = t.captain_zwift_id
            WHERE 1=1
        """
        params = []
        if category_filter:
            query += " AND TRIM(UPPER(r.category)) = ?"
            params.append(category_filter.upper())

        query += " ORDER BY t.name, r.name"
        rows_raw = cursor.execute(query, params).fetchall()

        # Raggruppa riders per team e salva il capitano
        lineup_per_team = {}
        team_categories = {}
        category_order = {"A": 1, "B": 2, "C": 3, "D": 4, "OTHER": 5}
        team_order = []

        for r in rows_raw:
            team = r["team"] or "Senza Team"
            team_cat = r["category"] or "OTHER"
            if team_cat.upper() == "A+":
                team_cat = "A"
            if team not in lineup_per_team:
                lineup_per_team[team] = []
                team_categories[team] = team_cat.upper()
                team_order.append((category_order.get(team_cat.upper(), 99), team))

            rider_cat = r["category"] or "OTHER"
            if rider_cat.upper() == "A+":
                rider_cat = "A"

            lineup_per_team[team].append({
                "rider_name": r["rider_name"],
                "category": rider_cat.upper(),
                "race_date": r["race_date"],
                "captain": r["captain"]
            })

        # Ordina i team
        team_order.sort()
        lineup_per_team = {team: lineup_per_team[team] for _, team in team_order}

        # Formatta data
        race_date = ""
        if rows_raw:
            try:
                race_date = datetime.datetime.strptime(rows_raw[0]["race_date"], "%Y-%m-%d").strftime("%d %B %Y")
            except Exception:
                race_date = rows_raw[0]["race_date"]

    # ---------------------
    # Report Team Composition
    # ---------------------
    elif report_type == "team_composition":
        query = """
            SELECT 
                t.name AS team_name,
                TRIM(UPPER(t.category)) AS team_category,
                r.name AS rider_name,
                TRIM(UPPER(r.category)) AS rider_category,
                COALESCE(rc.name, '') AS captain
            FROM teams t
            LEFT JOIN rider_teams rt ON rt.team_id = t.id
            LEFT JOIN riders r ON r.zwift_power_id = rt.zwift_power_id AND r.active = 1
            LEFT JOIN riders rc ON rc.zwift_power_id = t.captain_zwift_id
            WHERE 1=1
        """
        params = []
        if team_filter:
            query += " AND t.name = ?"
            params.append(team_filter)
        if category_filter:
            if category_filter.upper() == "A":
                query += " AND TRIM(UPPER(r.category)) IN ('A', 'A+')"
            else:
                query += " AND TRIM(UPPER(r.category)) = ?"
                params.append(category_filter.upper())

        query += " ORDER BY t.name, r.name"
        df = pd.read_sql_query(query, conn, params=params)
        rows = df.to_dict(orient="records")

        # Normalizza rider_category
        for r in rows:
            if r.get("rider_category") == "A+":
                r["rider_category"] = "A"

        # Raggruppa i rider per team
        lineup_per_team = {}
        team_categories = {}
        category_order = {"A": 1, "B": 2, "C": 3, "D": 4, "OTHER": 5}
        team_order = []

        for r in rows:
            team = r.get("team_name") or "Senza Team"
            team_cat = r.get("team_category") or "OTHER"
            if team_cat.upper() == "A+":
                team_cat = "A"
            if team not in lineup_per_team:
                lineup_per_team[team] = []
                team_categories[team] = team_cat.upper()
                team_order.append((category_order.get(team_cat.upper(), 99), team))

            rider_cat = r.get("rider_category") or "OTHER"
            if rider_cat.upper() == "A+":
                rider_cat = "A"

            lineup_per_team[team].append({
                "rider_name": r.get("rider_name") or "",
                "category": rider_cat.upper(),
                "captain": r.get("captain") or ""
            })

        # Ordina team
        team_order.sort()
        lineup_per_team = {team: lineup_per_team[team] for _, team in team_order}

        columns = ["team_name", "rider_name", "category", "captain"]

    conn.close()

    return render_template(
        "admin/reports/index.html",
        report_type=report_type,
        rows=rows,
        columns=columns,
        categories=categories,
        teams=teams_list,
        category_filter=category_filter,
        team_filter=team_filter,
        lineup_per_team=lineup_per_team if report_type in ["lineup", "team_composition"] else None,
        team_categories=team_categories if report_type in ["lineup", "team_composition"] else None,
        race_date=race_date
    )


@admin_reports_bp.route("/export")
def export_report():
    import datetime
    import io
    import pandas as pd
    from flask import request, send_file, redirect, flash
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    report_type = request.args.get("report_type", "riders_compact")
    fmt = request.args.get("fmt", "csv")
    category_filter = (request.args.get("category") or "").strip().upper()
    team_filter = (request.args.get("team") or "").strip()

    conn = get_db()
    df = pd.DataFrame()
    params = []

    # ------------------------
    # RICAVA I DATI
    # ------------------------
    if report_type in ["riders", "riders_compact"]:
        query = """
            SELECT 
                r.zwift_power_id,
                r.name,
                TRIM(UPPER(r.category)) AS category,
                GROUP_CONCAT(DISTINCT t.name) AS teams
            FROM riders r
            LEFT JOIN rider_teams rt ON r.zwift_power_id = rt.zwift_power_id
            LEFT JOIN teams t ON t.id = rt.team_id
            WHERE r.active = 1
        """
        if category_filter:
            query += " AND TRIM(UPPER(r.category)) = ?"
            params.append(category_filter)
        query += " GROUP BY r.zwift_power_id, r.name, r.category ORDER BY r.name"
        df = pd.read_sql_query(query, conn, params=params)

        # pulizia valori nulli
        df["teams"] = df["teams"].fillna("").astype(str)
        split_teams = df["teams"].str.split(",", n=1, expand=True)
        df["team1"] = split_teams[0].fillna("").str.strip()
        df["team2"] = split_teams[1].fillna("").str.strip() if 1 in split_teams.columns else ""
        df = df[["zwift_power_id", "name", "category", "team1", "team2"]]

    elif report_type == "teams":
        query = """
            SELECT 
                t.name AS team, 
                t.category, 
                COUNT(rt.zwift_power_id) AS n_riders,
                COALESCE(c.name, '') AS captain
            FROM teams t
            LEFT JOIN rider_teams rt ON rt.team_id = t.id
            LEFT JOIN captains c ON c.team_id = t.id
            GROUP BY t.id
            ORDER BY t.category, t.name
        """
        df = pd.read_sql_query(query, conn)

    elif report_type == "lineup":
        query = """
            SELECT t.name AS team, r.name AS rider, TRIM(UPPER(r.category)) AS category, rl.race_date
            FROM race_lineup rl
            JOIN riders r ON r.zwift_power_id = rl.zwift_power_id
            JOIN teams t ON t.id = rl.team_id
            WHERE 1=1
        """
        if category_filter:
            query += " AND TRIM(UPPER(r.category)) = ?"
            params.append(category_filter)
        query += " ORDER BY t.name, r.name"
        df = pd.read_sql_query(query, conn, params=params)

    elif report_type == "team_composition":
        query = """
            SELECT 
                t.name AS team_name,
                r.name AS rider_name,
                TRIM(UPPER(r.category)) AS category,
                COALESCE(c.name, '') AS captain
            FROM teams t
            LEFT JOIN rider_teams rt ON rt.team_id = t.id
            LEFT JOIN riders r 
                ON r.zwift_power_id = rt.zwift_power_id 
                AND r.active = 1
            LEFT JOIN captains c 
                ON c.team_id = t.id AND c.active = 1
            WHERE 1=1
        """
        if category_filter:
            query += " AND TRIM(UPPER(r.category)) = ?"
            params.append(category_filter)
        if team_filter:
            query += " AND t.name = ?"
            params.append(team_filter)
        query += " ORDER BY t.name, r.name"
        df = pd.read_sql_query(query, conn, params=params)

    else:
        flash("Tipo di report non valido", "danger")
        conn.close()
        return redirect("/admin/reports")

    # ✅ chiudi connessione dopo aver caricato df
    conn.close()

    buffer = io.BytesIO()

    # ------------------------
    # Esportazione CSV
    # ------------------------
    if fmt == "csv":
        df.to_csv(buffer, index=False, sep=";", encoding="utf-8")
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"{report_type}.csv", mimetype="text/csv")

    # ------------------------
    # Esportazione XLSX
    # ------------------------
    elif fmt == "xlsx":
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Report")
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"{report_type}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ------------------------
    # Esportazione PDF
    # ------------------------

    elif fmt == "pdf":
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors

    # Footer con data/ora
        def footer(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 6)
            canvas.drawString(doc.leftMargin, 15, f"Generato il {datetime.datetime.now():%d %B %Y %H:%M}")
            canvas.restoreState()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=30,
            rightMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        styles = getSampleStyleSheet()
        elements = []

    # Colori ed emoji per le categorie
        color_map = {
            "A": colors.HexColor("#dc3545"),
            "B": colors.HexColor("#28a745"),
            "C": colors.HexColor("#17a2b8"),
            "D": colors.HexColor("#ffc107"),
            "OTHER": colors.HexColor("#6c757d")
        }
        emoji_map = {
            "A": "🔴", "B": "🟢", "C": "🔵", "D": "🟡", "OTHER": "⚫"
        }

    # --- Report: teams ---
        if report_type == "teams":
            if df.empty or "team" not in df.columns:
                elements.append(Paragraph("Nessun dato disponibile per i teams.", styles["Normal"]))
            else:
                df["category"] = df["category"].fillna("OTHER").str.upper().str.strip()
                df = df.sort_values(by=["category", "team"])
                grouped = df.groupby("category")

                for cat, group in grouped:
                    emoji = emoji_map.get(cat, "⚫")
                    elements.append(Paragraph(f"{emoji} Categoria {cat}", styles["Heading4"]))

                    data = [["Team", "N. Riders", "Capitano"]]
                    for _, row in group.iterrows():
                        team_name = str(row.get("team") or "—")
                        n_riders = str(int(row.get("n_riders") or 0))
                        captain = str(row.get("captain") or "—")
                        data.append([team_name, n_riders, captain])

                    table = Table(data, colWidths=[250, 60, 180], hAlign="LEFT")
                    table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), color_map.get(cat, colors.HexColor("#f0f0f0"))),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 1),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                    ]))
                    elements.append(table)

                    total = int(group["n_riders"].fillna(0).sum())
                    elements.append(Paragraph(f"<i>Totale rider: {total}</i>", styles["Normal"]))
                    elements.append(Spacer(1, 6))



        # --- Report: Team Composition (ordinato per categoria) ---

        elif report_type == "team_composition":
            if df.empty or "team_name" not in df.columns:
                elements.append(Paragraph("Nessun dato disponibile.", styles["Normal"]))
            else:
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib.pagesizes import A4

                # Funzione per il piè di pagina
                def footer(canvas, doc):
                    canvas.saveState()
                    canvas.setFont("Helvetica", 8)
                    canvas.drawString(doc.leftMargin, 15, f"Pagina {doc.page}")
                    canvas.restoreState()

                # Mappa colori e emoji per categoria
                color_map = {
                    "A": colors.HexColor("#dc3545"),
                    "B": colors.HexColor("#28a745"),
                    "C": colors.HexColor("#17a2b8"),
                    "D": colors.HexColor("#ffc107"),
                    "OTHER": colors.HexColor("#6c757d")
                }
                emoji_map = {
                    "A": "🔴", "B": "🟢", "C": "🔵", "D": "🟡", "OTHER": "⚫"
                }

                # Normalizza e ordina
                category_order = {"A": 1, "B": 2, "C": 3, "D": 4, "OTHER": 5}
                df["category_clean"] = df["category"].fillna("OTHER").str.upper()
                df["category_order"] = df["category_clean"].map(lambda x: category_order.get(x, 99))
                df = df.sort_values(by=["category_order", "team_name", "rider_name"])

                # Costruzione blocchi team
                team_blocks = []
                ordered_teams = df["team_name"].drop_duplicates()

                for team in ordered_teams:
                    group = df[df["team_name"] == team]
                    riders = group.to_dict(orient="records")
                    cat = riders[0].get("category_clean", "OTHER") if riders else "OTHER"
                    header_color = color_map.get(cat, colors.HexColor("#6c757d"))
                    emoji = emoji_map.get(cat, "⚫")
                    captain = riders[0].get("captain", "")

                    # Titolo del team
                    title_text = f"<b>{emoji} {team}</b>"
                    if captain:
                        title_text += f" — Capitano: {captain}"
                    title = Paragraph(title_text, styles["Heading4"])
                    spacer = Spacer(1, 4)

                    # Tabella con intestazione + 12 righe
                    data = [["Rider", "Categoria"]]
                    for i in range(12):
                        if i < len(riders):
                            r = riders[i]
                            categoria = f"{emoji} {r.get('category','')}" if r.get("category") else ""
                            data.append([r.get("rider_name",""), categoria])
                        else:
                            data.append(["", ""])

                    table = Table(data, colWidths=[140, 60])
                    table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), header_color),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ]))

                    team_blocks.append([title, spacer, table, Spacer(1, 6)])

                # Impaginazione in griglia 2x2 per pagina
                elements = []

                # Titolo del report
                report_title = Paragraph("<b>Composizione Squadre</b>", styles["Title"])
                elements.append(report_title)
                elements.append(Spacer(1, 12))
                
                for i in range(0, len(team_blocks), 4):
                    page_blocks = team_blocks[i:i+4]
                    while len(page_blocks) < 4:
                        page_blocks.append([Spacer(1, 0)])  # riempi con vuoti

                    grid = [
                        [page_blocks[0], page_blocks[1]],
                        [page_blocks[2], page_blocks[3]]
                    ]
                    table = Table(grid, colWidths=[260, 260])
                    table.setStyle(TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]))
                    elements.append(table)
                    elements.append(Spacer(1, 12))

        # --- Report: Lineup ---
        elif report_type == "lineup":
            if df.empty:
                elements.append(Paragraph("Nessuna lineup disponibile.", styles["Normal"]))
            else:
                # Normalizza e ordina per categoria
                df["category"] = df["category"].fillna("OTHER").str.upper().str.strip()

                category_order = {"A": 1, "B": 2, "C": 3, "D": 4, "OTHER": 5}
                df["category_order"] = df["category"].map(lambda x: category_order.get(x, 99))
                df = df.sort_values(by=["category_order", "team", "rider"])

                # Mappa colori e emoji
                color_map = {
                    "A": colors.HexColor("#dc3545"),
                    "B": colors.HexColor("#28a745"),
                    "C": colors.HexColor("#17a2b8"),
                    "D": colors.HexColor("#ffc107"),
                    "OTHER": colors.HexColor("#6c757d")
                }
                emoji_map = {
                    "A": "🔴", "B": "🟢", "C": "🔵", "D": "🟡", "OTHER": "⚫"
                }

                # Costruisci blocchi per ogni team (ordinati per categoria)
                team_blocks = []

                # Normalizza e prepara colonna categoria
                df["category"] = df.get("category", "OTHER").fillna("OTHER").astype(str).str.upper().str.strip()

                # Mappa ordine categorie
                category_order = {"A": 1, "B": 2, "C": 3, "D": 4, "OTHER": 5}
                df["category_order"] = df["category"].map(lambda x: category_order.get(x, 99))

                # Ordina prima per categoria, poi per nome team e rider
                df = df.sort_values(by=["category_order", "team", "rider"], na_position="last")

                # Elenco team univoci ordinati per categoria
                ordered_teams = (
                    df[["team", "category", "category_order"]]
                    .drop_duplicates(subset=["team"])
                    .sort_values(by=["category_order", "team"])
                )

                for _, row in ordered_teams.iterrows():
                    team = row.get("team", "Senza Team")
                    cat = row.get("category", "OTHER")
                    header_color = color_map.get(cat, colors.HexColor("#6c757d"))
                    emoji = emoji_map.get(cat, "⚫")

                    # Titolo del team
                    title_text = f"<b>{emoji} {team}</b> <font size=8>(Cat. {cat})</font>"
                    title = Paragraph(title_text, styles["Heading4"])
                    spacer = Spacer(1, 3)

                    # Filtra i rider del team corrente
                    group = df[df["team"] == team]

                    # Tabella con intestazione + 6 righe
                    data = [["Rider", "Categoria", "Data Gara", "Capitano"]]
                    for _, r in group.head(6).iterrows():
                        data.append([
                            r.get("rider", "—"),
                            r.get("category", "—"),
                            r.get("race_date", "—"),
                            r.get("captain", "—")
                        ])


                    # Riempi con righe vuote fino a 6
                    while len(data) < 7:
                        data.append(["", "", ""])

                    # Tabella compatta per stare nel layout 2×2
                    table = Table(data, colWidths=[100, 40, 50, 60])
                    table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), header_color),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]))

                    team_blocks.append([title, spacer, table, Spacer(1, 6)])



                # Impaginazione 2×2 per pagina
                elements.append(Paragraph("<b>Lineup Team</b>", styles["Title"]))
                elements.append(Spacer(1, 12))

                for i in range(0, len(team_blocks), 4):
                    page_blocks = team_blocks[i:i+4]
                    while len(page_blocks) < 4:
                        page_blocks.append([Spacer(1, 0)])  # riempi spazi vuoti

                    grid = [
                        [page_blocks[0], page_blocks[1]],
                        [page_blocks[2], page_blocks[3]]
                    ]

                    grid_table = Table(grid, colWidths=[260, 260])
                    grid_table.setStyle(TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ]))
                    elements.append(grid_table)
                    elements.append(Spacer(1, 12))



# Costruzione PDF

        doc.build(elements, onFirstPage=footer, onLaterPages=footer)
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{report_type}.pdf",
            mimetype="application/pdf"
        )
    
# ------------------------
# EXPORT HTML
# ------------------------
    elif fmt == "html":
        from flask import render_template_string

        report_title = f"Report: {report_type}"

        # --------------------------
        # Report riders / teams semplice
        # --------------------------
        if report_type in ["riders", "riders_compact", "teams"]:
            html_table = df.to_html(
                index=False,
                classes="table table-striped table-bordered",
                border=0,
                justify="left",
                escape=False
            )
            html_full = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <title>{report_title}</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            </head>
            <body>
                <div class="container mt-4">
                    <h2>{report_title}</h2>
                    {html_table}
                </div>
            </body>
            </html>
            """

        # --------------------------
        # Report lineup / team_composition (layout 2x2)
        # --------------------------
        elif report_type in ["lineup", "team_composition"]:
            df["category"] = df.get("category", "OTHER").fillna("OTHER").str.upper()
            category_order = {"A": 1, "B": 2, "C": 3, "D": 4, "OTHER": 5}
            df["category_order"] = df["category"].map(lambda x: category_order.get(x, 99))

            team_col = "team_name" if "team_name" in df.columns else "team"
            rider_col = "rider_name" if "rider_name" in df.columns else "rider"
            df = df.sort_values(by=["category_order", team_col, rider_col])

            ordered_teams = df[[team_col, "category", "category_order"]].drop_duplicates(subset=[team_col])
            team_blocks = []

            for _, row in ordered_teams.iterrows():
                team = row[team_col]
                cat = row["category"]
                group = df[df[team_col] == team]

                # Numero di righe dinamico
                max_rows = 12 if report_type == "team_composition" else 6

                # Capitano (vale anche per lineup)
                captain = ""
                if "captain" in group.columns:
                    captain_value = group["captain"].dropna().unique()
                    if len(captain_value) > 0 and str(captain_value[0]).strip():
                        captain = f" 👑 Capitano: {captain_value[0]}"

                # Titolo HTML
                title_html = f"<h5>{team} (Cat. {cat}){captain}</h5>"

                # Tabella HTML
                table_data = [["Rider", "Categoria", "Data Gara"]]
                for _, r in group.head(max_rows).iterrows():
                    table_data.append([
                        r.get(rider_col, "—"),
                        r.get("category", "—"),
                        r.get("race_date", "—") if "race_date" in r else "—"
                    ])

                while len(table_data) < (max_rows + 1):
                    table_data.append(["", "", ""])

                html_table = "<table class='table table-sm table-bordered'><thead><tr>"
                for col in table_data[0]:
                    html_table += f"<th>{col}</th>"
                html_table += "</tr></thead><tbody>"
                for row_data in table_data[1:]:
                    html_table += "<tr>" + "".join(f"<td>{c}</td>" for c in row_data) + "</tr>"
                html_table += "</tbody></table>"

                team_blocks.append({
                    "team": team,
                    "category": cat,
                    "html_table": html_table,
                    "title_html": title_html
                })


            # Layout 2x2 per pagina
            html_blocks = ""
            for i in range(0, len(team_blocks), 4):
                page_teams = team_blocks[i:i+4]
                while len(page_teams) < 4:
                    page_teams.append({"team": "", "category": "", "html_table": ""})
                html_blocks += "<div class='row mb-3'>"
                for j in range(2):
                    html_blocks += "<div class='col-md-6'>"
                    for k in [j, j+2]:
                        tb = page_teams[k]
                        if tb["team"]:
                            html_blocks += tb["title_html"]
                            html_blocks += tb["html_table"]
                            html_blocks += "<hr>"
                    html_blocks += "</div>"
                html_blocks += "</div>"

            html_full = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <title>{report_title}</title>
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
            </head>
            <body>
                <div class="container mt-4">
                    <h2>{report_title}</h2>
                    {html_blocks}
                </div>
            </body>
            </html>
            """

        # --------------------------
        # Invio come file scaricabile
        # --------------------------
        buffer = io.BytesIO(html_full.encode("utf-8"))
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{report_type}.html",
            mimetype="text/html"
        )



    # ✅ Fuori dal blocco 'elif fmt == "pdf":'
    flash("Formato non supportato", "danger")
    return redirect("/admin/reports")
