"""W1: WhatsApp-Bilder vom Handy in die pCloud kopieren (21.10.2026).

Plan: ``.hermes/plans/2026-10-21_whatsapp-bilder.md`` (Fassung 5, Schritt W1).

Laeuft am Handy in Termux. Kopiert die empfangenen und gesendeten WhatsApp-Bilder
(``.jpg/.jpeg/.png/.webp``) nach ``/Agent/whatsapp_bilder/<empfangen|gesendet>/<JJJJ>/``.
Token und Host kommen ueber ``zugang_aufloesen()`` (nur ``eapi.pcloud.com``, sonst
Exit 3 vor jeder Netzanfrage) — wie bei W0.

Grenzen (als Code):
    * **Am Handy aendert sich nichts:** die Bilder werden nur gelesen, nie
      geloescht, verschoben oder umbenannt.
    * **In der pCloud wird nie ueberschrieben:** Hochladen nur ueber
      ``hochladen_ohne_ueberschreiben`` (``renameifexists=1``, ``nopartial=1``).
    * **Trockenlauf ist Standard** und schreibt nirgends: keine Sperre, kein
      Manifest, kein Cloud-Ordner, kein ``uploadfile``. Er nutzt nur lesende
      Abfragen (``listfolder`` per Pfad, ``stat``, ``checksumfile``).
    * **Ein Schreiber:** Mit ``--schreiben`` nimmt der Lauf die Sperre
      ``~/foto_sortierung/.whatsapp_hochladen.sperre`` (``mkdir``); liegt sie, Exit 3.
    * **Ein Lesevorgang je Datei:** Die Datei wird einmal in den Speicher gelesen;
      sha256 und Upload kommen aus genau diesen Bytes.
    * **Ausgabe nur Zahlen:** keine Datei-, Ordner- oder Chatnamen, kein Token. Jede
      Ausnahme wird zu einer Fehlerart mit Zaehler.

Eigentumskennung und Vorab-Zeile (write-ahead):
    Jeder Upload bekommt eine zufaellige Kennung ``k`` (12 Hex-Zeichen); der Cloud-Name
    ist ``<stamm>_wa<k>.<endung>`` (das Datum am Namensanfang bleibt lesbar). Vor dem
    Upload steht die Manifestzeile ``upload_begonnen`` (fsync). Erst wenn der
    **Eigentumsbeleg** besteht — ``stat`` per fileid: (a) ``parentfolderid`` = Zielordner,
    (b) Name enthaelt ``_wa<k>``, (c) ``checksumfile`` sha256 = sha256 der gelesenen
    Bytes — folgt ``hochgeladen``. Sonst ``unklar_begonnen``.

Zustaende im Manifest (``~/foto_sortierung/whatsapp_bilder_manifest.jsonl``, streng gelesen,
nur anhaengen, enthaelt Dateinamen und liegt nur am Handy):
    ``upload_begonnen`` · ``hochgeladen`` · ``fehlt_in_cloud`` · ``unklar`` ·
    ``unklar_begonnen``.

Rueckweg: Von W1 erzeugt sind nur Dateien mit eigener Kennung im Namen und dem
Zustand ``hochgeladen`` (``entfernbare_fileids``); ``unklar`` und ``unklar_begonnen``
werden nie zum Entfernen freigegeben. Dieses Werkzeug entfernt selbst nichts.

Unlesbare letzte Manifestzeile:
    Ist die LETZTE Manifestzeile unlesbar und ohne Zeilenumbruch, bricht jeder Lauf (auch
    der Trockenlauf) mit Exit 3 ab: Schreibabbruch und Beschaedigung sind am Inhalt nicht
    zu unterscheiden. Nach einem BEKANNTEN Abbruch (zum Beispiel Akku leer waehrend des
    Schreibens) gibt ``--schreiben --letzte-zeile-verwerfen`` die Zeile bewusst frei: es
    wird ein Zeilenumbruch plus eine Markierung ``vorab_abgebrochen`` angehaengt, nichts
    geloescht. Das geschieht ATOMAR: erst eine Kopie ``<manifest>.vor_verwerfen_<stempel>``,
    dann eine Temp-Datei ``<manifest>.verwerfen_<stempel>.tmp`` (alte Bytes unveraendert +
    Umbruch + Markierung, fsync), dann ``os.replace`` auf das Manifest. Kopie und Temp-Datei
    werden exklusiv angelegt (Modus ``xb``); ist ein Name belegt, wird ein neuer gewaehlt —
    nichts wird ueberschrieben. Im Manifest steht danach entweder der alte Stand (der Ausweg
    funktioniert erneut) oder der neue (fertig), nie ein Zwischenstand. Eine Temp-Datei aus
    einem abgebrochenen Versuch bleibt unveraendert liegen; das Werkzeug benennt nichts um
    und loescht nichts. Ohne ``--schreiben`` ist die Option Exit 2; bei einer unauffaelligen
    letzten Zeile hat sie keine Wirkung (die Ausgabe sagt das in einer Zeile).

Exit: 0 = ok; 1 = mindestens ein Fehler; 2 = Aufrufe-/Schutzfehler (Ziel ausserhalb
``/Agent/``, Manifest im Repo, Option ohne ``--schreiben``); 3 = Voraussetzung fehlt
(Zugang, Host, Medienordner, Sperre, beschaedigtes Manifest).

Aufruf (am Handy, im Projektordner ``personal_ai_agent``):
    python tools/handy/whatsapp_bilder_hochladen.py                      # Trockenlauf
    python tools/handy/whatsapp_bilder_hochladen.py --schreiben --max 50
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

HIER = os.path.dirname(os.path.abspath(__file__))
if HIER not in sys.path:
    sys.path.insert(0, HIER)

import whatsapp_bilder_gemeinsam as gemeinsam  # noqa: E402

STANDARD_ZIEL = "/Agent/whatsapp_bilder"
STANDARD_MANIFEST = "~/foto_sortierung/whatsapp_bilder_manifest.jsonl"
STANDARD_SPERRE = "~/foto_sortierung/.whatsapp_hochladen.sperre"
MAX_KENNUNG_VERSUCHE = 3

ZUSTAND_BEGONNEN = "upload_begonnen"
ZUSTAND_HOCHGELADEN = "hochgeladen"
ZUSTAND_FEHLT = "fehlt_in_cloud"
ZUSTAND_UNKLAR = "unklar"
ZUSTAND_UNKLAR_BEGONNEN = "unklar_begonnen"
# Markierung: Zeile <n> war eine abgebrochene Vorab-Zeile (kein Upload gelaufen).
ZUSTAND_VORAB_ABGEBROCHEN = "vorab_abgebrochen"

BELEG_OK = "ok"
BELEG_FEHLT = "fehlt"
BELEG_VERLETZT = "verletzt"

MELDUNG_SPERRE = ("Voraussetzung fehlt: Sperre .whatsapp_hochladen.sperre liegt (anderer Lauf "
                  "aktiv oder frueher abgebrochen; Ordner pruefen und von Hand entfernen)")
MELDUNG_SPERRE_ANLEGEN = "Voraussetzung fehlt: Sperre konnte nicht angelegt werden"
MELDUNG_ZIEL = "Aufruf ungueltig: --ziel muss unter /Agent/ liegen."
MELDUNG_MANIFEST_REPO = "Aufruf ungueltig: --manifest darf nicht in einem Git-Repo liegen."
MELDUNG_MANIFEST_PRUEFEN = "Aufruf ungueltig: Manifestpfad nicht pruefbar."
MELDUNG_SPERRE_REPO = "Aufruf ungueltig: --sperre darf nicht in einem Git-Repo liegen."
MELDUNG_SPERRE_PRUEFEN = "Aufruf ungueltig: Sperrpfad nicht pruefbar."
MELDUNG_OFFENE_NEU = "Aufruf ungueltig: --offene-neu gilt nur zusammen mit --schreiben."
MELDUNG_VERWERFEN_OHNE_SCHREIBEN = ("Aufruf ungueltig: --letzte-zeile-verwerfen gilt nur "
                                    "zusammen mit --schreiben.")
HINWEIS_VERWERFEN = "--schreiben --letzte-zeile-verwerfen"
MELDUNG_MAX = "Aufruf ungueltig: --max braucht eine Zahl ab 1."


# ── Manifest: Wiederholung der Zeilen zu Versuchen ─────────────────────────

class Versuch:
    """Ein Upload-Versuch (eine Kennung) fuer einen relativen Pfad + sha256."""

    __slots__ = ("kennung", "ordner_id", "cloud_name", "fileid", "zustand", "notiz",
                 "groesse", "mtime")

    def __init__(self, kennung: str) -> None:
        self.kennung = kennung
        self.ordner_id: Optional[int] = None
        self.cloud_name: Optional[str] = None
        self.fileid: Optional[int] = None
        self.zustand: Optional[str] = None      # begonnen | hochgeladen | unklar_begonnen
        self.notiz: Optional[str] = None        # spaetere Feststellung: fehlt_in_cloud | unklar
        self.groesse: Optional[int] = None
        self.mtime: Optional[int] = None


def _als_int(wert: Any) -> Optional[int]:
    return wert if isinstance(wert, int) and not isinstance(wert, bool) else None


def versuche_aufbauen(zeilen: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Versuch]]:
    """Die Manifestzeilen zu Versuchen je (relativer Pfad, sha256) zusammenfuehren."""
    ergebnis: Dict[Tuple[str, str], List[Versuch]] = {}
    for zeile in zeilen:
        pfad, sha, kennung = zeile.get("pfad"), zeile.get("sha256"), zeile.get("kennung")
        zustand = zeile.get("zustand")
        if not (isinstance(pfad, str) and isinstance(sha, str) and isinstance(kennung, str)):
            continue
        liste = ergebnis.setdefault((pfad, sha), [])
        v = next((x for x in liste if x.kennung == kennung), None)
        if v is None:
            v = Versuch(kennung)
            liste.append(v)
        if zeile.get("ordner_id") is not None:
            v.ordner_id = _als_int(zeile.get("ordner_id"))
        if isinstance(zeile.get("cloud_name"), str):
            v.cloud_name = zeile["cloud_name"]
        v.groesse = _als_int(zeile.get("groesse")) if v.groesse is None else v.groesse
        v.mtime = _als_int(zeile.get("mtime")) if v.mtime is None else v.mtime
        if zustand == ZUSTAND_BEGONNEN and v.zustand is None:
            v.zustand = "begonnen"
        elif zustand == ZUSTAND_HOCHGELADEN:
            v.zustand = ZUSTAND_HOCHGELADEN
            v.fileid = _als_int(zeile.get("fileid"))
        elif zustand == ZUSTAND_UNKLAR_BEGONNEN:
            v.zustand = ZUSTAND_UNKLAR_BEGONNEN
        elif zustand in (ZUSTAND_FEHLT, ZUSTAND_UNKLAR):
            v.notiz = zustand
    return ergebnis


def _letzter(liste: List[Versuch]) -> Optional[Versuch]:
    for v in reversed(liste):
        if v.zustand is not None:
            return v
    return None


def entfernbare_fileids(zeilen: List[Dict[str, Any]]) -> Set[int]:
    """Die fileids, die W1 als eigene Uploads belegen kann (nur lesend, entfernt nichts).

    Nur Versuche mit Zustand ``hochgeladen`` und ohne spaetere Feststellung
    ``unklar``/``fehlt_in_cloud``. ``unklar`` und ``unklar_begonnen`` sind nie dabei.
    Ein spaeteres Werkzeug muss den Eigentumsbeleg vor dem Entfernen erneut pruefen.
    """
    frei: Set[int] = set()
    for liste in versuche_aufbauen(zeilen).values():
        for v in liste:
            if v.zustand == ZUSTAND_HOCHGELADEN and v.notiz is None and v.fileid is not None:
                frei.add(v.fileid)
    return frei


class ManifestFehler(Exception):
    """Das Manifest ist nicht schreibbar (write/flush/fsync) — der Lauf stoppt.

    Ohne gesicherte Vorab-Zeile darf kein Upload starten; ohne gesicherte
    Ergebniszeile kein weiterer. Die Ausnahme traegt keinen Text.
    """


@dataclass
class ManifestStand:
    """Das gelesene Manifest: Zeilen, ob der Schluss-Umbruch fehlt, abgebrochene Zeile."""

    zeilen: List[Dict[str, Any]] = field(default_factory=list)
    ohne_umbruch: bool = False
    abgebrochene_zeile: Optional[int] = None


# Je Zustand die Pflichtfelder (Name -> Typ: "str" nichtleer, "int" ganzzahlig, nicht bool).
_PFLICHT_BASIS = {"pfad": "str", "sha256": "str", "kennung": "str"}
_PFLICHT_MIT_ORT = {**_PFLICHT_BASIS, "ordner_id": "int", "cloud_name": "str"}
PFLICHTFELDER: Dict[str, Dict[str, str]] = {
    ZUSTAND_BEGONNEN: _PFLICHT_MIT_ORT,
    ZUSTAND_HOCHGELADEN: {**_PFLICHT_MIT_ORT, "fileid": "int"},
    ZUSTAND_UNKLAR_BEGONNEN: _PFLICHT_MIT_ORT,
    ZUSTAND_FEHLT: _PFLICHT_BASIS,
    ZUSTAND_UNKLAR: _PFLICHT_BASIS,
    ZUSTAND_VORAB_ABGEBROCHEN: {"zeile": "int"},
}
# Dazu optionale Felder: wenn vorhanden (nicht None), dann ganzzahlig.
_OPTIONAL_INT = ("groesse", "mtime", "fileid", "ordner_id")


def _wert_passt(wert: Any, typ: str) -> bool:
    if typ == "str":
        return isinstance(wert, str) and bool(wert)
    return _als_int(wert) is not None


def zeile_gueltig(eintrag: Any) -> bool:
    """Hat die Zeile einen bekannten Zustand und alle dafuer noetigen Felder mit Typ?"""
    if not isinstance(eintrag, dict):
        return False
    zustand = eintrag.get("zustand")
    if not isinstance(zustand, str) or zustand not in PFLICHTFELDER:
        return False
    for feld, typ in PFLICHTFELDER[zustand].items():
        if not _wert_passt(eintrag.get(feld), typ):
            return False
    for feld in _OPTIONAL_INT:
        if eintrag.get(feld) is not None and _als_int(eintrag.get(feld)) is None:
            return False
    return True


def manifest_streng_lesen(pfad: str, letzte_zeile_verwerfen: bool = False) -> ManifestStand:
    """Das Manifest streng lesen (statt ``manifest_lesen()``, das Defektes uebergeht).

    * Fehlt die Datei: leer.
    * Eine nicht lesbare Zeile MITTEN im Manifest: ``Voraussetzung`` (Exit 3) mit
      der Zeilennummer — es koennte eine Vorab-Zeile fehlen, ein Upload waere dann
      eine Dublette.
    * Eine leere oder nur aus Leerzeichen bestehende Zeile ist ebenfalls ein Fehler (eine
      beschaedigte Vorab-Zeile koennte so verschwunden sein). Erlaubt ist nur das leere
      Ende hinter dem letzten Zeilenumbruch. CRLF-Zeilenenden werden gueltig gelesen.
    * Dasselbe gilt fuer eine Zeile, die zwar gueltiges JSON ist, aber einen
      unbekannten Zustand oder fehlende / falsch typisierte Pflichtfelder hat
      (``zeile_gueltig``) — auch als letzte Zeile. Nichts wird still uebersprungen.
    * Eine nicht lesbare LETZTE Zeile ohne abschliessenden Zeilenumbruch wird NICHT von
      selbst als abgebrochene Vorab-Zeile gewertet: Ein Schreibabbruch und eine
      Beschaedigung (NUL, BOM, fremder Zeilentrenner) sind am Inhalt nicht sicher zu
      unterscheiden, und eine verschwundene Vorab-Zeile kaeme als Dublette zurueck.
      Ohne Zustimmung: ``Voraussetzung`` (Exit 3) mit Zeilennummer und dem Hinweis auf
      ``--letzte-zeile-verwerfen``. Mit ``letzte_zeile_verwerfen=True`` (bewusst, nach
      bekanntem Abbruch) gilt genau diese Zeile als abgebrochen: ``ManifestSchreiber``
      schreibt einen Zeilenumbruch und eine Markierung ``vorab_abgebrochen`` — nichts
      wird geloescht, das Manifest ist danach streng lesbar. Fuer jede andere
      beschaedigte Zeile (mit Umbruch, inhaltlich ungueltig) hilft die Option nicht.
    """
    if not os.path.exists(pfad):
        return ManifestStand()
    roh = None
    try:
        with open(pfad, "rb") as datei:
            roh = datei.read()
    except OSError:
        pass                          # nur ein Merkmal (roh bleibt None)
    if roh is None:
        raise gemeinsam.Voraussetzung("Voraussetzung fehlt: Manifest nicht lesbar")
    if not roh:
        return ManifestStand()
    ohne_umbruch = not roh.endswith(b"\n")
    teile = roh.split(b"\n")
    if not ohne_umbruch:
        teile.pop()
    zeilen: List[Dict[str, Any]] = []
    defekt: List[int] = []
    markiert: Set[int] = set()
    for nr, teil in enumerate(teile, 1):
        if teil.endswith(b"\r"):
            teil = teil[:-1]                          # CRLF: ein abschliessendes CR gilt als Zeilenende
        if not teil.strip():                          # Leerzeile: Vorab-Zeile koennte verloren sein
            raise gemeinsam.Voraussetzung(
                f"Voraussetzung fehlt: Manifest beschaedigt, Zeile {nr}")
        try:
            eintrag = json.loads(teil.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            defekt.append(nr)                         # Syntax kaputt (evtl. abgebrochene Zeile)
            continue
        if not zeile_gueltig(eintrag):                # lesbar, aber inhaltlich unbrauchbar
            raise gemeinsam.Voraussetzung(
                f"Voraussetzung fehlt: Manifest beschaedigt, Zeile {nr}")
        if eintrag["zustand"] == ZUSTAND_VORAB_ABGEBROCHEN:
            markiert.add(eintrag["zeile"])
        zeilen.append(eintrag)
    abgebrochen: Optional[int] = None
    for nr in defekt:
        if nr in markiert:
            continue                                  # frueher als abgebrochen markiert
        if nr == len(teile) and ohne_umbruch:
            if not letzte_zeile_verwerfen:
                raise gemeinsam.Voraussetzung(
                    f"Voraussetzung fehlt: Manifest beschaedigt, letzte Zeile {nr} unlesbar "
                    f"(nur nach bekanntem Abbruch: {HINWEIS_VERWERFEN})")
            abgebrochen = nr
            continue
        raise gemeinsam.Voraussetzung(f"Voraussetzung fehlt: Manifest beschaedigt, Zeile {nr}")
    return ManifestStand(zeilen=zeilen, ohne_umbruch=ohne_umbruch, abgebrochene_zeile=abgebrochen)


def manifest_einzeln(pfad: str) -> Optional[bool]:
    """``True``: das Manifest fehlt noch oder hat genau einen Namen (``st_nlink`` 1).

    ``False``: mehrere Namen (harter Link, der auf eine andere Datei zeigen koennte).
    ``None``: nicht pruefbar. Liefert nur Wahrheitswerte, nie einen Pfad.
    """
    ergebnis: Optional[bool] = None
    try:
        ergebnis = int(os.stat(pfad).st_nlink) <= 1
    except FileNotFoundError:
        ergebnis = True               # noch nicht vorhanden: wird neu angelegt
    except Exception:
        ergebnis = None
    return ergebnis


class ManifestSchreiber:
    """Haengt Zeilen an das Manifest (write, flush, fsync je Zeile). Nur im Schreiblauf.

    Jeder Fehler beim Aufbereiten und Schreiben (OSError, UnicodeEncodeError,
    ValueError, TypeError ... auch von ``fsync``) wird zu ``ManifestFehler`` —
    nie verschluckt.
    """

    def __init__(self, pfad: str, zeitgeber: Any, stand: Optional[ManifestStand] = None) -> None:
        self.pfad = pfad
        self._zeit = zeitgeber
        stand = stand or ManifestStand()
        self._ohne_umbruch = stand.ohne_umbruch
        self._abgebrochen = stand.abgebrochene_zeile

    def markierung_schreiben(self) -> None:
        """Die verworfene letzte Zeile abschliessen und markieren (ohne neuen Eintrag)."""
        self.anhaengen(None)

    def _exklusiv_anlegen(self, vorn: str, ende: str) -> Any:
        """Eine NEUE Datei ``<vorn><stempel><ende>`` exklusiv oeffnen (``xb``, ``O_EXCL``).

        Ist der Name belegt — auch erst nach der Namenswahl —, wird ein neuer gewaehlt.
        Es wird nie ueberschrieben und nie umbenannt; das Pruefen und Anlegen ist ein
        einziger Aufruf.
        """
        stempel = time.strftime("%Y%m%dT%H%M%S") + "_" + secrets.token_hex(3)
        for zaehler in range(1, 1000):
            name = vorn + stempel + ("" if zaehler == 1 else f"_{zaehler}") + ende
            datei = None
            belegt = False
            try:
                datei = open(name, "xb")
            except FileExistsError:
                belegt = True                         # nur ein Merkmal; weiter mit neuem Namen
            if not belegt:
                return datei
        raise OSError("kein freier Dateiname")

    def _ordner_sichern(self, ordner: str) -> None:
        """Ordner-fsync, soweit das System es kann (Windows: ohne Wirkung)."""
        try:
            handle = os.open(ordner or ".", os.O_RDONLY)
            try:
                os.fsync(handle)
            finally:
                os.close(handle)
        except (OSError, AttributeError):
            pass                                       # best effort

    def _reparieren(self) -> None:
        """Atomar: Kopie, Temp-Datei (alt + Umbruch + Markierung), ``os.replace``.

        Im Manifest steht entweder der alte Stand oder der fertige neue Stand.
        """
        ordner = os.path.dirname(self.pfad)
        if manifest_einzeln(self.pfad) is not True:
            raise ManifestFehler()                     # harter Link: nichts lesen, nichts schreiben
        with open(self.pfad, "rb") as quelle:
            alt = quelle.read()
        with self._exklusiv_anlegen(self.pfad + ".vor_verwerfen_", "") as datei:
            datei.write(alt)
            datei.flush()
            os.fsync(datei.fileno())
        zusatz = b""
        if self._ohne_umbruch:
            zusatz += b"\n"                           # die offene letzte Zeile abschliessen
        if self._abgebrochen is not None:
            zusatz += (json.dumps({"zeit": self._zeit(), "zustand": ZUSTAND_VORAB_ABGEBROCHEN,
                                   "zeile": self._abgebrochen}, ensure_ascii=False)
                       + "\n").encode("utf-8")
        with self._exklusiv_anlegen(self.pfad + ".verwerfen_", ".tmp") as datei:
            temp = datei.name                          # eigener Name je Versuch
            datei.write(alt + zusatz)
            datei.flush()
            os.fsync(datei.fileno())
        if manifest_einzeln(self.pfad) is not True:
            raise ManifestFehler()                     # erst jetzt zum Link geworden: Abbruch
        os.replace(temp, self.pfad)
        self._ordner_sichern(ordner)

    def anhaengen(self, eintrag: Optional[Dict[str, Any]]) -> None:
        fehlgeschlagen = False
        try:
            if self._ohne_umbruch or self._abgebrochen is not None:
                self._reparieren()
                self._ohne_umbruch = False
                self._abgebrochen = None
            if eintrag is None:
                return                                 # nichts weiter zu schreiben
            text = json.dumps({"zeit": self._zeit(), **eintrag}, ensure_ascii=False) + "\n"
            ordner = os.path.dirname(self.pfad)
            if ordner:
                os.makedirs(ordner, exist_ok=True)
            if manifest_einzeln(self.pfad) is not True:
                raise ManifestFehler()                 # harter Link: nicht ins Ziel schreiben
            with open(self.pfad, "a", encoding="utf-8", newline="\n") as datei:
                datei.write(text)
                datei.flush()
                os.fsync(datei.fileno())
        except Exception:                              # auch Kodierungs-/Typ-/Wertfehler
            fehlgeschlagen = True     # nur ein Merkmal; geworfen wird ausserhalb des except
        if fehlgeschlagen:
            raise ManifestFehler()


# ── Huellen um Altcode-Pruefungen der Aufrufargumente ─────────────────────

class AufrufFehler(Exception):
    """Ein Aufrufargument ist ungueltig oder nicht pruefbar (Exit 2). Nur ein fester Text."""


def manifest_im_repo(ug: Any, pfad: str) -> bool:
    """``ug._im_repo`` als Huelle: ``True``/``False``, jede Ausnahme wird zu ``AufrufFehler``.

    Der Altcode kann bei einem Dateisystemfehler eine Ausnahme mit dem Pfad im Text
    werfen. Hier wird sie nur vermerkt; die feste Ausnahme entsteht nach dem ``except``
    (ohne Ursache, ohne Kontext, ohne Pfad).
    """
    ergebnis: Optional[bool] = None
    try:
        # angegebener Pfad UND aufgeloester Pfad (alle Links aufgeloest): einer im Repo genuegt
        angegeben = bool(ug._im_repo(Path(pfad)))
        aufgeloest = bool(ug._im_repo(Path(os.path.realpath(pfad))))
        ergebnis = angegeben or aufgeloest
    except Exception:
        ergebnis = None
    if ergebnis is None:
        raise AufrufFehler(MELDUNG_MANIFEST_PRUEFEN)
    return ergebnis


def datei_kein_link(pfad: str, meldung: str) -> None:
    """Die Datei selbst darf kein symbolischer Link sein (auch kein toter): sonst ``AufrufFehler``.

    Ein Ordner-Link im Pfad bleibt erlaubt; der Repo-Schutz greift dort ueber ``realpath``.
    """
    ist_link: Optional[bool] = None
    try:
        ist_link = bool(os.path.islink(pfad))
    except Exception:
        ist_link = None
    if ist_link is None or ist_link:
        raise AufrufFehler(meldung)


def datei_einzeln(pfad: str, meldung: str) -> None:
    """Existiert die Datei, darf sie nur einen Namen haben (``st_nlink`` 1): sonst ``AufrufFehler``.

    Ein harter Link ausserhalb des Repos koennte auf eine Datei im Repo zeigen; ``realpath``
    sieht das nicht. Nicht pruefbar zaehlt wie Verstoss.
    """
    if manifest_einzeln(pfad) is not True:
        raise AufrufFehler(meldung)


def sperre_im_repo(ug: Any, pfad: str) -> bool:
    """Wie ``manifest_im_repo``, aber fuer den Sperrpfad (feste Meldung ohne Pfad)."""
    ergebnis: Optional[bool] = None
    try:
        ergebnis = manifest_im_repo(ug, pfad)
    except AufrufFehler:
        ergebnis = None               # nur ein Merkmal; die feste Ausnahme folgt nach dem except
    if ergebnis is None:
        raise AufrufFehler(MELDUNG_SPERRE_PRUEFEN)
    return ergebnis


def ziel_pruefen(ug: Any, ziel: Any) -> str:
    """``ug.ziel_pfad_pruefen`` als Huelle: jede Ausnahme wird zu ``AufrufFehler`` (fester Text)."""
    ergebnis: Optional[str] = None
    try:
        ergebnis = ug.ziel_pfad_pruefen(ziel)
    except Exception:
        ergebnis = None               # auch UebergabeFehler: sein Text nennt den Pfad
    if not isinstance(ergebnis, str):
        raise AufrufFehler(MELDUNG_ZIEL)
    return ergebnis


# ── Ordnerweg mit fester Fehlerart ─────────────────────────────────────────

_FEST_ARTEN = (
    ("pCloud nicht erreichbar", "netz"),
    ("pCloud lieferte", "antwort"),
    ("pCloud ist nicht konfiguriert", "konfig"),
    ("Abgewiesen", "aufruf"),
    ("Zielordner fehlt", "aufruf"),
    ("Schreiben ist nur", "aufruf"),
)
_MUSTER_HTTP = re.compile(r"pCloud antwortete mit HTTP (\d{1,3})\.")
_MUSTER_CODE = re.compile(r"pCloud meldet Fehler (\d{1,5}):")


def _art_aus_altfehler(problem: BaseException) -> Tuple[str, Optional[int]]:
    """Feste Fehlerart zu einer Ausnahme des Altcodes — ohne je Text weiterzugeben.

    Nur der Anfang der festen Meldungen des Altcodes wird erkannt; aus dem Rest
    (Fehlertext der pCloud, Pfad) wird allein ein validierter Zahlencode gelesen.
    """
    text = str(problem)
    treffer = _MUSTER_HTTP.match(text)
    if treffer:
        return "http", int(treffer.group(1))
    treffer = _MUSTER_CODE.match(text)
    if treffer:
        return "abgelehnt", int(treffer.group(1))
    for anfang, art in _FEST_ARTEN:
        if text.startswith(anfang):
            return art, None
    return "abgelehnt", None


def ordner_holen_sicher(ug: Any, pfad: str, **kw: Any) -> int:
    """``ug.ordner_holen_oder_anlegen`` als Huelle: Ausnahmen nur mit fester Art.

    Der Altcode (``uebergabe_hochladen.py``) bleibt unveraendert; er kann Fehlertext
    der pCloud oder den Zielpfad in einer Ausnahme tragen. Hier wird jede Ausnahme
    in ``PCloudFehler`` (feste Art, ggf. Zahlencode) umgewandelt — ohne Ursache
    und ohne Kontext (die neue Ausnahme entsteht ausserhalb des ``except``).
    """
    try:
        return ug.ordner_holen_oder_anlegen(pfad, **kw)
    except ug.PCloudFehler:
        raise                                         # bereits mit fester Art
    except Exception as problem:
        art, code = _art_aus_altfehler(problem)
    raise ug.PCloudFehler(art, code)


# ── Der Lauf ───────────────────────────────────────────────────────────────

class Lauf:
    """Ein Lauf: lesen, einordnen, ggf. hochladen. Zaehler statt Namen."""

    def __init__(self, ug: Any, zugang: Any, *, ziel: str, schreiben: bool,
                 max_uploads: Optional[int], offene_neu: bool, manifest_pfad: str,
                 stand: ManifestStand) -> None:
        self.ug = ug
        self._kw = {"token": zugang.token, "host": zugang.host}
        self.ziel = ziel
        self.schreiben = schreiben
        self.max = max_uploads
        self.offene_neu = offene_neu
        self.manifest = ManifestSchreiber(manifest_pfad, ug._jetzt_iso, stand)
        self.versuche = versuche_aufbauen(stand.zeilen)
        self.gestoppt = False                      # Manifest nicht schreibbar -> kein Upload mehr
        self.verwerfen_angefordert = False         # --letzte-zeile-verwerfen gesetzt
        self.verworfen_zeile: Optional[int] = None  # Zeilennummer, wenn die Option wirkte
        self.z: Counter = Counter()
        self.fehlerarten: Counter = Counter()
        self.ordner_ids: Dict[str, int] = {}
        self.vormerk: Set[str] = set()
        self.uploads = 0

    def letzte_zeile_verwerfen(self, angefordert: bool, stand: ManifestStand) -> None:
        """Die bewusst verworfene letzte Zeile sofort markieren (write, fsync)."""
        self.verwerfen_angefordert = angefordert
        if stand.abgebrochene_zeile is None:
            return
        try:
            self._nur_schreibend()
            self.manifest.markierung_schreiben()
            self.verworfen_zeile = stand.abgebrochene_zeile
        except ManifestFehler as problem:
            self.gestoppt = True
            self.fehler(problem)

    # -- Schutz: im Trockenlauf darf nichts Schreibendes passieren ------------
    def _nur_schreibend(self) -> None:
        if not self.schreiben:
            raise RuntimeError("Schreibweg im Trockenlauf")

    def fehler(self, problem: BaseException) -> None:
        self.z["fehler"] += 1
        self.fehlerarten[gemeinsam.fehlerart(problem)] += 1

    def _buche(self, rel: str, sha: str, v: Versuch, zustand: str, **zusatz: Any) -> None:
        """Eine Manifestzeile anhaengen (nur im Schreiblauf)."""
        self._nur_schreibend()
        eintrag = {"pfad": rel, "groesse": v.groesse, "sha256": sha, "mtime": v.mtime,
                   "kennung": v.kennung, "zustand": zustand, "fileid": v.fileid,
                   "cloud_name": v.cloud_name, "ordner_id": v.ordner_id}
        eintrag.update(zusatz)
        self.manifest.anhaengen(eintrag)

    # -- Eigentumsbeleg ------------------------------------------------------
    def beleg(self, fileid: Any, ordner_id: Any, kennung: str, sha: str
              ) -> Tuple[str, Optional[str]]:
        """``(ok|fehlt|verletzt, Name in der Cloud)`` fuer eine fileid.

        Alle drei muessen stimmen: Zielordner, Kennung im Namen, Cloud-Pruefsumme.
        Netzfehler werfen (kein Raten).
        """
        if _als_int(fileid) is None:
            return BELEG_VERLETZT, None
        try:
            meta = self.ug.stat_datei(fileid, **self._kw)
        except self.ug.PCloudNichtGefunden:
            return BELEG_FEHLT, None
        name = meta.get("name") if isinstance(meta.get("name"), str) else None
        parent = _als_int(meta.get("parentfolderid"))
        ziel_id = _als_int(ordner_id)
        if (meta.get("isfolder") or name is None or parent is None or ziel_id is None
                or parent != ziel_id or f"_wa{kennung}" not in name):
            return BELEG_VERLETZT, name
        widerspruch = False
        gemerkt: Optional[BaseException] = None
        try:
            cloud = self.ug.pruefsumme_cloud(fileid, **self._kw)
        except self.ug.PCloudNichtGefunden:
            widerspruch = True        # stat fand die Datei, checksumfile nicht: Widerspruch
        except self.ug.PCloudFehler as problem:
            gemerkt = problem         # nur merken; geworfen wird ausserhalb des except
            widerspruch = getattr(problem, "art", None) == "antwort"   # keine gueltige Summe
        if gemerkt is not None and not widerspruch:
            raise gemerkt             # andere Fehler: als Fehlerart zaehlen, kein Upload
        if widerspruch:
            return BELEG_VERLETZT, name   # unklar: kein Upload, nicht entfernbar
        if cloud != sha:
            return BELEG_VERLETZT, name
        return BELEG_OK, name

    # -- Wiederaufnahme: Vorab-Zeilen ohne Ergebnis aufloesen -----------------
    def wiederaufnahme(self) -> None:
        zwischenspeicher: Dict[int, Optional[List[Dict[str, Any]]]] = {}
        for (rel, sha), liste in sorted(self.versuche.items()):
            v = _letzter(liste)
            if v is None or v.zustand != "begonnen":
                continue
            if self.gestoppt:
                return
            try:
                self._aufloesen(rel, sha, v, zwischenspeicher)
            except ManifestFehler as problem:
                self.gestoppt = True
                self.fehler(problem)
            except Exception as problem:
                self.fehler(problem)

    def _aufloesen(self, rel: str, sha: str, v: Versuch,
                   zwischenspeicher: Dict[int, Optional[List[Dict[str, Any]]]]) -> None:
        treffer: List[Dict[str, Any]] = []
        if v.ordner_id is not None:
            if v.ordner_id not in zwischenspeicher:
                zwischenspeicher[v.ordner_id] = self.ug.ordner_auflisten(
                    folderid=v.ordner_id, **self._kw)
            marke = f"_wa{v.kennung}"
            treffer = [e for e in zwischenspeicher[v.ordner_id] or []
                       if not e.get("isfolder") and isinstance(e.get("name"), str)
                       and marke in e["name"] and _als_int(e.get("fileid")) is not None]
        if len(treffer) == 1:
            fileid = treffer[0]["fileid"]
            status, name = self.beleg(fileid, v.ordner_id, v.kennung, sha)
            if status == BELEG_OK:
                v.zustand, v.fileid = ZUSTAND_HOCHGELADEN, fileid
                v.cloud_name = name or v.cloud_name
                if self.schreiben:
                    self._buche(rel, sha, v, ZUSTAND_HOCHGELADEN)
                return
        v.zustand = ZUSTAND_UNKLAR_BEGONNEN
        if self.schreiben:
            self._buche(rel, sha, v, ZUSTAND_UNKLAR_BEGONNEN)

    # -- Je Datei -------------------------------------------------------------
    def verarbeiten(self, eintrag: Any) -> None:
        if self.gestoppt:
            return
        try:
            self._verarbeiten(eintrag)
        except ManifestFehler as problem:
            self.gestoppt = True                      # kein weiterer Upload in diesem Lauf
            self.fehler(problem)
        except Exception as problem:
            self.fehler(problem)

    def _verarbeiten(self, e: Any) -> None:
        # Ein einziger Lesevorgang: Groesse/mtime vom selben Dateizeiger, sha256 und
        # Upload aus genau diesen Bytes.
        with open(e.pfad, "rb") as datei:
            st = os.fstat(datei.fileno())
            daten = datei.read()
        if not daten:
            self.z["leer"] += 1
            return
        sha = hashlib.sha256(daten).hexdigest()
        rel = f"{e.kategorie}/{e.name}"
        mtime = int(st.st_mtime)
        v = _letzter(self.versuche.get((rel, sha), []))

        if v is None:
            self.z["neu"] += 1
        elif v.zustand == ZUSTAND_HOCHGELADEN:
            status, _name = self.beleg(v.fileid, v.ordner_id, v.kennung, sha)
            if status == BELEG_OK:
                self.z["erledigt"] += 1
                return
            if status == BELEG_FEHLT:
                self.z["fehlt_in_cloud"] += 1
                if self.schreiben and v.notiz != ZUSTAND_FEHLT:
                    self._buche(rel, sha, v, ZUSTAND_FEHLT)
                    v.notiz = ZUSTAND_FEHLT
            else:
                self.z["unklar"] += 1
                if self.schreiben and v.notiz != ZUSTAND_UNKLAR:
                    self._buche(rel, sha, v, ZUSTAND_UNKLAR)
                    v.notiz = ZUSTAND_UNKLAR
                return
        elif v.zustand == ZUSTAND_UNKLAR_BEGONNEN:
            self.z["unklar_begonnen"] += 1
            if not (self.schreiben and self.offene_neu):
                return
        else:
            return                                   # Wiederaufnahme war nicht moeglich

        self._hochladen(e, rel, sha, daten, mtime)

    def _ordner_id(self, pfad: str) -> int:
        if pfad not in self.ordner_ids:
            self._nur_schreibend()
            self.ordner_ids[pfad] = ordner_holen_sicher(self.ug, pfad, **self._kw)
        return self.ordner_ids[pfad]

    def _hochladen(self, e: Any, rel: str, sha: str, daten: bytes, mtime: int) -> None:
        if self.max is not None and self.uploads >= self.max:
            self.z["zurueckgestellt"] += 1
            return
        zielpfad = f"{self.ziel}/{e.kategorie}/{e.jahr}"
        if not self.schreiben:                        # Trockenlauf: nur vormerken
            self.uploads += 1
            self.z["bytes"] += len(daten)
            self.vormerk.add(zielpfad)
            return

        ordner_id = self._ordner_id(zielpfad)
        stamm, endung = os.path.splitext(e.name)
        endung = endung.lower()
        kennung = cloud_name = None
        for _versuch in range(MAX_KENNUNG_VERSUCHE):  # Ordner unmittelbar vor dem Upload lesen
            kandidat = secrets.token_hex(6)
            name = f"{stamm}_wa{kandidat}{endung}"
            inhalt = self.ug.ordner_auflisten(folderid=ordner_id, **self._kw) or []
            if name not in {i.get("name") for i in inhalt}:
                kennung, cloud_name = kandidat, name
                break
        if kennung is None or cloud_name is None:
            self.z["unklar"] += 1                     # praktisch ausgeschlossen
            return

        self.uploads += 1
        self.z["bytes"] += len(daten)
        v = Versuch(kennung)
        v.zustand, v.ordner_id, v.cloud_name = "begonnen", ordner_id, cloud_name
        v.groesse, v.mtime = len(daten), mtime
        self.versuche.setdefault((rel, sha), []).append(v)
        self._buche(rel, sha, v, ZUSTAND_BEGONNEN)    # Vorab-Zeile, fsync — DANN erst der Upload

        fileid, name_cloud = self.ug.hochladen_ohne_ueberschreiben(
            cloud_name, daten, ordner_id, **self._kw)
        if fileid is None:
            v.zustand = ZUSTAND_UNKLAR_BEGONNEN
            self._buche(rel, sha, v, ZUSTAND_UNKLAR_BEGONNEN)
            self.z["unklar_begonnen"] += 1
            return
        status, name_beleg = self.beleg(fileid, ordner_id, kennung, sha)
        if status == BELEG_OK:
            v.zustand, v.fileid = ZUSTAND_HOCHGELADEN, fileid
            v.cloud_name = name_beleg or name_cloud
            self._buche(rel, sha, v, ZUSTAND_HOCHGELADEN)
            self.z["hochgeladen"] += 1
        else:
            v.zustand = ZUSTAND_UNKLAR_BEGONNEN
            self._buche(rel, sha, v, ZUSTAND_UNKLAR_BEGONNEN)
            self.z["unklar_begonnen"] += 1

    # -- Trockenlauf: Zielordner nur lesend pruefen ---------------------------
    def zielordner_pruefen(self) -> None:
        for pfad in sorted(self.vormerk):
            try:
                inhalt = self.ug.ordner_auflisten(pfad=pfad, **self._kw)
            except Exception as problem:
                self.fehler(problem)
                continue
            self.z["zielordner_neu" if inhalt is None else "zielordner_vorhanden"] += 1


# ── Sperre ─────────────────────────────────────────────────────────────────

def _sperre_nehmen(pfad: str) -> None:
    meldung = None
    try:
        ordner = os.path.dirname(pfad)
        if ordner:
            os.makedirs(ordner, exist_ok=True)
        os.mkdir(pfad)                                # atomar: genau ein Schreiber
    except FileExistsError:
        meldung = MELDUNG_SPERRE      # nur ein Merkmal; geworfen wird ausserhalb des except
    except OSError:
        meldung = MELDUNG_SPERRE_ANLEGEN
    if meldung is not None:
        raise gemeinsam.Voraussetzung(meldung)


def _sperre_freigeben(pfad: str) -> None:
    """Nur die eigene Sperre (ein leerer Ordner) wieder freigeben."""
    try:
        os.rmdir(pfad)
    except OSError:
        pass


# ── Ausgabe ────────────────────────────────────────────────────────────────

def _zeilen(lauf: Lauf, gefunden: Dict[str, int], schreiben: bool) -> List[str]:
    z, n = lauf.z, gemeinsam.zahl_de
    zeilen = [
        "WhatsApp-Bilder -> pCloud: " + ("HOCHLADEN" if schreiben
                                         else "TROCKENLAUF (nichts wird geschrieben)"),
        f"Bilder gefunden: {n(sum(gefunden.values()))} "
        f"(empfangen {n(gefunden['empfangen'])}, gesendet {n(gefunden['gesendet'])})",
        f"neu {n(z['neu'])} · erledigt {n(z['erledigt'])} · fehlt_in_cloud {n(z['fehlt_in_cloud'])}"
        f" · unklar {n(z['unklar'])} · unklar_begonnen {n(z['unklar_begonnen'])}"
        f" · bytes {n(z['bytes'])}",
        f"nicht_bilder {n(z['nicht_bilder'])} · leer {n(z['leer'])} · fehler {n(z['fehler'])}",
    ]
    if schreiben:
        zeilen.append(f"hochgeladen {n(z['hochgeladen'])} · zurueckgestellt {n(z['zurueckgestellt'])}")
    else:
        zeilen.append(f"zielordner_vorhanden {n(z['zielordner_vorhanden'])} · "
                      f"zielordner_neu {n(z['zielordner_neu'])} · "
                      f"zurueckgestellt {n(z['zurueckgestellt'])}")
    if lauf.gestoppt:
        zeilen.append("Lauf gestoppt: Manifest nicht schreibbar, keine weiteren Uploads.")
    if lauf.verwerfen_angefordert and lauf.verworfen_zeile is not None:
        zeilen.append(f"Option --letzte-zeile-verwerfen: unlesbare letzte Zeile "
                      f"({n(lauf.verworfen_zeile)}) verworfen, Markierung geschrieben.")
    elif lauf.verwerfen_angefordert and not lauf.gestoppt:
        zeilen.append("Option --letzte-zeile-verwerfen: letzte Zeile unauffaellig, ohne Wirkung.")
    if lauf.fehlerarten:
        zeilen.append("Fehlerarten: " + ", ".join(
            f"{art} x{n(anzahl)}" for art, anzahl in sorted(lauf.fehlerarten.items())))
    if not schreiben:
        zeilen.append("Zum Ausfuehren: --schreiben anhaengen.")
    return zeilen


def _argumente(argv: Optional[List[str]] = None):
    p = gemeinsam.LeiserParser(
        description="WhatsApp-Bilder in die pCloud kopieren (Trockenlauf ist Standard). "
                    "Nur kopieren: am Handy bleibt alles, in der pCloud wird nie ueberschrieben.")
    p.add_argument("--ordner", default=gemeinsam.STANDARD_MEDIENPFAD,
                   help="Medienordner (Standard: WhatsApp Images auf dem Handy)")
    p.add_argument("--ziel", default=STANDARD_ZIEL,
                   help=f"pCloud-Zielordner, nur unter /Agent/ (Standard {STANDARD_ZIEL})")
    p.add_argument("--manifest", default=STANDARD_MANIFEST,
                   help=f"Manifest, nie im Repo (Standard {STANDARD_MANIFEST})")
    p.add_argument("--sperre", default=STANDARD_SPERRE,
                   help="Sperr-Ordner gegen zweite Schreiber (nur mit --schreiben)")
    p.add_argument("--schreiben", action="store_true", help="WIRKLICH hochladen")
    p.add_argument("--max", type=int, default=None, help="hoechstens N Uploads in diesem Lauf")
    p.add_argument("--offene-neu", action="store_true", dest="offene_neu",
                   help="unklar_begonnen-Dateien mit neuer Kennung erneut hochladen "
                        "(nur zusammen mit --schreiben)")
    p.add_argument("--letzte-zeile-verwerfen", action="store_true", dest="letzte_zeile_verwerfen",
                   help="NUR nach einem bekannten Abbruch: eine unlesbare letzte Manifestzeile "
                        "ohne Zeilenumbruch bewusst verwerfen (Markierung statt Loeschen; "
                        "nur zusammen mit --schreiben; sonst bricht der Lauf mit Exit 3 ab)")
    return p.parse_args(argv)


def _lauf(args: Any) -> int:
    ug = gemeinsam.uebergabe_laden()
    try:
        ziel = ziel_pruefen(ug, args.ziel)
    except AufrufFehler as fehler:
        print(str(fehler), file=sys.stderr)
        return gemeinsam.EXIT_AUFRUF
    if args.offene_neu and not args.schreiben:
        print(MELDUNG_OFFENE_NEU, file=sys.stderr)
        return gemeinsam.EXIT_AUFRUF
    if args.letzte_zeile_verwerfen and not args.schreiben:
        print(MELDUNG_VERWERFEN_OHNE_SCHREIBEN, file=sys.stderr)
        return gemeinsam.EXIT_AUFRUF
    if args.max is not None and args.max < 1:
        print(MELDUNG_MAX, file=sys.stderr)
        return gemeinsam.EXIT_AUFRUF
    manifest_angegeben = os.path.expanduser(args.manifest)
    sperre = os.path.expanduser(args.sperre)
    sperre_repo = False
    try:
        # Manifest: kein Link, nicht im Repo (angegeben ODER aufgeloest); ab hier gilt nur
        # der aufgeloeste Pfad (Lesen, Kopie, Temp, os.replace im aufgeloesten Ordner)
        datei_kein_link(manifest_angegeben, MELDUNG_MANIFEST_PRUEFEN)
        datei_einzeln(manifest_angegeben, MELDUNG_MANIFEST_PRUEFEN)
        im_repo = manifest_im_repo(ug, manifest_angegeben)
        if not im_repo:
            datei_kein_link(sperre, MELDUNG_SPERRE_PRUEFEN)
            sperre_repo = sperre_im_repo(ug, sperre)
    except AufrufFehler as fehler:
        print(str(fehler), file=sys.stderr)
        return gemeinsam.EXIT_AUFRUF
    if im_repo:
        print(MELDUNG_MANIFEST_REPO, file=sys.stderr)
        return gemeinsam.EXIT_AUFRUF
    if sperre_repo:
        print(MELDUNG_SPERRE_REPO, file=sys.stderr)
        return gemeinsam.EXIT_AUFRUF
    manifest_pfad = os.path.realpath(manifest_angegeben)

    zugang = gemeinsam.zugang_aufloesen()            # httpx, Host, Token — vor jedem Netz
    medien = gemeinsam.medien_lesen(args.ordner)
    bilder = [e for e in medien.dateien if gemeinsam.ist_bild(e.name)]
    gefunden = {k: sum(1 for e in bilder if e.kategorie == k) for k in gemeinsam.KATEGORIEN}

    if args.schreiben:
        _sperre_nehmen(sperre)
    try:
        stand = manifest_streng_lesen(manifest_pfad, bool(args.letzte_zeile_verwerfen))
        lauf = Lauf(ug, zugang, ziel=ziel, schreiben=bool(args.schreiben),
                    max_uploads=args.max, offene_neu=bool(args.offene_neu),
                    manifest_pfad=manifest_pfad, stand=stand)
        lauf.z["nicht_bilder"] = len(medien.dateien) - len(bilder)
        lauf.letzte_zeile_verwerfen(bool(args.letzte_zeile_verwerfen), stand)
        lauf.wiederaufnahme()
        for eintrag in bilder:
            if lauf.gestoppt:
                break
            lauf.verarbeiten(eintrag)
        if not args.schreiben:
            lauf.zielordner_pruefen()
    finally:
        if args.schreiben:
            _sperre_freigeben(sperre)

    for zeile in _zeilen(lauf, gefunden, bool(args.schreiben)):
        print(zeile)
    return gemeinsam.EXIT_FEHLER if lauf.z["fehler"] else gemeinsam.EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _argumente(argv)
    except SystemExit as ende:
        return int(ende.code or 0)
    try:
        return _lauf(args)
    except gemeinsam.Voraussetzung as fehler:
        return gemeinsam.voraussetzung_melden(fehler)
    except Exception as fehler:                      # letzte Absicherung: nur die Fehlerart
        print(f"Fehler: unerwarteter Abbruch ({gemeinsam.fehlerart(fehler)})", file=sys.stderr)
        return gemeinsam.EXIT_FEHLER


if __name__ == "__main__":
    raise SystemExit(main())
