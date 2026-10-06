"""Sebastians eigene Notizen durchsuchbar machen (07.10.2026).

Anlass: In der App stehen Notizen an Personen (Gruppen-Quiz, Feld
„Notiz/Erinnerung" per 🎙) und Geschichten an Ereignissen (Erzähl-Ansicht).
Beide waren für den Chat **unsichtbar**: auf die Frage „was arbeitet mein
Bruder?" konnte der Agent nicht antworten, obwohl die Angabe in der
Personen-Notiz stand. Dieses Modul liest beide Quellen und sucht darin.

Quellen (nur lesen, es wird nichts geschrieben):
  * Personen-Profile ``personen_profile.json`` — Beziehung und Notizen je
    Person (Pfad über :func:`app.services.gruppen_quiz._schreibpfad`).
  * Geschichten ``geschichten.jsonl`` — Erzählungen zu Ereignissen und
    einzelnen Bildern (Pfad über :func:`app.services.erzaehl_service.geschichten_pfad`).

Suche: **kein Netz, kein Modell** — reine Wortsuche, diakritika-frei, und zwar
auf Wortanfänge, damit „Bruder" auch „Bruders" findet und „Urlaub" auch
„Urlaubsbilder". Ein Begriff, der nirgends vorkommt, wird ehrlich als „nicht
gefunden" gemeldet, statt etwas zu erfinden.

Ausgabe: nur Klartext (Notiztexte, Quelle, Datum). Keine Koordinaten, keine
Kennungen, keine Telefonnummern. Tests und Doku arbeiten ausschließlich mit
erfundenen Namen und Notizen.
"""
from __future__ import annotations

import json
import os
import unicodedata
from typing import Any, Dict, List, Optional

MAX_TREFFER = 8
MAX_NOTIZ_ZEICHEN = 400

# Umlaute/ß für die Suche vereinheitlichen (Suche soll „Buße"/„Busse" finden —
# ß ist im Deutschen ein Doppel-s, darum NICHT auf ein einzelnes s abbilden).
_UMLAUTE = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss",
                          "Ä": "A", "Ö": "O", "Ü": "U"})


def normalisiere(text: Any) -> str:
    """Kleinschreibung, Umlaute vereinheitlicht, Mehrfach-Leerraum weg."""
    if not isinstance(text, str):
        return ""
    ohne = unicodedata.normalize("NFKD", text.translate(_UMLAUTE))
    ohne = "".join(z for z in ohne if not unicodedata.combining(z))
    return " ".join(ohne.lower().split())


def profile_pfad() -> str:
    """Ort der Personen-Profile (über den Quiz-Dienst, damit es EINEN Weg gibt)."""
    from app.services import gruppen_quiz

    return gruppen_quiz._schreibpfad(gruppen_quiz.PROFILE_DATEINAME)  # noqa: SLF001


def geschichten_datei() -> str:
    """Ort der Erzähl-Geschichten (über den Erzähl-Dienst)."""
    from app.services import erzaehl_service

    return erzaehl_service.geschichten_pfad()


def _json_lesen(pfad: str) -> Dict[str, Any]:
    """Datei lesen; fehlt/defekt -> leeres Ergebnis (nie ein Wurf)."""
    if not isinstance(pfad, str) or not os.path.isfile(pfad):
        return {}
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            daten = json.load(datei)
    except Exception:
        return {}
    if isinstance(daten, dict) and isinstance(daten.get("profile"), dict):
        return daten["profile"]
    if isinstance(daten, dict):
        return daten
    return {}


def _notiz_text(notiz: Dict[str, Any]) -> str:
    text = notiz.get("text") if isinstance(notiz, dict) else None
    if not isinstance(text, str):
        return ""
    return " ".join(text.split()).strip()[:MAX_NOTIZ_ZEICHEN]


def personen_notizen() -> List[Dict[str, Any]]:
    """Alle Personen mit ihren aktuellen Notizen (zurückgenommene zählen nicht).

    Rückgabe je Person: ``{"name", "beziehung", "notizen": [{"text","zeit"}], "anzahl"}``.
    """
    profile = _json_lesen(profile_pfad())
    ergebnis: List[Dict[str, Any]] = []
    for name, eintrag in profile.items():
        if not isinstance(eintrag, dict):
            continue
        notizen = []
        for notiz in eintrag.get("notizen") or []:
            if not isinstance(notiz, dict) or notiz.get("zurueckgenommen"):
                continue
            text = _notiz_text(notiz)
            if text:
                notizen.append({"text": text, "zeit": str(notiz.get("zeit") or "")})
        ergebnis.append({
            "name": str(name),
            "beziehung": " ".join(str(eintrag.get("beziehung") or "").split()),
            "notizen": notizen,
            "anzahl": len(notizen),
        })
    ergebnis.sort(key=lambda p: normalisiere(p["name"]))
    return ergebnis


def person_finden(name: Any) -> Optional[Dict[str, Any]]:
    """Person über ihren Namen finden — exakt, sonst über den Wortanfang."""
    ziel = normalisiere(name)
    if not ziel:
        return None
    alle = personen_notizen()
    for p in alle:
        if normalisiere(p["name"]) == ziel:
            return p
    for p in alle:
        if normalisiere(p["name"]).startswith(ziel):
            return p
    return None


def geschichten() -> List[Dict[str, Any]]:
    """Aktuelle Geschichten (nur neueste Fassung) als Klartext-Zeilen."""
    from app.services import erzaehl_service

    zeilen: List[Dict[str, Any]] = []
    try:
        roh = erzaehl_service.geschichten()
    except Exception:
        return zeilen
    for eintrag in roh or []:
        if not isinstance(eintrag, dict):
            continue
        text = " ".join(str(eintrag.get("text") or "").split()).strip()[:MAX_NOTIZ_ZEICHEN]
        if not text:
            continue
        zeilen.append({
            "text": text,
            "ereignis_kennung": str(eintrag.get("ereignis_kennung") or ""),
            "datei_kennung": eintrag.get("datei_kennung"),
            "zeit": str(eintrag.get("zeit") or ""),
            "quelle": str(eintrag.get("quelle") or ""),
        })
    return zeilen


def _passt(text: str, begriffe: List[str]) -> bool:
    """Wahr, wenn JEDER Begriff als Wortanfang in ``text`` vorkommt."""
    pruef = normalisiere(text)
    return all(b and any(w.startswith(b) for w in pruef.split()) for b in begriffe)


def suche(begriff: Any = "", limit: int = MAX_TREFFER) -> Dict[str, Any]:
    """Notizen und Geschichten durchsuchen. Ohne Begriff: Bestandsaufnahme.

    Rückgabe ``{"personen": [...], "geschichten": [...], "gesamt_personen",
    "gesamt_geschichten", "mit_notizen", "begriff"}``.
    """
    grenze = max(1, min(int(limit or MAX_TREFFER), 25))
    wort = " ".join(str(begriff or "").split())
    begriffe = [b for b in normalisiere(wort).split() if len(b) >= 3]
    personen = personen_notizen()
    geschichten_alle = geschichten()

    if not begriffe:
        return {
            "begriff": "",
            "personen": [p for p in personen if p["anzahl"]][:grenze],
            "geschichten": geschichten_alle[:grenze],
            "mit_notizen": sum(1 for p in personen if p["anzahl"]),
            "gesamt_personen": len(personen),
            "gesamt_geschichten": len(geschichten_alle),
        }

    personen_treffer = [
        p for p in personen
        if _passt(p["name"], begriffe) or p["beziehung"] and _passt(p["beziehung"], begriffe)
        or any(_passt(n["text"], begriffe) for n in p["notizen"])
    ]
    geschichten_treffer = [g for g in geschichten_alle if _passt(g["text"], begriffe)]
    return {
        "begriff": wort,
        "personen": personen_treffer[:grenze],
        "geschichten": geschichten_treffer[:grenze],
        "mit_notizen": sum(1 for p in personen if p["anzahl"]),
        "gesamt_personen": len(personen),
        "gesamt_geschichten": len(geschichten_alle),
    }


def text_antwort(begriff: Any = "", person: Any = "", limit: int = MAX_TREFFER) -> str:
    """Fertiger Klartext für das Chat-Werkzeug — ehrlich, auch bei Leere."""
    if person:
        p = person_finden(person)
        if not p:
            return (f"Zu „{str(person).strip()}“ habe ich keine Notiz. "
                    "Vielleicht ist die Person in der App noch nicht benannt.")
        zeilen = [f"{p['name']}" + (f" ({p['beziehung']})" if p["beziehung"] else "")]
        if not p["notizen"]:
            zeilen.append("Keine Notiz hinterlegt.")
        for n in p["notizen"]:
            zeilen.append(f"- {n['text']}" + (f" ({n['zeit'][:10]})" if n["zeit"] else ""))
        return "\n".join(zeilen)

    stand = suche(begriff, limit=limit)
    if not stand["begriff"]:
        teile = [f"Eigene Notizen: {stand['mit_notizen']} von {stand['gesamt_personen']} "
                 f"Personen haben eine Notiz, dazu {stand['gesamt_geschichten']} Geschichten."]
        for p in stand["personen"]:
            teile.append(f"- {p['name']}: {p['notizen'][0]['text']}")
        return "\n".join(teile)

    if not stand["personen"] and not stand["geschichten"]:
        return (f"In deinen Notizen steht nichts zu „{stand['begriff']}“ "
                f"(durchsucht: {stand['mit_notizen']} Personen-Notizen, "
                f"{stand['gesamt_geschichten']} Geschichten).")

    teile = [f"Notizen zu „{stand['begriff']}“:"]
    for p in stand["personen"]:
        for n in p["notizen"]:
            if _passt(n["text"], [b for b in normalisiere(stand["begriff"]).split() if len(b) >= 3]) \
                    or _passt(p["name"], normalisiere(stand["begriff"]).split()):
                teile.append(f"- {p['name']}" + (f" ({p['beziehung']})" if p["beziehung"] else "")
                             + f": {n['text']}")
                break
    for g in stand["geschichten"]:
        teile.append(f"- Geschichte" + (f" zu {g['ereignis_kennung']}" if g["ereignis_kennung"] else "")
                     + f": {g['text']}")
    return "\n".join(teile)
