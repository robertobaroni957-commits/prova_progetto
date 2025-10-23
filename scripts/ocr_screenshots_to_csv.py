# ocr_screenshots_to_csv.py
import os, re, json
from PIL import Image, ImageFilter, ImageOps
import pytesseract
import pandas as pd
from datetime import datetime

# CONFIG
TESSERACT_CMD = r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR = r"C:\Program Files (x86)\Tesseract-OCR"
SCREENSHOT_DIR = r"C:\Progetti\gestioneZRL\screenshots"
OUTPUT_CSV = r"C:\Progetti\gestioneZRL\data\ocr_results.csv"
DEBUG_TEXT_DIR = r"C:\Progetti\gestioneZRL\data\ocr_debug"

# Impostazioni Tesseract
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
os.environ["TESSDATA_PREFIX"] = TESSDATA_DIR

os.makedirs(DEBUG_TEXT_DIR, exist_ok=True)


# Colonne attese nella tabella Race Result (ordine idealizzato)
EXPECTED_COLS = ["Rank","Team","Riders","FAL","FTS","FIN","PBT","Time","Gap","AVGW","CPW","POINTS"]

def preprocess_image(im):
    # Converti in grayscale e aumenta contrasto leggendo bene le tabelle
    im = im.convert("L")
    im = ImageOps.autocontrast(im)
    im = im.filter(ImageFilter.MedianFilter(3))
    # ridimensiona per migliorare l'OCR (opzionale)
    w,h = im.size
    if w < 1600:
        im = im.resize((int(w*1.6), int(h*1.6)), Image.LANCZOS)
    return im

def parse_table_text(text):
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 3]
    rows = []

    for ln in lines:
        # ignora righe di titolo
        if re.search(r'(team|points|rank)', ln, re.IGNORECASE):
            continue

        # sostituisci caratteri comuni OCR
        ln = ln.replace('|', '1').replace('l', '1').replace('I ', '1 ').replace('Â', '')

        # trova il nome del team (la prima sequenza di lettere lunghe)
        team_match = re.search(r'[A-Z]{3,}[\w\s\-]*', ln)
        team = team_match.group(0).strip() if team_match else ""

        # rank = primo numero all’inizio
        rank_match = re.match(r'^\d+', ln)
        rank = rank_match.group(0) if rank_match else ""

        rows.append({
            "Rank": rank,
            "Team": team,
            "_raw": ln
        })
    return rows


def process_all():
    all_rows = []
    files = sorted([f for f in os.listdir(SCREENSHOT_DIR) if f.lower().endswith((".png",".jpg",".jpeg"))])
    if not files:
        print("Nessuno screenshot in", SCREENSHOT_DIR)
        return
    for fn in files:
        fp = os.path.join(SCREENSHOT_DIR, fn)
        print("OCR:", fn)
        im = Image.open(fp)
        im = preprocess_image(im)
        # prova OCR impostando psm e oem
        custom_config = r'--oem 3 --psm 6'  # psm 6: assume un blocco uniforme di testo
        text = pytesseract.image_to_string(im, config=custom_config, lang='eng')
        debug_txt_path = os.path.join(DEBUG_TEXT_DIR, fn + ".txt")
        with open(debug_txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        rows = parse_table_text(text)
        # arricchisci con metadata
        for r in rows:
            r["_screenshot"] = fn
            from datetime import datetime, timezone
            r["_extracted_at"] = datetime.now(timezone.utc).isoformat()

        all_rows.extend(rows)

        import re

def clean_ocr_text(df):
    """
    Pulisce i testi OCR e normalizza i valori nel DataFrame.
    """
    def clean_text(text):
        if not isinstance(text, str):
            return text
        # Caratteri tipici dell'OCR che vanno rimossi o corretti
        replacements = {
            'â€™': "'", 'â€˜': "'", 'â€œ': '"', 'â€': '"', 'Â': '',
            'Ã©': 'é', 'Ã': 'à', '€': 'e', '™': '', '‚': ',',
            '|': ' ', '•': '-', '–': '-', '—': '-',
            '…': '...', '°': 'o', '’': "'", '‘': "'"
        }
        for bad, good in replacements.items():
            text = text.replace(bad, good)

        # Rimuove doppie spaziature e caratteri di controllo
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^A-Za-z0-9\s\-\':,.;()%/]', '', text)

        # Normalizza separatori numerici
        text = text.replace(' I ', ' 1 ')
        text = re.sub(r'(?<=\d)[lI](?=\d)', '1', text)  # I → 1 tra numeri

        return text.strip()

    # Applica la pulizia a tutte le colonne testuali
    for col in df.columns:
        df[col] = df[col].apply(clean_text)

    # Prova a estrarre numeri di rank più puliti
    if 'Rank' in df.columns:
        df['Rank'] = df['Rank'].str.extract(r'(\d+)')

    # Elimina righe completamente vuote
    df = df.dropna(how='all')

    return df


    # salva in CSV con pandas (salva tutti i campi trovati)
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
        print("Salvato CSV:", OUTPUT_CSV)
    else:
        print("Nessun dato estratto.")

if __name__ == "__main__":
    process_all()
