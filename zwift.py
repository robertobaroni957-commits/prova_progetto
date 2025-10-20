import sqlite3
import time
import urllib.parse as up
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# === CONFIGURAZIONE ===
DB_FILE = "zwift.db"
TEAM_URL = "https://zwiftpower.com/team.php?id=16461"

# === CONNESSIONE AL DATABASE ===
conn = sqlite3.connect(DB_FILE)
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()

# === CANCELLA CONTENUTO E AZZERA AUTOINCREMENTO ===
print("🧹 Pulizia tabella 'riders'...")
cur.execute("DELETE FROM riders")
cur.execute("DELETE FROM sqlite_sequence WHERE name='riders'")
conn.commit()

# === AVVIO CHROME ===
print("🌐 Apertura Chrome per login manuale...")
options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(TEAM_URL)

input("➡️ Fai login manuale nella finestra Chrome, poi premi INVIO qui per iniziare lo scraping...")

# === SCRAPING ===
members = []
page_number = 1
previous_html = ""

while True:
    print(f"⏳ Pagina {page_number}...")
    try:
        table_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "team_riders"))
        )
    except:
        print("❌ Tabella 'team_riders' non trovata.")
        break

    html = table_element.get_attribute("outerHTML")
    if html == previous_html:
        print("✅ Nessuna nuova riga, fine.")
        break
    previous_html = html

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table#team_riders tbody tr")

    print(f"🔍 Trovate {len(rows)} righe.")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        category = cols[0].get_text(strip=True)
        rank = cols[1].get_text(strip=True)
        name = cols[2].get_text(strip=True)
        profile_tag = cols[2].find("a")
        profile_url = profile_tag["href"] if profile_tag else ""
        zwift_id = None

        if profile_url:
            match = re.search(r"[?&](z|user|m)=(\d+)", profile_url)
            zwift_id = match.group(2) if match else None

        print(f"👤 {name} | ID: {zwift_id} | Cat: {category}")
        if name and zwift_id:
            members.append({
                "zwift_power_id": zwift_id,
                "name": name,
                "category": category
            })

    try:
        next_btn = driver.find_element(By.LINK_TEXT, "Next")
        next_btn.click()
        time.sleep(2)
        page_number += 1
    except:
        print("❌ Nessun pulsante 'Next' trovato.")
        break

driver.quit()

# === SALVATAGGIO NEL DATABASE ===
print(f"💾 Salvataggio di {len(members)} rider...")
for rider in members:
    cur.execute("""
        INSERT INTO riders (zwift_power_id, name, category)
        VALUES (?, ?, ?)
        ON CONFLICT(zwift_power_id) DO UPDATE SET
            name = excluded.name,
            category = excluded.category
    """, (
        rider["zwift_power_id"],
        rider["name"],
        rider["category"]
    ))
    conn.commit()

conn.close()
print(f"✅ Scraping completato. {len(members)} rider salvati in zwift.db")