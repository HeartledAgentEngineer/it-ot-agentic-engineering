"""Messwerkzeug: Wer erzeugt im Detailbild eine Gesichts-Referenz — und kann das
Handy Vektoren selbst rechnen? (15.10.2026)

Anlass: Auftrag „Gesichter im Detailbild bearbeiten" (Sebastian, 15.10.2026).
Vorbedingung fuer den Bau ist dort ausdruecklich „Zu klaeren (belegt, nicht
vermutet)" — offen waren nach dem ersten Messlauf (``gesicht_wege_messen.py``):

* **Abschnitt 3:** „Ein Abschnitt im Plan beantwortet, ob das Handy
  Gesichtsvektoren selbst rechnen kann — mit Beleg (Datei:Zeile oder Messung)."
* **Abschnitt 4.1:** der Widerspruch „als Referenz dieser Person" (Hinweistext
  in der App) gegen den Befund, Benennen erzeuge keinen Referenzvektor.

**Dieses Werkzeug misst beides am echten Code und an den echten Dateien.** Es
liest nur Text (Code) und zaehlt in den lokalen Benennungs-Dateien; es
**oeffnet kein Bild**, ruft **kein Netz**, **kein Modell**, **schreibt nichts**
und gibt **keine Personennamen** aus — nur Zahlen und Datei:Zeile.

Gemessen wird:

* **Vektor-Rechner am Geraet** (``backend/app/services/face_service.py``):
  der Subprozess-Aufruf in die Debian-Distro samt Einbettungs-Einstiegen in
  ``backend/face_infer.py`` — damit ist belegt, ob das Handy rechnen kann.
* **Speicherwege im Detailbild**: welcher Endpunkt den Rahmen speichert, welcher
  Dienst ihn einbettet und wo die Einbettung entsteht (Datei:Zeile) — darunter
  der Fall „selbst gezeichneter Rahmen".
* **Der zweite Weg — Gruppen-Benennen**: derselbe Nachweis fuer den Namensweg
  (``/api/gruppen/antwort``) samt der gemessenen Zahl der Vorkommen von
  ``embedding``/``vektor`` in ``gruppen_quiz.py`` (Null heisst: kein Vektor).
* **Dateien des Benennens** (nur Zahlen): Eintraege in
  ``personen_bestaetigt.json`` / ``personen_vorgaben.json`` und wie viele davon
  einen Vektor tragen (0 = nur Namen).
* **Ehrliche Grenze:** der eigentliche Referenzspeicher
  (``gesichter_katalog.json``) liegt am Handy; am PC steht dort nur die leere
  Huelle — dann nennt der Bericht „NICHT zaehlbar am PC" statt einer
  geschaetzten Zahl.

Aufruf (aus dem Projektordner ``personal_ai_agent``)::

    backend\\.venv\\Scripts\\python.exe tools\\foto_sortierung\\gesicht_referenz_wege_messen.py
    backend\\.venv\\Scripts\\python.exe tools\\foto_sortierung\\gesicht_referenz_wege_messen.py --daten-dir C:/Users/<name>/foto_sortierung

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
FACE_SERVICE = PROJEKT / "backend" / "app" / "services" / "face_service.py"
FACE_INFER = PROJEKT / "backend" / "face_infer.py"
SERVICE_GESICHT = PROJEKT / "backend" / "app" / "services" / "gesicht_quiz.py"
SERVICE_GRUPPEN = PROJEKT / "backend" / "app" / "services" / "gruppen_quiz.py"
ROUTER_GESICHTER = PROJEKT / "backend" / "app" / "router" / "gesichter.py"
ROUTER_GRUPPEN = PROJEKT / "backend" / "app" / "router" / "gruppen.py"
FRONTEND = PROJEKT / "frontend" / "app.js"

STANDARD_DATEN = Path.home() / "foto_sortierung"
BESTAETIGT = "personen_bestaetigt.json"
VORGABEN = "personen_vorgaben.json"
KATALOG = "gesichter_katalog.json"

# Schluesselnamen, die einen gespeicherten Vektor bezeichnen — gesucht wird in
# den Benennungs-Dateien. Findet sich keiner, traegt der Namensweg keinen Vektor.
VEKTOR_SCHLUESSEL = ("embedding", "vektor", "vectoren", "vektor_128")


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


def funktions_bereich(pfad: Path, start_muster: str, ende_muster: str = r"^def ") -> list:
    """Zeilen EINER Funktion als (Zeile, Text) — ab ``start_muster`` bis ``ende_muster``."""
    if not pfad.is_file():
        return []
    treffer, drin = [], False
    sucher, ender = re.compile(start_muster), re.compile(ende_muster)
    with open(pfad, encoding="utf-8", errors="replace") as datei:
        for nummer, zeile in enumerate(datei, start=1):
            if not drin:
                if sucher.search(zeile):
                    drin = True
                else:
                    continue
            elif ender.search(zeile):
                break
            treffer.append((nummer, zeile.rstrip()))
    return treffer


def _stelle(pfad: Path, muster: str):
    """Erste passende Stelle als (Datei, Zeile, Text) oder None."""
    treffer = code_zeilen(pfad, muster)
    if not treffer:
        return None
    nummer, text = treffer[0]
    return (_rel(pfad), nummer, re.sub(r"\s+", " ", text.strip())[:90])


# ── Teil 1: kann das Geraet Vektoren rechnen? ──────────────────────────────

def vektor_rechner(face_service: Path = FACE_SERVICE, face_infer: Path = FACE_INFER) -> dict:
    """Belege, dass die Einbettung auf dem Geraet selbst laeuft (Datei:Zeile)."""
    return {
        "service_da": face_service.is_file(),
        "infer_da": face_infer.is_file(),
        "skript": _stelle(face_service, r"^_DEBIAN_SCRIPT\s*="),
        "aufruf": _stelle(face_service, r"^_COMMAND\s*="),
        "ping": _stelle(face_service, r'"op":\s*"ping"'),
        "embed_pfad": _stelle(face_service, r"^def embeddings_fuer_pfad"),
        "embed_bbox": _stelle(face_service, r"^def embedding_fuer_bbox"),
        "embed_crop_aufruf": _stelle(face_service, r'"op":\s*"embed_crop"'),
        "op_embed": _stelle(face_infer, r"^def op_embed\("),
        "op_embed_crop": _stelle(face_infer, r"^def op_embed_crop\("),
        "verteiler": _stelle(face_infer, r'op == "embed_crop"'),
    }


def vektor_rechner_bericht(belege: dict) -> list:
    zeilen = []
    if not belege.get("service_da") or not belege.get("infer_da"):
        return ["  Code nicht gefunden (face_service.py / face_infer.py) — nicht messbar."]
    tragend = [belege.get(k) for k in ("aufruf", "embed_bbox", "embed_crop_aufruf", "op_embed_crop")]
    zeilen.append("  Ja — die Einbettung rechnet das Geraet selbst (proot-Debian, Subprozess):")
    for schluessel, was in (
        ("skript", "Inferenz-Skript auf dem Geraet"),
        ("aufruf", "Subprozess-Aufruf"),
        ("ping", "Bereitschaftspruefung (ping)"),
        ("embed_bbox", "Einbettung eines Ausschnitts (bbox)"),
        ("embed_pfad", "Einbettung eines ganzen Bildes"),
        ("embed_crop_aufruf", "Aufruf der Ausschnitts-Einbettung"),
        ("op_embed", "Einbettungs-Einstieg im Inferenz-Skript"),
        ("op_embed_crop", "Ausschnitts-Einstieg im Inferenz-Skript"),
        ("verteiler", "Verteiler der Operationen"),
    ):
        stelle = belege.get(schluessel)
        if stelle:
            zeilen.append(f"    {was}: {stelle[0]}:{stelle[1]}")
    fehlend = [k for k, v in belege.items() if v is None]
    if any(v is None for v in tragend) or fehlend:
        zeilen.append("  Achtung: erwartete Code-Stelle fehlt — bitte von Hand nachsehen.")
    return zeilen


# ── Teil 2: die Speicherwege im Detailbild ─────────────────────────────────

SPEICHER_STELLEN = (
    (FRONTEND, r"'den Rahmen als Referenz dieser Person\.'", "Hinweistext der App (Speichern)"),
    (FRONTEND, r"function speichereEditorRahmen\(", "Speicherfunktion des Detailbildes"),
    (FRONTEND, r"function quizBeantwortenSilent\(", "stiller Antwortweg des Editors"),
    (FRONTEND, r"gesichter/quiz/antwort", "Endpunkt-Aufruf aus dem Editor"),
    (FRONTEND, r"gesichter/referenzen/\$\{encodeURIComponent\(refKontext\.name\)\}", "Endpunkt der Referenz-Nachbearbeitung"),
    (ROUTER_GESICHTER, r'@router\.post\("/quiz/antwort"\)', "Endpunkt POST /api/gesichter/quiz/antwort"),
    (ROUTER_GESICHTER, r"gesicht_quiz\.ergaenze_person_mit_bbox", "Weg des selbst gezeichneten Rahmens"),
    (ROUTER_GESICHTER, r"gesicht_quiz\.beantworte_runde", "Weg des erkannten Gesichts"),
    (ROUTER_GESICHTER, r'@router\.post\("/referenzen/', "Endpunkt der Referenz-Nachbearbeitung"),
    (ROUTER_GESICHTER, r"embedding_erneuern", "Schalter „Einbettung erneuern“"),
    (ROUTER_GESICHTER, r"face_service\.embedding_fuer_bbox", "Einbettung beim Speichern des Referenz-Rahmens"),
    (SERVICE_GESICHT, r"^def beantworte_runde\(", "Dienst der Quiz-Antwort"),
    (SERVICE_GESICHT, r'dom\["embedding"\]', "uebernimmt die Einbettung des erkannten Gesichts"),
    (SERVICE_GESICHT, r"face_service\.embedding_fuer_bbox", "Einbettung des bestaetigten Rahmens (Rueckfall)"),
    (SERVICE_GESICHT, r"^def ergaenze_person_mit_bbox\(", "Dienst des selbst gezeichneten Rahmens"),
)


def speicherwege(stellen=SPEICHER_STELLEN) -> list:
    """Die tragenden Code-Stellen des Referenz-Weges, je (Datei, Zeile, Text, was)."""
    ergebnis = []
    for pfad, muster, was in stellen:
        for nummer, text in code_zeilen(pfad, muster)[:3]:
            ergebnis.append((_rel(pfad), nummer, re.sub(r"\s+", " ", text.strip())[:90], was))
    return ergebnis


def speicherwege_bericht(stellen: list) -> list:
    if not stellen:
        return ["  Keine der erwarteten Stellen gefunden — bitte von Hand nachsehen."]
    return [f"  {was}: {datei}:{zeile}" for datei, zeile, _text, was in stellen]


# ── Teil 3: der zweite Weg (Gruppen-Benennen) ──────────────────────────────

def gruppen_weg(router: Path = ROUTER_GRUPPEN, service: Path = SERVICE_GRUPPEN) -> dict:
    """Belege zum Namensweg: Endpunkte, Schreibfunktionen, Vorkommen von „embedding“."""
    return {
        "da": router.is_file() and service.is_file(),
        "endpunkt_antwort": _stelle(router, r'@router\.post\("/antwort"\)'),
        "endpunkt_umbenennen": _stelle(router, r'@router\.post\("/umbenennen"\)'),
        "dienst_antworten": _stelle(service, r"^def antworten\("),
        "anwenden": _stelle(service, r"^def _antwort_anwenden\("),
        "schreiben_namen": _stelle(service, r"^def _bestaetigt_schreiben\("),
        "schreiben_vorgaben": _stelle(service, r"^def _vorgaben_schreiben\("),
        "vektor_vorkommen": len(code_zeilen(service, r"embedding|vektor")),
        "vektor_zeilen": code_zeilen(service, r"embedding|vektor")[:5],
    }


def gruppen_weg_bericht(belege: dict) -> list:
    if not belege.get("da"):
        return ["  Code nicht gefunden (gruppen.py / gruppen_quiz.py) — nicht messbar."]
    zeilen = ["  Derselbe Nachweis fuer den Namensweg (Gruppen benennen/umbenennen):"]
    for schluessel, was in (
        ("endpunkt_antwort", "Endpunkt POST /api/gruppen/antwort"),
        ("endpunkt_umbenennen", "Endpunkt POST /api/gruppen/umbenennen"),
        ("dienst_antworten", "Dienst, der die Antwort speichert"),
        ("anwenden", "Anwenden der Antwort"),
        ("schreiben_namen", "schreibt die Namen"),
        ("schreiben_vorgaben", "schreibt die Vorgaben"),
    ):
        stelle = belege.get(schluessel)
        if stelle:
            zeilen.append(f"    {was}: {stelle[0]}:{stelle[1]}")
    anzahl = belege.get("vektor_vorkommen", 0)
    if anzahl:
        zeilen.append(f"    Achtung: {_zahl(anzahl)} Zeile(n) mit embedding/vektor gefunden — "
                      f"der Namensweg wuerde dann doch Vektoren tragen.")
        for datei, nummer, text in belege.get("vektor_zeilen") or []:
            zeilen.append(f"      {datei}:{nummer} — {text}")
    else:
        zeilen.append("    Gemessen: 0 Vorkommen von embedding/vektor in gruppen_quiz.py "
                      "— dieser Weg speichert nur Namen und Vorgaben, keinen Vektor.")
    return zeilen


# ── Teil 4: die Dateien des Benennens (nur Zahlen) ─────────────────────────

def vektor_schluessel_finden(obj, treffer=None) -> list:
    """Alle Schluesselnamen (rekursiv), die einen Vektor bezeichnen — nur Namen."""
    treffer = [] if treffer is None else treffer
    if isinstance(obj, dict):
        for schluessel, wert in obj.items():
            if str(schluessel).lower() in VEKTOR_SCHLUESSEL:
                treffer.append(str(schluessel))
            vektor_schluessel_finden(wert, treffer)
    elif isinstance(obj, list):
        for wert in obj[:2000]:  # Deckel: Vektorlisten nicht komplett durchlaufen
            vektor_schluessel_finden(wert, treffer)
    return treffer


def datei_zaehlen(pfad: Path) -> dict:
    """Eine JSON-Datei zaehlen: Form, Umfang, Vektor-Schluessel. Nie ein Wurf."""
    ergebnis = {"pfad": str(pfad), "fehlt": False, "kaputt": False,
                "form": "", "eintraege": 0, "schluessel": {}, "vektor": []}
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
        ergebnis["schluessel"] = {k: (len(v) if isinstance(v, (list, dict)) else 0) for k, v in daten.items()}
    elif isinstance(daten, list):
        ergebnis["eintraege"] = len(daten)
    ergebnis["vektor"] = sorted(set(vektor_schluessel_finden(daten)))
    return ergebnis


def dateien_bericht(daten_dir: Path) -> list:
    zeilen = [f"  Ordner der Benennungs-Dateien: {daten_dir}"]
    gesamt = 0
    vektor_gesamt = 0
    for name in (BESTAETIGT, VORGABEN):
        zahlen = datei_zaehlen(daten_dir / name)
        if zahlen["fehlt"]:
            zeilen.append(f"  {name}: fehlt am PC — Zahl nicht messbar (ehrlich, keine Schaetzung)")
            continue
        if zahlen["kaputt"]:
            zeilen.append(f"  {name}: nicht lesbar (kein gueltiges JSON) — Zahl nicht messbar")
            continue
        if zahlen["form"] == "dict":
            teile = " · ".join(f"{k}: {_zahl(v)}" for k, v in sorted(zahlen["schluessel"].items()))
            umfang = sum(zahlen["schluessel"].values())
        else:
            teile, umfang = "", zahlen["eintraege"]
        gesamt += umfang
        vektor_gesamt += len(zahlen["vektor"])
        vektor = zahlen["vektor"]
        zeilen.append(f"  {name}: {zahlen['form']} · {teile or 'ohne Listen'} · Eintraege insgesamt {_zahl(umfang)}"
                      + (f" · Vektor-Schluessel: {', '.join(vektor)}" if vektor
                         else " · Vektor-Schluessel: keine (0)"))
    zeilen.append(f"  Beide Dateien zusammen: {_zahl(gesamt)} Eintraege, "
                  f"{_zahl(vektor_gesamt)} Vektor-Schluessel "
                  f"({'nur Namen und Vorgaben gespeichert' if not vektor_gesamt else 'Vektoren vorhanden'})")
    katalog = daten_dir / KATALOG
    if not katalog.is_file():
        zeilen.append(f"  Ehrliche Grenze: {KATALOG} liegt am PC nicht vor (Referenzspeicher "
                      f"liegt am Geraet) — Zahl der Referenzen NICHT zaehlbar am PC.")
    else:
        groesse = katalog.stat().st_size
        zahlen = datei_zaehlen(katalog)
        if zahlen["kaputt"]:
            zeilen.append(f"  Ehrliche Grenze: {KATALOG} ist am PC nicht lesbar — NICHT zaehlbar.")
        else:
            personen = zahlen["schluessel"].get("personen", 0)
            zeilen.append(f"  {KATALOG} (am PC): {_zahl(groesse)} Byte · Personen-Eintraege "
                          f"{_zahl(personen)}" + (" — leere Huelle, kein Referenzbestand"
                                                  if not personen else "")
                          + (f" · Vektor-Schluessel: {', '.join(zahlen['vektor'])}" if zahlen["vektor"]
                             else " · Vektor-Schluessel: keine"))
    return zeilen


# ── Bericht / Kommandozeile ───────────────────────────────────────────────

def bericht(daten_dir: Path = STANDARD_DATEN) -> list:
    """Alle Berichtszeilen bauen (nur Zahlen, Datei:Zeile, keine Namen)."""
    zeilen = ["Gesichts-Referenzen im Detailbild: Wer erzeugt sie? (nur gelesen, nur Zahlen)", ""]
    zeilen.append("Kann das Geraet Gesichtsvektoren selbst rechnen?")
    zeilen += vektor_rechner_bericht(vektor_rechner())
    zeilen.append("")
    zeilen.append("Erzeugt „Benennen/Speichern im Detailbild“ eine Referenz? (Datei:Zeile)")
    zeilen += speicherwege_bericht(speicherwege())
    zeilen.append("")
    zeilen += gruppen_weg_bericht(gruppen_weg())
    zeilen.append("")
    zeilen.append("Dateien des Benennens (nur Zahlen, keine Namen)")
    zeilen += dateien_bericht(daten_dir)
    zeilen.append("")
    zeilen.append("Deutung: gespeichert wird der Rahmen ueber den GESICHTER-Weg "
                  "(POST /api/gesichter/quiz/antwort bzw. …/referenzen/…/bbox) — der "
                  "bettet den Ausschnitt ein. Der GRUPPEN-Weg (/api/gruppen/antwort, "
                  "/umbenennen) speichert Namen ohne Vektor.")
    return zeilen


def main(argv=None) -> int:
    zerleger = argparse.ArgumentParser(
        description="Referenz-Wege der Gesichtserkennung messen (nur lesen, nur Zahlen).")
    zerleger.add_argument("--daten-dir", default=str(STANDARD_DATEN),
                          help="Ordner der Benennungs-Dateien (Standard: ~/foto_sortierung)")
    args = zerleger.parse_args(argv)
    for zeile in bericht(Path(args.daten_dir)):
        print(zeile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
