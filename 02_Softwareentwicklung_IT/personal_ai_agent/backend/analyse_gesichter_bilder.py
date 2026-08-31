"""Analysiert Kandidaten-Bilder aus uploads/ per Vision-LLM (fuer Gesichter-Lern-Spiel).

Sendet jedes Bild als data_url an einen Vision-LLM (Gemini) und fragt eine
KOMPAKTE, strukturierte Beschreibung ab: Anzahl Personen, Positionen (links/
rechts/vorne/hinten), und kurze personenbezogene Merkmale (Geschlecht, etwaiges
Alter, Brille, Haar). NICHT nach Namen fragen (Agent kann sie nicht wissen),
nur nach beschreibenden Merkmalen, damit Sebastian die Dateien sicher zuordnet.
"""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services import llm_service  # noqa: E402

MODEL = "google/gemini-2.5-flash"
BASE = "/data/data/com.termux/files/home/it-ot-agentic-engineering/02_Softwareentwicklung_IT/personal_ai_agent/"
KANDIDATEN = [
    "uploads/8b102eb2e7f4.jpg",   # 22:58  (Gruppenbild?)
    "uploads/5305de8b69d7.jpg",   # 23:02
    "uploads/065e8490a052.jpg",   # 23:06
    "uploads/7afaa721e715.jpg",   # 23:10
]

PROMPT = (
    "Beschreibe die Personen auf diesem Foto KOMPAKT und FAKTENBASIERT, in "
    "einer Zeile pro Person. Antworte im Format:\n"
    "ANZAHL: <n>\n"
    "1. <Position im Bild, z.B. links/rechts/vorne/hinten>: <Geschlecht, "
    "geschätztes Alter in Jahren, Brille?, Haarfarbe/Frisur, auffällige "
    "Merkmale>\n"
    "...\n"
    "Wenn keine Person drauf ist: 'ANZAHL: 0'.\n"
    "Keine Namen erfinden, keine Spekulation."
)


def _bild_data_url(pfad: str) -> str:
    roh = open(pfad, "rb").read()
    return "data:image/jpeg;base64," + base64.b64encode(roh).decode("ascii")


def main():
    svc = llm_service.LLMService()
    if svc.client is None:
        print("Kein OpenRouter-Client (Key fehlt)")
        return
    for rel in KANDIDATEN:
        pfad = BASE + rel
        if not os.path.exists(pfad):
            continue
        try:
            data_url = _bild_data_url(pfad)
            r = svc.client.chat.completions.create(
                model=MODEL,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }],
                temperature=0.0,
                max_tokens=400,
            )
            txt = r.choices[0].message.content or "(leer)"
            print(f"\n### {os.path.basename(rel)}")
            print(txt.strip())
        except Exception as e:
            print(f"\n### {os.path.basename(rel)} FEHLER: {e}")


if __name__ == "__main__":
    main()