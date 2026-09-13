import os
import json
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

URL = "https://www.arbeitnow.com/api/job-board-api"
STICHWOERTER = ["python", "developer", "entwickler", "junior", "software"]
SEEN_DATEI = Path("seen.json")
LOG_DATEI = Path("watcher.log")

# --- Logging einrichten: schreibt in Datei UND in die Konsole ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DATEI, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def sende_telegram(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    antwort = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=10)
    antwort.raise_for_status()   # wirft einen Fehler, falls Telegram nicht 200 liefert


def lade_gesehene():
    if SEEN_DATEI.exists():
        with open(SEEN_DATEI, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return None


def speichere_gesehene(slugs):
    with open(SEEN_DATEI, "w", encoding="utf-8") as f:
        json.dump(sorted(slugs), f, indent=2)


def hole_treffer():
    antwort = requests.get(URL, timeout=10)
    antwort.raise_for_status()
    jobs = antwort.json()["data"]
    treffer = []
    for job in jobs:
        titel = job["title"].lower()
        if job["remote"] and any(w in titel for w in STICHWOERTER):
            treffer.append(job)
    return treffer


def main():
    logging.info("Wächter gestartet.")

    # Sicherheits-Check: sind die Zugangsdaten da?
    if not TOKEN or not CHAT_ID:
        logging.error("TELEGRAM_TOKEN oder TELEGRAM_CHAT_ID fehlt in der .env. Abbruch.")
        return

    # Jobs holen - abgesichert
    try:
        treffer = hole_treffer()
    except requests.RequestException as e:
        logging.error("Fehler beim Abrufen der API: %s", e)
        return   # sauber beenden, nicht abstürzen

    logging.info("%d passende Jobs gefunden.", len(treffer))

    aktuelle_slugs = {job["slug"] for job in treffer}
    gesehene = lade_gesehene()

    if gesehene is None:
        speichere_gesehene(aktuelle_slugs)
        logging.info("Erster Lauf: %d Jobs still gespeichert, keine Meldung.", len(aktuelle_slugs))
        return

    neue = [job for job in treffer if job["slug"] not in gesehene]

    if not neue:
        logging.info("Nichts Neues.")
    else:
        logging.info("%d neue Jobs -> sende an Telegram.", len(neue))
        for job in neue:
            nachricht = f"🔔 Neuer Job:\n{job['title']}\n{job['company_name']}\n{job['url']}"
            try:
                sende_telegram(nachricht)
                logging.info("Gesendet: %s", job["slug"])
            except requests.RequestException as e:
                logging.error("Konnte '%s' nicht senden: %s", job["slug"], e)

    speichere_gesehene(gesehene | aktuelle_slugs)
    logging.info("Wächter beendet.")


if __name__ == "__main__":
    main()