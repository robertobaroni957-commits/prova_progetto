def get_or_create_season(cursor, name, start_year, end_year):
    """
    Crea una stagione se non esiste già nel database.
    Restituisce l'ID della stagione esistente o appena creata.
    """
    cursor.execute("""
        SELECT id FROM seasons
        WHERE name = ? AND start_year = ? AND end_year = ?
    """, (name, start_year, end_year))
    season = cursor.fetchone()

    if season:
        return season["id"]

    cursor.execute("""
        INSERT INTO seasons (name, start_year, end_year)
        VALUES (?, ?, ?)
    """, (name, start_year, end_year))

    return cursor.lastrowid