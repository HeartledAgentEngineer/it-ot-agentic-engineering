"""Erzähl-Diashow (Auftrag E8a, 28.09.2026) — Dienst: Ereignisse lesen,
Geschichten anhängen.

Warum es diesen Dienst gibt
---------------------------
Sebastian wählt in der App ein Ereignis, klickt sich durch die Diashow der
Bilder und erzählt zu jedem Bild (tippen oder Mikrofon). Die Ereignisse
selbst liegen als eingefrorenes Schema in ``ereignisse.jsonl`` (gebaut von
``tools/foto_sortierung/ereignisse_bauen.py``, nur PC). Die Geschichten dazu
sind Sebastians eigene Worte — sie werden in einer zweiten Datei
``geschichten.jsonl`` als **Schicht "mensch"** nur angehängt.

Eiserne Regeln (aus dem Auftrag, bindend)
------------------------------------------
  * **Nur lesend** bei ``ereignisse.jsonl``. Defekte Zeilen werden gezählt,
    nicht geworfen.
  * **Nur anhängend** bei ``geschichten.jsonl`` — nie neu schreiben, nie
    löschen (``open(..., "a")`` + ``flush`` + ``os.fsync``).
  * Anker einer Geschichte ist die **Bildkennung** plus ein Schnappschuss von
    Ereignis-Datum/-Titel — das übersteht jede Neuberechnung der Ereignisse.
  * **Korrektur** = neue Zeile mit ``ersetzt: <alte id>``. Beim Lesen liefert
    :func:`geschichten` nur die jeweils neueste Fassung.
  * **Kein Netz.** Es wird ausschließlich lokal gelesen/geschrieben.
  * **Keine Geheimnisse.** Es werden nur Ereignis-/Geschichtendaten
    verarbeitet — kein Schlüssel, kein Token.

Pfade sind über Umgebungsvariablen übersteuerbar (Tests, anderes Gerät):
``ERZAEHL_EREIGNISSE_PFAD`` und ``ERZAEHL_GESCHICHTEN_PFAD``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Pfade ────────────────────────────────────────────────────────────────────

ERZAEHL_ORDNER = "foto_sortierung"
EREIGNISSE_DATEINAME = "ereignisse.jsonl"
GESCHICHTEN_DATEINAME = "geschichten.jsonl"

SCHICHT_MENSCH = "mensch"
SCHICHT_VERSION = 1

# Erlaubte Quellen einer Geschichte. "import" (Nachtrag 28.09.2026, Planer-
# Auftrag): spätere Übernahme von Erzählungen aus Hermes. Über die
# Oberfläche werden weiterhin nur "tippen"/"sprache" gesetzt — die
# POST-Validierung akzeptiert zusätzlich "import".
#
# "generiert" (G1, 02.11.2026): vom Programm erzeugte Bild-/Anlassgeschichte.
# Sie wird nur zusammen mit einer ``art`` gespeichert und ist nie eine Notiz.
QUELLEN_ERLAUBT = ("tippen", "sprache", "import", "generiert")

# Quellen, die eine **Notiz** im Sinn von Sebastians eigenen Worten sind.
NOTIZ_QUELLEN = ("tippen", "sprache", "import")

# Erlaubte ``art`` einer Geschichten-Zeile. Eine Zeile ohne ``art`` ist eine
# Notiz (oder Altbestand, siehe :func:`zeile_einordnen`).
ARTEN_ERLAUBT = ("bildgeschichte", "anlassgeschichte")

TEXT_MAX_LAENGE = 20_000

LIMIT_STANDARD = 200
LIMIT_MIN = 1
LIMIT_MAX = 500

_UMLAUTE = (
    ("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"),
    ("Ä", "ae"), ("Ö", "oe"), ("Ü", "ue"),
)


def ereignisse_pfad() -> str:
    """Ort der (nur lesenden) Ereignisdatei.

    Standard ``~/foto_sortierung/ereignisse.jsonl``, über
    ``ERZAEHL_EREIGNISSE_PFAD`` übersteuerbar (leer/nur Leerzeichen zählt
    nicht).
    """
    ueber = os.environ.get("ERZAEHL_EREIGNISSE_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.expanduser("~"), ERZAEHL_ORDNER, EREIGNISSE_DATEINAME)


def geschichten_pfad() -> str:
    """Ort der (nur anhängenden) Geschichten-Datei.

    Standard ``~/foto_sortierung/geschichten.jsonl``, über
    ``ERZAEHL_GESCHICHTEN_PFAD`` übersteuerbar (leer/nur Leerzeichen zählt
    nicht).
    """
    ueber = os.environ.get("ERZAEHL_GESCHICHTEN_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.expanduser("~"), ERZAEHL_ORDNER, GESCHICHTEN_DATEINAME)


# ── kleine Helfer ────────────────────────────────────────────────────────────

def _als_zahl(wert: Any) -> Optional[int]:
    """Wert als ganze Zahl lesen — sonst ``None`` (``bool`` zählt nie)."""
    if isinstance(wert, bool):
        return None
    if isinstance(wert, int):
        return wert
    if isinstance(wert, float) and wert.is_integer():
        return int(wert)
    if isinstance(wert, str) and wert.strip():
        roh = wert.strip()
        if roh.lstrip("+-").isdigit():
            return int(roh)
    return None


def _normalisieren(text: Any) -> str:
    """Text für den Vergleich vereinheitlichen (klein, Umlaute aufgelöst)."""
    if text is None:
        return ""
    zeichenkette = str(text).strip().lower()
    for umlaut, ersatz in _UMLAUTE:
        zeichenkette = zeichenkette.replace(umlaut, ersatz)
    return zeichenkette


def _limit_begrenzen(limit: Any) -> int:
    wert = _als_zahl(limit)
    if wert is None:
        return LIMIT_STANDARD
    return max(LIMIT_MIN, min(LIMIT_MAX, wert))


def _offset_begrenzen(offset: Any) -> int:
    wert = _als_zahl(offset)
    if wert is None or wert < 0:
        return 0
    return wert


def _titel_aus(ereignis: Dict[str, Any]) -> str:
    """Titel-Rückfall: ``event``, sonst ``thema``, sonst „Ohne Titel"."""
    for feld in ("event", "thema"):
        wert = ereignis.get(feld)
        if isinstance(wert, str) and wert.strip():
            return wert.strip()
    return "Ohne Titel"


def _jetzt_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ── Eigene Anlass-Titel (06.10.2026) ─────────────────────────────────────────
# Sebastian benennt Anlässe im Erzählen selbst; der Name gewinnt vor dem
# automatischen Titel und wird später zum Ordnernamen beim Sortieren (Plan
# Schritt 3). Nur anhängend wie die Geschichten: je Kennung gilt die neueste
# Zeile, ein leerer Name setzt auf den automatischen Titel zurück.

TITEL_DATEINAME = "anlass_umbenennung.jsonl"
TITEL_MAX_LAENGE = 120


def titel_pfad() -> str:
    """``anlass_umbenennung.jsonl`` im Ordner der Geschichten (Tests leiten ihn mit um)."""
    return os.path.join(os.path.dirname(geschichten_pfad()), TITEL_DATEINAME)


def eigene_titel() -> Dict[str, str]:
    """``{kennung: name}`` — neueste Zeile je Kennung, leerer Name = zurückgesetzt. **Wirft nie.**"""
    pfad = titel_pfad()
    if not os.path.isfile(pfad):
        return {}
    namen: Dict[str, str] = {}
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            for roh in datei:
                try:
                    eintrag = json.loads(roh)
                except ValueError:
                    continue
                if not isinstance(eintrag, dict):
                    continue
                kennung, name = eintrag.get("kennung"), eintrag.get("name")
                if isinstance(kennung, str) and kennung and isinstance(name, str):
                    namen[kennung] = name.strip()
    except OSError as e:
        logger.warning("Eigene Titel nicht lesbar (%s): %s", pfad, e)
        return {}
    return {k: n for k, n in namen.items() if n}


def _titel_fuer(ereignis: Dict[str, Any], eigene: Dict[str, str]) -> Tuple[str, bool]:
    """(gültiger Titel, eigener?) — der eigene Name gewinnt vor dem automatischen."""
    name = eigene.get(ereignis.get("kennung") or "")
    if name:
        return name, True
    return _titel_aus(ereignis), False


# ── Ereignisse lesen (nur lesend) ────────────────────────────────────────────

FOTOBUCH_DATEINAME = "fotobuch_ereignisse.jsonl"


def fotobuch_pfad() -> str:
    """Seiten des digitalen Fotobuchs (tools/foto_sortierung/fotobuch_lesen.py, 02.10.2026).

    Liegt im selben Ordner wie ``ereignisse.jsonl`` (Standard
    ``~/foto_sortierung/``; leitet ein Test den Ereignis-Pfad um, wandert das
    Fotobuch mit — echte Daten werden so nie versehentlich gelesen),
    übersteuerbar mit ``ERZAEHL_FOTOBUCH_PFAD``. Zeilenformat wie ``ereignisse.jsonl``.
    """
    ueber = os.environ.get("ERZAEHL_FOTOBUCH_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.dirname(ereignisse_pfad()), FOTOBUCH_DATEINAME)


ORDNER_EREIGNISSE_DATEINAME = "ordner_ereignisse.jsonl"


def ordner_ereignisse_pfad() -> str:
    """Anlässe der Sammlung „Bilder & Videos“ (tools/foto_sortierung/ereignisse_ordner_bauen.py, 07.10.2026).

    Liegt neben ``ereignisse.jsonl`` (wandert mit, wenn ein Test den Pfad
    umleitet), übersteuerbar mit ``ERZAEHL_ORDNER_EREIGNISSE_PFAD``.
    """
    ueber = os.environ.get("ERZAEHL_ORDNER_EREIGNISSE_PFAD")
    if ueber and ueber.strip():
        return ueber.strip()
    return os.path.join(os.path.dirname(ereignisse_pfad()), ORDNER_EREIGNISSE_DATEINAME)


OHNE_DATUM = "9999"


def _zeitschluessel(ereignis: Dict[str, Any]) -> str:
    """Chronologischer Schlüssel: Datum; nur Jahr -> ans Ende des Jahres; nichts -> ganz ans Ende."""
    datum = ereignis.get("datum")
    if isinstance(datum, str) and datum.strip():
        return datum.strip()
    jahr = _als_zahl(ereignis.get("jahr"))
    return f"{jahr:04d}-99" if jahr is not None and jahr >= 0 else OHNE_DATUM


def _ereignisse_laden() -> Tuple[List[Dict[str, Any]], int]:
    """Fotobuch-Seiten (zuerst, in Buchreihenfolge) + ``ereignisse.jsonl``. **Wirft nie.**

    Gibt es Anlässe aus „Bilder & Videos“ (``ordner_ereignisse.jsonl``), werden
    sie mit ``ereignisse.jsonl`` chronologisch zusammengeführt (stabil: bei
    gleichem Datum bleibt die Reihenfolge der Dateien).
    """
    buch, defekt_buch = _datei_ereignisse_laden(fotobuch_pfad())
    rest, defekt_rest = _datei_ereignisse_laden(ereignisse_pfad())
    ordner, defekt_ordner = _datei_ereignisse_laden(ordner_ereignisse_pfad())
    if ordner:
        rest = sorted(rest + ordner, key=_zeitschluessel)
    return buch + rest, defekt_buch + defekt_rest + defekt_ordner


def _datei_ereignisse_laden(pfad: str) -> Tuple[List[Dict[str, Any]], int]:
    """Eine Ereignis-JSONL zeilenweise lesen. **Wirft nie.**

    Liefert ``(gültige_ereignisse, defekte_zeilen)``. Fehlt die Datei, ist
    das Ergebnis ``([], 0)`` — kein Fehler, die App soll ehrlich „noch nicht
    vorhanden" melden können (das übernimmt der Router).
    """
    ereignisse: List[Dict[str, Any]] = []
    defekt = 0

    if not os.path.isfile(pfad):
        return ereignisse, defekt

    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            for zeile in datei:
                zeile = zeile.strip()
                if not zeile:
                    continue
                try:
                    eintrag = json.loads(zeile)
                except ValueError:
                    defekt += 1
                    continue
                if not isinstance(eintrag, dict):
                    defekt += 1
                    continue
                kennung = eintrag.get("kennung")
                if not isinstance(kennung, str) or not kennung.strip():
                    defekt += 1
                    continue
                ereignisse.append(eintrag)
    except OSError as e:
        logger.warning("Ereignisdatei nicht lesbar (%s): %s", pfad, e)
        return [], 0

    return ereignisse, defekt


def _ereignis_datei_kennungen(ereignis: Dict[str, Any]) -> List[int]:
    liste = ereignis.get("datei_kennungen")
    if not isinstance(liste, list):
        return []
    ergebnis: List[int] = []
    for wert in liste:
        zahl = _als_zahl(wert)
        if zahl is not None:
            ergebnis.append(zahl)
    return ergebnis


def anlaesse_zu_kennungen(kennungen: Any, limit: Any = 20) -> List[Dict[str, Any]]:
    """Anlässe, in denen mindestens eine dieser Datei-Kennungen vorkommt.

    Die Verknüpfung **Gesicht → Anlass** (10.10.2026): die Personen-Werkzeuge
    kennen die ``fileid`` je Bild (Quiz-/Gesichts-Zuordnung), die Ereignisse
    tragen ihre Dateien als ``datei_kennungen``. Hier treffen beide zusammen —
    nur lesend, nur Klartext (``kennung, datum, jahr, titel, kategorie,
    anzahl_dateien, treffer``), keine Bilder, keine Pfade. **Wirft nie**,
    neueste zuerst; fehlt eine Ereignisquelle, ist das Ergebnis leer.
    """
    zahlen = {z for z in (_als_zahl(k) for k in (kennungen or [])) if z is not None}
    if not zahlen:
        return []
    ereignisse, _ = _ereignisse_laden()
    eigene = eigene_titel()
    treffer: List[Dict[str, Any]] = []
    for ereignis in ereignisse:
        gemeinsam = zahlen & set(_ereignis_datei_kennungen(ereignis))
        if not gemeinsam:
            continue
        titel, _eigen = _titel_fuer(ereignis, eigene)
        datum = ereignis.get("datum")
        treffer.append({
            "kennung": ereignis.get("kennung"),
            "datum": str(datum)[:10] if isinstance(datum, str) and datum.strip() else None,
            "jahr": _als_zahl(ereignis.get("jahr")),
            "titel": titel,
            "kategorie": ereignis.get("kategorie"),
            "anzahl_dateien": _als_zahl(ereignis.get("anzahl_dateien")),
            "treffer": len(gemeinsam),
        })
    treffer.sort(key=lambda t: (t["datum"] or "", str(t["kennung"] or "")), reverse=True)
    grenze = _als_zahl(limit)
    if grenze is None or grenze < 1:
        grenze = 20
    return treffer[:grenze]


def ereignisse_existiert() -> bool:
    """Liegt eine Ereignisquelle vor (Ereignisse, Fotobuch oder Ordner-Anlässe)? (für den Router-Fehlertext)."""
    return (os.path.isfile(ereignisse_pfad()) or os.path.isfile(fotobuch_pfad())
            or os.path.isfile(ordner_ereignisse_pfad()))


def _ereignis_finden(kennung: str) -> Optional[Dict[str, Any]]:
    if not isinstance(kennung, str) or not kennung.strip():
        return None
    ereignisse, _ = _ereignisse_laden()
    for eintrag in ereignisse:
        if eintrag.get("kennung") == kennung:
            return eintrag
    return None


# ── Geschichten lesen (Schicht "mensch") ─────────────────────────────────────

def _geschichten_laden() -> List[Dict[str, Any]]:
    """Alle Zeilen aus ``geschichten.jsonl``. **Wirft nie.**

    Defekte Zeilen werden übersprungen (die Datei wird nur von diesem
    Dienst geschrieben, defekte Zeilen sind hier kein zu meldender
    Normalfall wie bei den Ereignissen — trotzdem kein Absturz).
    """
    pfad = geschichten_pfad()
    if not os.path.isfile(pfad):
        return []
    zeilen: List[Dict[str, Any]] = []
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            for roh in datei:
                roh = roh.strip()
                if not roh:
                    continue
                try:
                    eintrag = json.loads(roh)
                except ValueError:
                    continue
                if isinstance(eintrag, dict) and isinstance(eintrag.get("id"), str):
                    zeilen.append(eintrag)
    except OSError as e:
        logger.warning("Geschichten nicht lesbar (%s): %s", pfad, e)
        return []
    return zeilen


def _neueste_fassungen(zeilen: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Nur die jeweils neueste Fassung liefern.

    Eine Zeile gilt als ERSETZT, sobald irgendeine andere Zeile sie über
    ``ersetzt`` referenziert — unabhängig davon, an welchem Ereignis/Bild
    sie hängt. Zeilen mit geloescht=True gelten als gelöscht.
    """
    ersetzte_ids = {
        eintrag.get("ersetzt")
        for eintrag in zeilen
        if isinstance(eintrag.get("ersetzt"), str) and eintrag.get("ersetzt")
    }
    return [
        eintrag for eintrag in zeilen
        if eintrag.get("id") not in ersetzte_ids and not eintrag.get("geloescht")
    ]


# ── Notiz oder Geschichte? (G1, 02.11.2026) ─────────────────────────────────
# Frühere Fassungen des Knopfes „Bildgeschichte" haben das erzeugte Ergebnis wie
# eine Notiz gespeichert (``quelle: "tippen"``). Aus diesen Zeilen (Altbestand)
# wurde beim nächsten Lauf wieder eine „Notiz", und die Geschichte verschachtelte
# sich. Damit das nicht mehr passiert, gibt es EINE Regel an EINER Stelle:
# :func:`zeile_einordnen`. Die Datei wird nie umgeschrieben — nur gelesen.
#
# Festes Wortlaut-Inventar der früheren Generator-Fassungen als Paare
# (Satz, Stufe). Beleg je Eintrag und Commit (1da2f9f, 27466f2, 96de1fc,
# 05db80b): ``.hermes/plans/2026-11-02_geschichte-altbestand-saetze.md``.
#   E = eindeutig: Ein Treffer irgendwo im Text genügt.
#   M = mehrdeutig: zählt nur am Satzanfang und erst ab ZWEI verschiedenen M.
ALTE_GENERATOR_SAETZE: Tuple[Tuple[str, str], ...] = (
    ("Auf dem Bild sind", "M"),
    ("Auf dem Bild zu sehen:", "M"),
    ("Auf dem Foto bin ich zusammen mit", "M"),
    ("Auf dem Foto wird dieser Augenblick lebendig:", "E"),
    ("Auf dem ersten Foto wird dieser Augenblick lebendig:", "E"),
    ("Auf den Bildern bin ich allein zu sehen.", "M"),
    ("Auf der Aufnahme wird die Szene sichtbar:", "E"),
    ("Auf diesem Bild bin ich allein zu sehen.", "M"),
    ("Auf diesem Bild sind", "M"),
    ("Aufnahmen aus dem Familienarchiv zum Anlass „", "E"),
    ("Aufnahmen zum Anlass „", "E"),
    ("Aus den überlieferten Aufzeichnungen:", "E"),
    ("Das Bild zeigt", "M"),
    ("Das Foto fängt diesen Augenblick ein:", "E"),
    ("Das Foto fängt diesen Moment lebendig ein:", "E"),
    ("Das ist die Geschichte zu unserem Anlass „", "E"),
    ("Das ist die Geschichte zu „", "E"),
    ("Das ist eine schöne Erinnerung aus meiner Sammlung.", "E"),
    ("Dazu die persoenliche Notiz:", "E"),
    ("Der Anlass umfasst eine Einzelaufnahme.", "E"),
    ("Die Aufnahme zeigt", "M"),
    ("Die Aufnahmen dokumentieren das Geschehen:", "E"),
    ("Die Aufnahmen fangen die Szenen ein:", "E"),
    ("Die Aufnahmen fangen die Szenen warm ein:", "E"),
    ("Die Fotoreihe umfasst", "M"),
    ("Die visuelle Aufnahme zeigt:", "E"),
    ("Die visuelle Bildanalyse dokumentiert:", "E"),
    ("Die visuelle Bildanalyse hält fest:", "E"),
    ("Diese Aufnahmen entstanden in", "M"),
    ("Dieser Moment ist auf einem Foto festgehalten.", "E"),
    ("Dieses Foto entstand in", "M"),
    ("Dieses Foto wurde in", "M"),
    ("Dort bin ich zusammen mit", "M"),
    ("Ein Augenblick voller Geborgenheit, der diese Zeit lebendig hält.", "E"),
    ("Ein archiviertes Kapitel im Fotobestand.", "E"),
    ("Ein authentisches Zeitdokument, das diesen Lebensabschnitt festhält.", "E"),
    ("Ein festgehaltener Augenblick aus dem Fotoarchiv.", "E"),
    ("Ein festgehaltener Augenblick aus der Chronik", "E"),
    ("Ein lebendiges Zeitdokument in der Fotogalerie.", "E"),
    ("Ein schoener Moment, der hier auf diesem Foto festgehalten ist.", "E"),
    ("Ein schöner Moment zusammen mit", "M"),
    ("Ein vertrauter Augenblick in", "M"),
    ("Ein weiteres Bild zeigt:", "M"),
    ("Ein weiteres Foto hält fest:", "M"),
    ("Ein weiteres Foto zeigt:", "M"),
    ("Ein zusammenhängendes Ereignis aus dem Fotoarchiv.", "E"),
    ("Eine Aufnahme in", "M"),
    ("Eine Aufnahme zum Ereignis „", "E"),
    ("Eine Fotodokumentation zu „", "E"),
    ("Eine Momentaufnahme zu „", "E"),
    ("Eine besondere Erinnerung an unseren Anlass „", "E"),
    ("Eine lebendige Bilderreihe, die diese gemeinsamen Erinnerungen für immer bewahrt.", "E"),
    ("Eine schöne Erinnerung an „", "M"),
    ("Eine wertvolle Erinnerung, die für immer bleibt.", "M"),
    ("Eine wunderbare Erinnerung an „", "M"),
    ("Eine wunderbare Fotoserie, die diesen Anlass lebendig hält.", "E"),
    ("Es ist eine wertvolle Erinnerung in meiner Sammlung.", "E"),
    ("Fotodokumentation zu „", "E"),
    ("Fotodokumentation zum Anlass „", "E"),
    ("Genau dieser vertraute Moment eröffnet das Fotobuch – ein Bild voller Wärme, das man sich immer wieder gern ansieht.", "E"),
    ("Ich erinnere mich gern an diese Zeit", "M"),
    ("Ich erinnere mich gut an diese Zeit", "M"),
    ("Ich erinnere mich gut an diesen Moment", "M"),
    ("Im Mittelpunkt stehen", "M"),
    ("Meine Erinnerung dazu:", "M"),
    ("Mit dabei waren", "M"),
    ("Weitere Aufnahmen zeigen:", "M"),
    ("Weitere Motive fangen ein:", "E"),
    ("Zu diesem Anlass gehören", "M"),
)

_ALT_E = tuple(satz for satz, stufe in ALTE_GENERATOR_SAETZE if stufe == "E")
_ALT_M = tuple(satz for satz, stufe in ALTE_GENERATOR_SAETZE if stufe == "M")
_SATZGRENZE = re.compile(r"(?<=[.!?]) ")


def ist_erzeugt_alt(text: Any) -> bool:
    """Stammt ``text`` aus einer früheren Generator-Fassung? (reine Lesefunktion)

    Regel: mindestens ein E-Satz irgendwo im Text ODER mindestens zwei
    verschiedene M-Sätze am Satzanfang (Textanfang oder nach ``. ``, ``! ``,
    ``? `` bzw. einem Zeilenumbruch). Leerraum wird vor dem Vergleich
    zusammengezogen, Groß-/Kleinschreibung bleibt.
    """
    if not isinstance(text, str) or not text.strip():
        return False
    zeilen = [" ".join(z.split()) for z in text.splitlines()]
    zeilen = [z for z in zeilen if z]
    gesamt = " ".join(zeilen)
    if any(satz in gesamt for satz in _ALT_E):
        return True
    treffer = set()
    for zeile in zeilen:
        for abschnitt in _SATZGRENZE.split(zeile):
            for satz in _ALT_M:
                if abschnitt.startswith(satz):
                    treffer.add(satz)
                    if len(treffer) >= 2:
                        return True
    return False


def zeile_einordnen(zeile: Any) -> Dict[str, Any]:
    """Einordnung einer Geschichten-Zeile: ``{ist_notiz, ist_altbestand, art}``.

    * Zeile mit ``art`` (Bild-/Anlassgeschichte): keine Notiz, kein Altbestand.
    * ``notiz_bestaetigt: true``: immer Notiz, nie Altbestand („Das ist meine Notiz").
    * Sonst Altbestand, wenn :func:`ist_erzeugt_alt` den Text erkennt.
    * Notiz = ohne ``art``, ``quelle`` in tippen/sprache/import, kein Altbestand.
    """
    if not isinstance(zeile, dict):
        return {"ist_notiz": False, "ist_altbestand": False, "art": None}
    art = zeile.get("art")
    art = art.strip() if isinstance(art, str) and art.strip() else None
    if art:
        return {"ist_notiz": False, "ist_altbestand": False, "art": art}
    if zeile.get("notiz_bestaetigt") is True:
        return {"ist_notiz": True, "ist_altbestand": False, "art": None}
    if ist_erzeugt_alt(zeile.get("text")):
        return {"ist_notiz": False, "ist_altbestand": True, "art": None}
    return {
        "ist_notiz": zeile.get("quelle") in NOTIZ_QUELLEN,
        "ist_altbestand": False,
        "art": None,
    }


def eigene_notizen(ereignis_kennung: Optional[str] = None,
                   fileid: Any = None) -> List[Dict[str, Any]]:
    """ALLE Notizen (neueste Fassungen, nach ``zeit`` sortiert) — Quelle des Generators.

    Nur Zeilen mit ``ist_notiz`` — nie eine Bild-/Anlassgeschichte, nie Altbestand.

    * Mit ``fileid`` (Bildweg): Notizen an diesem Bild, dazu die Notizen zur
      ganzen Gruppe des Ereignisses (``datei_kennung`` leer), falls
      ``ereignis_kennung`` gegeben ist.
    * Ohne ``fileid`` (Anlassweg): alle Notizen des Ereignisses.
    * Ohne beides: leere Liste.
    """
    ek = ereignis_kennung.strip() if isinstance(ereignis_kennung, str) and ereignis_kennung.strip() else None
    fid = _als_zahl(fileid) if fileid is not None else None
    if ek is None and fid is None:
        return []
    treffer: List[Dict[str, Any]] = []
    for zeile in _neueste_fassungen(_geschichten_laden()):
        einordnung = zeile_einordnen(zeile)
        if not einordnung["ist_notiz"]:
            continue
        dk = _als_zahl(zeile.get("datei_kennung"))
        if fid is not None:
            if dk is not None:
                if dk != fid:
                    continue
            elif ek is None or zeile.get("ereignis_kennung") != ek:
                continue
        elif zeile.get("ereignis_kennung") != ek:
            continue
        treffer.append({**zeile, **einordnung})
    treffer.sort(key=lambda z: str(z.get("zeit") or ""))
    return treffer


def _notizen_zu_text(notizen: List[Dict[str, Any]]) -> str:
    """Alle Notizen als ein Text für die Schablone (jede als eigener Satz)."""
    teile: List[str] = []
    for notiz in notizen:
        sauber = _notiz_fuer_geschichte(notiz.get("text"))
        if not sauber:
            continue
        if sauber[-1] not in ".!?":
            sauber += "."
        teile.append(sauber)
    return " ".join(teile)


def geschichten(ereignis_kennung: Optional[str] = None,
                datei_kennung: Optional[int] = None) -> List[Dict[str, Any]]:
    """Geschichten (nur neueste Fassung), optional gefiltert.

    Jede Zeile trägt zusätzlich ``ist_notiz``, ``ist_altbestand`` und ``art``
    (siehe :func:`zeile_einordnen`). Ohne Filter kommen alle aktuellen
    Geschichten zurück. **Wirft nie** — fehlt die Datei, ist das Ergebnis eine
    leere Liste.
    """
    alle = _neueste_fassungen(_geschichten_laden())
    ek = ereignis_kennung.strip() if isinstance(ereignis_kennung, str) else None
    dk = _als_zahl(datei_kennung) if datei_kennung is not None else None

    ergebnis: List[Dict[str, Any]] = []
    for eintrag in alle:
        if ek and eintrag.get("ereignis_kennung") != ek:
            continue
        if dk is not None and _als_zahl(eintrag.get("datei_kennung")) != dk:
            continue
        ergebnis.append({**eintrag, **zeile_einordnen(eintrag)})
    return ergebnis


# ── Ereignisliste / -detail ──────────────────────────────────────────────────

def ereignisse_liste(jahr: Any = None, suche: Any = None, min_bilder: Any = 1,
                     limit: Any = LIMIT_STANDARD, offset: Any = 0,
                     neueste_zuerst: Any = False) -> Dict[str, Any]:
    """Gefilterte Ereignisliste fürs Frontend.

    Liefert ``{"eintraege": [...], "gesamt": n, "defekte_zeilen": n}``. Jeder
    Eintrag trägt ``kennung, datum, jahr, titel, kategorie, anzahl_dateien,
    vorschau_kennungen (erste 4), anzahl_geschichten``. Sortiert wird nach Datum über
    alle Quellen, ``neueste_zuerst`` absteigend (F1); Anlässe ohne Datum und Jahr
    stehen in beiden Richtungen am Ende (03.11.2026). Danach wird geblättert. **Wirft nie.**
    """
    ereignisse, defekt = _ereignisse_laden()

    jahr_wert = _als_zahl(jahr)
    suche_wert = _normalisieren(suche) or None
    min_bilder_wert = _als_zahl(min_bilder)
    if min_bilder_wert is None or min_bilder_wert < 0:
        min_bilder_wert = 1
    grenze = _limit_begrenzen(limit)
    versatz = _offset_begrenzen(offset)

    eigene = eigene_titel()
    alle_geschichten = _neueste_fassungen(_geschichten_laden())
    geschichten_je_ereignis: Dict[str, int] = {}
    for eintrag in alle_geschichten:
        if not zeile_einordnen(eintrag)["ist_notiz"]:
            continue  # Kachelzähler „✎ n": keine Bild-/Anlassgeschichte, kein Altbestand
        ek = eintrag.get("ereignis_kennung")
        if isinstance(ek, str) and ek:
            geschichten_je_ereignis[ek] = geschichten_je_ereignis.get(ek, 0) + 1

    treffer: List[Tuple[str, Dict[str, Any]]] = []
    for ereignis in ereignisse:
        kennung = ereignis.get("kennung")
        if not isinstance(kennung, str) or not kennung.strip():
            continue

        dateien = _ereignis_datei_kennungen(ereignis)
        anzahl_dateien = _als_zahl(ereignis.get("anzahl_dateien"))
        if anzahl_dateien is None:
            anzahl_dateien = len(dateien)
        if anzahl_dateien < min_bilder_wert:
            continue

        if jahr_wert is not None and _als_zahl(ereignis.get("jahr")) != jahr_wert:
            continue

        titel, titel_eigen = _titel_fuer(ereignis, eigene)
        automatisch = _titel_aus(ereignis)
        if suche_wert is not None and suche_wert not in _normalisieren(titel) \
                and suche_wert not in _normalisieren(automatisch):
            continue

        treffer.append((_zeitschluessel(ereignis), {
            "kennung": kennung,
            "datum": ereignis.get("datum") if isinstance(ereignis.get("datum"), str) else None,
            "jahr": _als_zahl(ereignis.get("jahr")),
            "titel": titel,
            "titel_eigen": titel_eigen,
            "titel_automatisch": automatisch,
            "kategorie": ereignis.get("kategorie") if isinstance(ereignis.get("kategorie"), str) else None,
            "anzahl_dateien": anzahl_dateien,
            "vorschau_kennungen": dateien[:4],
            "anzahl_geschichten": geschichten_je_ereignis.get(kennung, 0),
        }))

    # Stabil sortiert: bei gleichem Datum bleibt die Reihenfolge der Quellen (auch absteigend).
    datiert = sorted((p for p in treffer if p[0] != OHNE_DATUM), key=lambda p: p[0],
                     reverse=neueste_zuerst is True)
    reihe = [t for _, t in datiert] + [t for z, t in treffer if z == OHNE_DATUM]
    gesamt = len(reihe)
    seite = reihe[versatz:versatz + grenze]
    return {"eintraege": seite, "gesamt": gesamt, "defekte_zeilen": defekt}


def ereignis_detail(kennung: str) -> Optional[Dict[str, Any]]:
    """Ein Ereignis mit allen Datei-Kennungen und seinen Geschichten.

    ``None``, wenn die Kennung unbekannt ist (oder die Datei fehlt) —
    der Router macht daraus einen ehrlichen Fehlertext.
    """
    ereignis = _ereignis_finden(kennung)
    if ereignis is None:
        return None

    dateien = _ereignis_datei_kennungen(ereignis)
    titel, titel_eigen = _titel_fuer(ereignis, eigene_titel())
    return {
        "kennung": ereignis.get("kennung"),
        "datum": ereignis.get("datum") if isinstance(ereignis.get("datum"), str) else None,
        "jahr": _als_zahl(ereignis.get("jahr")),
        "titel": titel,
        "titel_eigen": titel_eigen,
        "titel_automatisch": _titel_aus(ereignis),
        "kategorie": ereignis.get("kategorie") if isinstance(ereignis.get("kategorie"), str) else None,
        "anzahl_dateien": _als_zahl(ereignis.get("anzahl_dateien")) or len(dateien),
        "datei_kennungen": dateien,
        "geschichten": geschichten(ereignis_kennung=kennung),
    }


# ── Was ist auf dem Bild, wo entstand es? (07.10.2026) ───────────────────────
# Sebastian: „genauere Beschreibung der einzelnen Bilder mit den Orten … wer wo
# drauf ist". Beides liegt schon am PC vor (Bildbeschreibungen aus dem
# Kontaktbogen-Lauf, Orte aus der OpenStreetMap-Zuordnung) und kommt per
# Übergabe neben ``ereignisse.jsonl``. Nur lesend; je Datei ein Zwischenspeicher,
# der erst bei geänderter Datei (Zeit/Größe) neu liest.

BESCHREIBUNGEN_DATEINAME = "bild_beschreibungen.jsonl"
# Reiche KI-Beschreibungen der Werkzeuge (Fotobuch u. a. stehen NUR hier); das Handy
# muss sie mit übernehmen (03.11.2026: Fotobuch 0 von 842 beschrieben am Handy).
REICHE_BESCHREIBUNGEN_DATEINAMEN = (
    "bild_beschreibungen_reich.jsonl",
    "bild_beschreibungen_papa_reich.jsonl",
    "bild_beschreibungen_rest_reich.jsonl",
    "bild_beschreibungen_altbestand_reich.jsonl",
)
BILD_ORTE_DATEINAME = "bild_orte.csv"
BESCHREIBUNG_MAX_LAENGE = 600

# Herkunft einer Beschreibung (G2, 02.11.2026). ``ki`` = Werkzeuge / SQLite / ``*_reich``
# (Zeilen ohne ``quelle``); ``hand`` = von Sebastian geschrieben; ``einzel_ki`` = Vorschlag
# für ein einzelnes Bild, von ihm übernommen. App-Zeilen tragen ``quelle`` und gehen vor.
HERKUNFT_KI = "ki"
QUELLE_HAND = "hand"
QUELLE_EINZEL_KI = "einzel_ki"
APP_BESCHREIBUNG_QUELLEN = (QUELLE_HAND, QUELLE_EINZEL_KI)
_BILDINFO_SPEICHER: Dict[str, Tuple[Tuple[float, int], Dict[int, Any]]] = {}


def beschreibungen_pfad() -> str:
    """``bild_beschreibungen.jsonl`` neben ``ereignisse.jsonl`` (wandert in Tests mit)."""
    return os.path.join(os.path.dirname(ereignisse_pfad()), BESCHREIBUNGEN_DATEINAME)


def life_archive_pfad() -> str:
    """``life_archive.db`` neben ``ereignisse.jsonl`` (wandert in Tests mit)."""
    return os.path.join(os.path.dirname(ereignisse_pfad()), "life_archive.db")


def _beschreibungen_sqlite_lesen(pfad: str) -> Dict[int, str]:
    """{fileid: beschreibung} aus SQLite life_archive.db (bevorzugt beschreibung_reich)."""
    import sqlite3
    ergebnis: Dict[int, str] = {}
    try:
        with sqlite3.connect(f"file:{pfad}?mode=ro", uri=True) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT fileid, beschreibung, beschreibung_reich FROM photos")
            for fid, b_basis, b_reich in cursor.fetchall():
                text = (b_reich if b_reich and b_reich.strip() else b_basis) or ""
                if text.strip():
                    ergebnis[int(fid)] = " ".join(text.split())[:BESCHREIBUNG_MAX_LAENGE]
    except Exception as e:
        logger.warning("Bild-Beschreibungen aus SQLite nicht lesbar (%s): %s", pfad, e)
    return ergebnis


def bild_orte_pfad() -> str:
    """``bild_orte.csv`` (tools/foto_sortierung/orte_aus_karte.py --zuordnen) neben ``ereignisse.jsonl``."""
    return os.path.join(os.path.dirname(ereignisse_pfad()), BILD_ORTE_DATEINAME)


def _zwischengespeichert(pfad: str, lesen) -> Dict[int, Any]:
    """Datei nur neu lesen, wenn sie sich geändert hat. **Wirft nie.**"""
    try:
        stand = os.stat(pfad)
    except OSError:
        return {}
    schluessel = (stand.st_mtime, stand.st_size)
    alt = _BILDINFO_SPEICHER.get(pfad)
    if alt and alt[0] == schluessel:
        return alt[1]
    try:
        daten = lesen(pfad)
    except (OSError, ValueError, UnicodeDecodeError) as e:
        logger.warning("Bild-Info nicht lesbar (%s): %s", pfad, e)
        daten = {}
    _BILDINFO_SPEICHER[pfad] = (schluessel, daten)
    return daten


def _beschreibungen_lesen(pfad: str) -> Dict[int, Tuple[str, str]]:
    """``{fileid: (text, herkunft)}`` — die Datei wächst nur an, die letzte Zeile je Bild gilt.

    Herkunft (G2, 02.11.2026): ``ki`` für Zeilen ohne ``quelle`` (Werkzeuge, ``*_reich``),
    ``hand`` / ``einzel_ki`` für Zeilen, die die App geschrieben hat (Feld ``quelle``).
    App-Zeilen gehen vor: eine spätere Werkzeugzeile derselben Datei überschreibt sie nicht,
    unter App-Zeilen gewinnt die neueste.
    """
    ergebnis: Dict[int, Tuple[str, str]] = {}
    with open(pfad, "r", encoding="utf-8", errors="ignore") as datei:
        for zeile in datei:
            try:
                eintrag = json.loads(zeile)
            except ValueError:
                continue
            if not isinstance(eintrag, dict):
                continue
            fileid = _als_zahl(eintrag.get("fileid"))
            text = eintrag.get("beschreibung_reich") or eintrag.get("beschreibung")
            if fileid is None or not isinstance(text, str) or not text.strip():
                continue
            quelle = eintrag.get("quelle")
            herkunft = quelle if quelle in APP_BESCHREIBUNG_QUELLEN else HERKUNFT_KI
            if herkunft == HERKUNFT_KI and fileid in ergebnis and ergebnis[fileid][1] != HERKUNFT_KI:
                continue                       # App-Zeile bleibt vor späteren Werkzeugzeilen
            ergebnis[fileid] = (" ".join(text.split())[:BESCHREIBUNG_MAX_LAENGE], herkunft)
    return ergebnis


def beschreibungen_alle_pfade() -> List[str]:
    """Liefert alle vorhandenen Beschreibungsdateien (JSONL) im Foto-Ordner."""
    ordner = os.path.dirname(ereignisse_pfad())
    kandidaten = [beschreibungen_pfad()] + [
        os.path.join(ordner, name) for name in REICHE_BESCHREIBUNGEN_DATEINAMEN]
    pfade: List[str] = []
    for p in kandidaten:
        if os.path.isfile(p) and p not in pfade:
            pfade.append(p)
    return pfade


def _beschreibungen_mit_herkunft() -> Dict[int, Tuple[str, str]]:
    """``{fileid: (text, herkunft)}`` aus SQLite und allen JSONL-Beständen (G2, 02.11.2026).

    Reihenfolge: zuerst SQLite, dann die JSONL-Dateien (reiche Texte überschreiben Basis-Texte),
    ZULETZT die Zeilen, die die App geschrieben hat (``quelle`` ``hand`` oder ``einzel_ki``):
    die neueste App-Zeile gewinnt gegen alle ``*_reich``-Dateien und SQLite. Die Herkunft ist
    die der zuletzt angewendeten Zeile — ``ki``, ``hand`` oder ``einzel_ki``.
    """
    ergebnis: Dict[int, Tuple[str, str]] = {}
    db_pfad = life_archive_pfad()
    if os.path.isfile(db_pfad):
        try:
            for fid, text in _zwischengespeichert(db_pfad, _beschreibungen_sqlite_lesen).items():
                ergebnis[fid] = (text, HERKUNFT_KI)
        except Exception as e:
            logger.warning("SQLite Beschreibungen fehlgeschlagen: %s", e)

    app_zeilen: Dict[int, Tuple[str, str]] = {}
    for j_pfad in beschreibungen_alle_pfade():
        try:
            j_daten = _zwischengespeichert(j_pfad, _beschreibungen_lesen)
        except Exception as e:
            logger.warning("JSONL Beschreibungen (%s) fehlgeschlagen: %s", j_pfad, e)
            continue
        for fid, (text, herkunft) in j_daten.items():
            if herkunft == HERKUNFT_KI:
                ergebnis[fid] = (text, herkunft)
            else:
                app_zeilen[fid] = (text, herkunft)
    ergebnis.update(app_zeilen)
    return ergebnis


def _beschreibungen_gesamt_lesen() -> Dict[int, str]:
    """``{fileid: text}`` — dünne Hülle über :func:`_beschreibungen_mit_herkunft`."""
    return {fid: text for fid, (text, _herkunft) in _beschreibungen_mit_herkunft().items()}


def beschreibung_holen(fileid: Any) -> Optional[str]:
    """Beschreibung eines einzelnen Bildes holen (aus SQLite oder JSONL)."""
    fid = _als_zahl(fileid)
    if fid is None:
        return None
    beschreibungen = _beschreibungen_gesamt_lesen()
    return beschreibungen.get(fid)


def beschreibung_mit_herkunft_holen(fileid: Any) -> Tuple[Optional[str], Optional[str]]:
    """``(text, herkunft)`` eines Bildes — ``(None, None)`` bei unbekannter Kennung oder ohne Text."""
    fid = _als_zahl(fileid)
    if fid is None:
        return None, None
    eintrag = _beschreibungen_mit_herkunft().get(fid)
    return eintrag if eintrag else (None, None)


def _beschreibung_schreiben(fileid: Any, text: str, quelle: str) -> Dict[str, Any]:
    """Eine App-Zeile (``quelle`` ``hand`` oder ``einzel_ki``) anhängen und SQLite nachziehen."""
    fid = _als_zahl(fileid)
    if fid is None:
        return {"ok": False, "fehler": "Ungültige Bildkennung."}
    sauberer_text = " ".join((text or "").split())[:BESCHREIBUNG_MAX_LAENGE]

    jsonl_pfad = beschreibungen_pfad()
    try:
        os.makedirs(os.path.dirname(jsonl_pfad), exist_ok=True)
        with open(jsonl_pfad, "a", encoding="utf-8") as datei:
            eintrag = {
                "fileid": fid,
                "beschreibung": sauberer_text,
                "quelle": quelle,
                "zeit": datetime.now().isoformat()
            }
            datei.write(json.dumps(eintrag, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning("Konnte bild_beschreibungen.jsonl nicht schreiben: %s", e)
        return {"ok": False, "fehler": f"Speichern fehlgeschlagen: {e}"}

    db_pfad = life_archive_pfad()
    if os.path.isfile(db_pfad):
        try:
            import sqlite3
            with sqlite3.connect(db_pfad) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE photos SET beschreibung_reich = ?, beschreibung = ? WHERE fileid = ?",
                    (sauberer_text, sauberer_text, fid)
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        "INSERT INTO photos (fileid, beschreibung, beschreibung_reich) VALUES (?, ?, ?)",
                        (fid, sauberer_text, sauberer_text)
                    )
                conn.commit()
        except Exception as e:
            logger.warning("Konnte SQLite beschreibung nicht aktualisieren: %s", e)

    _BILDINFO_SPEICHER.clear()
    return {"ok": True, "fileid": fid, "beschreibung": sauberer_text}


def beschreibung_speichern(fileid: Any, text: str) -> Dict[str, Any]:
    """Von Hand geschriebene Beschreibung speichern (Zeile mit ``quelle`` ``hand``).

    Seit G2 gewinnt sie gegen alle ``*_reich``-Dateien. Ein leerer Text wird zwar angehängt,
    beim Lesen aber übersprungen (er löscht nichts).
    """
    return _beschreibung_schreiben(fileid, text, QUELLE_HAND)


def beschreibung_uebernehmen_ki(fileid: Any, text: str) -> Dict[str, Any]:
    """Einen bestätigten KI-Vorschlag übernehmen (Zeile mit ``quelle`` ``einzel_ki``).

    Genau eine Zeile; ein leerer Text wird nicht gespeichert.
    """
    if not " ".join((text or "").split()):
        return {"ok": False, "fehler": "Eine leere Beschreibung wird nicht übernommen."}
    return _beschreibung_schreiben(fileid, text, QUELLE_EINZEL_KI)


def _bild_orte_lesen(pfad: str) -> Dict[int, Dict[str, Any]]:
    """``{fileid: {"landmarke", "art", "ort"}}`` aus ``bild_orte.csv`` — ohne Hausnummern, ohne Koordinaten."""
    import csv

    ergebnis: Dict[int, Dict[str, Any]] = {}
    with open(pfad, "r", encoding="utf-8", newline="") as datei:
        for zeile in csv.DictReader(datei):
            fileid = _als_zahl(zeile.get("fileid"))
            landmarke = (zeile.get("landmarke") or "").strip()
            ort = (zeile.get("ort_osm") or "").strip()
            if fileid is None or not (landmarke or ort):
                continue
            ergebnis[fileid] = {"landmarke": landmarke or None,
                                "art": (zeile.get("landmarke_art") or "").strip() or None,
                                "ort": ort or None}
    return ergebnis


def bilder_info(kennung: str) -> Optional[Dict[str, Any]]:
    """Beschreibung und Ort je Bild eines Anlasses, dazu die häufigsten Orte.

    ``None`` bei unbekanntem Anlass. Ergebnis ``{"bilder": {fileid: {"beschreibung",
    "ort"}}, "orte": [häufigste Namen, höchstens 3], "mit_beschreibung", "mit_ort",
    "beschreibungen_vorhanden", "orte_vorhanden"}`` — Bilder ohne beides fehlen in
    ``bilder``. **Wirft nie** (fehlende Dateien = leere Angaben).
    """
    ereignis = _ereignis_finden(kennung)
    if ereignis is None:
        return None
    db_pfad = life_archive_pfad()
    jsonl_pfade = beschreibungen_alle_pfade()
    beschreibungen = _beschreibungen_gesamt_lesen()
    orte = _zwischengespeichert(bild_orte_pfad(), _bild_orte_lesen)
    bilder: Dict[str, Dict[str, Any]] = {}
    zaehler: Dict[str, int] = {}
    for fileid in _ereignis_datei_kennungen(ereignis):
        text, ort = beschreibungen.get(fileid), orte.get(fileid)
        if not text and not ort:
            continue
        bilder[str(fileid)] = {"beschreibung": text, "ort": ort}
        name = ort and (ort.get("landmarke") or ort.get("ort"))
        if name:
            zaehler[name] = zaehler.get(name, 0) + 1
    haeufigste = sorted(zaehler.items(), key=lambda kv: (-kv[1], kv[0].casefold()))[:3]
    return {
        "bilder": bilder,
        "orte": [name for name, _ in haeufigste],
        "mit_beschreibung": sum(1 for b in bilder.values() if b["beschreibung"]),
        "mit_ort": sum(1 for b in bilder.values() if b["ort"]),
        "beschreibungen_vorhanden": bool(jsonl_pfade) or os.path.isfile(db_pfad),
        "orte_vorhanden": os.path.isfile(bild_orte_pfad()),
    }


# ── Geschichte speichern (nur anhängend) ─────────────────────────────────────

class GeschichteValidierungsfehler(ValueError):
    """Eine POST-Eingabe verletzt eine Regel — deutscher Klartext im Text."""


def geschichte_speichern(ereignis_kennung: str, text: str, quelle: str,
                         datei_kennung: Optional[int] = None,
                         ersetzt: Optional[str] = None,
                         abfrage: Optional[str] = None,
                         art: Optional[str] = None,
                         notiz_bestaetigt: bool = False) -> Dict[str, Any]:
    """Eine neue Geschichte anhängen (Schicht "mensch").

    Validiert nach den Regeln aus dem Auftrag; wirft
    :class:`GeschichteValidierungsfehler` (deutscher Text) bei ungültiger
    Eingabe. Schreibt **nur anhängend** (``"a"`` + ``flush`` + ``fsync``) und
    liefert die geschriebene Zeile zurück, ergänzt um die Einordnung
    (``ist_notiz``, ``ist_altbestand``, ``art`` — siehe :func:`zeile_einordnen`).

    ``art`` (G1): nur ``bildgeschichte`` oder ``anlassgeschichte``; ohne ``art``
    ist die Zeile eine Notiz. ``notiz_bestaetigt=True`` markiert eine Zeile
    dauerhaft als Notiz („Das ist meine Notiz"), auch wenn der Text wie
    Altbestand aussieht.
    """
    text_wert = text.strip() if isinstance(text, str) else ""
    if not text_wert:
        raise GeschichteValidierungsfehler("Text darf nicht leer sein.")
    if len(text_wert) > TEXT_MAX_LAENGE:
        raise GeschichteValidierungsfehler(
            f"Text ist zu lang ({len(text_wert)} Zeichen, erlaubt sind höchstens "
            f"{TEXT_MAX_LAENGE})."
        )

    quelle_wert = quelle.strip() if isinstance(quelle, str) else ""
    if quelle_wert not in QUELLEN_ERLAUBT:
        raise GeschichteValidierungsfehler(
            f"Quelle '{quelle}' ist ungültig (erlaubt: "
            f"{', '.join(QUELLEN_ERLAUBT)})."
        )

    art_wert: Optional[str] = None
    if art is not None and not (isinstance(art, str) and not art.strip()):
        art_wert = art.strip() if isinstance(art, str) else ""
        if art_wert not in ARTEN_ERLAUBT:
            raise GeschichteValidierungsfehler(
                f"Art '{art}' ist ungültig (erlaubt: {', '.join(ARTEN_ERLAUBT)})."
            )

    ek = ereignis_kennung.strip() if isinstance(ereignis_kennung, str) else ""
    if not ek:
        raise GeschichteValidierungsfehler("Ereignis-Kennung fehlt.")
    ereignis = _ereignis_finden(ek)
    if ereignis is None:
        raise GeschichteValidierungsfehler(f"Ereignis '{ek}' existiert nicht.")

    dk = _als_zahl(datei_kennung) if datei_kennung is not None else None
    if dk is not None:
        gueltige_dateien = _ereignis_datei_kennungen(ereignis)
        if dk not in gueltige_dateien:
            raise GeschichteValidierungsfehler(
                f"Bild {dk} gehört nicht zum Ereignis '{ek}'."
            )

    ersetzt_wert = ersetzt.strip() if isinstance(ersetzt, str) and ersetzt.strip() else None
    if ersetzt_wert is not None:
        vorhandene_ids = {e.get("id") for e in _geschichten_laden()}
        if ersetzt_wert not in vorhandene_ids:
            raise GeschichteValidierungsfehler(
                f"Ersetzte Geschichte '{ersetzt_wert}' existiert nicht."
            )

    zeile = {
        "id": str(uuid.uuid4()),
        "zeit": _jetzt_iso(),
        "schicht": SCHICHT_MENSCH,
        "version": SCHICHT_VERSION,
        "ereignis_kennung": ek,
        "ereignis_datum": ereignis.get("datum") if isinstance(ereignis.get("datum"), str) else None,
        "ereignis_titel": _titel_fuer(ereignis, eigene_titel())[0],
        "datei_kennung": dk,
        "text": text_wert,
        "quelle": quelle_wert,
        "ersetzt": ersetzt_wert,
        "abfrage": abfrage.strip() if isinstance(abfrage, str) and abfrage.strip() else None,
    }
    # Nur gesetzte Felder stehen in der Zeile (die Datei bleibt für Notizen unverändert).
    if art_wert:
        zeile["art"] = art_wert
    if notiz_bestaetigt is True:
        zeile["notiz_bestaetigt"] = True

    pfad = geschichten_pfad()
    ordner = os.path.dirname(pfad)
    if ordner:
        os.makedirs(ordner, exist_ok=True)

    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
        datei.flush()
        os.fsync(datei.fileno())

    return {**zeile, **zeile_einordnen(zeile)}



def geschichte_loeschen(geschichte_id: str) -> Dict[str, Any]:
    """Löscht eine Geschichte (hängt eine Zeile mit 'geloescht: True' und 'ersetzt: <id>' an).

    Schreibt nur anhängend ('a' + flush + fsync) für Revisionssicherheit.
    Wirft GeschichteValidierungsfehler, wenn die ID nicht existiert.
    """
    gid = geschichte_id.strip() if isinstance(geschichte_id, str) else ""
    if not gid:
        raise GeschichteValidierungsfehler("Geschichte-ID fehlt.")
    alle = _neueste_fassungen(_geschichten_laden())
    vorhanden = next((g for g in alle if g.get("id") == gid), None)
    if not vorhanden:
        raise GeschichteValidierungsfehler(f"Geschichte '{gid}' existiert nicht oder ist bereits gelöscht.")

    zeile = {
        "id": str(uuid.uuid4()),
        "zeit": _jetzt_iso(),
        "schicht": SCHICHT_MENSCH,
        "version": SCHICHT_VERSION,
        "ereignis_kennung": vorhanden.get("ereignis_kennung"),
        "datei_kennung": vorhanden.get("datei_kennung"),
        "text": "",
        "quelle": "loeschung",
        "ersetzt": gid,
        "geloescht": True,
    }

    pfad = geschichten_pfad()
    ordner = os.path.dirname(pfad)
    if ordner:
        os.makedirs(ordner, exist_ok=True)

    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
        datei.flush()
        os.fsync(datei.fileno())

    return {"ok": True, "geloescht": gid}


def titel_setzen(kennung: str, name: Any) -> Dict[str, Any]:
    """Eigenen Titel für einen Anlass setzen (leer = zurück zum automatischen).

    Validiert (Anlass existiert, höchstens ``TITEL_MAX_LAENGE`` Zeichen,
    Leerraum zusammengezogen) und wirft :class:`GeschichteValidierungsfehler`
    mit deutschem Text. Schreibt **nur anhängend** (``"a"`` + ``flush`` +
    ``fsync``); die vorige Fassung bleibt in der Datei (Rückweg).
    """
    ek = kennung.strip() if isinstance(kennung, str) else ""
    if not ek:
        raise GeschichteValidierungsfehler("Ereignis-Kennung fehlt.")
    ereignis = _ereignis_finden(ek)
    if ereignis is None:
        raise GeschichteValidierungsfehler(f"Ereignis '{ek}' existiert nicht.")
    wert = " ".join(name.split()) if isinstance(name, str) else ""
    if len(wert) > TITEL_MAX_LAENGE:
        raise GeschichteValidierungsfehler(
            f"Titel ist zu lang ({len(wert)} Zeichen, erlaubt sind höchstens {TITEL_MAX_LAENGE})."
        )
    vorher, _ = _titel_fuer(ereignis, eigene_titel())
    zeile = {"kennung": ek, "name": wert, "zeit": _jetzt_iso(), "vorher": vorher}
    pfad = titel_pfad()
    ordner = os.path.dirname(pfad)
    if ordner:
        os.makedirs(ordner, exist_ok=True)
    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write(json.dumps(zeile, ensure_ascii=False) + "\n")
        datei.flush()
        os.fsync(datei.fileno())
    titel, eigen = _titel_fuer(ereignis, eigene_titel())
    return {"kennung": ek, "titel": titel, "titel_eigen": eigen, "titel_automatisch": _titel_aus(ereignis)}


def format_datum_de(datum_str: Optional[str]) -> str:
    """Wandelt '2018-07-15' oder '2018' in natuerliches Deutsch um ('am 15. Juli 2018' / 'im Jahr 2018')."""
    if not datum_str:
        return ""
    s = str(datum_str).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        jahr, monat, tag = int(m.group(1)), int(m.group(2)), int(m.group(3))
        monate = [
            "Januar", "Februar", "Maerz", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember"
        ]
        if 1 <= monat <= 12:
            return f"am {tag}. {monate[monat - 1]} {jahr}"
    m_jahr = re.match(r"^(\d{4})", s)
    if m_jahr:
        return f"im Jahr {m_jahr.group(1)}"
    return s


# ── Bildanalyse, Prompts & Organische Verschmelzung ──────────────────────────

GESCHICHTE_SYSTEM_PROMPT = """Du bist ein warmherziger, einfühlsamer Chronist und Erzähler für ein persönliches Foto- und Familienarchiv.
Deine Aufgabe ist es, aus Bildbeschreibungen, persönlichen Notizen/Erinnerungen und Metadaten (Personen, Ort, Zeit) eine einzige, harmonisch verschmolzene Geschichte zu weben.

VERBINDLICHE REGELN:
1. ORGANISCHE VERSCHMELZUNG: Verschmelze die sichtbare Bildszene nahtlos mit den persönlichen Gedanken und Erinnerungen der Notiz. Die Geschichte muss wie aus einem Guss klingen – als würde man sich liebevoll an diesen Moment erinnern.
2. KEIN STACCATO, KEINE AUFZÄHLUNG: Schreibe fließende, natürliche Sätze mit melodischen Übergängen. Niemals Faktenlisten („Mit dabei waren: ...“, „Zu diesem Anlass gehören: ...“) oder abgehackte Einzelblöcke aneinanderreihen.
3. KEINE ZITATE: Zitiere die Notiz niemals mit Anführungszeichen oder Zitat-Labels wie „Meine Notiz dazu: ...“. Übernimm die Gedanken, Emotionen und Details direkt und lebendig in die Erzählung.
4. ECHTE BEZIEHUNGEN STATT GENERISCHER ROLLEN: Ersetze generische Begriffe aus der Bildanalyse („ein Erwachsener“, „eine Frau“, „ein Mann“, „ein Baby“) konsequent durch die echten Personen und familiären Beziehungen (z. B. „mein Papa Matthias“, „ich als kleines Baby“).
5. PERSPEKTIVE: Halte die vorgegebene Perspektive („ich“-Form oder neutrale Erzählerperspektive) strikt ein.
6. LÄNGE & VORLESE-QUALITÄT: 3 bis 6 wohlklingende, leicht verständliche Sätze. Keine Schachtelsätze, sondern Text, der beim Vorlesen wie eine echte Erzählung klingt."""


def erstelle_geschichte_prompt(
    titel: Optional[str] = None,
    datum_lesbar: Optional[str] = None,
    ort: Optional[str] = None,
    personen: Optional[List[str]] = None,
    beschreibungen: Optional[List[str]] = None,
    notiz: Optional[str] = None,
    anzahl_dateien: int = 1,
    perspektive: str = "ich"
) -> str:
    """Erstellt den Benutzer-Prompt für eine fließende Verschmelzung durch ein LLM."""
    pers_text = ", ".join(personen) if personen else "Nicht angegeben"
    szenen_text = "; ".join(beschreibungen) if beschreibungen else "Keine visuelle Bildanalyse vorhanden"
    notiz_text = notiz.strip() if notiz else "Keine persönliche Notiz vorhanden"

    return f"""Hier sind die Angaben für die Geschichte:
- Anlass/Titel: {titel or 'Ohne Titel'}
- Datum & Ort: {datum_lesbar or 'Unbekanntes Datum'} in {ort or 'unbekanntem Ort'}
- Beteiligte Personen: {pers_text}
- Anzahl der Aufnahmen: {anzahl_dateien}
- Visuelle Bildbeschreibung(en): {szenen_text}
- Persönliche Notiz/Erinnerung: {notiz_text}
- Gewünschte Erzählperspektive: {'Ich-Form (persönlich, emotional)' if perspektive == 'ich' else 'Erzähler (dokumentarisch, neutral)'}

Bitte verfasse daraus eine lebendige, zusammenhängende Erzählung ohne Staccato oder Faktenaufzählung."""


def deutsch_fuer_bildbeschreibung(text: str) -> str:
    """Übersetzt/glättet typische englische Gemini-Vision-Bildbeschreibungen in natürliches Deutsch (01.11.2026)."""
    if not text or not isinstance(text, str):
        return ""
    t = text.strip()
    ist_deutsch = any(w in t.lower() for w in (" und ", " der ", " die ", " das ", " ein ", " eine ", " im ", " auf dem ", " von "))
    if ist_deutsch and not any(t.startswith(w) for w in ("A ", "An ", "The ", "Two ", "Three ", "Four ", "Several ", "Close-up ")):
        return t

    regeln = [
        (r'\bAn adult lies down indoors playing with a small baby lying beside them\b', 'Ein Erwachsener liegt drinnen und spielt mit einem kleinen Baby, das daneben liegt'),
        (r'\bThe adult playfully makes a face while the baby watches closely\b', 'Er schneidet spielerisch Grimassen, während das Baby aufmerksam zuschaut'),
        (r'\bThe indoor setting is cozy and softly lit\b', 'Die Umgebung ist gemütlich und sanft beleuchtet'),
        (r'\bA young man sits indoors holding two small boys close to him\b', 'Ein junger Mann sitzt drinnen und hält zwei kleine Jungen im Arm'),
        (r'\bEveryone looks pleased and relaxed in the soft indoor light\b', 'Alle wirken zufrieden und entspannt im sanften Raumlicht'),
        (r'\bThe background features simple home decor\b', 'Im Hintergrund sieht man eine schlichte Wohnungseinrichtung'),
        (r'\bA woman and a man sit together outdoors at a wooden table\b', 'Eine Frau und ein Mann sitzen gemeinsam draußen an einem Holztisch'),
        (r'\bThey are talking and smiling with coffee cups placed before them\b', 'Sie unterhalten sich lächelnd mit Kaffeetassen vor sich'),
        (r'\bWarm late-afternoon sunlight illuminates the scene\b', 'Warmes Nachmittagslicht erhellt die Szene'),
        (r'\bA woman and three young boys smile together from a living room sofa\b', 'Eine Frau und drei kleine Jungen lächeln gemeinsam vom Sofa'),
        (r'\bThe indoor scene captures a joyful family portrait\b', 'Die Aufnahme zeigt ein fröhliches Familienporträt'),
        (r'\bA newborn baby rests peacefully\b', 'Ein neugeborenes Baby ruht friedlich'),
        (r'\bA joyful group of friends laughing around a birthday cake\b', 'Eine fröhliche Gruppe von Freunden lacht um eine Geburtstagstorte'),
        (r'\bA close-up view shows\b', 'Eine Nahaufnahme zeigt'),
        (r'\bA close-up shot of\b', 'Eine Nahaufnahme von'),
        (r'\bA wide interior view of\b', 'Ein weiter Blick in'),
        (r'\bAn elevated view captures\b', 'Ein erhöhter Blick zeigt'),
        (r'\bA large crowd of people walks across\b', 'Eine große Menschenmenge geht über'),
        (r'\bMusicians perform on a stage illuminated by\b', 'Musiker spielen auf einer Bühne, erleuchtet von'),
        (r'\bPeople walk along\b', 'Menschen spazieren entlang'),
        (r'\bA person sits reclined on a couch\b', 'Eine Person liegt entspannt auf einer Couch'),
        (r'\bTwo friends laughing by the river\b', 'Zwei Freunde lachen am Flussufer'),
        (r'\bA joyful family portrait\b', 'Ein fröhliches Familienporträt'),
        (r'\bThe mood is calm and peaceful\b', 'Die Stimmung ist ruhig und friedlich'),
        (r'\bThe mood is quiet and relaxed\b', 'Die Atmosphäre ist ruhig und entspannt'),
        (r'\bThe vibe is relaxed and sunny\b', 'Die Stimmung ist entspannt und sonnig'),
        (r'\bunder a clear sky\b', 'unter klarem Himmel'),
        (r'\bin front of\b', 'vor'),
        (r'\bin the background\b', 'im Hintergrund'),
        (r'\bin the foreground\b', 'im Vordergrund'),
        (r'\bat the camera\b', 'in die Kamera'),
        (r'\bsmiling at the camera\b', 'lächelnd in die Kamera'),
    ]
    res = t
    for pattern, repl in regeln:
        res = re.sub(pattern, repl, res, flags=re.IGNORECASE)
    return res


def _notiz_fuer_geschichte(notiz: Optional[str]) -> str:
    """Bereinigt Notizen für die inhaltliche Übernahme (keine Zitatzeichen, keine Notiz-Labels)."""
    if not notiz:
        return ""
    n = notiz.strip().strip('"\'\u201e\u201c\u00bb\u00ab')
    n = re.sub(r'^(Meine Notiz dazu|Meine Erinnerung dazu|Dazu die persönliche Notiz|Dazugehörige Anmerkung|Notiz|Erinnerung)\s*:\s*', '', n, flags=re.IGNORECASE)
    return n.strip().strip('"\'\u201e\u201c\u00bb\u00ab')


def personalisiere_szene(
    beschreibung: str,
    personen: Optional[List[str]] = None,
    notiz: Optional[str] = None,
    perspektive: str = "ich"
) -> str:
    """Ersetzt generische Bildanalyse-Begriffe (Erwachsener, Mann, Frau, Baby) durch reale Personen."""
    if not beschreibung:
        return ""
    b = deutsch_fuer_bildbeschreibung(beschreibung).strip()

    personen_liste = [p.strip() for p in (personen or []) if p and p.strip()]
    notiz_l = (notiz or "").lower()

    hat_papa = any(w in notiz_l for w in ("papa", "vater")) or any("matthias" in p.lower() for p in personen_liste)
    hat_mama = any(w in notiz_l for w in ("mama", "mutter"))
    ist_sebastian = any("sebastian" in p.lower() for p in personen_liste)

    andere_personen = [p for p in personen_liste if p.lower() not in ("sebastian", "ich")]
    andere_text = ", ".join(andere_personen[:-1]) + " und " + andere_personen[-1] if len(andere_personen) > 1 else (andere_personen[0] if andere_personen else "")

    if perspektive == "ich":
        if hat_papa:
            b = re.sub(r'\bEin Erwachsener\b', 'Mein Papa', b)
            b = re.sub(r'\bDer Erwachsene\b', 'Mein Papa', b)
            b = re.sub(r'\bEin Mann\b', 'Mein Papa', b)
            b = re.sub(r'\bDer Mann\b', 'Mein Papa', b)
            if "matthias" in andere_text.lower() and "papa" not in notiz_l:
                b = re.sub(r'\bMein Papa\b', 'Mein Papa Matthias', b, count=1)
        elif andere_text:
            b = re.sub(r'\bEin Mann\b', andere_text, b, count=1)
            b = re.sub(r'\bEine Frau\b', andere_text, b, count=1)
            b = re.sub(r'\bEin Erwachsener\b', andere_text, b, count=1)

        ist_baby = any(w in notiz_l for w in ("baby", "wochen alt", "monate alt", "klein")) or ("baby" in b.lower() and (hat_papa or len(andere_personen) > 0))
        if ist_sebastian and ist_baby:
            b = re.sub(r'\bmit einem kleinen Baby, das daneben liegt\b', 'mit mir als kleinem Baby', b)
            b = re.sub(r'\bmit einem kleinen Baby\b', 'mit mir als kleinem Baby', b)
            b = re.sub(r'\bwährend das Baby aufmerksam zuschaut\b', 'während ich ganz aufmerksam zu ihm aufschaue', b)
            b = re.sub(r'\bdas Baby\b', 'ich', b)
            b = re.sub(r'\bein Baby\b', 'mich als Baby', b)
            b = re.sub(r'\bein kleines Baby\b', 'mich als kleines Baby', b)
            b = re.sub(r'\bein neugeborenes Baby\b', 'mich als Neugeborenes', b)
    else:  # erzaehler
        if hat_papa and andere_text:
            b = re.sub(r'\bEin Erwachsener\b', f'Vater {andere_text}', b)
            b = re.sub(r'\bDer Erwachsene\b', 'Der Vater', b)
        elif andere_text:
            b = re.sub(r'\bEin Erwachsener\b', andere_text, b, count=1)
        if ist_sebastian and any(w in notiz_l for w in ("baby", "wochen alt", "monate alt", "klein")):
            b = re.sub(r'\bmit einem kleinen Baby, das daneben liegt\b', 'mit Sohn Sebastian als kleinem Baby', b)
            b = re.sub(r'\bmit einem kleinen Baby\b', 'mit Sohn Sebastian als kleinem Baby', b)
            b = re.sub(r'\bwährend das Baby aufmerksam zuschaut\b', 'während das kleine Baby aufmerksam zusieht', b)

    return b


def verschmelze_geschichte(
    titel: Optional[str] = None,
    datum_text: Optional[str] = None,
    ort: Optional[str] = None,
    personen: Optional[List[str]] = None,
    beschreibungen: Optional[List[str]] = None,
    notiz: Optional[str] = None,
    anzahl_dateien: int = 1,
    perspektive: str = "ich"
) -> str:
    """Verschmilzt Bildinhalt, Notizen und Metadaten zu einer fließenden Geschichte ohne Staccato."""
    personen_liste = [p.strip() for p in (personen or []) if p and p.strip()]
    beschr_liste = [b.strip() for b in (beschreibungen or []) if b and b.strip()]

    # 1. Szenen personalisieren
    szenen_personalisiert = [personalisiere_szene(b, personen_liste, notiz, perspektive) for b in beschr_liste]
    hauptszene = szenen_personalisiert[0] if szenen_personalisiert else ""
    nebenszene = szenen_personalisiert[1] if len(szenen_personalisiert) > 1 else ""

    # 2. Notiz säubern
    notiz_sauber = _notiz_fuer_geschichte(notiz)
    titel_sauber = (titel or "").strip()
    ort_sauber = (ort or "").strip()
    datum_sauber = (datum_text or "").strip()

    andere_personen = [p for p in personen_liste if p.lower() not in ("sebastian", "ich")]
    andere_text = ", ".join(andere_personen[:-1]) + " und " + andere_personen[-1] if len(andere_personen) > 1 else (andere_personen[0] if andere_personen else "")
    alle_pers_text = ", ".join(personen_liste[:-1]) + " und " + personen_liste[-1] if len(personen_liste) > 1 else (personen_liste[0] if personen_liste else "")

    teile: List[str] = []

    if perspektive == "ich":
        notiz_k = notiz_sauber.lower()

        # 1. Warmherziger situativer Rahmen (Ort, Datum, Titel, Personen)
        rahmen_teile: List[str] = []
        if titel_sauber and datum_sauber and ort_sauber:
            rahmen_teile.append(f"Eine wunderbare Erinnerung an „{titel_sauber}“ {datum_sauber} in {ort_sauber}")
        elif titel_sauber and datum_sauber:
            rahmen_teile.append(f"Eine schöne Erinnerung an „{titel_sauber}“ {datum_sauber}")
        elif titel_sauber and ort_sauber:
            rahmen_teile.append(f"Eine Momentaufnahme zu „{titel_sauber}“ in {ort_sauber}")
        elif titel_sauber:
            rahmen_teile.append(f"Eine besondere Erinnerung an unseren Anlass „{titel_sauber}“")
        elif datum_sauber and ort_sauber:
            rahmen_teile.append(f"Ich erinnere mich gut an diesen Moment {datum_sauber} in {ort_sauber}")
        elif datum_sauber:
            rahmen_teile.append(f"Ich erinnere mich gut an diese Zeit {datum_sauber}")
        elif ort_sauber:
            rahmen_teile.append(f"Ein vertrauter Augenblick in {ort_sauber}")

        if andere_text:
            if rahmen_teile:
                if "erinnere mich" in rahmen_teile[0].lower():
                    rahmen_teile.append(f"mit {andere_text}")
                else:
                    rahmen_teile.append(f"zusammen mit {andere_text}")
            else:
                rahmen_teile.append(f"Ein schöner Moment zusammen mit {andere_text}")

        if rahmen_teile:
            rahmen_satz = ", ".join(rahmen_teile) + "."
            rahmen_satz = rahmen_satz.replace(", zusammen mit ", " – festgehalten zusammen mit ")
            teile.append(rahmen_satz)

        # 2. Notiz & Bildszene organisch verschmelzen
        if notiz_sauber:
            saetze = [s.strip() for s in re.split(r'(?<=[.!?])\s+', notiz_sauber) if s.strip()]
            if saetze:
                auftakt = saetze[0]
                rest_notiz = " ".join(saetze[1:])
                teile.append(auftakt)

                if hauptszene:
                    if len(szenen_personalisiert) > 1:
                        teile.append(f"Auf dem ersten Foto wird dieser Augenblick lebendig: {hauptszene.rstrip('.')}.")
                        if nebenszene:
                            teile.append(f"Ein weiteres Bild zeigt: {nebenszene.rstrip('.')}.")
                    else:
                        teile.append(f"Auf dem Foto wird dieser Augenblick lebendig: {hauptszene.rstrip('.')}.")

                if rest_notiz:
                    teile.append(rest_notiz)
            else:
                teile.append(notiz_sauber)
                if hauptszene:
                    teile.append(f"Auf der Aufnahme wird die Szene sichtbar: {hauptszene.rstrip('.')}.")
        elif hauptszene:
            if len(szenen_personalisiert) > 1:
                teile.append(f"Die Aufnahmen fangen die Szenen warm ein: {hauptszene.rstrip('.')}.")
                if nebenszene:
                    teile.append(f"Ein weiteres Foto hält fest: {nebenszene.rstrip('.')}.")
            else:
                teile.append(f"Das Foto fängt diesen Moment lebendig ein: {hauptszene.rstrip('.')}.")

        # 3. Runder, natürlicher Ausklang
        if "titelbild" in notiz_k or "titel" in titel_sauber.lower():
            teile.append("Genau dieser vertraute Moment eröffnet das Fotobuch – ein Bild voller Wärme, das man sich immer wieder gern ansieht.")
        elif anzahl_dateien > 1:
            teile.append("Eine lebendige Bilderreihe, die diese gemeinsamen Erinnerungen für immer bewahrt.")
        else:
            teile.append("Ein Augenblick voller Geborgenheit, der diese Zeit lebendig hält.")

    else:  # erzaehler
        notiz_k = notiz_sauber.lower()
        umfang_hinweis = f" mit {anzahl_dateien} Aufnahmen" if anzahl_dateien > 1 else ""

        if titel_sauber and datum_sauber and ort_sauber:
            teile.append(f"Eine Fotodokumentation zu „{titel_sauber}“ {datum_sauber} in {ort_sauber}{umfang_hinweis}.")
        elif titel_sauber and datum_sauber:
            teile.append(f"Eine Momentaufnahme zu „{titel_sauber}“ {datum_sauber}{umfang_hinweis}.")
        elif titel_sauber:
            teile.append(f"Aufnahmen aus dem Familienarchiv zum Anlass „{titel_sauber}“{umfang_hinweis}.")
        elif datum_sauber and ort_sauber:
            teile.append(f"Eine Aufnahme {datum_sauber} in {ort_sauber}{umfang_hinweis}.")
        elif datum_sauber:
            teile.append(f"Eine Aufnahme {datum_sauber}{umfang_hinweis}.")
        elif ort_sauber:
            teile.append(f"Eine Aufnahme in {ort_sauber}{umfang_hinweis}.")
        else:
            teile.append(f"Ein festgehaltener Augenblick aus der Chronik{umfang_hinweis}.")

        if alle_pers_text:
            teile.append(f"Im Mittelpunkt stehen {alle_pers_text}.")

        if hauptszene:
            if len(szenen_personalisiert) > 1:
                teile.append(f"Die Aufnahmen dokumentieren das Geschehen: {hauptszene.rstrip('.')}.")
                if nebenszene:
                    teile.append(f"Weitere Motive fangen ein: {nebenszene.rstrip('.')}.")
            else:
                teile.append(f"Die visuelle Aufnahme zeigt: {hauptszene.rstrip('.')}.")

        if notiz_sauber:
            teile.append(f"Aus den überlieferten Aufzeichnungen: {notiz_sauber}")

        teile.append("Ein authentisches Zeitdokument, das diesen Lebensabschnitt festhält.")

    return " ".join(teile)


def _erzaehle_text(
    *,
    titel: str = "",
    datum_text: str = "",
    ort: str = "",
    personen: Optional[List[str]] = None,
    beschreibungen: Optional[List[str]] = None,
    notiz: str = "",
    anzahl_dateien: int = 1,
    perspektive: str = "ich",
) -> Tuple[str, str, Optional[float]]:
    """Erst das KI-Modell (ZDR) frei formulieren lassen, bei Fehler/kein Schlüssel die Vorlage.

    Rückgabe ``(text, quelle, kosten_usd)`` mit ``quelle`` ∈ {"ki", "vorlage"}.
    So wirkt die frei formulierte Fassung im Alltag (Schlüssel vorhanden), während
    Tests und der Offline-Betrieb verlässlich die Vorlage bekommen. Die Vorlage ist
    der sichere Rückfall — die Oberfläche bleibt nie ohne Geschichte.
    """
    def _vorlage() -> str:
        return verschmelze_geschichte(
            titel=titel, datum_text=datum_text, ort=ort, personen=personen,
            beschreibungen=beschreibungen, notiz=notiz,
            anzahl_dateien=anzahl_dateien, perspektive=perspektive,
        )

    try:
        from app.services import geschichte_erzaehlen_ki as _kem
    except Exception:
        return _vorlage(), "vorlage", None
    try:
        if not _kem.verfuegbar():
            return _vorlage(), "vorlage", None
        erg = _kem.erzaehle_geschichte(
            titel=titel, datum_text=datum_text, ort=ort, personen=personen,
            beschreibungen=beschreibungen, notiz=notiz,
            anzahl_dateien=anzahl_dateien, perspektive=perspektive,
        )
    except Exception:
        return _vorlage(), "vorlage", None
    if isinstance(erg, dict) and erg.get("ok") and (erg.get("geschichte") or "").strip():
        return erg["geschichte"].strip(), "ki", erg.get("kosten_usd")
    return _vorlage(), "vorlage", None


def ki_geschichte_generieren(fileid: Any,
                             perspektive: str = "ich",
                             ereignis_kennung: Optional[str] = None,
                             notiz: Optional[str] = None,
                             ort: Optional[str] = None,
                             datum: Optional[str] = None,
                             personen: Optional[List[str]] = None,
                             beschreibung: Optional[str] = None) -> Dict[str, Any]:
    """Erzeugt eine lebendige Bildgeschichte aus Bilddaten, Personen, KI-Bildanalysen und Notizen (01.11.2026).
    Waehlbar in 'ich'-Perspektive (Ich-Form) oder 'erzaehler' (neutrale Sicht).
    Verschmilzt Bildinhalt und Erinnerung organisch ohne Staccato.

    Quelle der Notizen (G1, 02.11.2026): ausschliesslich :func:`eigene_notizen`
    (ALLE Notizen des Bildes und der Gruppe, nie eine Bild-/Anlassgeschichte).
    Der Parameter ``notiz`` wird aus Rueckwaertsverstaendnis angenommen, aber
    NICHT mehr als Quelle benutzt."""
    fid = _als_zahl(fileid)
    if fid is None:
        return {"ok": False, "fehler": "Ungueltige Bildkennung."}

    perspektive = "erzaehler" if str(perspektive).lower().startswith("erz") else "ich"

    # 1. Bildbeschreibung ermitteln & eindeutschen
    if not beschreibung:
        beschreibung = beschreibung_holen(fid) or ""
    if not beschreibung and ereignis_kennung:
        try:
            b_info = bilder_info(ereignis_kennung)
            if b_info and b_info.get("bilder"):
                b_dat = b_info["bilder"].get(str(fid)) or {}
                beschreibung = b_dat.get("beschreibung") or ""
        except Exception:
            pass
    beschreibung_gefunden = bool((beschreibung or "").strip())
    beschr_sauber = deutsch_fuer_bildbeschreibung(beschreibung)

    # 2. Alle eigenen Notizen sammeln (G1) — nie eine fruehere Geschichte
    notiz_inhalt = _notizen_zu_text(eigene_notizen(ereignis_kennung, fid))

    # 3. Personen auf dem Bild ermitteln
    if personen is None:
        try:
            from app.services import gruppen_quiz
            wb = gruppen_quiz.personen_auf_bildern([str(fid)])
            b_info = (wb.get("bilder") or {}).get(str(fid)) or {}
            personen = b_info.get("namen") or []
        except Exception:
            personen = []

    # 4. Ort, Datum und Titel aus Ereignis/Bilddaten ergaenzen
    ereignis_titel = ""
    if ereignis_kennung:
        try:
            detail = ereignis_detail(ereignis_kennung)
            if detail and detail.get("titel"):
                ereignis_titel = str(detail["titel"]).strip()
        except Exception:
            pass
        if not ort or not datum:
            try:
                b_info = bilder_info(ereignis_kennung)
                if b_info and b_info.get("bilder"):
                    img_data = b_info["bilder"].get(str(fid)) or {}
                    if not ort and img_data.get("ort"):
                        ort = img_data["ort"]
                    if not datum and img_data.get("datum"):
                        datum = img_data["datum"]
            except Exception:
                pass
        if not datum:
            try:
                detail = ereignis_detail(ereignis_kennung)
                if detail:
                    datum = detail.get("datum")
            except Exception:
                pass

    datum_text = format_datum_de(datum)
    ort_sauber = str(ort).strip() if ort else ""
    pers_liste = [p.strip() for p in (personen or []) if p and p.strip()]

    # Frei formulierte KI-Erzählung (Vorlage als Rückfall)
    beschr_liste = [beschr_sauber] if beschr_sauber else []
    geschichte_text, erz_quelle, erz_kosten = _erzaehle_text(
        titel=ereignis_titel,
        datum_text=datum_text,
        ort=ort_sauber,
        personen=pers_liste,
        beschreibungen=beschr_liste,
        notiz=notiz_inhalt,
        anzahl_dateien=1,
        perspektive=perspektive,
    )

    return {
        "ok": True,
        "fileid": fid,
        "perspektive": perspektive,
        "geschichte": geschichte_text,
        "daten": {
            "datum": datum,
            "datum_lesbar": datum_text,
            "ort": ort_sauber,
            "personen": pers_liste,
            "beschreibung": beschr_sauber,
            "beschreibung_gefunden": beschreibung_gefunden,
            "notiz": notiz_inhalt or "",
            "erzaehlquelle": erz_quelle,
            "kosten_usd": erz_kosten
        }
    }


def anlass_geschichte_generieren(
    ereignis_kennung: Optional[str] = None,
    perspektive: str = "ich",
    notiz: Optional[str] = None,
    titel: Optional[str] = None,
    datum: Optional[str] = None,
    ort: Optional[str] = None,
    personen: Optional[List[str]] = None,
    anzahl_dateien: Optional[int] = None,
    beschreibungen: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Erzeugt eine lebendige Anlass-Geschichte für ein gesamtes Ereignis (01.11.2026).

    Verknüpft Anlasstitel, Zeitraum, Orte, beteiligte Personen, KI-Bildanalysen und Notizen
    zu einem fließenden Text. Wählbar in 'ich'-Perspektive oder neutraler 'erzaehler'-Sicht.
    Verschmilzt Bildanalysen aller Bilder organisch mit den persönlichen Notizen ohne Staccato.

    Quelle der Notizen (G1, 02.11.2026): ausschliesslich :func:`eigene_notizen`
    des Ereignisses — nie eine Anlassgeschichte, nie Altbestand. Der Parameter
    ``notiz`` wird angenommen, aber NICHT mehr als Quelle benutzt.
    """
    detail: Optional[Dict[str, Any]] = None
    if ereignis_kennung:
        try:
            detail = ereignis_detail(ereignis_kennung)
        except Exception:
            detail = None

    if detail is None and not any([titel, datum, personen, anzahl_dateien is not None]):
        return {"ok": False, "fehler": f"Anlass „{ereignis_kennung or ''}“ nicht gefunden."}

    perspektive = "erzaehler" if str(perspektive).lower().startswith("erz") else "ich"

    titel_sauber = str(titel or (detail.get("titel") if detail else "") or "").strip()
    datum_roh = datum or (detail.get("datum") if detail else None)
    jahr_roh = detail.get("jahr") if detail else None
    datum_text = format_datum_de(datum_roh)
    if not datum_text and jahr_roh:
        datum_text = f"im Jahr {jahr_roh}"

    dateien = detail.get("datei_kennungen") or [] if detail else []
    anzahl = anzahl_dateien if anzahl_dateien is not None else (detail.get("anzahl_dateien") if detail else len(dateien))
    if anzahl is None:
        anzahl = len(dateien)

    # Orte ermitteln
    orte_liste: List[str] = []
    if ort:
        orte_liste = [ort.strip()]
    elif ereignis_kennung:
        try:
            b_info = bilder_info(ereignis_kennung)
            if b_info and b_info.get("orte"):
                orte_liste = [str(o).strip() for o in b_info["orte"] if o and str(o).strip()]
        except Exception:
            pass
    ort_sauber = ", ".join(orte_liste) if orte_liste else ""

    # Personen ermitteln
    if personen is None and dateien:
        try:
            from app.services import gruppen_quiz
            wb = gruppen_quiz.personen_auf_bildern([str(fid) for fid in dateien])
            alle_namen = set()
            for b_fid, b_daten in (wb.get("bilder") or {}).items():
                for n in (b_daten.get("namen") or []):
                    if n and str(n).strip():
                        alle_namen.add(str(n).strip())
            personen = sorted(alle_namen)
        except Exception:
            personen = []
    pers_liste = [p.strip() for p in (personen or []) if p and p.strip()]

    # Bildbeschreibungen aller Bilder ermitteln & eindeutschen
    beschr_liste: List[str] = []
    if beschreibungen:
        beschr_liste = [deutsch_fuer_bildbeschreibung(b) for b in beschreibungen if b and b.strip()]
    elif dateien:
        try:
            alle_b = _beschreibungen_gesamt_lesen()
            for f in dateien:
                f_num = _als_zahl(f)
                if f_num and f_num in alle_b:
                    b_txt = deutsch_fuer_bildbeschreibung(alle_b[f_num])
                    if b_txt and b_txt not in beschr_liste:
                        beschr_liste.append(b_txt)
        except Exception:
            pass

    # Alle eigenen Notizen des Anlasses sammeln & bereinigen (keine Zitate)
    notizen_liste = eigene_notizen(ereignis_kennung, None) if ereignis_kennung else []
    notiz_inhalt = _notizen_zu_text(notizen_liste)

    # Frei formulierte KI-Erzählung (Vorlage als Rückfall)
    geschichte_text, erz_quelle, erz_kosten = _erzaehle_text(
        titel=titel_sauber,
        datum_text=datum_text,
        ort=ort_sauber,
        personen=pers_liste,
        beschreibungen=beschr_liste,
        notiz=notiz_inhalt,
        anzahl_dateien=anzahl,
        perspektive=perspektive,
    )

    return {
        "ok": True,
        "ereignis_kennung": ereignis_kennung,
        "titel": titel_sauber,
        "perspektive": perspektive,
        "geschichte": geschichte_text,
        "daten": {
            "datum": datum_roh,
            "datum_lesbar": datum_text,
            "ort": ort_sauber,
            "orte": orte_liste,
            "personen": pers_liste,
            "anzahl_dateien": anzahl,
            "beschreibungen": beschr_liste,
            "notiz": notiz_inhalt or "",
            # Zählzeile am Handy (03.11.2026): nur die Zahl, kein Inhalt.
            "anzahl_notizen": len(notizen_liste),
            "erzaehlquelle": erz_quelle,
            "kosten_usd": erz_kosten,
        }
    }
