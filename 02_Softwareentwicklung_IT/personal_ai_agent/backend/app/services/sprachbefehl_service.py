"""
Sprachbefehl-Service: Erkennt und strukturiert gesprochene App-Aktionen.

Erlaubt natuerliche Sprachsteuerung fuer:
- Navigation: Quiz oeffnen, Erzaehlmodus oeffnen, Chat oeffnen
- Blaettern: X Seiten/Bilder vorwaerts oder zurueck (mit Ziffern und Zahlwoertern)
- Event- & Bild-Auswahl: oberstes Event oeffnen, erstes Bild anzeigen
- Aktionen: Notiz hinzufuegen, Bildgeschichte generieren, Gruppen neu vorsortieren, speichern
- Mehrschritt-Befehle: Verknuepfung mit 'und' (z. B. 'oberstes Event oeffnen und erstes Bild zeigen')
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


ZAHLWOERTER: Dict[str, int] = {
    "eins": 1, "eine": 1, "einen": 1, "einem": 1, "einer": 1, "ein": 1,
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "fuenf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "elf": 11, "zwölf": 12, "zwoelf": 12, "dreizehn": 13, "vierzehn": 14,
    "fünfzehn": 15, "sechzehn": 16, "siebzehn": 17, "achtzehn": 18,
    "neunzehn": 19, "zwanzig": 20,
}

ORDINAL_WOERTER: Dict[str, int] = {
    "erste": 0, "erstes": 0, "ersten": 0, "erster": 0,
    "oberste": 0, "oberstes": 0, "obersten": 0, "oberster": 0,
    "neueste": 0, "neuestes": 0, "neuesten": 0, "neuester": 0,
    "zweite": 1, "zweites": 1, "zweiten": 1, "zweiter": 1,
    "dritte": 2, "drittes": 2, "dritten": 2, "dritter": 2,
    "vierte": 3, "viertes": 3, "vierten": 3, "vierter": 3,
    "fünfte": 4, "fuenfte": 4, "fünften": 4, "fuenften": 4,
    "letzte": -1, "letztes": -1, "letzten": -1, "letzter": -1,
}


def _extrahiere_zahl(text: str, standard: int = 1) -> int:
    """Findet eine Ziffer oder ein Zahlwort im Text."""
    # Ziffern suchen
    m = re.search(r"\b(\d+)\b", text)
    if m:
        try:
            return max(1, int(m.group(1)))
        except ValueError:
            pass
    # Zahlwoerter suchen
    for wort, wert in ZAHLWOERTER.items():
        if re.search(rf"\b{wort}\b", text, re.IGNORECASE):
            return wert
    return standard


def _extrahiere_ordinal(text: str, standard: int = 0) -> int:
    """Findet ein Ordinalwort oder eine Ordinalzahl (1., 2., etc.)."""
    m = re.search(r"\b(\d+)\.", text)
    if m:
        try:
            return max(0, int(m.group(1)) - 1)
        except ValueError:
            pass
    for wort, wert in ORDINAL_WOERTER.items():
        if re.search(rf"\b{wort}\b", text, re.IGNORECASE):
            return wert
    return standard


def _analysiere_einzelbefehl(segment: str) -> Optional[Dict[str, Any]]:
    """Prueft ein einzelnes Textsegment auf einen bekannten App-Befehl."""
    s = segment.strip().lower()
    if not s:
        return None

    # 1. Navigation: Quiz
    if re.search(r"\b(öffne|gehe\s+in(s)?|zeige)\s+.*(quiz|gruppen(-quiz)?)", s) or re.search(r"^(das\s+)?quiz(\s+öffnen)?$", s):
        return {
            "aktion": "quiz_oeffnen",
            "parameter": {},
            "antwort": "Öffne Gruppen-Quiz",
        }

    # 2. Navigation: Erzaehlmodus / Diashow
    if re.search(r"\b(öffne|gehe\s+in(s)?|zeige)\s+.*(erzähl(en|modus)?|diashow|ereignisse)", s) or re.search(r"^(den\s+)?erzählmodus(\s+öffnen)?$", s):
        return {
            "aktion": "erzaehlen_oeffnen",
            "parameter": {},
            "antwort": "Öffne Erzählmodus",
        }

    # 3. Navigation: Chat / Zurueck
    if re.search(r"\b(öffne|gehe\s+zum|zurück\s+zum)\s+chat\b", s) or re.search(r"\b(schließe|verlasse)\s+.*(erzähl(en|modus)?|quiz)\b", s):
        return {
            "aktion": "chat_oeffnen",
            "parameter": {},
            "antwort": "Zurück zum Chat",
        }

    # 4. Blaettern: X Seiten / Bilder vorwaerts oder zurueck
    # Zurueck
    if re.search(r"\b(zurück|vorheriges|rückwärts)\b", s):
        anzahl = _extrahiere_zahl(s, standard=1)
        return {
            "aktion": "blaettern",
            "parameter": {"richtung": "zurueck", "anzahl": anzahl},
            "antwort": f"Blättere {anzahl} Bild{'er' if anzahl > 1 else ''} zurück",
        }
    # Vorwaerts
    if re.search(r"\b(weiter|nächstes|vorwärts|vor)\b", s):
        anzahl = _extrahiere_zahl(s, standard=1)
        return {
            "aktion": "blaettern",
            "parameter": {"richtung": "vor", "anzahl": anzahl},
            "antwort": f"Blättere {anzahl} Bild{'er' if anzahl > 1 else ''} vor",
        }

    # 5. Event oeffnen: "oberstes Event", "obersten Anlass", "erstes Ereignis"
    if re.search(r"\b(event|anlass|ereignis)\b", s):
        if re.search(r"\b(öffne|zeig(e)?|gehe\s+auf)\b", s) or re.search(r"\b(oberste|erste|neueste|zweite|dritte|letzte)", s):
            idx = _extrahiere_ordinal(s, standard=0)
            return {
                "aktion": "event_oeffnen",
                "parameter": {"index": idx},
                "antwort": "Öffne Ereignis",
            }

    # 6. Bild oeffnen: "zeig mir das erste Bild", "erstes Foto", "drittes Bild"
    if re.search(r"\b(bild|foto|kachel)\b", s) and re.search(r"\b(zeig(e)?|öffne|wähle|klick)\b", s):
        idx = _extrahiere_ordinal(s, standard=0)
        return {
            "aktion": "bild_oeffnen",
            "parameter": {"index": idx},
            "antwort": f"Zeige Bild {idx + 1 if idx >= 0 else 'letztes'}",
        }

    # 7. Notizen hinzufuegen: "Notizen hinzufügen", "Notiz hinzufügen: ...", "Notiz: ..."
    m_notiz = re.search(r"\b(?:notiz(?:en)?|erinnerung(?:en)?)\s*(?:hinzufügen|hinzufuegen|anfügen|anfuegen|ergänzen|ergaenzen|dazu)?(?::|\s+dass|\s+wie)?\s*(.*)$", segment, re.IGNORECASE)
    if m_notiz and re.search(r"\b(?:notiz|erinnerung)", s):
        inhalt = m_notiz.group(1).strip() if m_notiz.group(1) else ""
        return {
            "aktion": "notiz_hinzufuegen",
            "parameter": {"text": inhalt},
            "antwort": "Notiz hinzugefügt" if inhalt else "Bereit für Notiz",
        }

    # 8. Geschichte erzaehlen: "Erzähl mir von da jetzt die Geschichte", "Bildgeschichte erzaehlen"
    if re.search(r"\berzähl(e)?\b.*(geschichte|was|dazu|bild)", s) or re.search(r"\b(bildgeschichte|geschichte\s+erzählen)\b", s):
        return {
            "aktion": "geschichte_erzaehlen",
            "parameter": {},
            "antwort": "Erzeuge Bildgeschichte",
        }

    # 9. Neu vorsortieren: "Neu vorsortieren", "Sortiere die Gruppen neu"
    if re.search(r"\b(neu\s*vorsortieren|gruppen\s*neu|zentroide\s*neu)\b", s):
        return {
            "aktion": "neu_vorsortieren",
            "parameter": {},
            "antwort": "Gruppen werden neu vorsortiert",
        }

    # 10. Speichern: "Speichern", "Eintrag sichern"
    if re.search(r"^(bitte\s*)?(speichern|sichern)!?$", s) or re.search(r"\b(notiz|geschichte)\s+speichern\b", s):
        return {
            "aktion": "speichern",
            "parameter": {},
            "antwort": "Gespeichert",
        }

    return None


def analysiere_sprachbefehl(text: str) -> Dict[str, Any]:
    """
    Analysiert gesprochenen Freitext auf strukturierte App-Aktionen.
    Unterstuetzt sowohl Einzelbefehle als auch Mehrschritt-Aktionen (z. B. mit 'und').
    """
    rohtext = (text or "").strip()
    if not rohtext:
        return {
            "ist_befehl": False,
            "aktionen": [],
            "antwort": None,
            "rohtext": rohtext,
        }

    # Segmente aufteilen: " und ", " danach ", " anschließend ", " sowie "
    trenner = re.split(r"\s+(?:und(?:\s+dann)?|danach|anschließend|sowie)\s+", rohtext, flags=re.IGNORECASE)
    gefundene_aktionen: List[Dict[str, Any]] = []

    for seg in trenner:
        befehl = _analysiere_einzelbefehl(seg)
        if befehl:
            gefundene_aktionen.append(befehl)

    # Falls Aufteilung keine Treffer fand, den Gesamtsatz als Ganzes pruefen
    if not gefundene_aktionen:
        ganzer = _analysiere_einzelbefehl(rohtext)
        if ganzer:
            gefundene_aktionen.append(ganzer)

    if gefundene_aktionen:
        antworten = [a.get("antwort", "") for a in gefundene_aktionen if a.get("antwort")]
        zusammenfassung = " und ".join(antworten) if antworten else "Befehl ausgeführt"
        return {
            "ist_befehl": True,
            "aktionen": gefundene_aktionen,
            "aktion": gefundene_aktionen[0]["aktion"],
            "parameter": gefundene_aktionen[0].get("parameter", {}),
            "antwort": zusammenfassung,
            "rohtext": rohtext,
        }

    return {
        "ist_befehl": False,
        "aktionen": [],
        "aktion": None,
        "parameter": {},
        "antwort": None,
        "rohtext": rohtext,
    }
