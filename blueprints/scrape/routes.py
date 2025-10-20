from flask import Blueprint, redirect, url_for, session, flash
import sqlite3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import datetime

scrape_bp = Blueprint("scrape", __name__)

@scrape_bp.route("/scrape")
def scrape():
    # Controllo admin
    if session.get("user_role") != "admin":
        flash("⛔ Accesso riservato agli admin", "danger")
        return redirect(url_for("auth.login_admin"))

    url = "https://zwiftpower.com/team.php?id=16461"
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)
    driver = webdriver.Chrome(options=options)

    driver.get(url)
    input("➡️ Fai login su ZwiftPower, poi premi INVIO qui nella console...")

    # Funzioni di sicurezza
    def safe_float(value):
        try:
            cleaned = re.sub(r"[^\d.]", "", value)
            return float(cleaned) if cleaned else None
        except:
            return None

    def safe_int(value):
        try:
            cleaned = re.sub(r"[^\d]", "", value)
            return int(cleaned) if cleaned else None
        except:
            return None

    def safe_text(value):
        return value.strip() if value else None

    # Connessione al database zwift.db
    db = sqlite3.connect("zwift.db")
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    zwift_ids_scraped = set()
    riders_imported = 0

    try:
        while True:
            table = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "team_riders"))
            )
            rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # salto header

            if not rows:
                break

            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 12:
                    continue

                name_link = cols[2].find_element(By.TAG_NAME, "a")
                name = safe_text(name_link.text)
                profile_url = name_link.get_attribute("href")
                zwift_power_id = safe_text(profile_url.split("=")[-1])
                zwift_ids_scraped.add(zwift_power_id)

                category = safe_text(cols[0].text)
                ranking = safe_float(cols[1].text)
                wkg_20min = safe_float(cols[3].text)
                watt_20min = safe_float(cols[4].text)
                wkg_15sec = safe_float(cols[5].text)
                watt_15sec = safe_float(cols[6].text)
                status = safe_text(cols[7].text)
                races = safe_int(cols[8].text)
                weight = safe_float(cols[9].text)
                ftp = safe_float(cols[10].text)
                age = safe_int(cols[11].text)

                cur.execute("""
                    INSERT OR REPLACE INTO zwift_power_riders (
                        zwift_power_id, name, category, ranking,
                        wkg_20min, watt_20min, wkg_15sec, watt_15sec,
                        status, races, weight, ftp, age
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    zwift_power_id, name, category, ranking, wkg_20min, watt_20min,
                    wkg_15sec, watt_15sec, status, races, weight, ftp, age
                ))
                riders_imported += 1

            # Pagina successiva
            try:
                next_li = driver.find_element(By.XPATH, "//li[contains(@class, 'paginate_button') and .//a[text()='Next']]")
                if "disabled" in next_li.get_attribute("class"):
                    break
                next_a = next_li.find_element(By.TAG_NAME, "a")
                driver.execute_script("arguments[0].click();", next_a)
                time.sleep(2)
            except:
                break

        # Rimuove i rider non più presenti
        if zwift_ids_scraped:
            placeholders = ",".join(["?"]*len(zwift_ids_scraped))
            cur.execute(f"DELETE FROM zwift_power_riders WHERE zwift_power_id NOT IN ({placeholders})", list(zwift_ids_scraped))

        db.commit()
        flash(f"✅ Importati {riders_imported} corridori in zwift_power_riders", "success")

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"⛔ Errore durante lo scraping: {str(e)}", "danger")

    finally:
        driver.quit()
        db.close()

    return redirect(url_for("admin_import_riders.import_zrl_riders"))
