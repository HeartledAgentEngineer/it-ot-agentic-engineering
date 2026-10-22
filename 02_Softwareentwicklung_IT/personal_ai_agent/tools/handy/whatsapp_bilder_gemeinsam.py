"""Gemeinsame Bausteine fuer die WhatsApp-Bilder-Werkzeuge W0 und W1 (21.10.2026).

Plan: ``.hermes/plans/2026-10-21_whatsapp-bilder.md`` (Fassung 5).

Dieses Modul wird von ``whatsapp_bilder_zaehlen.py`` (W0) und
``whatsapp_bilder_hochladen.py`` (W1) benutzt und enthaelt:

    * ``zugang_aufloesen()`` — Token und Host, fuer W0 und W1 gleich. Token und
      Host kommen ueber ``_token_aus_quellen``/``_host_aus_quellen`` aus
      ``tools/pcloud/uebergabe_hochladen.py`` (Umgebung, dann ``backend/.env``).
      **Host-Positivliste: nur ``eapi.pcloud.com``** — jeder andere Wert endet mit
      ``Voraussetzung`` (Exit 3), BEVOR irgendeine Netzanfrage geschieht. Werte aus
      der ``.env`` werden nie ausgegeben.
    * ``medien_lesen()`` — liest den WhatsApp-Medienordner nur lesend. Zugriff ist
      eine eigene Pruefung: fehlt der Ordner oder ist er nicht lesbar, kommt
      ``Voraussetzung`` (Exit 3) — nie eine Nullzaehlung.
    * die gemeinsamen Konstanten (Standard-Medienpfad, erlaubte Endungen, Exit-Codes).

Grenzen:
    * Nur lesend am Handy: kein Loeschen, kein Verschieben, kein Schreiben.
    * Ausgaben enthalten keine Datei-, Ordner- oder Chatnamen und keine Werte aus
      der ``.env``. Fehlermeldungen sind feste Texte.
"""

from __future__ import annotations

import argparse
import datetime
import importlib
import importlib.util
import os
import re
import stat as stat_modul
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

HIER = os.path.dirname(os.path.abspath(__file__))
PROJEKT = os.path.dirname(os.path.dirname(HIER))
UEBERGABE_PFAD = os.path.join(PROJEKT, "tools", "pcloud", "uebergabe_hochladen.py")

# Standard-Medienordner der empfangenen/gesendeten Bilder (Android, WhatsApp).
STANDARD_MEDIENPFAD = "/sdcard/Android/media/com.whatsapp/WhatsApp/Media/WhatsApp Images"

# Host-Positivliste: nur das EU-Rechenzentrum des Kontos.
ERLAUBTER_HOST = "eapi.pcloud.com"

# Nur diese Bildtypen gehen in die pCloud (W1); W0 zaehlt zusaetzlich alle Dateien.
ENDUNGEN = (".jpg", ".jpeg", ".png", ".webp")

# Dateitypen, die in der Zaehlung mit Namen erscheinen duerfen. Alles andere
# heisst "andere" — eine Endung kann Teil eines privaten Dateinamens sein.
BEKANNTE_TYPEN = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic",
                  ".mp4", ".3gp", ".pdf", ".txt")

KATEGORIEN = ("empfangen", "gesendet")
GESENDET_ORDNER = "Sent"
PRIVAT_ORDNER = "Private"

EXIT_OK = 0
EXIT_FEHLER = 1
EXIT_AUFRUF = 2
EXIT_VORAUSSETZUNG = 3

MELDUNG_KEIN_ZUGRIFF = ("kein Zugriff auf den WhatsApp-Medienordner "
                        "(Termux-Speicherrecht: termux-setup-storage)")
MELDUNG_HTTPX = "Voraussetzung fehlt: Python-Paket httpx (pip install httpx)"
MELDUNG_TOKEN = ("Voraussetzung fehlt: PCLOUD_TOKEN "
                 "(weder in der Umgebung noch in backend/.env)")
MELDUNG_HOST = f"Voraussetzung fehlt: gueltiger pCloud-Host (nur {ERLAUBTER_HOST} erlaubt)"
MELDUNG_ZUGANG_LESEN = "Voraussetzung fehlt: Zugangsdaten (backend/.env) nicht lesbar"
MELDUNG_ALTCODE = "Voraussetzung fehlt: tools/pcloud/uebergabe_hochladen.py"


class Voraussetzung(Exception):
    """Eine Voraussetzung fehlt — Exit 3 mit einer festen Zeile (``meldung``).

    Die Meldung enthaelt nie einen Token, Host-Wert, Pfad oder Dateinamen.
    """

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


# ── Kleine Helfer ──────────────────────────────────────────────────────────

def zahl_de(wert: Any) -> str:
    """Ganzzahl deutsch mit Tausenderpunkt (1234 -> "1.234")."""
    try:
        return f"{int(wert):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(wert)


# Feste Fehlerarten der pCloud-Ergaenzungen (wie ``ARTEN`` in uebergabe_hochladen.py).
ERLAUBTE_ARTEN = ("netz", "http", "json", "abgelehnt", "nicht_gefunden", "antwort",
                  "konfig", "aufruf")
_ART_MUSTER = re.compile(r"(?:" + "|".join(ERLAUBTE_ARTEN) + r")(?: \d{1,5})?")


def fehlerart(fehler: BaseException) -> str:
    """Die Fehlerart fuer die Ausgabe: eine feste ``art`` (plus Code) oder der Klassenname.

    Nie der Text der Ausnahme — der kann Datei-, Ordner- oder Chatnamen enthalten.
    Eine ``art`` wird nur ausgegeben, wenn sie genau dem festen Muster entspricht.
    """
    art = getattr(fehler, "art", None)
    if isinstance(art, str) and _ART_MUSTER.fullmatch(art):
        return art
    return fehler.__class__.__name__


class LeiserParser(argparse.ArgumentParser):
    """``argparse`` ohne Echo der falschen Eingabe (kann ein Pfad oder Name sein)."""

    def error(self, message: str) -> None:        # type: ignore[override]
        print("Aufruf ungueltig (--help zeigt die Optionen).", file=sys.stderr)
        raise SystemExit(EXIT_AUFRUF)


# ── httpx und das Schreib-/Lesemodul der pCloud ────────────────────────────

def httpx_pruefen() -> None:
    """``httpx`` muss importierbar sein, sonst ``Voraussetzung`` (Exit 3)."""
    fehlt = False
    try:
        importlib.import_module("httpx")
    except ImportError:
        fehlt = True                  # nur ein Merkmal; geworfen wird ausserhalb des except
    if fehlt:
        raise Voraussetzung(MELDUNG_HTTPX)


_UEBERGABE: Optional[Any] = None


def uebergabe_laden() -> Any:
    """Das Modul ``tools/pcloud/uebergabe_hochladen.py`` laden (einmal, dann gemerkt).

    Ist ``httpx`` nicht importierbar, kommt ``Voraussetzung`` statt eines
    ``ImportError``.
    """
    global _UEBERGABE
    if _UEBERGABE is not None:
        return _UEBERGABE
    httpx_pruefen()
    modul = None
    try:
        spez = importlib.util.spec_from_file_location("uebergabe_hochladen_wa", UEBERGABE_PFAD)
        if spez is not None and spez.loader is not None:
            modul = importlib.util.module_from_spec(spez)
            spez.loader.exec_module(modul)
    except Exception:
        modul = None                  # nur ein Merkmal; geworfen wird ausserhalb des except
    if modul is None:
        raise Voraussetzung(MELDUNG_ALTCODE)
    _UEBERGABE = modul
    return modul


@dataclass(frozen=True)
class Zugang:
    """Token und Host. ``repr`` zeigt den Token nie."""

    token: str = field(repr=False)
    host: str = ERLAUBTER_HOST


def zugang_aufloesen(token: Optional[str] = None, host: Optional[str] = None) -> Zugang:
    """Token und Host aufloesen — fuer W0 und W1 gleich, ohne Netzanfrage.

    Reihenfolge wie in ``uebergabe_hochladen.py``: Parameter, Umgebung, ``backend/.env``.
    Ein anderer Host als ``eapi.pcloud.com`` ist ``Voraussetzung`` (Exit 3); ebenso ein
    fehlender Token oder fehlendes ``httpx``. Keine Meldung nennt einen Wert.
    """
    httpx_pruefen()
    ug = uebergabe_laden()
    ziel_host = geheimnis = None
    try:
        # Altcode-Leser: faengt in der .env nur OSError. Jede andere Ausnahme (etwa
        # UnicodeDecodeError bei ungueltigem UTF-8, args mit Dateiinhalt/Token) wird
        # hier nur vermerkt und nach dem except durch eine feste Meldung ersetzt.
        ziel_host = ug._host_aus_quellen(host)
        geheimnis = ug._token_aus_quellen(token)
    except Exception:
        ziel_host = geheimnis = None
    if ziel_host is None or geheimnis is None:
        raise Voraussetzung(MELDUNG_ZUGANG_LESEN)
    if ziel_host.lower() != ERLAUBTER_HOST:
        raise Voraussetzung(MELDUNG_HOST)
    if not geheimnis:
        raise Voraussetzung(MELDUNG_TOKEN)
    return Zugang(token=geheimnis, host=ERLAUBTER_HOST)


# ── Datum / Jahr ───────────────────────────────────────────────────────────

_DATUM_KOMPAKT = re.compile(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")
_DATUM_STRICH = re.compile(r"(?<!\d)((?:19|20)\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?!\d)")


def jahr_bestimmen(name: str, mtime: float, aktuelles_jahr: Optional[int] = None) -> int:
    """Das Jahr einer Datei: aus dem Namen (``IMG-JJJJMMTT-WA####``), sonst aus mtime."""
    heute = aktuelles_jahr or datetime.date.today().year
    for muster in (_DATUM_KOMPAKT, _DATUM_STRICH):
        treffer = muster.search(name)
        if treffer and 1990 <= int(treffer.group(1)) <= heute + 1:
            return int(treffer.group(1))
    try:
        return datetime.datetime.fromtimestamp(mtime).year
    except (OverflowError, OSError, ValueError):
        return 1970


def ist_bild(name: str) -> bool:
    """True fuer die hochladbaren Bildtypen (jpg, jpeg, png, webp)."""
    return os.path.splitext(name)[1].lower() in ENDUNGEN


# ── Medienordner lesen (nur lesend) ────────────────────────────────────────

@dataclass(frozen=True)
class Eintrag:
    """Eine regulaere Datei aus dem Medienordner."""

    kategorie: str          # "empfangen" | "gesendet"
    name: str
    pfad: str
    groesse: int
    mtime: float
    jahr: int


@dataclass
class Medien:
    """Ergebnis von ``medien_lesen``: Dateien und Zaehler fuer Ausgelassenes."""

    dateien: List[Eintrag] = field(default_factory=list)
    versteckt: int = 0
    private: int = 0
    unterordner: int = 0
    nicht_lesbar: int = 0


def _ordner_listen(pfad: str) -> List[str]:
    """Einen Ordner lesbar auflisten oder ``Voraussetzung`` (Exit 3)."""
    if not os.path.isdir(pfad):
        raise Voraussetzung(MELDUNG_KEIN_ZUGRIFF)
    status: Any = None
    try:
        status = os.stat(pfad)
    except OSError:
        pass                          # nur ein Merkmal (status bleibt None)
    if status is None or not stat_modul.S_ISDIR(status.st_mode):
        raise Voraussetzung(MELDUNG_KEIN_ZUGRIFF)
    if not os.access(pfad, os.R_OK | os.X_OK):
        raise Voraussetzung(MELDUNG_KEIN_ZUGRIFF)
    inhalt: Optional[List[str]] = None
    try:
        inhalt = list(os.listdir(pfad))
    except OSError:
        pass                          # nur ein Merkmal (inhalt bleibt None)
    if inhalt is None:
        raise Voraussetzung(MELDUNG_KEIN_ZUGRIFF)
    return inhalt


def _sammeln(pfad: str, kategorie: str, medien: Medien, mit_unterordnern: bool) -> None:
    for name in sorted(_ordner_listen(pfad)):
        voll = os.path.join(pfad, name)
        if name.startswith("."):
            medien.versteckt += 1
            continue
        try:
            st = os.lstat(voll)
        except OSError:
            medien.nicht_lesbar += 1
            continue
        if stat_modul.S_ISDIR(st.st_mode):
            if mit_unterordnern:
                if name.casefold() == GESENDET_ORDNER.casefold():
                    continue                      # wird als "gesendet" eigens gelesen
                if name.casefold() == PRIVAT_ORDNER.casefold():
                    medien.private += 1           # nie geoeffnet, nie aufgelistet
                else:
                    medien.unterordner += 1
            continue
        if not stat_modul.S_ISREG(st.st_mode):
            medien.nicht_lesbar += 1
            continue
        medien.dateien.append(Eintrag(
            kategorie=kategorie, name=name, pfad=voll, groesse=int(st.st_size),
            mtime=float(st.st_mtime), jahr=jahr_bestimmen(name, st.st_mtime)))


def medien_lesen(wurzel: str) -> Medien:
    """Den Medienordner nur lesend einlesen (empfangen = Wurzel, gesendet = ``Sent``).

    Zugriff ist eine eigene Pruefung: fehlt die Wurzel, ist sie kein Ordner oder nicht
    lesbar (``os.access``, ``listdir`` wirft), kommt ``Voraussetzung`` — nie eine
    Nullzaehlung. Steht ``Sent`` in der Auflistung der Wurzel, wird er IMMER streng gelesen
    und nicht vorgefiltert: ist er kein lesbarer Ordner (Datei, ``isdir`` False, ``stat``
    oder ``listdir`` wirft), kommt ``Voraussetzung`` (Exit 3) — nie still "gesendet: 0".
    Fehlt ``Sent`` in der Auflistung ganz, gilt "gesendet: 0" (die Wurzel war lesbar).
    Versteckte Dateien, ``.nomedia`` und ``Private`` werden gezaehlt, nie gelesen.
    """
    wurzel = os.path.expanduser(str(wurzel))
    namen = _ordner_listen(wurzel)
    medien = Medien()
    _sammeln(wurzel, "empfangen", medien, mit_unterordnern=True)
    sent = next((n for n in namen if n.casefold() == GESENDET_ORDNER.casefold()), None)
    if sent is not None:
        _sammeln(os.path.join(wurzel, sent), "gesendet", medien, mit_unterordnern=False)
    medien.dateien.sort(key=lambda e: (e.kategorie, e.name))
    return medien


def voraussetzung_melden(fehler: Voraussetzung) -> int:
    """Die eine feste Zeile auf Standardfehler, Exit 3."""
    print(fehler.meldung, file=sys.stderr)
    return EXIT_VORAUSSETZUNG
