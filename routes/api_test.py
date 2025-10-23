import requests
import json

url = "https://www.wtrl.racing/api/wtrlruby/"

headers = {
    "Authorization": "Bearer 1925b76d2c05c727a33ccf928d1ac72e",  # copia aggiornata dal cookie
    "Wtrl-Integrity": "VALORE_CSFR_TOKEN_DA_META",               # copia esatto da meta[name="csrf-token"]
    "wtrl-api-version": "2.7",
    "Origin": "https://www.wtrl.racing",
    "Referer": "https://www.wtrl.racing/zwift-racing-league/results/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
}

data = {
    "action": "results",
    "wtrlid": "zrl",
    "season": "17",
    "race": "1",
    "category": "C",
    "gender": "M",
}

response = requests.post(url, headers=headers, data=data)

print("Status:", response.status_code)
print("Response text:\n", response.text[:800])
