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
    report_type = request.args.get("report_type", "riders_compact")
    category_filter = (request.args.get("category") or "").strip().upper()
    team_filter = (request.args.get("team") or "").strip()

    conn = get_db()
    # elenco categorie e teams per i select
    categories = [r["category"] for r in conn.execute(
        "SELECT DISTINCT category FROM riders WHERE active=1"
    ).fetchall()]
    teams_list = [r["name"] for r in conn.execute(
        "SELECT DISTINCT name FROM teams"
    ).fetchall()]

    rows, columns, lineup_per_team = [], [], {}
    race_date = None

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
        # riempi i valori nulli e cast a stringa
        for col in ["zwift_power_id", "name", "category", "teams"]:
            df[col] = df[col].fillna("").astype(str).str.strip()
        split_teams = df["teams"].str.split(",", n=1, expand=True)
        df["team1"] = split_teams[0].fillna("").str.strip()
        df["team2"] = split_teams[1].fillna("").str.strip() if 1 in split_teams.columns else ""
        df = df[["zwift_power_id", "name", "category", "team1", "team2"]]

        rows = df.to_dict(orient="records")
        columns = list(df.columns)

    elif report_type == "teams":
        query = """
            SELECT t.name AS team, t.category, COUNT(r.zwift_power_id) AS n_riders,
                   COALESCE(r2.name, '') AS captain
            FROM teams t
            LEFT JOIN rider_teams rt ON rt.team_id = t.id
            LEFT JOIN riders r ON r.zwift_power_id = rt.zwift_power_id AND r.active=1
            LEFT JOIN riders r2 ON r2.zwift_power_id = t.captain_zwift_id
            GROUP BY t.id
            ORDER BY t.category ASC, t.name ASC
        """
        rows = [dict(r) for r in conn.execute(query).fetchall()]
        columns = ["team", "category", "n_riders", "captain"]

    elif report_type == "lineup":
        query = """
            SELECT t.name AS team, r.name AS rider, TRIM(UPPER(r.category)) AS category, rl.race_date
            FROM race_lineup rl
            LEFT JOIN riders r ON r.zwift_power_id = rl.zwift_power_id AND r.active = 1
            LEFT JOIN teams t ON t.id = rl.team_id
            WHERE 1=1
        """
        params = []
        if category_filter:
            query += " AND TRIM(UPPER(r.category)) = ?"
            params.append(category_filter)
        query += " ORDER BY t.name, r.name"

        # Usa row_factory per avere dizionari coerenti
        conn.row_factory = sqlite3.Row
        rows_raw = conn.execute(query, params).fetchall()

        # Trasforma i Row in dizionari con nomi coerenti
        rows = []
        for r in rows_raw:
            rows.append({
                "team": r["team"] or "Senza Team",
                "rider": r["rider"] or "—",
                "category": r["category"] or "OTHER",
                "race_date": r["race_date"] or ""
            })

        # Raggruppa per team
        lineup_per_team = {}
        for r in rows:
            team = r["team"]
            lineup_per_team.setdefault(team, []).append({
                "rider": r["rider"],
                "category": r["category"],
                "race_date": r["race_date"]
            })

        # Format della data della gara (solo per visualizzazione)
        race_date = None
        if rows:
            first_date = rows[0]["race_date"]
            try:
                race_date = datetime.datetime.strptime(first_date, "%Y-%m-%d").strftime("%d %B %Y")
            except Exception:
                race_date = first_date

    # Debug (opzionale)
    # import pprint
    # pprint.pprint(lineup_per_team)


    elif report_type == "team_composition":
        query = """
            SELECT t.name AS team_name, r.name AS rider_name, TRIM(UPPER(r.category)) AS category
            FROM teams t
            LEFT JOIN rider_teams rt ON rt.team_id = t.id
            LEFT JOIN riders r 
                ON r.zwift_power_id = rt.zwift_power_id AND r.active = 1
            WHERE 1=1
        """
        params = []
        if category_filter:
            query += " AND TRIM(UPPER(r.category)) = ?"
            params.append(category_filter)
        if team_filter:
            query += " AND t.name = ?"
            params.append(team_filter)
        query += " ORDER BY t.name, r.name"

        rows = [dict(r) for r in conn.execute(query, params).fetchall()]

        # raggruppa per team
        lineup_per_team = {}
        for r in rows:
            team = r.get("team_name") or "Senza Team"
            r["rider_name"] = r.get("rider_name") or ""
            r["category"] = r.get("category") or "OTHER"
            lineup_per_team.setdefault(team, []).append(r)

    else:
        flash("Tipo di report non valido", "danger")
    
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
    category_filter = request.args.get("category", "").strip().upper()
    team_filter = request.args.get("team", "").strip()

    conn = get_db()
    df = pd.DataFrame()

    # --- Estrai dati dal DB ---
    if report_type in ["riders", "riders_compact"]:
        query = """
            SELECT 
                r.zwift_power_id,
                r.name,
                TRIM(UPPER(r.category)) AS category,
                GROUP_CONCAT(DISTINCT t.name) AS teams
            FROM riders r
            LEFT JOIN rider_teams rt ON rt.zwift_power_id = r.zwift_power_id
            LEFT JOIN teams t ON t.id = rt.team_id
            WHERE r.active = 1
        """
        params = []
        if category_filter:
            query += " AND TRIM(UPPER(r.category)) = ?"
            params.append(category_filter)
        query += " GROUP BY r.zwift_power_id, r.name, r.category ORDER BY r.name"
        df = pd.read_sql_query(query, conn, params=params)
        df["teams"] = df["teams"].fillna("").replace("None", "")
        split_teams = df["teams"].str.split(",", n=1, expand=True)
        df["team1"] = split_teams[0].fillna("").str.strip()
        df["team2"] = split_teams[1].fillna("").str.strip() if 1 in split_teams.columns else ""
        df = df[["zwift_power_id", "name", "category", "team1", "team2"]]

    elif report_type == "team_composition":
        query = """
            SELECT 
                t.name AS team_name,
                r.name AS rider_name,
                TRIM(UPPER(r.category)) AS category
            FROM teams t
            LEFT JOIN rider_teams rt ON rt.team_id = t.id
            LEFT JOIN riders r ON r.zwift_power_id = rt.zwift_power_id AND r.active = 1
            ORDER BY t.name, r.name
        """
        df = pd.read_sql_query(query, conn)
   

    elif report_type == "teams":
        query = """
            SELECT t.name AS team, t.category, COUNT(r.zwift_power_id) AS n_riders,
                   r2.name AS captain
            FROM teams t
            LEFT JOIN riders r ON r.team_id = t.id AND r.active=1
            LEFT JOIN riders r2 ON r2.zwift_power_id = t.captain_zwift_id
            GROUP BY t.id
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
        params = []
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
                TRIM(UPPER(r.category)) AS category
            FROM teams t
            LEFT JOIN rider_teams rt ON rt.team_id = t.id
            LEFT JOIN riders r 
                ON r.zwift_power_id = rt.zwift_power_id 
                AND r.active = 1
            WHERE 1=1
        """
        params = []
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

    conn.close()
    buffer = io.BytesIO()

    # --- CSV ---
    if fmt == "csv":
        df.to_csv(buffer, index=False, sep=";", encoding="utf-8")
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"{report_type}.csv", mimetype="text/csv")

    # --- XLSX ---
    elif fmt == "xlsx":
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Report")
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"{report_type}.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- PDF ---
    elif fmt == "pdf":
        def footer(canvas, doc):
            canvas.saveState()
            canvas.setFont("Helvetica", 6)
            canvas.drawString(doc.leftMargin, 15, f"Generato il {datetime.datetime.now():%d %B %Y %H:%M}")
            canvas.restoreState()

        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        elements = []

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

        if report_type == "lineup":
            race_date = None
            if not df.empty and "race_date" in df.columns:
                try:
                    race_date = datetime.datetime.strptime(df["race_date"].iloc[0], "%Y-%m-%d").strftime("%d %B %Y")
                except:
                    race_date = df["race_date"].iloc[0]

            title = f"Report Lineup"
            if race_date:
                title += f" – Gara del {race_date}"
            elements.append(Paragraph(title, styles["Title"]))
            elements.append(Spacer(1, 8))

            grouped = df.groupby("team")
            team_blocks = []

            for team, group in grouped:
                riders = group.to_dict(orient="records")
                cat = riders[0]["category"] if riders else "OTHER"
                header_color = color_map.get(cat, colors.HexColor("#6c757d"))
                emoji = emoji_map.get(cat, "⚫")

                team_title = Paragraph(f"<b>{team}</b>", styles["Heading4"])
                data = [["Rider", "Categoria"]]
                for i in range(6):
                    if i < len(riders):
                        r = riders[i]
                        categoria = f"{emoji} {r['category']}"
                        data.append([r["rider"], categoria])
                    else:
                        data.append(["", ""])

                table = Table(data, colWidths=[180, 100], hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), header_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ROWHEIGHT", (1, 0), (-1, -1), 18)
                ]))
                team_blocks.append([team_title, table])

            for i in range(0, len(team_blocks), 2):
                row = []
                for j in range(2):
                    if i + j < len(team_blocks):
                        row.append(team_blocks[i + j])
                    else:
                        row.append([Spacer(1, 0), Spacer(1, 0)])
                layout = Table([row], colWidths=[250, 250])
                layout.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6)
                ]))
                elements.append(layout)
                elements.append(Spacer(1, 6))

        elif report_type == "teams":
            elements.append(Paragraph("Report Teams", styles["Title"]))
            elements.append(Spacer(1, 6))

            df["category"] = df["category"].fillna("OTHER").str.upper().str.strip()
            df = df.sort_values(by=["category", "team"])
            grouped = df.groupby("category")

            for cat, group in grouped:
                emoji = emoji_map.get(cat, "⚫")
                elements.append(Paragraph(f"{emoji} Categoria {cat}", styles["Heading4"]))

                data = [["Team", "N. Riders", "Capitano"]]
                for _, row in group.iterrows():
                    data.append([
                        row["team"],
                        str(row["n_riders"]),
                        row["captain"] or ""
                    ])

                table = Table(data, colWidths=[250, 60, 180], hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]))
                elements.append(table)

                # Totale per categoria
                total = group["n_riders"].sum()
                elements.append(Paragraph(f"<i>Totale rider: {total}</i>", styles["Normal"]))
                elements.append(Spacer(1, 4))

        elif report_type == "team_composition":
            title = "Composizione Team"
            elements.append(Paragraph(f"📋 {title}", styles["Title"]))
            elements.append(Paragraph(f"Generato il {datetime.datetime.now():%d %B %Y %H:%M}", styles["Normal"]))
            elements.append(Spacer(1, 12))

            grouped = df.groupby("team_name")
            team_blocks = []

            for team, group in grouped:
                riders = group.to_dict(orient="records")
                cat = riders[0]["category"] if riders else "OTHER"
                header_color = color_map.get(cat, colors.HexColor("#6c757d"))
                emoji = emoji_map.get(cat, "⚫")

                team_title = Paragraph(f"<b>{team}</b>", styles["Heading4"])
                data = [["Rider", "Categoria"]]

        # 12 righe fisse
                for i in range(12):
                    if i < len(riders):
                        r = riders[i]
                        categoria = f"{emoji} {r['category']}" if r.get("category") else ""
                        data.append([r["rider_name"], categoria])
                    else:
                        data.append(["", ""])

                table = Table(data, colWidths=[200, 100], hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), header_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ROWHEIGHT", (1, 0), (-1, -1), 18),
                ]))
                team_blocks.append([team_title, table])

    # Tabelle 2 per riga
            for i in range(0, len(team_blocks), 2):
                row = []
                for j in range(2):
                    if i + j < len(team_blocks):
                        row.append(team_blocks[i + j])
                    else:
                        row.append([Spacer(1, 0), Spacer(1, 0)])
                layout = Table([[row[0], row[1]]], colWidths=[270, 270])
                layout.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6)
                ]))
                elements.append(layout)
                elements.append(Spacer(1, 12))
        

        else:
            # altri report PDF (riders)
            elements.append(Paragraph(f"Report {report_type}", styles["Title"]))
            elements.append(Spacer(1, 6))

            if not df.empty:
                table_data = [df.columns.tolist()] + df.values.tolist()
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#007BFF")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                elements.append(table)
            else:
                elements.append(Paragraph("Nessun dato disponibile.", styles["Normal"]))

        doc.build(elements, onFirstPage=footer, onLaterPages=footer)
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=f"{report_type}.pdf", mimetype="application/pdf")