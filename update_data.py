#!/usr/bin/env python3
import os
import sqlite3
import pandas as pd
import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime

# === CONFIGURAZIONE ===
DB_FILE = "zwift.db"
TEAM_URL = "https://zwiftpower.com/team.php?id=16461"
REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# === FUNZIONI DI PARSING ===
def parse_float(value):
    try:
        cleaned = re.sub(r"[^\d.]", "", value)
        return float(cleaned) if cleaned else 0.0
    except:
        return 0.0

def parse_int(value):
    try:
        cleaned = re.sub(r"[^\d]", "", value)
        return int(cleaned) if cleaned else 0
    except:
        return 0

# === FUNZIONE DI SCRAPING ===
def scrape_team():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # options.add_argument("--headless=new")  # opzionale

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(TEAM_URL)
    input("➡️ Fai login manuale nella finestra Chrome, poi premi INVIO qui per iniziare lo scraping...")

    members = []
    page_number = 1
    previous_html = ""

    while True:
        print(f"⏳ Pagina {page_number}...")
        try:
            table_element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "team_riders"))
            )
        except Exception as e:
            print("❌ Tabella 'team_riders' non trovata.", e)
            break

        html = table_element.get_attribute("outerHTML")
        if html == previous_html:
            print("✅ Nessuna nuova riga, fine.")
            break
        previous_html = html

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table#team_riders tbody tr")
        print(f"🔍 Trovate {len(rows)} righe.")

        for idx, row in enumerate(rows):
            cols = row.find_all("td")
            if len(cols) < 12:
                continue

            # Categoria (colonna 0)
            category = cols[0].get_text(strip=True)

            # Rank (colonna 1)
            ranking = parse_float(cols[1].get_text(strip=True))

            # Colonna nome (colonna 2)
            name_col_element = driver.find_elements(By.CSS_SELECTOR, "table#team_riders tbody tr")[idx].find_elements(By.TAG_NAME, "td")[2]
            name_html = name_col_element.get_attribute("innerHTML")
            name = name_col_element.text.strip()

            # Profilo ZwiftPower
            profile_tag = name_col_element.find_element(By.TAG_NAME, "a") if name_col_element.find_elements(By.TAG_NAME, "a") else None
            profile_url = profile_tag.get_attribute("href") if profile_tag else ""
            zwift_id = None
            if profile_url:
                match = re.search(r"[?&](z|user|m)=(\d+)", profile_url)
                zwift_id = match.group(2) if match else None

            # Estrazione country dal <span class="flag-icon flag-icon-xx">
            country = ""
            match = re.search(r'flag-icon-([a-z]{2})', name_html)
            if match:
                country = match.group(1).upper()  # IT, US, FR, ecc.

            # Altri valori
            wkg_20min = parse_float(cols[3].get_text(strip=True))
            watt_20min = parse_float(cols[4].get_text(strip=True))
            wkg_15sec = parse_float(cols[5].get_text(strip=True))
            watt_15sec = parse_float(cols[6].get_text(strip=True))
            status = cols[7].get_text(strip=True)
            races = parse_int(cols[8].get_text(strip=True))
            weight = parse_float(cols[9].get_text(strip=True))
            ftp = parse_float(cols[10].get_text(strip=True))
            age = parse_int(cols[11].get_text(strip=True))

            if zwift_id:
                members.append({
                    "zwift_power_id": zwift_id,
                    "name": name,
                    "category": category,
                    "ranking": ranking,
                    "wkg_20min": wkg_20min,
                    "watt_20min": watt_20min,
                    "wkg_15sec": wkg_15sec,
                    "watt_15sec": watt_15sec,
                    "status": status,
                    "races": races,
                    "weight": weight,
                    "ftp": ftp,
                    "age": age,
                    "country": country
                })

        # Pagina successiva
        try:
            next_btn = driver.find_element(By.LINK_TEXT, "Next")
            next_btn.click()
            time.sleep(2)
            page_number += 1
        except Exception as e:
            print("❌ Nessun pulsante 'Next' trovato.", e)
            break

    driver.quit()
    return members

# === SALVATAGGIO SU DB ===
def save_to_db(members):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # Crea tabella aggiornata
    cur.execute("""
    CREATE TABLE IF NOT EXISTS zwift_power_riders (
        zwift_power_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        ranking REAL,
        wkg_20min REAL,
        watt_20min REAL,
        wkg_15sec REAL,
        watt_15sec REAL,
        status TEXT,
        races INTEGER,
        weight REAL,
        ftp REAL,
        age INTEGER,
        country TEXT
    )
    """)

    # Pulizia tabella
    print("🧹 Pulizia tabella 'zwift_power_riders'...")
    cur.execute("DELETE FROM zwift_power_riders")
    cur.execute("DELETE FROM sqlite_sequence WHERE name='zwift_power_riders'")
    conn.commit()

    # Inserimento dati
    values = [(r["zwift_power_id"], r["name"], r["category"], r["ranking"],
               r["wkg_20min"], r["watt_20min"], r["wkg_15sec"], r["watt_15sec"],
               r["status"], r["races"], r["weight"], r["ftp"], r["age"], r["country"])
              for r in members]

    cur.executemany("""
    INSERT INTO zwift_power_riders (
        zwift_power_id, name, category, ranking, wkg_20min, watt_20min,
        wkg_15sec, watt_15sec, status, races, weight, ftp, age, country
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(zwift_power_id) DO UPDATE SET
        name = excluded.name,
        category = excluded.category,
        ranking = excluded.ranking,
        wkg_20min = excluded.wkg_20min,
        watt_20min = excluded.watt_20min,
        wkg_15sec = excluded.wkg_15sec,
        watt_15sec = excluded.watt_15sec,
        status = excluded.status,
        races = excluded.races,
        weight = excluded.weight,
        ftp = excluded.ftp,
        age = excluded.age,
        country = excluded.country
    """, values)

    conn.commit()
    conn.close()
    print(f"✅ Salvati {len(members)} record nella tabella 'zwift_power_riders'")

# === ESPORTAZIONE FILE ===
def export_files(members):
    df = pd.DataFrame(members)
    csv_path = os.path.join(REPO_DIR, "riders.csv")
    json_path = os.path.join(REPO_DIR, "riders.json")
    df.to_csv(csv_path, index=False)
    df.to_json(json_path, orient="records", indent=2)
    print(f"📤 File esportati: {csv_path}, {json_path}")

# === MAIN ===
def main():
    print("🚀 Avvio scraping")
    members = scrape_team()
    print(f"🔢 Totale membri trovati: {len(members)}")
    save_to_db(members)
    export_files(members)
    print("🎉 Fine.")

if __name__ == "__main__":
    main()
