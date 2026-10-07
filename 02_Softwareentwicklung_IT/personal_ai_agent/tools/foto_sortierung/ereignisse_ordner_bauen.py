"""Anlässe für die Sammlung „Bilder & Videos" (Issue #4 A1, 07.10.2026).

Warum:
  Die Erzähl-Diashow kennt bisher nur die Anlässe des Upload-Stapels
  (``ereignisse.jsonl``, 2.127 Anlässe) und die Fotobuch-Seiten. Die Sammlung
  „Bilder & Videos" (11.630 Einträge, Sebastians eigene Ordner, darin die
  Urlaube) hatte **null** Anlässe — „erzähl mir von meinem Urlaub 2000" fand
  deshalb nichts. Dieses Werkzeug bildet aus der Sammlung Anlässe im Format der
  Erzähl-Diashow und schreibt sie in eine **eigene** Datei
  ``~/foto_sortierung/ordner_ereignisse.jsonl`` — die vorhandenen Dateien bleiben
  unberührt.

Datum je Datei (Reihenfolge, so entschieden):
  1. **EXIF-Aufnahmezeit** aus dem Gesichterlauf (``metadaten.aufnahme`` in den
     Vektordateien — jedes Foto wurde dort einmal geladen; kein neuer Download).
     Kamera-Uhr mit Uhrzeit; übersteht Bearbeiten und Umbenennen.
  2. **Dateiname** (``IMG_20190705_143000``, ``IMG-20190705-WA0001`` …), mit
     Uhrzeit, wenn sie im Namen steht. Bei Kamera-Dateien meist gleich EXIF;
     WhatsApp entfernt EXIF, dort trägt nur der Name das Datum.
  3. **pCloud ``modified``** (falls die Planzeile oder ``--liste`` es liefert).
     ``created`` ist nur der Upload und wird nie benutzt.
  4. Sonst nur das **Jahr** aus dem Ordnerpfad (``…/Konzerte_Party/2016``), sonst
     das Plan-Jahr — dann ohne genaues Datum.
  Plausibel ist ein Datum ab 1990 bis heute; ältere oder künftige Werte (die
  Unsinns-Jahre 1901–1970 aus Dateinamen, Kamera-Uhren auf 1970) fallen auf die
  nächste Quelle zurück. Trägt der Ordnerpfad ein Jahr und weicht das Datum um
  **mehr als ein Jahr** davon ab (Scan-/Bearbeitungsdatum), gewinnt das
  Ordnerjahr — ein Jahr Toleranz, damit Silvesterfotos nach Mitternacht bleiben.

Bündelung (so entschieden):
  Je **Handordner** (``von_ordner``) chronologisch; ein neuer Anlass beginnt,
  wenn zwischen zwei Aufnahmen mehr als ``--luecke-stunden`` (Standard 18)
  liegen. Eine Reise mit Fotos an jedem Tag bleibt so ein Anlass (Nachtpause
  ~12 h), zwei Konzerte an zwei Abenden werden getrennt (~24 h). Dateien nur mit
  Jahr bilden je Ordner und Jahr einen Anlass „ohne genaues Datum". Dateien, die
  schon in einer anderen Ereignis-Datei stehen (Fotobuch, Upload-Stapel), werden
  übersprungen — kein Bild steht doppelt im Erzählen.

Ausgabe (JSONL, je Zeile ein Anlass, ASCII, schlüsselsortiert)::

    {"anlass_id", "kennung": "O-<kleinste fileid>", "art": "ereignis",
     "sammlung": "bilder_videos", "anzahl_dateien", "videos",
     "datei_kennungen" (chronologisch), "datum", "bis", "jahr",
     "event" (Titel: Ordnername · Zeitraum), "event_quelle": "ordner",
     "event_stufe": null, "thema" (Ordnername), "kategorie" (erste Ordnerebene),
     "quellen": {"datum": {Quelle: Anzahl}, "dateien": …}, "stand", "ziel_ordner": null}

  Die Kennung hängt nur an der kleinsten fileid des Anlasses und damit nicht an
  der Reihenfolge. Die Erzähl-Diashow liest die Datei neben ``ereignisse.jsonl``
  (``erzaehl_service``) und sortiert beide chronologisch zusammen.

Datenschutz und Regeln:
  * Kein Netz, kein Modell, keine Bilder. Gelesen werden nur lokale Dateien.
  * Konsole nur **Zahlen** — keine Ordner-, Datei- oder Personennamen.
  * Ziel im Repo -> Exit 2. Standard ist der Trockenlauf; ``--schreiben``
    schreibt atomar; gleicher Inhalt -> Datei bleibt unangetastet (wiederholbar).
  * ``--senden`` legt die Datei per adb nach ``/sdcard/Download`` (die App
    übernimmt sie beim Start, ``uebergabe_uebernehmen``).

Aufruf (PowerShell, aus dem Projektordner)::

    & backend\\.venv\\Scripts\\python.exe tools\\foto_sortierung\\ereignisse_ordner_bauen.py
    & backend\\.venv\\Scripts\\python.exe tools\\foto_sortierung\\ereignisse_ordner_bauen.py --senden

Exit: 0 ok, 1 Übertragung fehlgeschlagen, 2 Aufruf/Schutz, 3 Plan fehlt/kaputt.
"""
from __future__ import annotations

import argparse
import datetime
import email.utils
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections import Counter
from typing import Callable, Dict, Iterable, List, Optional, Tuple

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
STANDARD_PLAN = os.path.join(STANDARD_BASIS, "sortierplan_bildervideos.json")
STANDARD_VEKTOREN = ("personen_vektoren_n0929_bildervideos.jsonl", "video_vektoren_bildervideos.jsonl")
STANDARD_OHNE = ("ereignisse.jsonl", "fotobuch_ereignisse.jsonl")
DATEINAME = "ordner_ereignisse.jsonl"
STANDARD_AUSGABE = os.path.join(STANDARD_BASIS, DATEINAME)

WURZEL = "Bilder & Videos"
LUECKE_STUNDEN = 18
FRUEHESTES_JAHR = 1990            # Digitalfotos/Dateinamen davor: Unsinn (1901–1970)
FRUEHESTES_ORDNERJAHR = 1900      # von Hand benannte Ordner dürfen älter sein (Scans)
ORDNERJAHR_TOLERANZ = 1
VIDEO_ENDUNGEN = (".mp4", ".mov", ".3gp", ".mkv", ".avi", ".m4v")
QUELLEN = ("exif", "dateiname", "geaendert", "ordnerjahr", "planjahr", "ohne")

# Datum im Dateinamen, optional mit Uhrzeit (auch Millisekunden wie bei PXL_…).
_NAME_DATUM = re.compile(
    r"(?<!\d)((?:19|20)\d{2})[-_.]?(\d{2})[-_.]?(\d{2})"
    r"(?:[-_ T.]?(\d{2})[-_.:]?(\d{2})[-_.:]?(\d{2})(?:\d{1,3})?)?(?!\d)")


def _anlass_namen():
    """``anlass_namen`` (Zeitraum-Text, Handordner-Zerlegung) wiederverwenden statt nachbauen."""
    spez = importlib.util.spec_from_file_location("anlass_namen", os.path.join(HIER, "anlass_namen.py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)  # type: ignore[union-attr]
    return modul


_AN = _anlass_namen()


# ── Kleine Helfer ────────────────────────────────────────────────────────────

def _text(wert) -> str:
    return wert.strip() if isinstance(wert, str) else ""


def _als_int(wert) -> Optional[int]:
    if isinstance(wert, bool):
        return None
    if isinstance(wert, int):
        return wert
    if isinstance(wert, float) and wert.is_integer():
        return int(wert)
    if isinstance(wert, str) and wert.strip().isdigit():
        return int(wert.strip())
    return None


def _zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# ── 1. Datum je Datei (reine Funktionen) ─────────────────────────────────────

def datum_aus_exif(wert) -> Optional[Tuple[datetime.datetime, bool]]:
    """``"JJJJ-MM-TTTHH:MM:SS"`` (Gesichterlauf) -> ``(Zeitpunkt, mit_uhrzeit)``."""
    text = _text(wert)
    if not text:
        return None
    try:
        return datetime.datetime.fromisoformat(text.replace(" ", "T")[:19]), True
    except ValueError:
        return None


def datum_aus_name(name) -> Optional[Tuple[datetime.datetime, bool]]:
    """Datum (und Uhrzeit, falls vorhanden) aus dem Dateinamen."""
    treffer = _NAME_DATUM.search(_text(name))
    if not treffer:
        return None
    j, m, t, hh, mm, ss = treffer.groups()
    try:
        if hh is not None:
            return datetime.datetime(int(j), int(m), int(t), int(hh), int(mm), int(ss)), True
        return datetime.datetime(int(j), int(m), int(t), 12, 0, 0), False
    except ValueError:                   # 2019-13-45 oder 25:61 -> kein Datum
        if hh is not None:
            try:
                return datetime.datetime(int(j), int(m), int(t), 12, 0, 0), False
            except ValueError:
                return None
        return None


def datum_aus_geaendert(wert) -> Optional[Tuple[datetime.datetime, bool]]:
    """pCloud ``modified`` (``"Thu, 21 Feb 2019 10:00:00 +0000"``) oder ISO-Text."""
    text = _text(wert)
    if not text:
        return None
    try:
        zeit = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        zeit = None
    if zeit is None:
        try:
            zeit = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return zeit.replace(tzinfo=None), True


def ordner_teile(von_ordner) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """``(kategorie, name, ordner_jahr)`` aus dem Handordner-Pfad (Wurzel „Bilder & Videos" fällt weg)."""
    segmente = [s.strip() for s in _text(von_ordner).replace("\\", "/").split("/") if s.strip()]
    if segmente and segmente[0].casefold() == WURZEL.casefold():
        segmente = segmente[1:]
    if not segmente:
        return None, None, None
    name, jahr = _AN.handordner_zerlegen("/".join(segmente))
    erste = segmente[0]
    kategorie = None if _AN.JAHR_MUSTER.match(erste) else re.sub(r"\s+", " ", erste.replace("_", " ")).strip()
    return kategorie or None, name, jahr


def datum_waehlen(exif, name, geaendert, ordner_jahr: Optional[int], plan_jahr: Optional[int],
                  heute: datetime.date) -> Dict:
    """Ein Datum je Datei nach der festen Reihenfolge (siehe Kopf). **Wirft nie.**

    Rückgabe ``{"zeit": datetime|None, "mit_uhrzeit": bool, "jahr": int|None,
    "quelle": …, "verworfen": int (unplausible Kandidaten), "ordnerjahr_gewinnt": bool}``.
    """
    verworfen = 0
    for quelle, kandidat in (("exif", datum_aus_exif(exif)), ("dateiname", datum_aus_name(name)),
                             ("geaendert", datum_aus_geaendert(geaendert))):
        if kandidat is None:
            continue
        zeit, mit_uhrzeit = kandidat
        if not (FRUEHESTES_JAHR <= zeit.year and zeit.date() <= heute):
            verworfen += 1
            continue
        if ordner_jahr is not None and abs(zeit.year - ordner_jahr) > ORDNERJAHR_TOLERANZ:
            return {"zeit": None, "mit_uhrzeit": False, "jahr": ordner_jahr, "quelle": "ordnerjahr",
                    "verworfen": verworfen, "ordnerjahr_gewinnt": True}
        return {"zeit": zeit, "mit_uhrzeit": mit_uhrzeit, "jahr": zeit.year, "quelle": quelle,
                "verworfen": verworfen, "ordnerjahr_gewinnt": False}
    for quelle, jahr in (("ordnerjahr", ordner_jahr), ("planjahr", plan_jahr)):
        if jahr is not None and FRUEHESTES_ORDNERJAHR <= jahr <= heute.year:
            return {"zeit": None, "mit_uhrzeit": False, "jahr": jahr, "quelle": quelle,
                    "verworfen": verworfen, "ordnerjahr_gewinnt": False}
    return {"zeit": None, "mit_uhrzeit": False, "jahr": None, "quelle": "ohne",
            "verworfen": verworfen, "ordnerjahr_gewinnt": False}


# ── 2. Eingaben lesen (tolerant, nie raten) ─────────────────────────────────

def _jsonl(pfad: str) -> Iterable[Dict]:
    with open(pfad, encoding="utf-8") as datei:
        for zeile in datei:
            zeile = zeile.strip()
            if not zeile:
                continue
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                continue
            if isinstance(eintrag, dict):
                yield eintrag


def plan_lesen(pfad: str) -> List[Dict]:
    """``zuege[]`` aus dem Sortierplan. Fehlt die Datei oder das Feld -> ``ValueError``."""
    with open(pfad, encoding="utf-8") as datei:
        daten = json.load(datei)
    zuege = daten.get("zuege") if isinstance(daten, dict) else daten
    if not isinstance(zuege, list):
        raise ValueError("Sortierplan ohne Feld 'zuege'.")
    return [z for z in zuege if isinstance(z, dict)]


def aufnahmen_lesen(pfade: Iterable[str]) -> Dict[int, str]:
    """``{fileid: aufnahme}`` aus den Vektordateien des Gesichterlaufs (nur ``metadaten.aufnahme``).

    Video-Standbilder (``"9#t=2"``) zählen für ihre fileid. Fehlende Dateien
    werden übersprungen; die erste Aufnahmezeit je fileid gilt.
    """
    aufnahmen: Dict[int, str] = {}
    for pfad in pfade:
        if not pfad or not os.path.isfile(pfad):
            continue
        for zeile in _jsonl(pfad):
            fileid = _als_int(str(zeile.get("bild_id") or "").split("#", 1)[0])
            metadaten = zeile.get("metadaten")
            aufnahme = metadaten.get("aufnahme") if isinstance(metadaten, dict) else None
            if fileid and isinstance(aufnahme, str) and aufnahme.strip() and fileid not in aufnahmen:
                aufnahmen[fileid] = aufnahme.strip()
    return aufnahmen


def geaendert_lesen(pfad: Optional[str]) -> Dict[int, str]:
    """Optionale Liste ``{fileid, modified}`` je Zeile (JSONL) -> ``{fileid: modified}``."""
    ergebnis: Dict[int, str] = {}
    if not pfad or not os.path.isfile(pfad):
        return ergebnis
    for zeile in _jsonl(pfad):
        fileid = _als_int(zeile.get("fileid"))
        wert = zeile.get("modified")
        if fileid and isinstance(wert, str) and wert.strip():
            ergebnis[fileid] = wert.strip()
    return ergebnis


def vergebene_lesen(pfade: Iterable[str]) -> set:
    """fileids, die schon in einer anderen Ereignis-Datei stehen (Fotobuch, Upload-Stapel)."""
    vergeben: set = set()
    for pfad in pfade:
        if not pfad or not os.path.isfile(pfad):
            continue
        for zeile in _jsonl(pfad):
            for wert in zeile.get("datei_kennungen") or []:
                zahl = _als_int(wert)
                if zahl:
                    vergeben.add(zahl)
    return vergeben


# ── 3. Anlässe bilden (rein) ─────────────────────────────────────────────────

def eintraege_bauen(zuege: List[Dict], aufnahmen: Dict[int, str], geaendert: Dict[int, str],
                    vergeben: set, heute: datetime.date) -> Tuple[List[Dict], Counter]:
    """Planzeilen -> Einträge mit gewähltem Datum. Zähler nur als Zahlen."""
    zahlen: Counter = Counter()
    gesehen: set = set()
    eintraege: List[Dict] = []
    for zug in zuege:
        zahlen["planzeilen"] += 1
        fileid = _als_int(zug.get("fileid"))
        if not fileid:
            zahlen["ohne_fileid"] += 1
            continue
        if fileid in gesehen:
            zahlen["doppelt"] += 1
            continue
        gesehen.add(fileid)
        if fileid in vergeben:
            zahlen["schon_in_anderen_anlaessen"] += 1
            continue
        name = _text(zug.get("von_name"))
        ordner = _text(zug.get("von_ordner"))
        kategorie, ordnername, ordner_jahr = ordner_teile(ordner)
        wahl = datum_waehlen(aufnahmen.get(fileid), name, geaendert.get(fileid) or zug.get("modified"),
                             ordner_jahr, _als_int(zug.get("jahr")), heute)
        zahlen["quelle_" + wahl["quelle"]] += 1
        zahlen["unplausibel_verworfen"] += wahl["verworfen"]
        zahlen["ordnerjahr_gewinnt"] += 1 if wahl["ordnerjahr_gewinnt"] else 0
        video = name.lower().endswith(VIDEO_ENDUNGEN)
        zahlen["videos" if video else "fotos"] += 1
        eintraege.append({"fileid": fileid, "ordner": ordner, "kategorie": kategorie,
                          "name": ordnername, "video": video, **wahl})
    return eintraege, zahlen


def _gruppe_zu_knoten(gruppe: List[Dict], stand: str) -> Dict:
    erster = gruppe[0]
    zeiten = [e["zeit"] for e in gruppe if e["zeit"] is not None]
    jahre = [e["jahr"] for e in gruppe if e["jahr"] is not None]
    jahr = zeiten[0].year if zeiten else (min(jahre) if jahre else None)
    zeitraum = _AN.zeitraum_text(sorted({(z.year, z.month) for z in zeiten}), jahr)
    name = erster["name"]
    titel = " · ".join(t for t in (name, zeitraum) if t) or "Ohne Titel"
    kennung = "O-" + str(min(e["fileid"] for e in gruppe))
    return {
        "anlass_id": kennung, "kennung": kennung, "art": "ereignis", "sammlung": "bilder_videos",
        "anzahl_dateien": len(gruppe), "videos": sum(1 for e in gruppe if e["video"]),
        "datei_kennungen": [e["fileid"] for e in gruppe],
        "datum": zeiten[0].date().isoformat() if zeiten else None,
        "bis": zeiten[-1].date().isoformat() if zeiten else None,
        "jahr": jahr, "event": titel, "event_quelle": "ordner", "event_stufe": None,
        "thema": name, "kategorie": erster["kategorie"],
        "quellen": {"datum": dict(sorted(Counter(e["quelle"] for e in gruppe).items())),
                    "dateien": "sortierplan_bildervideos.json:zuege"},
        "stand": stand, "ziel_ordner": None,
    }


def anlaesse_bilden(eintraege: List[Dict], luecke_stunden: float = LUECKE_STUNDEN,
                    stand: str = "") -> List[Dict]:
    """Je Handordner chronologisch, neuer Anlass ab ``luecke_stunden`` Pause (siehe Kopf).

    Einträge nur mit Jahr bilden je Ordner und Jahr einen Anlass ohne genaues
    Datum, Einträge ganz ohne Datum je Ordner einen. Ergebnis sortiert nach
    (Jahr, Datum, Kennung); undatierte Anlässe stehen am Ende ihres Jahres.
    """
    if not luecke_stunden or luecke_stunden <= 0:
        raise ValueError("--luecke-stunden muss größer als 0 sein.")
    grenze = datetime.timedelta(hours=luecke_stunden)
    je_ordner: Dict[str, List[Dict]] = {}
    for eintrag in eintraege:
        je_ordner.setdefault(eintrag["ordner"], []).append(eintrag)
    knoten: List[Dict] = []
    for ordner in sorted(je_ordner):
        liste = je_ordner[ordner]
        datiert = sorted((e for e in liste if e["zeit"] is not None), key=lambda e: (e["zeit"], e["fileid"]))
        gruppe: List[Dict] = []
        for eintrag in datiert:
            if gruppe and eintrag["zeit"] - gruppe[-1]["zeit"] > grenze:
                knoten.append(_gruppe_zu_knoten(gruppe, stand))
                gruppe = []
            gruppe.append(eintrag)
        if gruppe:
            knoten.append(_gruppe_zu_knoten(gruppe, stand))
        nur_jahr: Dict[Optional[int], List[Dict]] = {}
        for eintrag in liste:
            if eintrag["zeit"] is None:
                nur_jahr.setdefault(eintrag["jahr"], []).append(eintrag)
        for jahr in sorted(nur_jahr, key=lambda j: (j is None, j or 0)):
            knoten.append(_gruppe_zu_knoten(sorted(nur_jahr[jahr], key=lambda e: e["fileid"]), stand))
    knoten.sort(key=lambda k: (k["jahr"] is None, k["jahr"] or 0, k["datum"] or "9999", k["kennung"]))
    return knoten


def zahlen_text(knoten: List[Dict], zahlen: Counter) -> List[str]:
    """Bericht — **nur Zahlen**, keine Namen, keine Kennungen."""
    jahre = [k["jahr"] for k in knoten if k["jahr"] is not None]
    groessen = sorted(k["anzahl_dateien"] for k in knoten)
    zeilen = [
        f"Planzeilen:            {_zahl(zahlen['planzeilen'])} (ohne fileid {_zahl(zahlen['ohne_fileid'])}, "
        f"doppelt {_zahl(zahlen['doppelt'])}, schon in anderen Anlässen {_zahl(zahlen['schon_in_anderen_anlaessen'])})",
        f"aufgenommen:           {_zahl(zahlen['fotos'])} Fotos, {_zahl(zahlen['videos'])} Videos",
        "Datum aus:             " + ", ".join(f"{q} {_zahl(zahlen['quelle_' + q])}" for q in QUELLEN),
        f"unplausibel verworfen: {_zahl(zahlen['unplausibel_verworfen'])} Kandidaten (vor {FRUEHESTES_JAHR} "
        f"oder in der Zukunft); Ordnerjahr gewinnt: {_zahl(zahlen['ordnerjahr_gewinnt'])}",
        f"Anlässe:               {_zahl(len(knoten))} (mit Datum {_zahl(sum(1 for k in knoten if k['datum']))}, "
        f"nur Jahr {_zahl(sum(1 for k in knoten if not k['datum'] and k['jahr']))}, "
        f"ohne Jahr {_zahl(sum(1 for k in knoten if k['jahr'] is None))})",
    ]
    if jahre:
        zeilen.append(f"Jahre:                 {min(jahre)}–{max(jahre)}")
    if groessen:
        zeilen.append(f"Dateien je Anlass:     {_zahl(groessen[0])} bis {_zahl(groessen[-1])}, "
                      f"Mitte {_zahl(groessen[len(groessen) // 2])}")
    return zeilen


# ── 4. Schreiben, Senden ─────────────────────────────────────────────────────

def _im_repo(pfad: str) -> bool:
    ziel = os.path.normcase(os.path.abspath(pfad))
    repo = os.path.normcase(os.path.abspath(REPO))
    try:
        return os.path.commonpath([ziel, repo]) == repo
    except ValueError:                        # anderes Laufwerk
        return False


def knoten_zeile(knoten: Dict) -> str:
    return json.dumps(knoten, ensure_ascii=True, sort_keys=True)


def schreiben(pfad: str, knoten: List[Dict]) -> bool:
    """Atomar schreiben. ``False``, wenn der Inhalt schon genau so dasteht (Datei unangetastet)."""
    inhalt = "".join(knoten_zeile(k) + "\n" for k in knoten)
    if os.path.isfile(pfad):
        with open(pfad, encoding="utf-8", newline="") as datei:
            if datei.read() == inhalt:
                return False
    os.makedirs(os.path.dirname(os.path.abspath(pfad)), exist_ok=True)
    temp = pfad + ".tmp"
    try:
        with open(temp, "w", encoding="utf-8", newline="\n") as datei:
            datei.write(inhalt)
        os.replace(temp, pfad)
    except Exception:
        if os.path.exists(temp):
            os.remove(temp)                   # nur die eigene temp-Datei
        raise
    return True


def _ausfuehren(befehl: List[str]) -> Tuple[int, str]:
    try:
        lauf = subprocess.run(befehl, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return 127, problem.__class__.__name__
    return lauf.returncode, (lauf.stdout or "") + (lauf.stderr or "")


def _ohne_stand(knoten: List[Dict]) -> List[Dict]:
    return [{k: v for k, v in eintrag.items() if k != "stand"} for eintrag in knoten]


def _alter_stand(pfad: str, knoten: List[Dict]) -> Optional[str]:
    """Stand der vorhandenen Datei übernehmen, wenn sich sonst nichts geändert hat (wiederholbar)."""
    if not os.path.isfile(pfad):
        return None
    alt = list(_jsonl(pfad))
    if alt and _ohne_stand(alt) == _ohne_stand(knoten):
        return alt[0].get("stand")
    return None


def main(argv=None, heute: Optional[datetime.date] = None, ausfuehren: Callable = _ausfuehren) -> int:
    p = argparse.ArgumentParser(description="Anlässe für „Bilder & Videos“ (nur Zahlen auf der Konsole).")
    p.add_argument("--plan", default=STANDARD_PLAN)
    p.add_argument("--vektoren", nargs="*", default=None,
                   help="Vektordateien des Gesichterlaufs (EXIF-Aufnahmezeit); Standard: beide der Sammlung")
    p.add_argument("--liste", default=None, help="optional: JSONL {fileid, modified} (pCloud)")
    p.add_argument("--ohne", nargs="*", default=None,
                   help="Ereignis-Dateien, deren Bilder übersprungen werden (Standard: Upload-Stapel, Fotobuch)")
    p.add_argument("--ausgabe", default=STANDARD_AUSGABE)
    p.add_argument("--luecke-stunden", type=float, default=LUECKE_STUNDEN)
    p.add_argument("--schreiben", action="store_true")
    p.add_argument("--senden", action="store_true", help="schreiben und per adb nach /sdcard/Download")
    a = p.parse_args(argv)

    if _im_repo(a.ausgabe):
        print("FEHLER: Ziel liegt im Repo - es wird nichts geschrieben.")
        return 2
    if a.luecke_stunden <= 0:
        print("FEHLER: --luecke-stunden muss größer als 0 sein.")
        return 2
    basis = os.path.dirname(os.path.abspath(a.plan))
    vektoren = a.vektoren if a.vektoren is not None else [os.path.join(basis, n) for n in STANDARD_VEKTOREN]
    ohne = a.ohne if a.ohne is not None else [os.path.join(basis, n) for n in STANDARD_OHNE]
    try:
        zuege = plan_lesen(a.plan)
    except (OSError, ValueError):
        print("FEHLER: Sortierplan fehlt oder ist nicht lesbar.")
        return 3

    heute = heute or datetime.date.today()
    eintraege, zahlen = eintraege_bauen(zuege, aufnahmen_lesen(vektoren), geaendert_lesen(a.liste),
                                        vergebene_lesen(ohne), heute)
    knoten = anlaesse_bilden(eintraege, a.luecke_stunden)
    stand = _alter_stand(a.ausgabe, knoten) or datetime.datetime.now().isoformat(timespec="seconds")
    for eintrag in knoten:
        eintrag["stand"] = stand
    for zeile in zahlen_text(knoten, zahlen):
        print(zeile)

    if not (a.schreiben or a.senden):
        print("Trockenlauf - nichts geschrieben. Mit --schreiben bzw. --senden ausführen.")
        return 0
    geaendert = schreiben(a.ausgabe, knoten)
    print(f"{'geschrieben' if geaendert else 'unverändert'}: {DATEINAME} ({_zahl(len(knoten))} Anlässe, außerhalb des Repos)")
    if a.senden:
        groesse = os.path.getsize(a.ausgabe)
        c1, _ = ausfuehren(["adb", "push", a.ausgabe, f"/sdcard/Download/{DATEINAME}"])
        c2, aus = ausfuehren(["adb", "shell", "stat", "-c", "%s", f"/sdcard/Download/{DATEINAME}"])
        if c1 != 0 or c2 != 0 or aus.strip() != str(groesse):
            print("FEHLER: Übertragung aufs Handy fehlgeschlagen (Kabel? USB-Debugging?)")
            return 1
        print("gesendet. Beim nächsten App-Start stehen die Anlässe in 📖 Erzählen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
