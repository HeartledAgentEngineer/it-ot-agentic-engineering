"""Messwerkzeug: Wie tief sind die gespeicherten Bildbeschreibungen? (15.10.2026)

Anlass: Abschnitt 2 des Plans ``.hermes/plans/2026-10-10_personen-orte-erzaehlungen.md``
("Detailtiefe auf Zuruf") hat eine offene Frage - dort steht als Annahme, die gespeicherten
Beschreibungen seien "~30 Woerter (2 Saetze)". Ob das fuer welche Datei stimmt, war nie
gemessen. **Dies ist die Messung.**

Das Werkzeug **misst nur**. Es liest ausschliesslich die lokalen Beschreibungsdateien (Text),
oeffnet **kein Bild**, ruft **kein Netz** und **kein Modell**, **schreibt nichts** und gibt
**keinen Beschreibungstext** aus - nur Zahlen je Datei.

Gemessen wird je Datei:

* Anzahl Zeilen, kaputte (nicht lesbare) Zeilen, leere Beschreibungen,
* **Woerter** je Beschreibung (Median, Mittel, 90-Prozent-Wert, groesste),
* **Zeichen** (Median, groesste) und **Saetze** (Median, groesste),
* grobe **Sprachschaetzung** (ueberwiegend deutsch / ueberwiegend englisch) anhand
  haeufiger Funktionswoerter - bewusst grob, nur als Anteil,
* die **Wortgrenze je Prompt-Fassung** direkt aus ``bild_beschreiben.py`` (einzige Quelle
  ist ``PROMPT_VARIANTEN``), damit Zahl und Grenze zusammen genannt werden.

Aufruf (aus dem Projektordner ``personal_ai_agent``)::

    backend\\.venv\\Scripts\\python.exe tools\\foto_sortierung\\beschreibungstiefe_messen.py

Mit ``--ordner`` laesst sich der Ort der Dateien umstellen, mit ``--dateien Name=pfad``
einzelne Dateien. Fehlt eine Datei, wird das ehrlich gemeldet (kein Abbruch).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import statistics
import sys
from pathlib import Path

WERKZEUG_BESCHREIBEN = (
    Path(__file__).resolve().parent / "bild_beschreiben.py"
)

STANDARD_ORDNER = Path.home() / "foto_sortierung"

# Reihenfolge: aelteste Fassung zuerst, dann die drei reichen Quellen, dann Nachzuegler.
STANDARD_DATEIEN = (
    ("stichwort (Altbestand, 14-Wort-Grenze)", "bild_beschreibungen.jsonl"),
    ("bildgeschichte Sammlung", "bild_beschreibungen_reich.jsonl"),
    ("bildgeschichte Papa", "bild_beschreibungen_papa_reich.jsonl"),
    ("bildgeschichte Nachzuegler", "bild_beschreibungen_rest_reich.jsonl"),
    ("bildgeschichte Altbestand-Nachzug", "bild_beschreibungen_altbestand_reich.jsonl"),
)

WORTE = re.compile(r"\S+")
SAETZE = re.compile(r"[.!?]+(?:\s|$)")

# Grobe Sprachschaetzung ueber Funktionswoerter. Nur Anteile, nie Inhalte.
DE_WOERTER = re.compile(
    r"\b(der|die|das|und|mit|auf|im|ein|eine|ist|sind|von|zu|am|vor|dem|den|nicht|auch)\b",
    re.I,
)
EN_WOERTER = re.compile(
    r"\b(the|and|with|of|in|on|a|an|is|are|to|at|from|his|her|their|was|were)\b",
    re.I,
)


def _perzentil(werte: list[int], anteil: float) -> int:
    """Einfacher Perzentilwert (naechstgelegener Rang), robust fuer kleine Listen."""
    if not werte:
        return 0
    sortiert = sorted(werte)
    rang = int(round(anteil * (len(sortiert) - 1)))
    return sortiert[max(0, min(len(sortiert) - 1, rang))]


def texte_lesen(pfad: Path) -> tuple[list[str], int]:
    """Liest die Beschreibungstexte einer JSONL-Datei. Rueckgabe: (Texte, kaputte Zeilen).

    Eine kaputte Zeile wird gezaehlt, nicht geworfen. Fehlende oder nicht-textuelle
    ``beschreibung``-Felder zaehlen als leerer Text (sie bleiben in der Liste, damit die
    Stichprobengroesse ehrlich bleibt).
    """
    texte: list[str] = []
    kaputt = 0
    with pfad.open(encoding="utf-8") as fh:
        for zeile in fh:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                eintrag = json.loads(zeile)
            except json.JSONDecodeError:
                kaputt += 1
                continue
            wert = eintrag.get("beschreibung") if isinstance(eintrag, dict) else None
            texte.append(wert if isinstance(wert, str) else "")
    return texte, kaputt


def kennzahlen(texte: list[str]) -> dict:
    """Nur Zahlen zu einer Textliste. Kein Textinhalt verlaesst diese Funktion."""
    if not texte:
        return {"n": 0, "kaputt": 0, "leer": 0, "woerter_median": 0, "woerter_mittel": 0.0,
                "woerter_p90": 0, "woerter_max": 0, "zeichen_median": 0, "zeichen_max": 0,
                "saetze_median": 0, "saetze_max": 0, "anteil_deutsch": 0.0,
                "anteil_englisch": 0.0}
    woerter = [len(WORTE.findall(t)) for t in texte]
    zeichen = [len(t) for t in texte]
    saetze = [max(1, len(SAETZE.findall(t.strip()))) if t.strip() else 0 for t in texte]
    deutsch, englisch = sprache_schaetzen(texte)
    return {
        "n": len(texte),
        "leer": sum(1 for t in texte if not t.strip()),
        "woerter_median": statistics.median(woerter),
        "woerter_mittel": round(statistics.fmean(woerter), 1),
        "woerter_p90": _perzentil(woerter, 0.9),
        "woerter_max": max(woerter),
        "zeichen_median": statistics.median(zeichen),
        "zeichen_max": max(zeichen),
        "saetze_median": statistics.median(saetze),
        "saetze_max": max(saetze),
        "anteil_deutsch": deutsch,
        "anteil_englisch": englisch,
    }


def sprache_schaetzen(texte: list[str]) -> tuple[float, float]:
    """Grobe Sprachanteile in Prozent: ueberwiegend deutsch / ueberwiegend englisch.

    Gezaehlt werden nur Beschreibungen mit Text. Eine Beschreibung gilt als englisch, wenn
    mindestens ein englisches Funktionswort vorkommt und es mindestens so viele sind wie die
    deutschen. Das ist bewusst grob - es soll nur die Groessenordnung zeigen.
    """
    mit_text = [t for t in texte if t.strip()]
    if not mit_text:
        return 0.0, 0.0
    deutsch = sum(1 for t in mit_text if len(DE_WOERTER.findall(t)) > len(EN_WOERTER.findall(t)))
    englisch = sum(
        1
        for t in mit_text
        if EN_WOERTER.search(t) and len(EN_WOERTER.findall(t)) >= len(DE_WOERTER.findall(t))
    )
    return round(100.0 * deutsch / len(mit_text), 1), round(100.0 * englisch / len(mit_text), 1)


def wortgrenzen(pfad: Path = WERKZEUG_BESCHREIBEN) -> dict[str, int]:
    """Wortgrenze je Prompt-Fassung aus ``bild_beschreiben.PROMPT_VARIANTEN``.

    Liest das Modul ueber den Pfad (kein Import ueber ``sys.path``), damit der Aufruf aus
    jedem Arbeitsordner funktioniert. Fehlt die Datei, wird das ehrlich gemeldet.
    """
    if not pfad.is_file():
        return {}
    spez = importlib.util.spec_from_file_location("bild_beschreiben_grenzen", pfad)
    if spez is None or spez.loader is None:
        return {}
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return {str(k): int(v) for k, v in getattr(modul, "PROMPT_VARIANTEN", {}).items()}


def bericht(dateien, ordner: Path, grenzen: dict[str, int] | None = None):
    """Liefert die Berichtszeilen (nur Zahlen, keine Inhalte)."""
    grenzen = wortgrenzen() if grenzen is None else grenzen
    yield "Bildbeschreibungen: Tiefe je Datei (nur Zahlen, kein Inhalt)"
    yield ""
    for name, dateiname in dateien:
        pfad = Path(dateiname)
        if not pfad.is_absolute():
            pfad = ordner / dateiname
        if not pfad.is_file():
            yield f"{name} — Datei fehlt: {pfad}"
            yield ""
            continue
        texte, kaputt = texte_lesen(pfad)
        k = kennzahlen(texte)
        k["kaputt"] = kaputt
        yield f"{name} ({pfad.name})"
        yield (f"  Zeilen {k['n']} · kaputt {kaputt} · leer {k['leer']} · "
               f"Woerter Median {k['woerter_median']} · Mittel {k['woerter_mittel']} · "
               f"90 % {k['woerter_p90']} · groesste {k['woerter_max']}")
        yield (f"  Zeichen Median {k['zeichen_median']} · groesste {k['zeichen_max']} · "
               f"Saetze Median {k['saetze_median']} · groesste {k['saetze_max']}")
        yield (f"  ueberwiegend deutsch {k['anteil_deutsch']} % · ueberwiegend englisch "
               f"{k['anteil_englisch']} %")
        yield ""
    if grenzen:
        yield "Wortgrenze je Prompt-Fassung (aus bild_beschreiben.PROMPT_VARIANTEN):"
        for variante, grenze in sorted(grenzen.items()):
            yield f"  {variante}: {grenze} Woerter"
    else:
        yield "Wortgrenzen nicht gelesen (bild_beschreiben.py nicht gefunden)."
    return 0


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Tiefe der gespeicherten Bildbeschreibungen messen "
                    "(nur lesen, nur Zahlen, nichts schreiben).")
    zerleger.add_argument("--ordner", default=str(STANDARD_ORDNER),
                          help="Ordner der Beschreibungsdateien (Standard: ~/foto_sortierung)")
    zerleger.add_argument("--dateien", nargs="*", default=None,
                          help="Statt der Voreinstellung: Dateien als Name=Pfad ...")
    args = zerleger.parse_args(argv)

    if args.dateien:
        dateien = []
        for eintrag in args.dateien:
            if "=" not in eintrag:
                print(f"Abbruch: '{eintrag}' hat die Form Name=pfad (Beispiel: alt=./a.jsonl).")
                return 2
            name, pfad = eintrag.split("=", 1)
            dateien.append((name, pfad))
    else:
        dateien = list(STANDARD_DATEIEN)

    ordner = Path(args.ordner)
    gefunden = sum(
        1 for _, d in dateien if (Path(d) if os.path.isabs(d) else ordner / d).is_file()
    )
    if gefunden == 0:
        print(f"Abbruch: keine Beschreibungsdatei gefunden (Ordner: {ordner}).")
        return 2

    for zeile in bericht(dateien, ordner):
        print(zeile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
