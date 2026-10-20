"""T0 — datensparsamer Quellenstatus der Fotokette.

Auftrag: ``.hermes/plans/gesamtplan-foto-erinnerungen-2026-10-11.md``, Abschnitt
**T0** („Fotoquellen wirklich bis zum Handy nachweisen"). Ergebnis für den Nutzer
ist eine Statuszeile je Quelle —
``entpackt → Bildindex → Gesichtserkennung → Gruppenbestand → auf diesem Handy``.

Zwei harte Regeln des Auftrags, hier fest verdrahtet:

1. **Nur Summen.** Kein privater Pfad, kein Name, kein Ortswert, keine Bild-ID
   und kein Vektor steht im Bericht — nur Zahlen und feste Bezeichner. Die
   Funktionen geben deshalb nie die gelesenen Kennungen selbst zurück, sondern
   nur ihre Anzahl.
2. **Fehlender Messwert ist ``None``, nicht ``0``.** Eine fehlende Datei und eine
   Datei ohne Treffer dürfen nicht gleich aussehen; welcher Wert fehlt, steht in
   ``fehlende_werte``.

Dazu: die Stationen werden über **dieselben technischen Medienkennungen**
(``fileid``) abgeglichen, und die Gruppen sind ein **Bestand**, kein Zuwachs.
Eine Quelle kann neue Gruppen bilden oder bestehende ergänzen — die Gesamtsumme
ist deshalb keine Zahl neuer Personen und wird hier nirgends so dargestellt
(``offene_gruppen``/``spaeter_gruppen`` tragen den Stand des GANZEN Bestands in
jeder Zeile und dürfen über die Quellen NICHT addiert werden).

Die fünfte Station (``handy_stand_geprueft``) ist am PC nicht messbar. Ohne
Messung bleibt sie ``None`` — der Auftrag nennt sie als eigenen Punkt.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from app.services import gruppen_quiz

logger = logging.getLogger(__name__)

STANDARD_BASIS = os.path.join(os.path.expanduser("~"), "foto_sortierung")
UNTERORDNER = "personen_gruppen"
INDEX_DATEINAME = "bild_index.db"
INDEX_TABELLE = "bilder"
ZUORDNUNG_DATEINAME = "gesicht_zuordnung.jsonl"
VIDEO_ENDUNGEN = (".mp4", ".mov", ".3gp", ".mkv", ".avi", ".m4v")

#: Eine Quelle = fester Bezeichner + ihre Plan-Datei(en) + ihre Vektor-Datei(en).
#: Die Bezeichner sind Maschinentexte (stabil, ohne Pfad und ohne Inhalt).
QUELLEN: Tuple[Tuple[str, Tuple[str, ...], Tuple[str, ...]], ...] = (
    ("fotos", ("sortierplan.json",), ("personen_vektoren_n0929_voll.jsonl",)),
    ("bilder_und_videos", ("sortierplan_bildervideos.json",),
     ("personen_vektoren_n0929_bildervideos.jsonl",)),
    ("papas_album", ("sortierplan_papa.json",), ("personen_vektoren_papa.jsonl",)),
    ("neuausrichtung", ("gedreht_plan.json",), ("personen_vektoren_gedreht_neu.jsonl",)),
    ("fotobuch", ("fotobuch_plan.json",), ("personen_vektoren_fotobuch.jsonl",)),
)

#: Felder des Berichtsvertrags (T0) in fester Reihenfolge.
VERTRAGSFELDER: Tuple[str, ...] = (
    "quelle_typ", "gelesen_am", "bilder_im_plan", "bilder_im_index",
    "bilder_mit_gesichtslauf", "erkannte_gesichter", "gesichter_im_gruppenbestand",
    "offene_gruppen", "spaeter_gruppen", "handy_stand_geprueft",
)

HINWEIS = (
    "Summen je Quelle; die Stationen sind über die technische Medienkennung "
    "abgeglichen. Die Gruppen sind ein Bestand, kein Zuwachs: eine Quelle kann "
    "Gruppen bilden oder ergänzen — über die Quellen zusammengezählt ergeben sie "
    "keine Zahl neuer Personen. Fehlender Messwert = null (nicht 0)."
)


# ── Werkzeuge ────────────────────────────────────────────────────────────────

def _kennung(wert: Any) -> str:
    """Eine Medienkennung als reiner Zifferntext — leer, wenn nichts messbar ist."""
    if wert is None or isinstance(wert, bool):
        return ""
    if isinstance(wert, int):
        return str(wert)
    text = str(wert).strip()
    if not text:
        return ""
    if text.endswith(".0") and text[:-2].isdigit():
        return text[:-2]
    return text


def _pfad(basis: str, *teile: str) -> str:
    return os.path.join(basis, *teile)


# ── Die vier Stationen, je Station eine eigene, kleine Lesefunktion ──────────
# Jede gibt ``None`` zurück, wenn der Wert nicht gemessen werden kann (Datei
# fehlt oder ist nicht lesbar) — nie eine 0 als Ersatz.

def plan_kennungen(pfad: str) -> Optional[Set[str]]:
    """Alle Medienkennungen eines Sortierplans — nur die Menge, nie ein Name."""
    if not os.path.isfile(pfad):
        return None
    try:
        with open(pfad, encoding="utf-8") as datei:
            daten = json.load(datei)
    except (OSError, ValueError):
        return None
    if isinstance(daten, dict):
        zuege = daten.get("zuege")
    elif isinstance(daten, list):        # auch eine reine Liste von Zügen ist gültig
        zuege = daten
    else:
        zuege = None
    if not isinstance(zuege, list):
        return None
    kennungen: Set[str] = set()
    for zug in zuege:
        if isinstance(zug, dict):
            k = _kennung(zug.get("fileid") if zug.get("fileid") is not None
                         else zug.get("bild_id"))
        else:
            k = _kennung(zug)
        if k:
            kennungen.add(k)
    return kennungen


def vektoren_zaehlen(pfad: str) -> Optional[Dict[str, int]]:
    """Bilder und Gesichter einer Vektordatei zählen (nur Zahlen)."""
    if not os.path.isfile(pfad):
        return None
    bilder: Set[str] = set()
    gesichter = 0
    video_zeilen = 0
    kaputte_zeilen = 0
    doppelte_zeilen = 0
    try:
        datei = open(pfad, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with datei:
        for zeile in datei:
            if not zeile.strip():
                continue
            try:
                satz = json.loads(zeile)
            except ValueError:
                kaputte_zeilen += 1
                continue
            if not isinstance(satz, dict):
                kaputte_zeilen += 1
                continue
            kennung = _kennung(satz.get("bild_id"))
            if not kennung:
                kaputte_zeilen += 1
                continue
            if "#t=" in kennung:          # Standbild-Zeile eines Videos, kein Bild
                video_zeilen += 1
                continue
            if kennung in bilder:
                doppelte_zeilen += 1
            bilder.add(kennung)
            gesichter_liste = satz.get("gesichter")
            if isinstance(gesichter_liste, list):
                gesichter += len(gesichter_liste)
    return {"bilder": len(bilder), "gesichter": gesichter,
            "video_zeilen": video_zeilen, "kaputte_zeilen": kaputte_zeilen,
            "doppelte_zeilen": doppelte_zeilen}


def index_kennungen(pfad: str) -> Optional[Set[str]]:
    """Die Kennungen im Bildindex (nur lesend geöffnet, nie geschrieben)."""
    if not os.path.isfile(pfad):
        return None
    try:
        verbindung = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return None
    try:
        kennungen: Set[str] = set()
        try:
            zeilen = verbindung.execute(f'SELECT fileid FROM {INDEX_TABELLE}')
        except sqlite3.Error:
            return None
        for (wert,) in zeilen:
            k = _kennung(wert)
            if k:
                kennungen.add(k)
        return kennungen
    except sqlite3.Error:
        return None
    finally:
        verbindung.close()


def gruppen_zeilen(pfad: str) -> Optional[Dict[str, int]]:
    """Zeilen der Zuordnungsdatei zählen: gesamt, mit Gruppe, ohne Gruppe."""
    if not os.path.isfile(pfad):
        return None
    zeilen = mit_gruppe = ohne_gruppe = kaputt = 0
    try:
        datei = open(pfad, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with datei:
        for zeile in datei:
            if not zeile.strip():
                continue
            try:
                satz = json.loads(zeile)
            except ValueError:
                kaputt += 1
                continue
            if not isinstance(satz, dict):
                kaputt += 1
                continue
            zeilen += 1
            if _kennung(satz.get("kennung")):
                mit_gruppe += 1
            else:
                ohne_gruppe += 1
    return {"zeilen": zeilen, "mit_gruppe": mit_gruppe,
            "ohne_gruppe": ohne_gruppe, "kaputte_zeilen": kaputt}


def gruppen_stand_lesen() -> Dict[str, Optional[int]]:
    """Stand des ganzen Gruppenbestands über den Quizdienst — nur Zahlen.

    Namen liest der Dienst, aber sie werden hier **nicht** übernommen: der
    Bericht trägt ausschließlich Anzahl en.
    """
    leer: Dict[str, Optional[int]] = {"gruppen": None, "benannt": None,
                                      "offen": None, "spaeter": None,
                                      "gesichter": None}
    try:
        stand = gruppen_quiz.stand()
    except Exception:                     # der Dienst wirft nicht, aber doppelt hält besser
        logger.warning("Gruppenstand nicht lesbar")
        return leer
    if not isinstance(stand, dict) or not stand.get("ok"):
        return leer
    for feld in leer:
        wert = stand.get(feld)
        if isinstance(wert, int) and not isinstance(wert, bool):
            leer[feld] = wert
    return leer


# ── Der Bericht ──────────────────────────────────────────────────────────────

def _jetzt(zeitpunkt: Optional[datetime] = None) -> str:
    stamp = zeitpunkt or datetime.now(timezone.utc)
    return stamp.astimezone().isoformat(timespec="seconds")


def quelle_status(quelle_typ: str,
                  plan_dateien: Sequence[str] = (),
                  vektor_dateien: Sequence[str] = (),
                  *,
                  basis: str = STANDARD_BASIS,
                  index_datei: Optional[str] = None,
                  zuordnung_datei: Optional[str] = None,
                  offene_gruppen: Optional[int] = None,
                  spaeter_gruppen: Optional[int] = None,
                  handy_geprueft: Optional[bool] = None,
                  gelesen_am: Optional[str] = None) -> Dict[str, Any]:
    """Eine Zeile des Berichtsvertrags für EINE Quelle — genau die zehn Felder."""
    plan_kennungen_gesamt: Set[str] = set()
    plan_gemessen = False
    for name in plan_dateien:
        gefunden = plan_kennungen(_pfad(basis, name))
        if gefunden is None:
            continue
        plan_gemessen = True
        plan_kennungen_gesamt |= gefunden

    vektor_bilder: Optional[int] = None
    vektor_gesichter: Optional[int] = None
    for name in vektor_dateien:
        gezaehlt = vektoren_zaehlen(_pfad(basis, name))
        if gezaehlt is None:
            continue
        vektor_bilder = (vektor_bilder or 0) + gezaehlt["bilder"]
        vektor_gesichter = (vektor_gesichter or 0) + gezaehlt["gesichter"]

    index = index_kennungen(index_datei) if index_datei else None

    # Gesichter dieser Quelle im Gruppenbestand: Zeilen der Zuordnungsdatei,
    # deren Medienkennung zum Plan dieser Quelle gehört und die eine Gruppe
    # tragen. Fehlt eine der beiden Seiten, bleibt der Wert offen (None).
    gesichter_im_bestand: Optional[int] = None
    if zuordnung_datei and plan_gemessen and plan_kennungen_gesamt:
        zeilen = _zuordnung_mit_gruppe_nach_quelle(zuordnung_datei, plan_kennungen_gesamt)
        if zeilen is not None:
            gesichter_im_bestand = zeilen

    zeile = {
        "quelle_typ": quelle_typ,
        "gelesen_am": gelesen_am or _jetzt(),
        "bilder_im_plan": len(plan_kennungen_gesamt) if plan_gemessen else None,
        "bilder_im_index": (len(plan_kennungen_gesamt & index)
                            if (plan_gemessen and index is not None) else None),
        "bilder_mit_gesichtslauf": vektor_bilder,
        "erkannte_gesichter": vektor_gesichter,
        "gesichter_im_gruppenbestand": gesichter_im_bestand,
        "offene_gruppen": offene_gruppen,
        "spaeter_gruppen": spaeter_gruppen,
        "handy_stand_geprueft": handy_geprueft,
    }
    return {feld: zeile[feld] for feld in VERTRAGSFELDER}


def _zuordnung_mit_gruppe_nach_quelle(pfad: str, kennungen: Set[str]) -> Optional[int]:
    """Zeilen mit Gruppe, deren Medienkennung in ``kennungen`` liegt."""
    if not os.path.isfile(pfad):
        return None
    treffer = 0
    try:
        datei = open(pfad, encoding="utf-8", errors="replace")
    except OSError:
        return None
    with datei:
        for zeile in datei:
            if not zeile.strip():
                continue
            try:
                satz = json.loads(zeile)
            except ValueError:
                continue
            if not isinstance(satz, dict) or not _kennung(satz.get("kennung")):
                continue
            if _kennung(satz.get("bild_id")).split("#t=")[0] in kennungen:
                treffer += 1
    return treffer


def status(basis: str = STANDARD_BASIS,
           quellen: Sequence[Tuple[str, Sequence[str], Sequence[str]]] = QUELLEN,
           *,
           index_datei: Optional[str] = None,
           zuordnung_datei: Optional[str] = None,
           handy_geprueft: Optional[bool] = None,
           zeitpunkt: Optional[datetime] = None) -> Dict[str, Any]:
    """Der ganze Quellenstatus — je Quelle eine Zeile des Berichtsvertrags.

    Nicht gemessene Werte sind ``None`` und stehen zusätzlich namentlich in
    ``fehlende_werte``. Es wird **nichts** geschrieben und kein Netzzugriff
    gemacht; alle Pfade kommen aus ``basis`` (oder werden übergeben).
    """
    gelesen_am = _jetzt(zeitpunkt)
    index = index_datei or _pfad(basis, INDEX_DATEINAME)
    zuordnung = zuordnung_datei or _pfad(basis, UNTERORDNER, ZUORDNUNG_DATEINAME)

    stand = gruppen_stand_lesen()
    zeilen = [
        quelle_status(typ, plan, vektoren, basis=basis, index_datei=index,
                      zuordnung_datei=zuordnung, offene_gruppen=stand["offen"],
                      spaeter_gruppen=stand["spaeter"], handy_geprueft=handy_geprueft,
                      gelesen_am=gelesen_am)
        for typ, plan, vektoren in quellen
    ]

    fehlende: List[str] = []
    for zeile in zeilen:
        for feld in VERTRAGSFELDER:
            if feld in ("quelle_typ", "gelesen_am"):
                continue
            if zeile[feld] is None:
                fehlende.append(f"{zeile['quelle_typ']}.{feld}")
    for feld, wert in stand.items():
        if wert is None:
            fehlende.append(f"gruppenbestand.{feld}")

    return {
        "gelesen_am": gelesen_am,
        "quellen": zeilen,
        "gruppenbestand": {"gruppen": stand["gruppen"], "benannt": stand["benannt"],
                           "offen": stand["offen"], "spaeter": stand["spaeter"],
                           "gesichter": stand["gesichter"]},
        "handy_stand_geprueft": handy_geprueft,
        "fehlende_werte": fehlende,
        "hinweis": HINWEIS,
    }


# ── Zwischenspeicher für die Anzeige in der App ──────────────────────────────
# Auftrag: derselbe Gesamtplan, Abschnitt T0 („Fotoquellen wirklich bis zum
# Handy nachweisen"), Ergebnis für den Nutzer: **unter „Datenstand" eine
# Statuszeile pro Quelle**. Der Bericht selbst ist fertig — es fehlte der Weg in
# die Oberfläche.
#
# Warum ein Speicher davor: eine volle Messung liest die Plan- und
# Vektordateien (auf dem Gerät zusammen rund 250 MB) und braucht dafür
# Sekunden bis Minuten. Eine Anzeige, die beim Öffnen misst, würde das Gerät
# blockieren und bei jedem Neuladen erneut messen. Deshalb gilt EIN gemessener
# Stand je Basis für eine Weile (``STANDARD_CACHE_SEKUNDEN``); auf Wunsch misst
# ``neu=True`` frisch. Der gespeicherte Wert ist derselbe Bericht, den
# :func:`status` liefert — es kommt nichts hinzu und nichts weg.
STANDARD_CACHE_SEKUNDEN = 600.0
_CACHE: Dict[str, Any] = {"schluessel": None, "bericht": None,
                          "zeitpunkt": 0.0, "dauer_sekunden": None}
_SPERRE = threading.Lock()


def cache_leeren() -> None:
    """Den Zwischenspeicher verwerfen (für Tests und nach einem Datenwechsel)."""
    with _SPERRE:
        _CACHE.update(schluessel=None, bericht=None, zeitpunkt=0.0,
                      dauer_sekunden=None)


def _cache_schluessel(basis: str, quellen: Any, index_datei: Optional[str],
                      zuordnung_datei: Optional[str],
                      handy_geprueft: Optional[bool]) -> Tuple[Any, ...]:
    """Was einen Stand kennzeichnet: Basis, Quellenliste und die festen Dateien."""
    kennung = tuple((typ, tuple(plan), tuple(vektoren)) for typ, plan, vektoren in quellen)
    return (os.path.abspath(basis), kennung, index_datei, zuordnung_datei,
            handy_geprueft)


def status_gecacht(basis: str = STANDARD_BASIS, *,
                   ttl_sekunden: float = STANDARD_CACHE_SEKUNDEN,
                   neu: bool = False,
                   quellen: Sequence[Tuple[str, Sequence[str], Sequence[str]]] = QUELLEN,
                   index_datei: Optional[str] = None,
                   zuordnung_datei: Optional[str] = None,
                   handy_geprueft: Optional[bool] = None,
                   zeitpunkt: Optional[datetime] = None) -> Dict[str, Any]:
    """:func:`status` mit Zwischenspeicher — **wirft nie** wegen des Speichers.

    Rückgabe: ``{"bericht": …, "aus_cache": bool, "dauer_sekunden": float,
    "gemessen_sekunden": float}``.

    * ``aus_cache`` sagt, ob dieser Aufruf wirklich gemessen hat (``False``)
      oder den gespeicherten Stand geliefert hat (``True``).
    * ``dauer_sekunden`` ist die Dauer der Messung, die zu diesem Stand geführt
      hat — auch dann, wenn gerade aus dem Speicher geliefert wird.
    * ``gemessen_sekunden`` ist die Dauer DIESES Aufrufs.
    * ``neu=True`` misst immer frisch; ``ttl_sekunden <= 0`` schaltet den
      Speicher ab (jeder Aufruf misst). Ist eine frühere Messung gescheitert,
      wird nichts gespeichert — der nächste Aufruf versucht es erneut.
    """
    schluessel = _cache_schluessel(basis, quellen, index_datei, zuordnung_datei,
                                   handy_geprueft)
    beginn = time.monotonic()
    if not neu and ttl_sekunden > 0:
        with _SPERRE:
            gespeichert = _CACHE["bericht"]
            passt = _CACHE["schluessel"] == schluessel
            frisch = (time.monotonic() - float(_CACHE["zeitpunkt"])) < ttl_sekunden
            dauer = _bericht_dauer(_CACHE["dauer_sekunden"])
        if gespeichert is not None and passt and frisch:
            return {"bericht": gespeichert, "aus_cache": True,
                    "dauer_sekunden": dauer,
                    "gemessen_sekunden": time.monotonic() - beginn}

    bericht = status(basis=basis, quellen=quellen, index_datei=index_datei,
                     zuordnung_datei=zuordnung_datei,
                     handy_geprueft=handy_geprueft, zeitpunkt=zeitpunkt)
    gemessen = time.monotonic() - beginn
    with _SPERRE:
        _CACHE.update(schluessel=schluessel, bericht=bericht,
                      zeitpunkt=time.monotonic(), dauer_sekunden=gemessen)
    return {"bericht": bericht, "aus_cache": False,
            "dauer_sekunden": gemessen, "gemessen_sekunden": gemessen}


def _bericht_dauer(wert: Any) -> Optional[float]:
    """Eine gespeicherte Messdauer als Zahl — ``None`` bleibt ``None``."""
    if isinstance(wert, (int, float)) and not isinstance(wert, bool):
        return float(wert)
    return None
