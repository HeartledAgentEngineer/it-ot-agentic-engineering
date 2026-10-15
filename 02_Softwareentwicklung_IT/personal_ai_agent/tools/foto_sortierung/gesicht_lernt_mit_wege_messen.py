"""Messwerkzeug: Wo fuehrt eine Gesichts-Korrektur heute nach? — Referenz am
Geraet gegen Gruppenmittelpunkt am PC (15.10.2026)

Anlass: Auftrag „Gesichter im Detailbild bearbeiten\" (Sebastian, 15.10.2026),
**Abschnitt 4.2**: „Wunsch Nr. 8 ‚Erkennung lernt mit' ist damit verbunden: Wenn
Korrekturen den Mittelpunkt nachfuehren sollen (Issue #5), dann ist genau dieses
Verruecken-und-Speichern der Ort, an dem das passieren muss.\"

Der vorige Messlauf (``gesicht_referenz_wege_messen.py``) hat Abschnitt 4.1
geklaert: der Detailbild-Editor speichert ueber den **Gesichter-Weg**, und der
legt eine Referenz **mit Vektor** an. **Offen war die Frage dahinter:** wo im
Bestand wird ein Mittelpunkt nachgefuehrt — und reicht der Referenzvektor dafuer?

**Dieses Werkzeug misst das am echten Code und an den echten Dateien.** Es liest
nur Text (Code) und zaehlt lokal; es **oeffnet kein Bild**, ruft **kein Netz**,
**kein Modell**, **schreibt nichts**, **startet nichts** und gibt **keine
Personennamen** aus — nur Zahlen und Datei:Zeile.

Gemessen wird:

* **Referenz-Weg am Geraet** (``backend/app/services/gesicht_quiz.py`` +
  ``gesichter_service.py``): wo die neue Einbettung entsteht, wo sie gespeichert
  wird und welche Schwelle verhindert, dass eine Korrektur ankommt.
* **Gruppen-Weg am PC** (``gruppen_quiz.zuordnen`` →
  ``personen_vorgaben.json`` → ``personen_gruppieren``): die einzige Stelle, an
  der eine feste Zuordnung den Gruppenmittelpunkt eines naechsten Laufs bildet.
* **Die Luecke, gemessen statt behauptet:** wie oft der PC-Gruppenlauf die
  Geraete-Referenzen (``gesichter_katalog.json``) liest, und wie oft irgendein
  Dienst auf dem Geraet einen Mittelpunkt rechnet (Vorkommen im echten Code).
* **Zahlen am echten Bestand:** Eintraege in den Vorgaben/Bestaetigungen, Zeilen
  der Gesichtszuordnung, Kennungen der Gruppen — und die ehrliche Grenze fuer
  alles, was nur am Geraet liegt.

Aufruf (aus dem Projektordner ``personal_ai_agent``)::

    backend\\\\.venv\\\\Scripts\\\\python.exe tools\\\\foto_sortierung\\\\gesicht_lernt_mit_wege_messen.py
    backend\\\\.venv\\\\Scripts\\\\python.exe tools\\\\foto_sortierung\\\\gesicht_lernt_mit_wege_messen.py --daten-dir C:/Users/<name>/foto_sortierung

Fehlt eine Datei, wird das ehrlich gemeldet — kein Abbruch, keine geratene Zahl.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

PROJEKT = Path(__file__).resolve().parents[2]
SERVICE_GESICHT = PROJEKT / "backend" / "app" / "services" / "gesicht_quiz.py"
SERVICE_GESICHTER = PROJEKT / "backend" / "app" / "services" / "gesichter_service.py"
SERVICE_GRUPPEN = PROJEKT / "backend" / "app" / "services" / "gruppen_quiz.py"
GRUPPIEREN = PROJEKT / "tools" / "foto_sortierung" / "personen_gruppieren.py"

STANDARD_DATEN = Path.home() / "foto_sortierung"
BESTAETIGT = "personen_bestaetigt.json"
VORGABEN = "personen_vorgaben.json"
KATALOG = "gesichter_katalog.json"
GRUPPEN_ORDNER = "personen_gruppen"
ZUORDNUNG = "gesicht_zuordnung.jsonl"
KENNUNGEN = "kennungen.json"

# Schluessel in ``personen_vorgaben.json`` — die vier Regeln des Benennens.
VORGABEN_REGELN = ("zugeordnet", "ausgeschlossen", "gleich", "verschieden")

# Wo ein Mittelpunkt entstehen kann (Wort, nach dem im echten Code gesucht wird).
MITTELPUNKT = r"mittelpunkt|Mittelpunkt|schwerpunkt|zentroid|centroid"


def _zahl(wert) -> str:
    """Ganze Zahl mit Punkt als Tausendertrenner."""
    return f"{int(wert):,}".replace(",", ".")


def _rel(pfad: Path) -> str:
    try:
        return os.path.relpath(pfad, PROJEKT).replace(os.sep, "/")
    except ValueError:
        return str(pfad)


def code_zeilen(pfad: Path, muster: str) -> list:
    """Alle Zeilen einer Textdatei, die auf ``muster`` passen — als (Zeile, Text)."""
    if not pfad.is_file():
        return []
    treffer, sucher = [], re.compile(muster)
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for nummer, zeile in enumerate(datei, start=1):
            if sucher.search(zeile):
                treffer.append((nummer, zeile.rstrip()))
    return treffer


def _stelle(pfad: Path, muster: str, nummer: int = 0):
    """Die ``nummer``-te passende Stelle als (Datei, Zeile, Text) oder None."""
    treffer = code_zeilen(pfad, muster)
    if len(treffer) <= nummer:
        return None
    zeile, text = treffer[nummer]
    return (_rel(pfad), zeile, re.sub(r"\s+", " ", text.strip())[:90])


# ── Teil 1: der Referenz-Weg am Geraet ─────────────────────────────────────

def referenz_weg(gesicht: Path = SERVICE_GESICHT, dienst: Path = SERVICE_GESICHTER) -> dict:
    """Belege: die Korrektur wird eingebettet und als Referenz gespeichert."""
    return {
        "da": gesicht.is_file() and dienst.is_file(),
        "antwort_dienst": _stelle(gesicht, r"^def beantworte_runde\("),
        "bbox_fallback": _stelle(gesicht, r"face_service\.embedding_fuer_bbox"),
        "neue_referenz": _stelle(gesicht, r"^    neue_ref = \{"),
        "schwelle": _stelle(gesicht, r"zu_alt > 0\.05"),
        "speichern": _stelle(gesicht, r"gesichter_service\.person_speichern\(\*\*basis"),
        "katalog_datei": _stelle(dienst, r"^KATALOG_DATEI = "),
        "person_speichern": _stelle(dienst, r"^def person_speichern\("),
        "atomar": _stelle(dienst, r"os\.replace\(tmp, KATALOG_DATEI\)"),
    }


def referenz_weg_bericht(belege: dict) -> list:
    if not belege.get("da"):
        return ["  Code nicht gefunden (gesicht_quiz.py / gesichter_service.py) — nicht messbar."]
    zeilen = ["  Der Editor speichert ueber den Gesichter-Weg; dort wird die Korrektur eingebettet:"]
    for schluessel, was in (
        ("antwort_dienst", "Dienst der Quiz-Antwort"),
        ("bbox_fallback", "Einbettung des bestaetigten (verschobenen) Rahmens"),
        ("neue_referenz", "neue Referenz mit embedding + Rahmen"),
        ("schwelle", "Schwelle, ab der die Referenz angehaengt wird"),
        ("speichern", "Speichern der Referenzliste"),
        ("katalog_datei", "Ablageort des Referenzspeichers"),
        ("person_speichern", "Schreibfunktion"),
        ("atomar", "atomares Schreiben (tmp + rename)"),
    ):
        stelle = belege.get(schluessel)
        if stelle:
            zeilen.append(f"    {was}: {stelle[0]}:{stelle[1]}")
    if any(belege.get(k) is None for k in ("bbox_fallback", "neue_referenz", "speichern", "katalog_datei")):
        zeilen.append("  Achtung: erwartete Code-Stelle fehlt — bitte von Hand nachsehen.")
    zeilen.append("    Folge: der REFERENZVEKTOR dieser Person fuehrt die Korrektur nach — "
                  "aber nur die naechste Referenz, nicht die Gruppe.")
    return zeilen


# ── Teil 2: der Gruppen-Weg am PC ──────────────────────────────────────────

def gruppen_weg(gruppen: Path = SERVICE_GRUPPEN, gruppieren: Path = GRUPPIEREN) -> dict:
    """Belege: die einzige Stelle, an der ein Mittelpunkt die Korrektur nachfuehrt."""
    return {
        "da": gruppen.is_file() and gruppieren.is_file(),
        "zuordnen": _stelle(gruppen, r"^def zuordnen\("),
        "schreibt_zugeordnet": _stelle(gruppen, r'daten\["zugeordnet"\] = zug_liste'),
        "schreibt_vorgaben": _stelle(gruppen, r"_atomar_schreiben\(VORGABEN_DATEINAME, daten\)", 0),
        "aufloesen": _stelle(gruppieren, r"^def _einzelzuordnungen_auflosen\("),
        "liest_fest": _stelle(gruppieren, r"fest = _einzelzuordnungen_auflosen\(vorg, namen\)", 1),
        "vorbilder": _stelle(gruppieren, r"vorbilder\.setdefault\(eintrag\[\"kennung\"\]"),
        "fixiert": _stelle(gruppieren, r"^    for i in \(fixiert or \(\)\):"),
        "startgruppen": _stelle(gruppieren, r"for kennung in sorted\(vorbilder or \{\}\):"),
        "gruppieren_v2": _stelle(gruppieren, r"erg = gruppieren_v2\(v, bild_ids"),
    }


def gruppen_weg_bericht(belege: dict) -> list:
    if not belege.get("da"):
        return ["  Code nicht gefunden (gruppen_quiz.py / personen_gruppieren.py) — nicht messbar."]
    zeilen = ["  Der Mittelpunkt entsteht nur im PC-Gruppenlauf — gespeist aus den festen Zuordnungen:"]
    for schluessel, was in (
        ("zuordnen", "feste Einzelzuordnung (Dienst)"),
        ("schreibt_zugeordnet", "schreibt sie nach personen_vorgaben.json"),
        ("schreibt_vorgaben", "atomares Schreiben der Vorgaben"),
        ("aufloesen", "Aufloesen der festen Zuordnungen (PC)"),
        ("liest_fest", "der PC-Lauf liest sie"),
        ("vorbilder", "daraus werden Vorbilder"),
        ("fixiert", "und fixierte Stellen"),
        ("startgruppen", "Vorbild-Gruppen starten mit ihrem Mittelpunkt"),
        ("gruppieren_v2", "der eigentliche Gruppenlauf"),
    ):
        stelle = belege.get(schluessel)
        if stelle:
            zeilen.append(f"    {was}: {stelle[0]}:{stelle[1]}")
    if any(belege.get(k) is None for k in ("zuordnen", "schreibt_zugeordnet", "liest_fest",
                                           "startgruppen", "gruppieren_v2")):
        zeilen.append("  Achtung: erwartete Code-Stelle fehlt — bitte von Hand nachsehen.")
    return zeilen


# ── Teil 3: die Luecke — gemessen, nicht behauptet ─────────────────────────

def luecke(gruppieren: Path = GRUPPIEREN, gruppen: Path = SERVICE_GRUPPEN,
           gesicht: Path = SERVICE_GESICHT) -> dict:
    """Zaehlt im echten Code, wer die Geraete-Referenzen liest und wer Mittelpunkte rechnet."""
    return {
        "da": gruppieren.is_file() and gruppen.is_file() and gesicht.is_file(),
        "pc_liest_katalog": len(code_zeilen(gruppieren, r"gesichter_katalog")),
        "geraet_mittelpunkt": {
            "gruppen_quiz.py": len(code_zeilen(gruppen, MITTELPUNKT)),
            "gesicht_quiz.py": len(code_zeilen(gesicht, MITTELPUNKT)),
        },
        "pc_mittelpunkt": len(code_zeilen(gruppieren, MITTELPUNKT)),
    }


def luecke_bericht(belege: dict) -> list:
    if not belege.get("da"):
        return ["  Code nicht gefunden — Luecke nicht messbar."]
    zeilen = []
    katalog = belege.get("pc_liest_katalog", 0)
    if katalog:
        zeilen.append(f"    Achtung: der PC-Gruppenlauf nennt gesichter_katalog {_zahl(katalog)}x "
                      f"— die Referenzen waeren dann im Spiel.")
    else:
        zeilen.append("    Gemessen: der PC-Gruppenlauf (personen_gruppieren.py) liest "
                      "gesichter_katalog.json GENAU 0x — die Geraete-Referenzen kommen in der "
                      "Gruppenbildung nicht vor.")
    geraet = belege.get("geraet_mittelpunkt") or {}
    summe = sum(geraet.values())
    if summe:
        zeilen.append(f"    Achtung: {_zahl(summe)} Mittelpunkt-Stelle(n) im Geraete-Code gefunden "
                      f"({', '.join(f'{k}: {v}' for k, v in sorted(geraet.items()))}).")
    else:
        zeilen.append("    Gemessen: 0 Mittelpunkt-Stellen im Geraete-Code "
                      f"({', '.join(f'{k}: 0' for k in sorted(geraet))}) — "
                      "das Handy rechnet keinen Gruppenmittelpunkt nach.")
    zeilen.append(f"    Gegenprobe: derselbe Suchbegriff findet im PC-Werkzeug "
                  f"{_zahl(belege.get('pc_mittelpunkt', 0))} Stellen — der Begriff ist also "
                  f"nicht einfach unauffindbar.")
    return zeilen


# ── Teil 4: Zahlen am echten Bestand ───────────────────────────────────────

def json_zaehlen(pfad: Path) -> dict:
    """Eine JSON-Datei zaehlen: Form, Listenlaengen, kaputt/fehlt. Nie ein Wurf."""
    ergebnis = {"pfad": str(pfad), "fehlt": False, "kaputt": False, "form": "", "listen": {}}
    if not pfad.is_file():
        ergebnis["fehlt"] = True
        return ergebnis
    try:
        with open(pfad, encoding="utf-8", errors="replace") as datei:
            daten = json.load(datei)
    except (ValueError, OSError):
        ergebnis["kaputt"] = True
        return ergebnis
    ergebnis["form"] = type(daten).__name__
    if isinstance(daten, dict):
        for schluessel, wert in daten.items():
            if isinstance(wert, (list, dict, set)):
                ergebnis["listen"][str(schluessel)] = len(wert)
    elif isinstance(daten, list):
        ergebnis["listen"]["(Liste)"] = len(daten)
    return ergebnis


def jsonl_zeilen(pfad: Path, deckel: int = 200000) -> dict:
    """Zeilen einer JSONL-Datei zaehlen (nur lesend, mit Deckel)."""
    if not pfad.is_file():
        return {"fehlt": True, "zeilen": 0}
    zeilen = 0
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for _ in datei:
            zeilen += 1
            if zeilen >= deckel:
                break
    return {"fehlt": False, "zeilen": zeilen}


def bestand_bericht(daten_dir: Path) -> list:
    zeilen = [f"  Ordner des Bestands: {daten_dir}"]

    vorgaben = json_zaehlen(daten_dir / VORGABEN)
    if vorgaben["fehlt"]:
        zeilen.append(f"  {VORGABEN}: fehlt am PC — Zahl der festen Zuordnungen NICHT messbar.")
    elif vorgaben["kaputt"]:
        zeilen.append(f"  {VORGABEN}: nicht lesbar (kein gueltiges JSON) — NICHT messbar.")
    else:
        teile = " · ".join(f"{k}: {_zahl(vorgaben['listen'].get(k, 0))}" for k in VORGABEN_REGELN)
        zeilen.append(f"  {VORGABEN}: {teile} · Summe {_zahl(sum(vorgaben['listen'].values()))}")
        if not vorgaben["listen"].get("zugeordnet"):
            zeilen.append("    Davon feste Einzelzuordnungen (zugeordnet): 0 — in dieser Kopie "
                          "fuehrt heute keine Korrektur einen Mittelpunkt nach.")

    bestaetigt = json_zaehlen(daten_dir / BESTAETIGT)
    if bestaetigt["fehlt"] or bestaetigt["kaputt"]:
        zeilen.append(f"  {BESTAETIGT}: fehlt oder nicht lesbar — NICHT messbar.")
    else:
        zeilen.append(f"  {BESTAETIGT}: {bestaetigt['form']} · "
                      f"Summe der Listen {_zahl(sum(bestaetigt['listen'].values()))}")

    zuordnung = jsonl_zeilen(daten_dir / GRUPPEN_ORDNER / ZUORDNUNG)
    if zuordnung["fehlt"]:
        zeilen.append(f"  {GRUPPEN_ORDNER}/{ZUORDNUNG}: fehlt — Gesichtszahl NICHT messbar.")
    else:
        zeilen.append(f"  {GRUPPEN_ORDNER}/{ZUORDNUNG}: {_zahl(zuordnung['zeilen'])} Zeilen "
                      f"(jede Zeile ein Gesicht mit Gruppe)")

    kennungen = json_zaehlen(daten_dir / GRUPPEN_ORDNER / KENNUNGEN)
    if kennungen["fehlt"] or kennungen["kaputt"]:
        zeilen.append(f"  {GRUPPEN_ORDNER}/{KENNUNGEN}: fehlt oder nicht lesbar — NICHT messbar.")
    else:
        anzahl = kennungen["listen"].get("kennungen")
        zeilen.append(f"  {GRUPPEN_ORDNER}/{KENNUNGEN}: {_zahl(anzahl or 0)} Kennungen")

    katalog = daten_dir / KATALOG
    if not katalog.is_file():
        zeilen.append(f"  Ehrliche Grenze: {KATALOG} liegt am PC nicht vor (Referenzspeicher "
                      f"liegt am Geraet) — Zahl der Referenzen NICHT zaehlbar am PC.")
    else:
        zahlen = json_zaehlen(katalog)
        if zahlen["kaputt"]:
            zeilen.append(f"  Ehrliche Grenze: {KATALOG} am PC nicht lesbar — NICHT zaehlbar.")
        else:
            personen = zahlen["listen"].get("personen", 0)
            zeilen.append(f"  {KATALOG} (am PC): Personen-Eintraege {_zahl(personen)}"
                          + (" — leere Huelle, kein Referenzbestand" if not personen else ""))
    return zeilen


# ── Bericht / Kommandozeile ───────────────────────────────────────────────

def bericht(daten_dir: Path = STANDARD_DATEN) -> list:
    """Alle Berichtszeilen bauen (nur Zahlen, Datei:Zeile, keine Namen)."""
    zeilen = ["Lernt die Erkennung mit? Wo eine Gesichts-Korrektur heute nachfuehrt "
              "(nur gelesen, nur Zahlen)", ""]
    zeilen.append("1. Referenzvektor (Geraet, Gesichter-Weg)")
    zeilen += referenz_weg_bericht(referenz_weg())
    zeilen.append("")
    zeilen.append("2. Gruppenmittelpunkt (PC, naechster Gruppenlauf)")
    zeilen += gruppen_weg_bericht(gruppen_weg())
    zeilen.append("")
    zeilen.append("3. Die Luecke dazwischen (Vorkommen im echten Code)")
    zeilen += luecke_bericht(luecke())
    zeilen.append("")
    zeilen.append("4. Zahlen am echten Bestand (nur Zahlen, keine Namen)")
    zeilen += bestand_bericht(daten_dir)
    zeilen.append("")
    zeilen.append("Deutung: „Verruecken und Speichern\" im Detailbild geht ueber den "
                  "Gesichter-Weg — es fuehrt den Referenzvektor nach, den Gruppenmittelpunkt "
                  "nicht (der entsteht nur im PC-Lauf und liest die Geraete-Referenzen nie). "
                  "Damit „Erkennung lernt mit\" den Mittelpunkt erreicht, muss die Korrektur "
                  "zusaetzlich als feste Einzelzuordnung gespeichert werden "
                  "(POST /api/gruppen/zuordnen → personen_vorgaben.json).")
    return zeilen


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Nachfuehren einer Gesichts-Korrektur messen (nur lesen, nur Zahlen).")
    zerleger.add_argument("--daten-dir", default=str(STANDARD_DATEN),
                          help="Ordner des Bestands (Standard: ~/foto_sortierung)")
    args = zerleger.parse_args(argv)
    for zeile in bericht(Path(args.daten_dir)):
        print(zeile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
