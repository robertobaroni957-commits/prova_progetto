import logging
import requests
from datetime import datetime

# -------------------------------
# Configurazione logging
# -------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# -------------------------------
# Cookie e token dal browser
# -------------------------------
WTRL_SID = "df7064bdb4364452c5b9b90d309aff3f"
WTRL_OUID = "eyJpYXQiOjE3NTk4MTYxMDQsImVhdCI6MTc2MjQwODEwNCwicHJvZmlsZV9waWMiOiJodHRwczpcL1wvd3d3Lnd0cmwucmFjaW5nXC91cGxvYWRzXC9wcm9maWxlX3BpY3R1cmVcLzE2NDExOTc0NTZfYmVsbGEtdGFydGFydWdhLXN1bGxhLWJpY2ktYWRlc2l2by5qcGciLCJmaXJzdF9uYW1lIjoiUm9iZXJ0byIsImxhc3RfbmFtZSI6IkJhcm9uaSIsImVtYWlsIjoicm9iZXJ0by5iYXJvbmlAbGliZXJvLml0IiwidXNlckNsYXNzIjoiMSIsInp3aWZ0SWQiOiIyOTc1MzYxIiwidXVpZCI6ImM2ZWU4NThiLWRjMGMtNDFiNi04M2JjLThjMzRlNWE0OTQ3MCIsInVzZXJJZCI6IjQ0Nzg1IiwiY291bnRyeV9pZCI6IjM4MCIsImdlbmRlciI6Ik1hbGUiLCJyYWNlVGVhbSI6IjAifQ==.df7064bdb4364452c5b9b90d309aff3f"
CSRF_TOKEN = "442cc944b46c4d18e13b0024fe2ad0bd109f1790294b0200aafeee317aab52bb9c515d"

# -------------------------------
# Funzioni di scraping
# -------------------------------
def fetch_zrl_seasons():
    """
    Recupera le stagioni ZRL tramite API WTRL.
    """
    url = "https://www.wtrl.racing/api/wtrlruby/"
    payload = {"wtrl": '[{"action":"zrlSeasons"}]'}  # deve essere stringa JSON
    headers = {
        "Authorization": f"Bearer {WTRL_SID}",
        "Wtrl-Integrity": CSRF_TOKEN,
        "wtrl-api-version": "2.7",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Cookie": f"wtrl_sid={WTRL_SID}; wtrl_ouid={WTRL_OUID}"
    }

    try:
        response = requests.get(url, params=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("payload") or data.get("wtrl")
    except requests.HTTPError as e:
        logger.error(f"❌ Errore nella richiesta: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Errore imprevisto: {e}")
        return None


def import_rounds():
    """
    Recupera stagioni e round e li stampa.
    Qui puoi inserire la logica per salvare i dati nel database zrl_db.
    """
    logger.info("🚀 Inizio importazione round ZRL")
    seasons = fetch_zrl_seasons()

    if not seasons:
        logger.warning("⚠️ Nessuna stagione trovata o formato errato")
        return

    logger.info(f"🌐 Recupero stagioni ZRL…")
    for season in seasons:
        season_name = season.get("name", "Unknown")
        season_id = season.get("id", 0)
        logger.info(f"➡️ Stagione: {season_name} ({season_id})")

        rounds = season.get("rounds", [])
        logger.info(f"   🔹 Trovati {len(rounds)} round")

        for rnd in rounds:
            if rnd is None:
                logger.warning("⚠️ Round None trovato")
                continue
            round_name = rnd.get("name", "Unknown")
            round_date = rnd.get("date", "Unknown")
            logger.info(f"      • Round: {round_name} ({round_date})")

            # TODO: qui inserisci la logica per inserire i round nel database
            # esempio:
            # db.insert_round(season_id, round_name, round_date)


if __name__ == "__main__":
    import_rounds()
