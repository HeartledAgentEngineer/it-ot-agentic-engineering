"""Themen-Stufe: Vorschaubilder in Stapeln holen, Kontaktboegen je Tag/Anlass bauen.

Was dieses Werkzeug tut (Nachtlauf-Schritt N4, 27.09.2026):
  Es liest den Sortierschluessel (CSV aus Stufe 1) und gruppiert die Dateien
  eines Jahres zu **Anlaessen** — Sitzungen innerhalb eines Tages. Fuer jeden
  Anlass holt es die **Vorschaubilder** ueber die pCloud-API (`getthumbs`,
  type=jgp, base64) und legt daraus einen **Kontaktbogen** (JPEG-Kacheln mit
  Nummern 1..n) samt Zuordnungs-JSON ab. Der Vision-Blick spaeter sieht EINEN
  Bogen statt hundert Bilder — das ist die Kostengrenze der Themen-Stufe.

Die Anlass-Regel (warum so):
  * Gleiche Minute = immer derselbe Anlass (Garantie, aus dem Plan:
    "Thema je Anlass statt je Bild (gleiche Minute = gleicher Anlass)").
  * Zusaetzlich bilden Aufnahmen bis zu ``LUECKE_MINUTEN`` (Standard 30)
    Abstand EINE Sitzung — sonst waere der Anlass faktisch das Einzelbild und
    der Vision-Call je Anlass haette keinen Vorteil. Ueber ``--luecke 1``
    laesst sich auf Minutengranularitaet zurueckstellen.
  * Dateien ohne Uhrzeit im Namen (WhatsApp-Empfang: ``IMG-…-WA0001.jpg``)
    kommen in einen eigenen Anlass am Tagesende ("ohne Uhrzeit").
  * Ein Anlass zaehlt pro Tag; eine Sitzung ueber Mitternacht wird am
    Tageswechsel getrennt (dokumentiert, nicht umgangen).

Live geprueft (27.09.2026, eapi.pcloud.com):
  * ``getthumbs`` liefert eine Textzeile je Datei:
    ``fileid|0|86x120|data:image/jpeg;base64,…`` — KEINE Binaerdaten.
    ``type=png`` scheitert bei diesem Konto (Code 5002), deshalb ``type=jgp``.
  * Mehrere fileids in EINEM Aufruf sind erlaubt (Stapel): 40 ids -> 40 Zeilen,
    ~1 s. Die Zeilen kommen nicht garantiert in Anfrage-Reihenfolge — hier
    wird deshalb ueber die fileid zugeordnet, nie ueber die Position.
  * Videos (mp4) und HEIC bekommen ebenfalls ein JPEG-Vorschaubild geliefert.
    Videos werden trotzdem mit Kennzeichen "VIDEO" markiert (ist_video im
    JSON); ein echter erster Frame via ffmpeg ist ein spaeterer Schritt.

Regeln, die das Werkzeug einhaelt:
  * NUR LESEND: listfolder + getthumbs. Kein Schreiben in die pCloud, kein
    Loeschen, kein rekursiver Vollscan (ein Ordner = ein listfolder).
  * Ausgabe NUR nach ``~/foto_sortierung/boegen/<Jahr>/`` (nie ins Repo, nie
    in die pCloud) — dort liegen private Dateinamen, deshalb ausserhalb.
  * Der Token bleibt ein Geheimnis: Er wird nie ausgegeben, nie geloggt und
    aus jeder Fehlermeldung entfernt (``ohne_token``).
  * Idempotent: Ein vorhandener Bogen (JPEG + JSON) wird uebersprungen; das
    Werkzeug darf beliebig oft laufen, ohne etwas doppelt anzulegen.
  * ``--trocken`` und ``--nur-liste`` holen NICHTS und schreiben NICHTS
    (kein API-Aufruf, kein Token noetig).

Aufruf (venv des Backends, enthaelt httpx + Pillow)::

    cd backend
    .venv/Scripts/python ../tools/foto_sortierung/foto_themen.py \\
        --jahr 2025 --limit 3 --trocken        # zeigen, nichts holen
    .venv/Scripts/python ../tools/foto_sortierung/foto_themen.py \\
        --jahr 2025 --anlass 2025-06-06_Anlass-01   # EINEN Anlass bauen
"""

from __future__ import annotations

import argparse
import base64
import csv
import datetime
import importlib.util
import io
import json
import math
import os
import re
import time

import httpx
from PIL import Image, ImageDraw, ImageFont

# ── Nachbarmodule per Pfad laden (das Werkzeug liegt ausserhalb des Backends) ─

HIER = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HIER))            # .../personal_ai_agent
ENV_PFAD = os.path.join(REPO, "backend", ".env")


def _modul_aus_pfad(pfad: str, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    if spez is None or spez.loader is None:
        raise RuntimeError(f"Modul nicht gefunden: {pfad}")
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


# Sortierschluessel: Datum-aus-Name und Plausibilitaets-Pruefung werden
# wiederverwendet statt doppelt gebaut (reine Funktionen aus Stufe 1).
_sort = _modul_aus_pfad(os.path.join(HIER, "sortierschluessel.py"),
                        "sortierschluessel")
# Token-Leser der Selbstheilung — liest PCLOUD_TOKEN/PCLOUD_HOST ohne Ausgabe.
_token_werkzeug = _modul_aus_pfad(
    os.path.join(HIER, "..", "pcloud", "pcloud_token_erneuern.py"),
    "pcloud_token_erneuern")


# ── Feste Werte ────────────────────────────────────────────────────────────

STANDARD_CSV = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                            "sortierschluessel.csv")
STANDARD_BOEGEN = os.path.join(os.path.expanduser("~"), "foto_sortierung",
                               "boegen")

# Anlass-Regel: gleiche Minute = ein Anlass; neue Sitzung ab dieser Luecke.
LUECKE_MINUTEN = 30

# Vorschaubilder: erlaubte Groessen laut pCloud-Doku; angefragt wird JPEG,
# weil type=png bei diesem Konto mit Code 5002 scheitert (live geprueft).
ERLAUBTE_GROESSEN = ("32x32", "120x120")
STANDARD_GROESSE = "120x120"

# Stapelgroesse je getthumbs-Aufruf (live: 40 ids gingen in ~1 s; 25 laesst
# Reserve) und Wiederholungen bei Netzfehlern.
MAX_PRO_STAPEL = 25
VERSUCHE = 3
PAUSE_SEKUNDEN = 0.8
TIMEOUT_SEKUNDEN = 30.0
STANDARD_HOST = "eapi.pcloud.com"

VIDEO_ENDUNGEN = (".mp4", ".3gp", ".mov", ".avi", ".mkv")

# Schriften: erst Windows-Standardschriften, dann Linux/DejaVu, dann Notnagel.
SCHRIFT_PFADE = (
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


class FotoThemenFehler(Exception):
    """Fehler dieses Werkzeugs — die Meldung enthaelt nie den Token."""


class FotoThemenNetzfehler(FotoThemenFehler):
    """Netz-/Transportfehler — darf wiederholt werden (max. VERSUCHE)."""


def ohne_token(text: str, token: str) -> str:
    """Den Token aus einem Text entfernen, falls er hineingeraten ist.

    Letzte Verteidigungslinie wie im pcloud_service: Selbst wenn eine fremde
    Fehlermeldung die volle URL samt auth enthielte, wird sie hier entschaerft.
    """
    if token and token in text:
        return text.replace(token, "***")
    return text


def _warte(sekunden: float) -> None:
    """Kurze Pause zwischen Wiederholungen (in Tests ersetzt)."""
    time.sleep(sekunden)


def _als_int(wert) -> int:
    """Zahl tolerant lesen — unbrauchbare Werte werden ehrlich 0."""
    try:
        return int(float(wert))
    except (TypeError, ValueError):
        return 0


# ── Sortierschluessel lesen und Anlaesse bilden (reine Funktionen) ─────────

def zeilen_lesen(csv_pfad: str) -> list[dict]:
    """Die Sortier-CSV lesen — je Zeile ein Dict (Spalten wie in Stufe 1)."""
    with open(csv_pfad, newline="", encoding="utf-8") as datei:
        return list(csv.DictReader(datei))


def datum_teile(zeile: dict):
    """(Jahr, Monat, Tag) einer CSV-Zeile als ints — None, wenn unbrauchbar."""
    try:
        jahr = int(zeile.get("jahr") or 0)
        monat = int(zeile.get("monat") or 0)
        tag = int(zeile.get("tag") or 0)
    except (TypeError, ValueError):
        return None
    if 1990 <= jahr <= 2027 and 1 <= monat <= 12 and 1 <= tag <= 31:
        return (jahr, monat, tag)
    return None


# Zeit im Dateinamen: erst die Formen mit Datum + Trennzeichen, dann die
# Kompaktform (OnePlus/Oppo ohne Trenner), zuletzt Epoche-Millisekunden.
ZEIT_MUSTER = (
    # 059956_2024-08-09_17-14-43_96.jpg  ·  Screenshot_2024-06-09-02-49-36-…
    # IMG_20250606_185746027_BURST008.jpg · 20190209_161112_HDR.jpg
    # VID_20241221_193523_175.mp4 · image_20220730_142043_438.jpg
    re.compile(r"^(?:\d{6}_)?\D*(\d{4})[-_]?(\d{2})[-_]?(\d{2})"
               r"[_-](\d{2})[-_.]?(\d{2})[-_.]?(\d{2})"),
    # IMG20220804140219.jpg · VID20250225185258.mp4 (ohne Trenner)
    re.compile(r"^\D*(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})"),
)
EPOCHE = re.compile(r"^(1[0-9]{12})\b")


def zeit_aus_name(name: str, erwartetes_datum=None):
    """(Stunde, Minute, Sekunde) aus dem Dateinamen — None, wenn nicht belegbar.

    Kein Raten: Das Datum im Namen muss plausibel sein und (falls angegeben)
    dem Datum der CSV-Zeile entsprechen — sonst gibt es None. Zeitlose Namen
    (WhatsApp: ``IMG-20230623-WA0000.jpg``) liefern bewusst None.
    """
    for muster in ZEIT_MUSTER:
        treffer = muster.match(name)
        if not treffer:
            continue
        jahr, monat, tag, stunde, minute, sekunde = (
            int(gruppe) for gruppe in treffer.groups())
        if not _sort._plausibel(jahr, monat, tag):
            continue
        if erwartetes_datum and (jahr, monat, tag) != erwartetes_datum:
            continue
        if stunde < 24 and minute < 60 and sekunde < 60:
            return (stunde, minute, sekunde)

    treffer = EPOCHE.match(name)
    if treffer:
        try:
            zeitpunkt = datetime.datetime.fromtimestamp(int(treffer.group(1)) / 1000)
        except (OverflowError, OSError, ValueError):
            return None
        if erwartetes_datum and (zeitpunkt.year, zeitpunkt.month,
                                 zeitpunkt.day) != erwartetes_datum:
            return None
        return (zeitpunkt.hour, zeitpunkt.minute, zeitpunkt.second)
    return None


def ist_video(datei: str) -> bool:
    """True fuer Video-Endungen (Kennzeichen auf dem Bogen und im JSON)."""
    return str(datei).lower().endswith(VIDEO_ENDUNGEN)


def _abstand_minuten(frueher, spaeter) -> float:
    """Minuten zwischen zwei (h, m, s)-Zeiten desselben Tages."""
    return ((spaeter[0] * 3600 + spaeter[1] * 60 + spaeter[2])
            - (frueher[0] * 3600 + frueher[1] * 60 + frueher[2])) / 60.0


def _anlass_bauen(jahr: int, datum: str, nummer: int, gruppe: list[dict]) -> dict:
    """Aus den Zeilen einer Sitzung den Anlass-Eintrag formen."""
    zeiten = [z["zeit"] for z in gruppe if z.get("zeit")]
    ohne_uhrzeit = not zeiten
    return {
        "jahr": jahr,
        "datum": datum,
        "titel": f"{datum}_Anlass-{nummer:02d}",
        "nummer": nummer,
        "von": f"{min(zeiten)[0]:02d}:{min(zeiten)[1]:02d}" if zeiten else "",
        "bis": f"{max(zeiten)[0]:02d}:{max(zeiten)[1]:02d}" if zeiten else "",
        "ohne_uhrzeit": ohne_uhrzeit,
        "anzahl": len(gruppe),
        "videos": sum(1 for z in gruppe if ist_video(z["datei"])),
        "bytes": sum(_als_int(z.get("bytes")) for z in gruppe),
        "zeilen": gruppe,
    }


def anlaesse_bilden(zeilen: list[dict], luecke_minuten: int = LUECKE_MINUTEN) -> list[dict]:
    """CSV-Zeilen nach Jahr und Aufnahmetag zu Anlaessen gruppieren.

    Innerhalb eines Tages: Zeilen mit Uhrzeit werden chronologisch sortiert;
    eine neue Sitzung beginnt, wenn die Luecke zur vorigen Aufnahme groesser
    als ``luecke_minuten`` ist (>= 1). Bilder derselben Minute liegen damit
    IMMER im selben Anlass. Zeilen ohne Uhrzeit (WhatsApp-Empfang) bilden
    einen eigenen Anlass am Tagesende. Zeilen ohne Datum werden uebersprungen.

    Rueckgabe: Liste von Anlaessen (chronologisch), je Anlass mit jahr, datum,
    titel ("2024-07-14_Anlass-01"), nummer, von/bis, ohne_uhrzeit, anzahl,
    videos, bytes und den Zeilen selbst (inkl. "zeit").
    """
    if luecke_minuten < 1:
        raise FotoThemenFehler("--luecke muss mindestens 1 Minute sein.")

    tage: dict[tuple, list[dict]] = {}
    for zeile in zeilen:
        teile = datum_teile(zeile)
        if teile is None:
            continue
        kopie = dict(zeile)
        kopie["zeit"] = zeit_aus_name(str(zeile.get("datei") or ""), teile)
        tage.setdefault(teile, []).append(kopie)

    anlaesse: list[dict] = []
    for (jahr, monat, tag), eintraege in tage.items():
        mit_zeit = sorted((e for e in eintraege if e["zeit"]),
                          key=lambda e: (e["zeit"], e["datei"]))
        ohne_zeit = sorted((e for e in eintraege if not e["zeit"]),
                           key=lambda e: e["datei"])
        gruppen: list[list[dict]] = []
        aktuelle: list[dict] = []
        for eintrag in mit_zeit:
            if aktuelle and _abstand_minuten(aktuelle[-1]["zeit"],
                                             eintrag["zeit"]) > luecke_minuten:
                gruppen.append(aktuelle)
                aktuelle = []
            aktuelle.append(eintrag)
        if aktuelle:
            gruppen.append(aktuelle)
        if ohne_zeit:
            gruppen.append(ohne_zeit)

        datum = f"{jahr:04d}-{monat:02d}-{tag:02d}"
        for nummer, gruppe in enumerate(gruppen, start=1):
            anlaesse.append(_anlass_bauen(jahr, datum, nummer, gruppe))

    anlaesse.sort(key=lambda a: (a["jahr"], a["datum"],
                                 a["von"] or "99:99", a["titel"]))
    return anlaesse


# ── pCloud: nur lesend (listfolder + getthumbs) ────────────────────────────

def zugang_lesen(env_pfad: str = ENV_PFAD):
    """(Token, Host) aus der backend/.env — ohne Ausgabe (nutzt das Token-Werkzeug)."""
    return _token_werkzeug.aus_env(env_pfad)


def _api_aufruf(pfad: str, felder: dict, token: str, host: str) -> dict:
    """Ein GET gegen die pCloud-API; Fehlertexte ohne Token."""
    parameter = {name: wert for name, wert in felder.items() if wert is not None}
    parameter["auth"] = token
    url = f"https://{host}/{pfad.lstrip('/')}"
    try:
        antwort = httpx.get(url, params=parameter, timeout=TIMEOUT_SEKUNDEN)
    except Exception as fehler:                     # Klasse statt Text: der
        raise FotoThemenNetzfehler(                 # Text kann die URL tragen
            f"pCloud nicht erreichbar ({fehler.__class__.__name__}).") from None
    if antwort.status_code != 200:
        raise FotoThemenNetzfehler(f"pCloud antwortete mit HTTP {antwort.status_code}.")
    try:
        daten = antwort.json()
    except Exception:
        raise FotoThemenFehler("pCloud lieferte keine lesbare JSON-Antwort.") from None
    if not isinstance(daten, dict):
        raise FotoThemenFehler("pCloud lieferte eine unerwartete Antwort.")
    if daten.get("result") != 0:
        meldung = ohne_token(str(daten.get("error") or "ohne Fehlertext"), token)
        raise FotoThemenFehler(f"pCloud meldet Fehler {daten.get('result')}: {meldung}")
    return daten


def echter_api_abruf(env_pfad: str = ENV_PFAD):
    """Standard-Abruf fuer API-Aufrufe (tokenbehaftet, nie ausgegeben)."""
    token, host = zugang_lesen(env_pfad)
    if not token:
        raise FotoThemenFehler(
            f"Kein PCLOUD_TOKEN in {env_pfad} — Zugang fehlt (siehe pcloud_token_erneuern.py).")
    return lambda pfad, felder: _api_aufruf(pfad, felder, token, host or STANDARD_HOST)


def echter_thumb_abruf(env_pfad: str = ENV_PFAD):
    """Standard-Abruf fuer getthumbs (Textzeilen, type=jgp)."""
    token, host = zugang_lesen(env_pfad)
    if not token:
        raise FotoThemenFehler(
            f"Kein PCLOUD_TOKEN in {env_pfad} — Zugang fehlt (siehe pcloud_token_erneuern.py).")

    def abruf(dateiids, groesse: str) -> str:
        parameter = {
            "auth": token,
            "fileids": ",".join(str(int(i)) for i in dateiids),
            "size": groesse,
            "type": "jgp",
        }
        try:
            antwort = httpx.get(f"https://{host or STANDARD_HOST}/getthumbs",
                                params=parameter, timeout=TIMEOUT_SEKUNDEN)
        except Exception as fehler:
            raise FotoThemenNetzfehler(
                f"pCloud nicht erreichbar ({fehler.__class__.__name__}).") from None
        if antwort.status_code != 200:
            raise FotoThemenNetzfehler(
                f"pCloud antwortete mit HTTP {antwort.status_code}.")
        return antwort.content.decode("utf-8", errors="replace")

    return abruf


def liste(folderid: int, abruf) -> list[dict]:
    """Eintraege EINES Ordners (Ordner zuerst, dann Name) — ein listfolder."""
    daten = abruf("/listfolder", {"folderid": int(folderid)})
    metadata = daten.get("metadata")
    inhalte = metadata.get("contents") if isinstance(metadata, dict) else None
    ergebnis = []
    for eintrag in inhalte or []:
        if not isinstance(eintrag, dict):
            continue
        ergebnis.append({
            "name": str(eintrag.get("name") or ""),
            "ist_ordner": bool(eintrag.get("isfolder")),
            "folderid": eintrag.get("folderid"),
            "fileid": eintrag.get("fileid"),
            "groesse": eintrag.get("size"),
        })
    ergebnis.sort(key=lambda e: (not e["ist_ordner"], e["name"].casefold()))
    return ergebnis


def ordner_pfad_teile(ordner: str) -> list[str]:
    """'P:/Automatic Upload/Geraet/DCIM/Camera' -> Teile ohne Laufwerk und Slashes."""
    teile = (ordner or "").replace("\\", "/").split("/")
    return [t for t in teile if t and not re.fullmatch(r"[A-Za-z]:", t)]


def _ordner_inhalt(folderid: int, abruf, zwischenspeicher: dict) -> list[dict]:
    """Ordnerinhalt mit Zwischenspeicher (je Lauf wird ein Ordner einmal gelesen)."""
    if folderid not in zwischenspeicher:
        zwischenspeicher[folderid] = liste(folderid, abruf)
    return zwischenspeicher[folderid]


def ordner_finden(pfad_teile: list[str], abruf, zwischenspeicher: dict | None = None):
    """folderid eines Ordnerpfads ab der Wurzel — None, wenn ein Teil fehlt."""
    speicher = {} if zwischenspeicher is None else zwischenspeicher
    folderid = 0
    for teil in pfad_teile:
        unterordner = [e for e in _ordner_inhalt(folderid, abruf, speicher)
                       if e["ist_ordner"]]
        treffer = next((e for e in unterordner if e["name"] == teil), None)
        if treffer is None:
            treffer = next((e for e in unterordner
                            if e["name"].casefold() == teil.casefold()), None)
        if treffer is None or treffer["folderid"] is None:
            return None
        folderid = int(treffer["folderid"])
    return folderid


def dateien_im_ordner(ordner: str, abruf, zwischenspeicher: dict | None = None) -> dict:
    """{Dateiname: {fileid, groesse}} eines CSV-Ordners ueber die API.

    Eine Ordner-Ebene = ein listfolder (kein rekursiver Vollscan). Nicht
    gefundene Ordner liefern {} — der Aufrufer zaehlt die Dateien dann als
    "nicht gefunden", statt still etwas zu erfinden.
    """
    speicher = {} if zwischenspeicher is None else zwischenspeicher
    folderid = ordner_finden(ordner_pfad_teile(ordner), abruf, speicher)
    if folderid is None:
        return {}
    return {
        e["name"]: {"fileid": e["fileid"], "groesse": e["groesse"]}
        for e in _ordner_inhalt(folderid, abruf, speicher)
        if not e["ist_ordner"]
    }


# ── Vorschaubilder holen (Stapel, mit Wiederholung) ────────────────────────

def pruefe_groesse(groesse: str) -> None:
    if groesse not in ERLAUBTE_GROESSEN:
        raise FotoThemenFehler(
            "Unbekannte Vorschaugroesse: erlaubt sind "
            + " und ".join(ERLAUBTE_GROESSEN) + ".")


def antwort_zerlegen(text: str) -> dict:
    """getthumbs-Textzeilen auswerten: {fileid: {ergebnis, bytes}}.

    Format (live geprueft): ``fileid|0|86x120|data:image/jpeg;base64,…`` —
    Fehlerfall ohne Daten: ``fileid|5002|0``. Zuordnung ueber die fileid,
    NICHT ueber die Zeilenposition (die Reihenfolge ist nicht garantiert).
    """
    ergebnis: dict[int, dict] = {}
    for zeile in (text or "").splitlines():
        zeile = zeile.strip()
        if not zeile:
            continue
        teile = zeile.split("|")
        if len(teile) < 2:
            continue
        try:
            dateiid = int(teile[0])
        except ValueError:
            continue
        daten_uri = teile[3] if len(teile) > 3 else ""
        bild = None
        if teile[1] == "0" and "base64," in daten_uri:
            try:
                bild = base64.b64decode(daten_uri.split("base64,", 1)[1])
            except Exception:
                bild = None
        ergebnis[dateiid] = {"ergebnis": teile[1], "bytes": bild}
    return ergebnis


def _text_holen(dateiids: list[int], groesse: str, abruf, versuche: int) -> str:
    """getthumbs-Text mit Wiederholung bei Netzfehlern (max. ``versuche``)."""
    letzter = "kein Aufruf"
    for versuch in range(1, versuche + 1):
        try:
            return abruf(dateiids, groesse)
        except FotoThemenFehler as problem:
            if not isinstance(problem, FotoThemenNetzfehler):
                raise                       # definitive Antwort: nicht wiederholen
            letzter = str(problem)
        except Exception as problem:        # fremder Transportfehler: Klasse statt Text
            letzter = problem.__class__.__name__
        if versuch < versuche:
            _warte(PAUSE_SEKUNDEN * versuch)
    raise FotoThemenFehler(
        f"pCloud nach {versuche} Versuchen nicht erreichbar ({letzter}).")


def vorschau_holen(fileid, groesse: str = STANDARD_GROESSE, abruf=None,
                   versuche: int = VERSUCHE) -> bytes:
    """Vorschaubild EINES fileids als Bytes — mit Wiederholung bei Netzfehler.

    Es werden NUR Vorschaubilder geholt (nie Originale); die pCloud wird nicht
    veraendert. Ohne Vorschaubild (z. B. Code 5002) gibt es eine klare Meldung
    statt einer Wiederholung — das ist eine definitive Antwort.
    """
    pruefe_groesse(groesse)
    dateiid = int(fileid)
    abruf = abruf or echter_thumb_abruf()
    gelesen = antwort_zerlegen(_text_holen([dateiid], groesse, abruf, versuche))
    zeile = gelesen.get(dateiid)
    if zeile and zeile["bytes"]:
        return zeile["bytes"]
    code = zeile["ergebnis"] if zeile else "keine Antwortzeile"
    raise FotoThemenFehler(
        f"pCloud liefert zu fileid {dateiid} kein Vorschaubild (Code {code}).")


def vorschau_stapel(dateiids, groesse: str = STANDARD_GROESSE, abruf=None,
                    max_pro_aufruf: int = MAX_PRO_STAPEL,
                    versuche: int = VERSUCHE) -> dict:
    """Vorschaubilder MEHRERER fileids in Stapeln holen.

    Rueckgabe: {fileid: bytes} fuer gelieferte Bilder, {fileid: None} fuer
    Dateien ohne Vorschaubild (definitiv). Fehlende Antwortzeilen werden wie
    "kein Vorschaubild" behandelt und im Aufrufer gezaehlt.
    """
    pruefe_groesse(groesse)
    ids = [int(i) for i in dateiids]
    if not ids:
        return {}
    abruf = abruf or echter_thumb_abruf()
    ergebnis: dict[int, bytes | None] = {}
    for start in range(0, len(ids), max_pro_aufruf):
        stapel = ids[start:start + max_pro_aufruf]
        gelesen = antwort_zerlegen(_text_holen(stapel, groesse, abruf, versuche))
        for dateiid in stapel:
            zeile = gelesen.get(dateiid)
            ergebnis[dateiid] = zeile["bytes"] if (zeile and zeile["bytes"]) else None
    return ergebnis


# ── Kontaktbogen bauen und Zuordnung schreiben ─────────────────────────────

def _schrift(groesse: int):
    for pfad in SCHRIFT_PFADE:
        try:
            return ImageFont.truetype(pfad, groesse)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=groesse)
    except TypeError:
        return ImageFont.load_default()


def _masse(zeichner: ImageDraw.ImageDraw, text: str, schrift):
    kasten = zeichner.textbbox((0, 0), text, font=schrift)
    return kasten[2] - kasten[0], kasten[3] - kasten[1], kasten


def _text_kasten(zeichner, text, x, y, schrift, fuellung, schriftfarbe,
                 innen: int = 4):
    """Text mit gefuelltem Kasten zeichnen — gut lesbar auch auf hellem Bild."""
    breite, hoehe, kasten = _masse(zeichner, text, schrift)
    zeichner.rectangle([x, y, x + breite + 2 * innen, y + hoehe + 2 * innen],
                       fill=fuellung)
    zeichner.text((x + innen - kasten[0], y + innen - kasten[1]), text,
                  font=schrift, fill=schriftfarbe)
    return breite + 2 * innen, hoehe + 2 * innen


def _kachel_bauen(bild_bytes, kachel: int, video: bool) -> Image.Image:
    """Eine Kachel: Bild bzw. Platzhalter, auf kachel x kachel eingepasst."""
    kasten = Image.new("RGB", (kachel, kachel), (70, 70, 74))
    gezeichnet = False
    if bild_bytes:
        try:
            with Image.open(io.BytesIO(bild_bytes)) as bild:
                bild.load()
                bild = bild.convert("RGB")
                faktor = min(kachel / bild.width, kachel / bild.height)
                breite = max(1, round(bild.width * faktor))
                hoehe = max(1, round(bild.height * faktor))
                klein = bild.resize((breite, hoehe), Image.Resampling.LANCZOS)
                kasten.paste(klein, ((kachel - breite) // 2,
                                     (kachel - hoehe) // 2))
                gezeichnet = True
        except Exception:
            gezeichnet = False

    zeichner = ImageDraw.Draw(kasten)
    schrift = _schrift(max(12, kachel // 8))
    if not gezeichnet:
        text = "VIDEO" if video else "kein Bild"
        breite, hoehe, kasten_masse = _masse(zeichner, text, schrift)
        zeichner.text(((kachel - breite) / 2 - kasten_masse[0],
                       (kachel - hoehe) / 2 - kasten_masse[1]),
                      text, font=schrift, fill=(235, 235, 235))
    elif video:
        # Kennzeichen "VIDEO" unten rechts (spaeter: erster Frame via ffmpeg).
        breite, hoehe, _ = _masse(zeichner, "VIDEO", schrift)
        x = kachel - breite - 16
        y = kachel - hoehe - 14
        _text_kasten(zeichner, "VIDEO", x, y, schrift, (150, 24, 24),
                     (255, 255, 255), innen=4)
    return kasten


def bogen_bauen(anlass: dict, vorschaubilder: dict,
                spalten: int = 8, kachel: int = 160) -> bytes:
    """Kontaktbogen als JPEG-Bytes: nummerierte Kacheln 1..n in Reihenfolge der
    Anlass-Zeilen, mit Rand und Abstand zwischen den Kacheln.

    ``vorschaubilder``: {fileid: bytes} (fehlend/None = Platzhalter-Kachel).
    Die Nummern sind Pflicht: Der Vision-Blick sagt spaeter "Kachel 12" und
    die Zuordnungsdatei loest das exakt in die Datei auf.
    """
    zeilen = list(anlass.get("zeilen") or [])
    spalten = max(1, int(spalten))
    kachel = max(40, int(kachel))
    reihen = max(1, math.ceil(len(zeilen) / spalten))
    rand = max(8, kachel // 10)
    abstand = max(4, kachel // 16)
    breite = rand * 2 + spalten * kachel + (spalten - 1) * abstand
    hoehe = rand * 2 + reihen * kachel + (reihen - 1) * abstand

    bogen = Image.new("RGB", (breite, hoehe), (28, 28, 32))
    zeichner = ImageDraw.Draw(bogen)
    nummern_schrift = _schrift(max(14, kachel // 6))

    for nummer, zeile in enumerate(zeilen, start=1):
        reihe, spalte = divmod(nummer - 1, spalten)
        x = rand + spalte * (kachel + abstand)
        y = rand + reihe * (kachel + abstand)
        bild = vorschaubilder.get(zeile.get("fileid"))
        kachelbild = _kachel_bauen(bild, kachel, ist_video(zeile.get("datei") or ""))
        bogen.paste(kachelbild, (x, y))
        _text_kasten(zeichner, str(nummer), x + 4, y + 4, nummern_schrift,
                     (0, 0, 0), (255, 255, 255), innen=5)

    puffer = io.BytesIO()
    bogen.save(puffer, "JPEG", quality=88, optimize=True)
    return puffer.getvalue()


def zuordnung_schreiben(anlass: dict, eintraege: list[dict], ziel: str) -> dict:
    """Zuordnung Kachel-Nummer -> Datei als JSON neben dem Bogen (atomar).

    ``eintraege``: je Kachel {kachel, fileid, datei, bytes, ist_video, ordner}.
    Die Nummern muessen lueckenlos 1..n sein — sonst wird nichts geschrieben
    (eine halbe Zuordnung waere schlimmer als keine).
    """
    nummern = [e.get("kachel") for e in eintraege]
    if nummern != list(range(1, len(eintraege) + 1)):
        raise FotoThemenFehler(
            "Zuordnung unvollstaendig: Kachel-Nummern muessen lueckenlos 1..n sein.")
    daten = {
        "titel": anlass["titel"],
        "jahr": anlass["jahr"],
        "datum": anlass["datum"],
        "von": anlass.get("von", ""),
        "bis": anlass.get("bis", ""),
        "ohne_uhrzeit": bool(anlass.get("ohne_uhrzeit")),
        "bogen": os.path.basename(ziel).rsplit(".", 1)[0] + ".jpg",
        "anzahl": len(eintraege),
        "anzahl_videos": sum(1 for e in eintraege if e.get("ist_video")),
        "bytes": sum(_als_int(e.get("bytes")) for e in eintraege),
        "kacheln": [
            {
                "kachel": e["kachel"],
                "fileid": e.get("fileid"),
                "datei": e["datei"],
                "bytes": _als_int(e.get("bytes")),
                "ist_video": bool(e.get("ist_video")),
                "ordner": e.get("ordner", ""),
            }
            for e in eintraege
        ],
    }
    ordner = os.path.dirname(os.path.abspath(ziel))
    os.makedirs(ordner, exist_ok=True)
    temp = ziel + ".tmp"
    with open(temp, "w", encoding="utf-8") as datei:
        json.dump(daten, datei, ensure_ascii=False, indent=1)
    os.replace(temp, ziel)
    return daten


# ── Kommandozeile ──────────────────────────────────────────────────────────

def _mw(bytes_wert) -> str:
    return f"{_als_int(bytes_wert) / 1e6:.2f} MB"


def _anlass_zeile(anlass: dict) -> str:
    zeitraum = f"{anlass['von']}-{anlass['bis']}" if anlass["von"] else "ohne Uhrzeit"
    return (f"{anlass['titel']:<24} {anlass['datum']} {zeitraum:<14} "
            f"{anlass['anzahl']:>4} Kacheln ({anlass['videos']} Videos) "
            f"{_mw(anlass['bytes']):>10}")


def main(argv=None, api_abruf=None, thumb_abruf=None) -> int:
    """Kommandozeilen-Teil. ``api_abruf``/``thumb_abruf`` sind fuer Tests
    injizierbar — ohne sie wird der echte, tokenbehaftete Abruf gebaut."""
    zerleger = argparse.ArgumentParser(
        description="Vorschaubilder in Stapeln holen, Kontaktboegen je Tag/Anlass bauen.")
    zerleger.add_argument("--csv", default=STANDARD_CSV,
                          help="Sortierschluessel (CSV aus Stufe 1)")
    zerleger.add_argument("--boegen", default=STANDARD_BOEGEN,
                          help="Zielordner der Boegen (ausserhalb des Repos)")
    zerleger.add_argument("--jahr", default="", help="z. B. 2025 (leer = alle Jahre)")
    zerleger.add_argument("--limit", type=int, default=3,
                          help="Anzahl Anlaesse, kleinster-sicherer Wert (0 = alle)")
    zerleger.add_argument("--anlass", default="",
                          help="genau ein Anlass, z. B. 2025-06-06_Anlass-01")
    zerleger.add_argument("--luecke", type=int, default=LUECKE_MINUTEN,
                          help="Minuten bis eine neue Sitzung beginnt (Standard 30; "
                               "1 = Minutengranularitaet)")
    zerleger.add_argument("--spalten", type=int, default=8, help="Kacheln je Reihe")
    zerleger.add_argument("--kachel", type=int, default=160, help="Kachelgroesse in Pixeln")
    zerleger.add_argument("--trocken", action="store_true",
                          help="nur zeigen, was passieren wuerde (holt und schreibt nichts)")
    zerleger.add_argument("--nur-liste", dest="nur_liste", action="store_true",
                          help="nur die geplanten Anlaesse auflisten")
    args = zerleger.parse_args(argv)

    if not os.path.exists(args.csv):
        print(f"Sortierschluessel nicht gefunden: {args.csv}")
        return 2

    start = time.time()
    zeilen = zeilen_lesen(args.csv)
    anlaesse = anlaesse_bilden(zeilen, luecke_minuten=args.luecke)
    ohne_datum = sum(1 for z in zeilen if datum_teile(z) is None)

    if args.jahr:
        anlaesse = [a for a in anlaesse if a["jahr"] == int(args.jahr)]
    if args.anlass:
        anlaesse = [a for a in anlaesse if a["titel"] == args.anlass]
    geplant = anlaesse[:args.limit] if args.limit and args.limit > 0 else anlaesse

    print(f"Sortierschluessel: {args.csv}")
    print(f"Zeilen: {len(zeilen)} (ohne Datum: {ohne_datum})   "
          f"Anlaesse gesamt: {len(anlaesse)}"
          + (f"   Jahr {args.jahr}" if args.jahr else "")
          + (f"   Auswahl: {args.anlass}" if args.anlass else ""))
    print(f"Regel: gleiche Minute = ein Anlass; neue Sitzung ab {args.luecke} min Luecke")
    print(f"Geplant ({len(geplant)}"
          + (f" von {len(anlaesse)}, Limit {args.limit}" if len(geplant) < len(anlaesse) else "")
          + f"), Zielordner: {os.path.join(args.boegen, '<Jahr>')}")
    print()
    for anlass in geplant:
        print("  " + _anlass_zeile(anlass))

    if args.nur_liste:
        print(f"\nNur-Liste: nichts geholt, nichts geschrieben "
              f"({time.time() - start:.1f} s).")
        return 0

    if args.trocken:
        print()
        for anlass in geplant:
            ziel = os.path.join(args.boegen, str(anlass["jahr"]), anlass["titel"])
            vorhanden = (os.path.exists(ziel + ".jpg") and os.path.exists(ziel + ".json"))
            print(f"  {anlass['titel']}: "
                  + ("waere uebersprungen (Bogen vorhanden)" if vorhanden
                     else f"wuerde gebaut -> {ziel}.jpg + .json "
                          f"[{anlass['anzahl']} Vorschaubilder zu holen]"))
        print(f"\nTrockenlauf: nichts geholt, nichts geschrieben ({time.time() - start:.1f} s).")
        return 0

    # ── Echter Lauf ─────────────────────────────────────────────────────
    abruf_api = api_abruf or echter_api_abruf()
    abruf_thumbs = thumb_abruf or echter_thumb_abruf()
    speicher: dict = {}
    geholt = 0
    bytes_geholt = 0
    uebersprungen = 0
    gebaut = 0
    fehlgeschlagen = 0
    nicht_gefunden = 0

    print()
    for anlass in geplant:
        anlass_start = time.time()
        ordner_jahr = os.path.join(args.boegen, str(anlass["jahr"]))
        ziel_jpg = os.path.join(ordner_jahr, anlass["titel"] + ".jpg")
        ziel_json = os.path.join(ordner_jahr, anlass["titel"] + ".json")
        if os.path.exists(ziel_jpg) and os.path.exists(ziel_json):
            uebersprungen += 1
            print(f"  {anlass['titel']}: uebersprungen (Bogen vorhanden)")
            continue

        for zeile in anlass["zeilen"]:
            index = dateien_im_ordner(zeile.get("ordner") or "", abruf_api, speicher)
            gefunden = index.get(zeile["datei"])
            zeile["fileid"] = gefunden["fileid"] if gefunden else None
            if not gefunden:
                nicht_gefunden += 1
        ids = [z["fileid"] for z in anlass["zeilen"] if z.get("fileid")]

        if not ids:
            fehlgeschlagen += 1
            print(f"  {anlass['titel']}: FEHLER — kein einziges fileid gefunden, "
                  f"kein Bogen gebaut")
            continue

        vorschauen = vorschau_stapel(ids, abruf=abruf_thumbs)
        anzahl_geholt = sum(1 for bild in vorschauen.values() if bild)
        bytes_dies = sum(len(bild) for bild in vorschauen.values() if bild)
        geholt += anzahl_geholt
        bytes_geholt += bytes_dies

        bogen = bogen_bauen(anlass, vorschauen, spalten=args.spalten,
                            kachel=args.kachel)
        eintraege = [
            {
                "kachel": nummer,
                "fileid": zeile.get("fileid"),
                "datei": zeile["datei"],
                "bytes": _als_int(zeile.get("bytes")),
                "ist_video": ist_video(zeile["datei"]),
                "ordner": zeile.get("ordner", ""),
            }
            for nummer, zeile in enumerate(anlass["zeilen"], start=1)
        ]
        os.makedirs(ordner_jahr, exist_ok=True)
        temp = ziel_jpg + ".tmp"
        with open(temp, "wb") as datei:
            datei.write(bogen)
        os.replace(temp, ziel_jpg)
        zuordnung_schreiben(anlass, eintraege, ziel_json)
        gebaut += 1
        print(f"  {anlass['titel']}: {anlass['anzahl']} Kacheln, "
              f"{anzahl_geholt} Vorschauen geholt ({bytes_dies} Bytes), "
              f"Bogen {len(bogen)} Bytes -> {ziel_jpg} "
              f"({time.time() - anlass_start:.1f} s)")

    dauer = time.time() - start
    print()
    print(f"Anlaesse: {len(geplant)} geplant   geholt: {geholt} Vorschaubilder "
          f"({bytes_geholt} Bytes)   uebersprungen: {uebersprungen}   "
          f"gebaut: {gebaut}   fehlgeschlagen: {fehlgeschlagen}")
    if nicht_gefunden:
        print(f"Nicht gefunden (Name nicht im pCloud-Ordner): {nicht_gefunden} Dateien")
    print(f"Dauer: {dauer:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
