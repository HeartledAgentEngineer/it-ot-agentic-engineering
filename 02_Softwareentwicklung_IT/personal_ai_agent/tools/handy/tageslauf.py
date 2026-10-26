"""Tagesimport am Handy: ein Aufruf holt alles Lokale einmal am Tag nach (25.10.2026).

Plan: ``.hermes/plans/2026-10-25_tagesimport-handy.md`` (Fassung 1, Schritt C1).

Laeuft in Termux, rein deterministisch: kein Sprachmodell, kein Agent. Ausgeloest wird es
vom Start (``termux/start-vorbereiten.sh`` ruft ``--wenn-faellig`` im Hintergrund auf);
einen Cron oder Termux-Job braucht es nicht.

Aufruf (im Projektordner ``personal_ai_agent``):
    python -B tools/handy/tageslauf.py --wenn-faellig   # nur, wenn heute noch nicht gelaufen
    python -B tools/handy/tageslauf.py --jetzt          # von Hand, ignoriert die Faelligkeit
    python -B tools/handy/tageslauf.py --trocken        # zeigen, nichts schreiben

Schalter: ``~/foto_sortierung/tageslauf.json``. Fehlt die Datei, gilt ``{"an": false}``.
Nur ein echtes ``true`` schaltet ein. Ist der Schalter aus, steht eine Zeile
"Tagesimport: aus" da, Exit 0 — und es wird NICHTS geschrieben (auch keine Stand-Datei).
Weitere Schluessel der Datei: ``kamera_ordner`` (pCloud-Pfad, kein Standardwert) und
``gemini_letzter_export`` (ISO-Datum).

Bausteine (Fehler eines Bausteins stoppt die anderen nicht):
    1. WhatsApp-Bilder: Unterprozess ``whatsapp_bilder_hochladen.py --schreiben`` (ohne
       Mengenbegrenzung), Zeitgrenze 2 Stunden. Im Trockenlauf ohne ``--schreiben``. Der einzige
       Weg, der in die pCloud schreibt; jede Operation steht im W1-Manifest.
    2. WhatsApp-Chats: Platzhalter ("nicht eingerichtet (W2 Teil B)"), kein Fehler.
    3. Kamera zaehlen (nur lesend): ``listfolder`` auf ``kamera_ordner`` (nicht rekursiv),
       Vergleich mit der Zahl des letzten vollstaendigen Laufs. Keine Dateinamen.
    4. Gemini: nur Erinnerung, wenn der letzte Takeout-Export mehr als 60 Tage zurueckliegt
       oder unbekannt ist. Kein Netz.

Schutz:
    * Nie loeschen. Geloescht wird nur die eigene Sperrkennung beim Freigeben der Sperre.
    * Sperre ``.tageslauf.sperre`` (``os.mkdir``, atomar) mit Kennung; eine Sperre mit
      eigener Kennung, die aelter als 6 Stunden ist, gilt als verwaist und wird abgeraeumt;
      jede andere alte Sperre bleibt liegen (Exit 3, im Zweifel nicht starten).
    * Akku unter 20 Prozent ohne Laden (``termux-battery-status``, falls vorhanden):
      der schreibende Baustein wird uebersprungen; der Lauf gilt dann nicht als vollstaendig.
    * Stand-, Bericht- und Sperrdatei: keine symbolischen und keine harten Links, nie in
      einem Git-Repo; Schreiben atomar (Temp-Datei, fsync, ``os.replace``).
    * Ausgabe, Log und Bericht enthalten nur Zahlen und feste Texte: keine Pfade, keine
      Datei- oder Chatnamen, keine Werte aus der ``.env``.

Dateien im Datenordner (Standard ``~/foto_sortierung``, ueber ``--daten-ordner`` oder die
Umgebungsvariable ``TAGESLAUF_DATEN`` aenderbar):
    ``tageslauf.json`` (Schalter, gelesen) · ``.tageslauf_stand.json`` (letzter vollstaendiger
    Lauf) · ``tageslauf_bericht.json`` (letzter Bericht, maschinenlesbar) · ``.tageslauf.sperre``.
Das Protokoll ``tageslauf.log`` liegt im Diagnose-Ordner (``--log-ordner``; Standard
``<Download>/hermes_diag``, wie bei den anderen Startschritten).

Der Stand wird nur bei vollstaendigem Erfolg aller aktiven Bausteine fortgeschrieben; sonst
laeuft der naechste Start den Tagesimport erneut.

Exit: 0 ok · 1 Fehler in einem Baustein · 2 Aufruf-/Schutzfehler · 3 nicht pruefbar
(Voraussetzung fehlt, Sperre unklar, Einstellungen unlesbar). Der Gesamt-Exit ist der
schlechteste Exit der Bausteine.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

HIER = os.path.dirname(os.path.abspath(__file__))
if HIER not in sys.path:
    sys.path.insert(0, HIER)

import whatsapp_bilder_gemeinsam as gemeinsam  # noqa: E402

STANDARD_DATEN = "~/foto_sortierung"
UMGEBUNG_DATEN = "TAGESLAUF_DATEN"
EINSTELLUNGEN_NAME = "tageslauf.json"
STAND_NAME = ".tageslauf_stand.json"
BERICHT_NAME = "tageslauf_bericht.json"
SPERRE_NAME = ".tageslauf.sperre"
KENNUNG_NAME = "kennung.json"
LOG_NAME = "tageslauf.log"
W1_SKRIPT = os.path.join(HIER, "whatsapp_bilder_hochladen.py")

W1_ZEITGRENZE_S = 2 * 3600
SPERRE_ALTER_S = 6 * 3600
AKKU_GRENZE = 20
GEMINI_TAGE = 60
AKKU_ZEITGRENZE_S = 15

EXIT_OK = gemeinsam.EXIT_OK
EXIT_FEHLER = gemeinsam.EXIT_FEHLER
EXIT_AUFRUF = gemeinsam.EXIT_AUFRUF
EXIT_NICHT_PRUEFBAR = gemeinsam.EXIT_VORAUSSETZUNG

LESENDE_METHODEN = ("listfolder",)

MELDUNG_REPO = "Aufruf ungueltig: Daten- und Log-Ordner duerfen nicht in einem Git-Repo liegen."
MELDUNG_LINK = "Aufruf ungueltig: Stand-, Bericht- oder Sperrdatei ist ein Link."


class Schutzverstoss(Exception):
    """Ein Schreibziel ist ein Link oder liegt im Repo (Exit 2). Die Meldung ist fest."""


@dataclass
class Ergebnis:
    """Ergebnis eines Bausteins: nur Zahlen und ein fester Text."""

    name: str
    status: str            # ok | fehler | uebersprungen | nicht_eingerichtet | nicht_pruefbar | aufruf | erinnerung
    exit: int
    text: str
    zahlen: Dict[str, int] = field(default_factory=dict)
    vollstaendig: bool = True      # False: der Tag gilt nicht als erledigt


def schlechtester_exit(ergebnisse: List[Ergebnis]) -> int:
    return max([e.exit for e in ergebnisse], default=EXIT_OK)


# ── Kleine Helfer ──────────────────────────────────────────────────────────

def _heute() -> datetime.date:
    return datetime.date.today()


def _jetzt_iso() -> str:
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def _epoche() -> float:
    return time.time()


def _zahl(wert: Any) -> str:
    return gemeinsam.zahl_de(wert)


def _im_repo(pfad: str) -> bool:
    """True, wenn ueber dem aufgeloesten Pfad (oder auf ihm) ein ``.git`` liegt."""
    voll = os.path.realpath(os.path.expanduser(pfad))
    kandidat = voll
    while True:
        if os.path.exists(os.path.join(kandidat, ".git")):
            return True
        eltern = os.path.dirname(kandidat)
        if eltern == kandidat:
            return False
        kandidat = eltern


def _schreibziel_pruefen(pfad: str) -> None:
    """Zieldatei darf kein Link sein (weder symbolisch noch hart)."""
    if os.path.islink(pfad):
        raise Schutzverstoss(MELDUNG_LINK)
    try:
        if os.stat(pfad).st_nlink > 1:
            raise Schutzverstoss(MELDUNG_LINK)
    except FileNotFoundError:
        pass


def _atomar_schreiben(pfad: str, text: str) -> None:
    """Datei atomar schreiben: eigene Temp-Datei im selben Ordner, fsync, ``os.replace``."""
    _schreibziel_pruefen(pfad)
    ordner = os.path.dirname(pfad) or "."
    os.makedirs(ordner, exist_ok=True)
    temp = os.path.join(ordner, f"{os.path.basename(pfad)}.{secrets.token_hex(4)}.tmp")
    with open(temp, "xb") as datei:
        datei.write(text.encode("utf-8"))
        datei.flush()
        os.fsync(datei.fileno())
    os.replace(temp, pfad)


def _json_lesen(pfad: str) -> Tuple[str, Any]:
    """``("fehlt"|"ok"|"defekt", Daten)`` — wirft nie."""
    if not os.path.exists(pfad):
        return "fehlt", None
    daten: Any = None
    gelesen = False
    try:
        with open(pfad, "r", encoding="utf-8") as datei:
            daten = json.load(datei)
        gelesen = True
    except (OSError, ValueError):
        gelesen = False
    return ("ok", daten) if gelesen else ("defekt", None)


def _log_schreiben(ordner: Optional[str], zeilen: List[str]) -> None:
    """Zeilen mit Zeitstempel an ``tageslauf.log`` haengen. Best effort, wirft nie."""
    if not ordner:
        return
    try:
        if not os.path.isdir(ordner):
            if not os.path.isdir(os.path.dirname(ordner) or "."):
                return                                    # Download-Ordner gibt es nicht: kein Log
            os.makedirs(ordner, exist_ok=True)
        pfad = os.path.join(ordner, LOG_NAME)
        _schreibziel_pruefen(pfad)
        stempel = _jetzt_iso()
        with open(pfad, "a", encoding="utf-8", newline="\n") as datei:
            for zeile in zeilen:
                datei.write(f"{stempel} {zeile}\n")
            datei.flush()
            os.fsync(datei.fileno())
    except (OSError, Schutzverstoss):
        return


def _log_ordner_standard() -> str:
    heim = os.path.expanduser("~")
    downloads = os.path.join(heim, "storage", "downloads")
    if not os.path.isdir(downloads):
        downloads = "/sdcard/Download"
    return os.path.join(downloads, "hermes_diag")


# ── Sperre ─────────────────────────────────────────────────────────────────

def _sperre_nehmen(pfad: str) -> Tuple[str, Optional[str]]:
    """``(status, kennung)``; Status ``ok`` | ``laeuft`` | ``unklar`` | ``fehler``."""
    for _versuch in range(2):
        kennung = secrets.token_hex(6)
        angelegt = belegt = False
        try:
            os.mkdir(pfad)
            angelegt = True
        except FileExistsError:
            belegt = True
        except OSError:
            return "fehler", None
        if angelegt:
            try:
                with open(os.path.join(pfad, KENNUNG_NAME), "x", encoding="utf-8") as datei:
                    json.dump({"kennung": kennung, "pid": os.getpid(), "start": _epoche()}, datei)
                    datei.flush()
                    os.fsync(datei.fileno())
                return "ok", kennung
            except OSError:
                _sperre_ordner_freigeben(pfad)
                return "fehler", None
        if belegt:
            urteil = _sperre_beurteilen(pfad)
            if urteil != "verwaist":
                return urteil, None
            if not _sperre_abraeumen(pfad):
                return "unklar", None
    return "laeuft", None


def _sperre_beurteilen(pfad: str) -> str:
    """``laeuft`` | ``unklar`` | ``verwaist`` (nur mit eigener Kennung und Alter > 6 h)."""
    if not os.path.isdir(pfad) or os.path.islink(pfad):
        return "unklar"
    status, inhalt = _json_lesen(os.path.join(pfad, KENNUNG_NAME))
    start = inhalt.get("start") if isinstance(inhalt, dict) else None
    kennung = inhalt.get("kennung") if isinstance(inhalt, dict) else None
    eigen = (status == "ok" and isinstance(kennung, str)
             and re.fullmatch(r"[0-9a-f]{12}", kennung) is not None
             and isinstance(start, (int, float)) and not isinstance(start, bool))
    if eigen:
        return "verwaist" if _epoche() - float(start) > SPERRE_ALTER_S else "laeuft"
    try:
        alter = _epoche() - os.stat(pfad).st_mtime
    except OSError:
        return "unklar"
    return "laeuft" if alter <= SPERRE_ALTER_S else "unklar"


def _sperre_abraeumen(pfad: str) -> bool:
    """Eine verwaiste EIGENE Sperre entfernen (nur Kennungsdatei und leerer Ordner)."""
    try:
        if sorted(os.listdir(pfad)) != [KENNUNG_NAME]:
            return False
        os.remove(os.path.join(pfad, KENNUNG_NAME))
        os.rmdir(pfad)
        return True
    except OSError:
        return False


def _sperre_ordner_freigeben(pfad: str) -> None:
    try:
        os.rmdir(pfad)
    except OSError:
        pass


def _sperre_freigeben(pfad: str, kennung: Optional[str]) -> None:
    """Nur die eigene Sperre freigeben (Kennung muss stimmen)."""
    if kennung is None:
        return
    status, inhalt = _json_lesen(os.path.join(pfad, KENNUNG_NAME))
    if status != "ok" or not isinstance(inhalt, dict) or inhalt.get("kennung") != kennung:
        return
    try:
        os.remove(os.path.join(pfad, KENNUNG_NAME))
        os.rmdir(pfad)
    except OSError:
        pass


# ── Akku ───────────────────────────────────────────────────────────────────

def _akku_ausgabe() -> Optional[str]:
    """Ausgabe von ``termux-battery-status`` oder ``None`` (Befehl fehlt / schlaegt fehl)."""
    befehl = shutil.which("termux-battery-status")
    if not befehl:
        return None
    ausgabe: Optional[str] = None
    try:
        lauf = subprocess.run([befehl], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=AKKU_ZEITGRENZE_S, stdin=subprocess.DEVNULL)
        if lauf.returncode == 0:
            ausgabe = lauf.stdout
    except Exception:
        ausgabe = None
    return ausgabe


def akku_niedrig(text: Optional[str]) -> bool:
    """True bei unter 20 Prozent ohne Laden; unlesbar oder unbekannt zaehlt als nicht niedrig."""
    if not text:
        return False
    daten: Any = None
    try:
        daten = json.loads(text)
    except ValueError:
        return False
    if not isinstance(daten, dict):
        return False
    prozent = daten.get("percentage")
    if not isinstance(prozent, (int, float)) or isinstance(prozent, bool):
        return False
    laedt = (str(daten.get("status", "")).upper() in ("CHARGING", "FULL")
             or str(daten.get("plugged", "UNPLUGGED")).upper() not in ("UNPLUGGED", ""))
    return prozent < AKKU_GRENZE and not laedt


# ── Baustein 1: WhatsApp-Bilder ────────────────────────────────────────────

_MUSTER_HOCH = re.compile(r"(?m)^hochgeladen ([\d.]+)")
_MUSTER_NEU = re.compile(r"(?m)^neu ([\d.]+)")
_MUSTER_FEHLER = re.compile(r"(?m)\bfehler ([\d.]+)")


def _ganz(treffer: Optional["re.Match[str]"]) -> Optional[int]:
    if treffer is None:
        return None
    ziffern = treffer.group(1).replace(".", "")
    return int(ziffern) if ziffern.isdigit() else None


def w1_auswerten(ausgabe: str) -> Dict[str, Any]:
    """Zahlen aus der W1-Ausgabe (``hochgeladen N``, ``neu N``, ``fehler N``, ``abgebrochen``)."""
    return {
        "hochgeladen": _ganz(_MUSTER_HOCH.search(ausgabe)),
        "neu": _ganz(_MUSTER_NEU.search(ausgabe)),
        "fehler": _ganz(_MUSTER_FEHLER.search(ausgabe)),
        "abgebrochen": "abgebrochen" in ausgabe,
    }


# Fester Zusatz statt W1-Rohausgabe: ein harter Abbruch (Zeitgrenze) kann die W1-Sperre
# oder eine halbe Manifestzeile hinterlassen; dann endet jeder Folgelauf mit Exit 3.
_W1_HINWEIS = " (W1-Sperre/Manifest prüfen)"


def baustein_wa_bilder(skript: str, schreiben: bool, akku_zu_niedrig: bool,
                       zeitgrenze: float) -> Ergebnis:
    name = "wa_bilder"
    if schreiben and akku_zu_niedrig:
        return Ergebnis(name, "uebersprungen", EXIT_OK,
                        "WhatsApp-Bilder: übersprungen (Akku niedrig)", {}, False)
    if not os.path.isfile(skript):
        return Ergebnis(name, "nicht_pruefbar", EXIT_NICHT_PRUEFBAR,
                        "WhatsApp-Bilder: Werkzeug nicht gefunden", {}, False)
    befehl = [sys.executable, "-B", skript] + (["--schreiben"] if schreiben else [])
    lauf: Optional["subprocess.CompletedProcess[str]"] = None
    zeit_ueberschritten = False
    start_fehler = False
    try:
        lauf = subprocess.run(befehl, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=zeitgrenze, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        zeit_ueberschritten = True
    except Exception:
        start_fehler = True
    if zeit_ueberschritten:
        return Ergebnis(name, "fehler", EXIT_FEHLER,
                        "WhatsApp-Bilder: Zeitgrenze überschritten" + _W1_HINWEIS, {}, False)
    if start_fehler or lauf is None:
        return Ergebnis(name, "nicht_pruefbar", EXIT_NICHT_PRUEFBAR,
                        "WhatsApp-Bilder: Start nicht möglich", {}, False)
    z = w1_auswerten(lauf.stdout or "")
    zahlen = {k: v for k, v in z.items() if isinstance(v, int) and not isinstance(v, bool)}
    code = lauf.returncode
    if code == 0:
        wert = z["hochgeladen"] if schreiben else z["neu"]
        if wert is None:
            return Ergebnis(name, "nicht_pruefbar", EXIT_NICHT_PRUEFBAR,
                            "WhatsApp-Bilder: Ausgabe nicht lesbar", zahlen, False)
        if schreiben:
            return Ergebnis(name, "ok", EXIT_OK,
                            f"WhatsApp-Bilder: {_zahl(wert)} hochgeladen", zahlen, True)
        return Ergebnis(name, "ok", EXIT_OK,
                        f"WhatsApp-Bilder (Trockenlauf): {_zahl(wert)} neu", zahlen, True)
    if code == EXIT_AUFRUF:
        return Ergebnis(name, "aufruf", EXIT_AUFRUF,
                        "WhatsApp-Bilder: Aufruf- oder Schutzfehler (Exit 2)", zahlen, False)
    if code == EXIT_NICHT_PRUEFBAR:
        return Ergebnis(name, "nicht_pruefbar", EXIT_NICHT_PRUEFBAR,
                        "WhatsApp-Bilder: Voraussetzung fehlt (Exit 3; W1-Sperre/Manifest prüfen)",
                        zahlen, False)
    hoch = _zahl(z["hochgeladen"] or 0)
    fehler = _zahl(z["fehler"] or 0)
    text = f"WhatsApp-Bilder: {hoch} hochgeladen, {fehler} Fehler"
    if z["abgebrochen"]:
        text += " (abgebrochen)"
    return Ergebnis(name, "fehler", EXIT_FEHLER, text, zahlen, False)


# ── Baustein 2: WhatsApp-Chats (Platzhalter) ───────────────────────────────

def baustein_wa_chats() -> Ergebnis:
    return Ergebnis("wa_chats", "nicht_eingerichtet", EXIT_OK,
                    "WhatsApp-Chats: nicht eingerichtet (W2 Teil B)", {}, True)


# ── Baustein 3: Kamera zaehlen (nur lesend) ────────────────────────────────

def _pcloud_lesen(methode: str, felder: Dict[str, Any]) -> Dict[str, Any]:
    """Genau eine lesende pCloud-Abfrage ueber den vorhandenen Weg (nie schreibend)."""
    if methode not in LESENDE_METHODEN:
        raise ValueError("nur lesende Methoden")
    zugang = gemeinsam.zugang_aufloesen()
    ug = gemeinsam.uebergabe_laden()
    return ug._api_lesen(methode, felder, token=zugang.token, host=zugang.host)


def _kamera_pfad(wert: Any) -> Optional[str]:
    """Der pCloud-Pfad oder ``None`` (unzulaessig: Crypto Folder, '..', Rueckstrich, '//')."""
    if not isinstance(wert, str):
        return None
    pfad = wert.strip()
    if not pfad.startswith("/") or len(pfad) < 2:
        return None
    if ".." in pfad or "\\" in pfad or "//" in pfad:
        return None
    if any("crypto" in teil.casefold() for teil in pfad.split("/")):
        return None
    return pfad


def baustein_kamera(einstellungen: Dict[str, Any], stand: Dict[str, Any]) -> Ergebnis:
    name = "kamera"
    roh = einstellungen.get("kamera_ordner")
    if not isinstance(roh, str) or not roh.strip():
        return Ergebnis(name, "nicht_eingerichtet", EXIT_OK, "Kamera: nicht eingerichtet", {}, True)
    pfad = _kamera_pfad(roh)
    if pfad is None:
        return Ergebnis(name, "aufruf", EXIT_AUFRUF, "Kamera: Ordner nicht zulässig", {}, False)
    daten: Any = None
    voraussetzung = False
    fehlerart: Optional[str] = None
    try:
        daten = _pcloud_lesen("listfolder", {"path": pfad})
    except gemeinsam.Voraussetzung:
        voraussetzung = True
    except Exception as problem:
        fehlerart = gemeinsam.fehlerart(problem)
    if voraussetzung:
        return Ergebnis(name, "nicht_pruefbar", EXIT_NICHT_PRUEFBAR,
                        "Kamera: Voraussetzung fehlt", {}, False)
    if fehlerart is not None:
        return Ergebnis(name, "fehler", EXIT_FEHLER,
                        f"Kamera: Zählung fehlgeschlagen ({fehlerart})", {}, False)
    meta = daten.get("metadata") if isinstance(daten, dict) else None
    inhalt = meta.get("contents") if isinstance(meta, dict) else None
    if not isinstance(inhalt, list):
        return Ergebnis(name, "fehler", EXIT_FEHLER,
                        "Kamera: Zählung fehlgeschlagen (antwort)", {}, False)
    anzahl = sum(1 for e in inhalt if isinstance(e, dict) and not e.get("isfolder"))
    vorher = stand.get("kamera_zahl")
    if isinstance(vorher, int) and not isinstance(vorher, bool) and vorher >= 0:
        neu = max(0, anzahl - vorher)
        text = f"Kamera: {_zahl(neu)} neue Dateien seit letztem Lauf"
        zahlen = {"dateien": anzahl, "neu": neu}
    else:
        text = f"Kamera: {_zahl(anzahl)} Dateien (Grundstand)"
        zahlen = {"dateien": anzahl}
    return Ergebnis(name, "ok", EXIT_OK, text, zahlen, True)


# ── Baustein 4: Gemini-Erinnerung ──────────────────────────────────────────

def baustein_gemini(einstellungen: Dict[str, Any]) -> Ergebnis:
    name = "gemini"
    faellig_text = "Gemini: Takeout-Export fällig (alle 2 Monate)"
    wert = einstellungen.get("gemini_letzter_export")
    letzter: Optional[datetime.date] = None
    if isinstance(wert, str):
        try:
            letzter = datetime.date.fromisoformat(wert.strip())
        except ValueError:
            letzter = None
    if letzter is None:
        return Ergebnis(name, "erinnerung", EXIT_OK, faellig_text, {}, True)
    tage = (_heute() - letzter).days
    if tage < 0 or tage > GEMINI_TAGE:
        return Ergebnis(name, "erinnerung", EXIT_OK, faellig_text, {}, True)
    return Ergebnis(name, "ok", EXIT_OK,
                    f"Gemini: ok (letzter Export vor {_zahl(tage)} Tagen)", {"tage": tage}, True)


# ── Ablauf ─────────────────────────────────────────────────────────────────

BAUSTEIN_LABEL = {"wa_bilder": "WhatsApp-Bilder", "wa_chats": "WhatsApp-Chats",
                  "kamera": "Kamera", "gemini": "Gemini"}


def _isoliert(name: str, funktion: Callable[[], Ergebnis]) -> Ergebnis:
    """Einen Baustein ausfuehren; jede Ausnahme wird zu einem Fehler mit fester Art."""
    art: Optional[str] = None
    ergebnis: Optional[Ergebnis] = None
    try:
        ergebnis = funktion()
    except Exception as problem:
        art = gemeinsam.fehlerart(problem)
    if ergebnis is not None:
        return ergebnis
    return Ergebnis(name, "fehler", EXIT_FEHLER,
                    f"{BAUSTEIN_LABEL[name]}: unerwarteter Fehler ({art})", {}, False)


def _argumente(argv: Optional[List[str]] = None):
    p = gemeinsam.LeiserParser(
        description="Tagesimport am Handy (WhatsApp-Bilder, Kamera zaehlen, Erinnerungen). "
                    "Standard ist aus; Schalter in tageslauf.json.")
    modus = p.add_mutually_exclusive_group(required=True)
    modus.add_argument("--wenn-faellig", action="store_true", dest="wenn_faellig",
                       help="nur laufen, wenn heute noch kein vollstaendiger Lauf war")
    modus.add_argument("--jetzt", action="store_true", help="jetzt laufen (ignoriert die Faelligkeit)")
    modus.add_argument("--trocken", action="store_true", help="zeigen, nichts schreiben")
    p.add_argument("--daten-ordner", default=None, dest="daten_ordner",
                   help=f"Datenordner (Standard {STANDARD_DATEN}, Umgebung {UMGEBUNG_DATEN})")
    p.add_argument("--log-ordner", default=None, dest="log_ordner",
                   help="Diagnose-Ordner fuer tageslauf.log (Standard <Download>/hermes_diag)")
    p.add_argument("--w1-skript", default=W1_SKRIPT, dest="w1_skript",
                   help="Pfad des WhatsApp-Bilder-Werkzeugs (nur fuer Tests)")
    p.add_argument("--w1-zeitgrenze", type=float, default=W1_ZEITGRENZE_S, dest="w1_zeitgrenze",
                   help="Zeitgrenze des WhatsApp-Bausteins in Sekunden (Standard 7200)")
    return p.parse_args(argv)


def _ausgeben(zeile: str) -> None:
    print(zeile)


def _einstellungen_lesen(pfad: str) -> Tuple[Dict[str, Any], bool]:
    """``(Einstellungen, lesbar)``. Fehlende Datei: Standard ``{"an": False}``."""
    status, daten = _json_lesen(pfad)
    if status == "fehlt":
        return {"an": False}, True
    if status == "ok" and isinstance(daten, dict):
        return daten, True
    return {"an": False}, False


def _stand_lesen(pfad: str) -> Dict[str, Any]:
    status, daten = _json_lesen(pfad)
    return daten if status == "ok" and isinstance(daten, dict) else {}


def _faellig(stand: Dict[str, Any]) -> bool:
    return stand.get("letzter_gesamtlauf") != _heute().isoformat()


def _lauf(args: Any) -> int:
    modus = "trocken" if args.trocken else ("jetzt" if args.jetzt else "wenn_faellig")
    schreibend = modus != "trocken"
    daten_ordner = os.path.expanduser(args.daten_ordner or os.environ.get(UMGEBUNG_DATEN)
                                      or STANDARD_DATEN)
    log_ordner = os.path.expanduser(args.log_ordner) if args.log_ordner else _log_ordner_standard()

    if _im_repo(daten_ordner) or _im_repo(log_ordner):
        print(MELDUNG_REPO, file=sys.stderr)
        return EXIT_AUFRUF

    einstellungen, lesbar = _einstellungen_lesen(os.path.join(daten_ordner, EINSTELLUNGEN_NAME))
    if einstellungen.get("an") is not True:
        _ausgeben("Tagesimport: aus" + ("" if lesbar else " (Einstellungen nicht lesbar)"))
        return EXIT_OK if lesbar else EXIT_NICHT_PRUEFBAR

    stand_pfad = os.path.join(daten_ordner, STAND_NAME)
    stand = _stand_lesen(stand_pfad)
    if modus == "wenn_faellig" and not _faellig(stand):
        _ausgeben("Tagesimport: heute schon erledigt")
        return EXIT_OK

    bericht_pfad = os.path.join(daten_ordner, BERICHT_NAME)
    sperre_pfad = os.path.join(daten_ordner, SPERRE_NAME)
    kennung: Optional[str] = None
    if schreibend:
        try:
            for ziel in (stand_pfad, bericht_pfad, sperre_pfad):
                if os.path.islink(ziel):
                    raise Schutzverstoss(MELDUNG_LINK)
            _schreibziel_pruefen(stand_pfad)
            _schreibziel_pruefen(bericht_pfad)
        except Schutzverstoss as fehler:
            print(str(fehler), file=sys.stderr)
            return EXIT_AUFRUF
        try:
            os.makedirs(daten_ordner, exist_ok=True)
        except OSError:
            _ausgeben("Tagesimport: Datenordner nicht anlegbar")
            return EXIT_NICHT_PRUEFBAR
        status, kennung = _sperre_nehmen(sperre_pfad)
        if status == "laeuft":
            _ausgeben("Tagesimport: läuft bereits")
            return EXIT_OK
        if status == "unklar":
            _ausgeben("Tagesimport: Sperre unklar, nicht gestartet")
            return EXIT_NICHT_PRUEFBAR
        if status != "ok":
            _ausgeben("Tagesimport: Sperre nicht anlegbar, nicht gestartet")
            return EXIT_NICHT_PRUEFBAR
        stand = _stand_lesen(stand_pfad)                 # nach der Sperre noch einmal pruefen
        if modus == "wenn_faellig" and not _faellig(stand):
            _sperre_freigeben(sperre_pfad, kennung)
            _ausgeben("Tagesimport: heute schon erledigt")
            return EXIT_OK

    try:
        return _bausteine_und_bericht(args, modus, schreibend, einstellungen, stand,
                                      stand_pfad, bericht_pfad, log_ordner)
    finally:
        if schreibend:
            _sperre_freigeben(sperre_pfad, kennung)


def _bausteine_und_bericht(args: Any, modus: str, schreibend: bool, einstellungen: Dict[str, Any],
                           stand: Dict[str, Any], stand_pfad: str, bericht_pfad: str,
                           log_ordner: str) -> int:
    modus_text = {"trocken": "trocken", "jetzt": "jetzt", "wenn_faellig": "fällig"}[modus]
    zeilen: List[str] = [f"Tagesimport: Start ({modus_text})"]
    akku = akku_niedrig(_akku_ausgabe()) if schreibend else False

    ergebnisse = [
        _isoliert("wa_bilder", lambda: baustein_wa_bilder(
            args.w1_skript, schreibend, akku, args.w1_zeitgrenze)),
        _isoliert("wa_chats", baustein_wa_chats),
        _isoliert("kamera", lambda: baustein_kamera(einstellungen, stand)),
        _isoliert("gemini", lambda: baustein_gemini(einstellungen)),
    ]
    zeilen += [e.text for e in ergebnisse]
    rc = schlechtester_exit(ergebnisse)
    komplett = rc == EXIT_OK and all(e.vollstaendig for e in ergebnisse)
    fortgeschrieben = False

    if schreibend:
        heute = _heute().isoformat()
        try:
            if komplett:
                neu = dict(stand)
                neu["version"] = 1
                neu["letzter_gesamtlauf"] = heute
                bausteine = dict(neu["bausteine"]) if isinstance(neu.get("bausteine"), dict) else {}
                for e in ergebnisse:
                    if e.status == "ok" and e.name in ("wa_bilder", "kamera"):
                        bausteine[e.name] = heute
                neu["bausteine"] = bausteine
                kamera = next(e for e in ergebnisse if e.name == "kamera")
                if kamera.status == "ok":
                    neu["kamera_zahl"] = kamera.zahlen["dateien"]
                _atomar_schreiben(stand_pfad, json.dumps(neu, ensure_ascii=False, indent=2) + "\n")
                fortgeschrieben = True
        except Schutzverstoss as fehler:
            print(str(fehler), file=sys.stderr)
            rc = max(rc, EXIT_AUFRUF)
        except OSError:
            zeilen.append("Tagesimport: Stand nicht speicherbar")
            rc = max(rc, EXIT_FEHLER)
        zeilen.append(f"Tagesimport: fertig (Exit {rc}, Stand "
                      + ("fortgeschrieben)" if fortgeschrieben else "nicht fortgeschrieben)"))
        bericht = {
            "version": 1, "zeit": _jetzt_iso(), "datum": heute, "modus": modus,
            "exit": rc, "stand_fortgeschrieben": fortgeschrieben,
            "bausteine": [{"name": e.name, "status": e.status, "exit": e.exit,
                           "text": e.text, "zahlen": e.zahlen} for e in ergebnisse],
        }
        try:
            _atomar_schreiben(bericht_pfad, json.dumps(bericht, ensure_ascii=False, indent=2) + "\n")
        except Schutzverstoss as fehler:
            print(str(fehler), file=sys.stderr)
            rc = max(rc, EXIT_AUFRUF)
        except OSError:
            zeilen.append("Tagesimport: Bericht nicht speicherbar")
            rc = max(rc, EXIT_FEHLER)
        _log_schreiben(log_ordner, zeilen)
    else:
        zeilen.append(f"Tagesimport: fertig (Trockenlauf, Exit {rc}, nichts geschrieben)")

    for zeile in zeilen:
        _ausgeben(zeile)
    return rc


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _argumente(argv)
    except SystemExit as ende:
        return int(ende.code or 0)
    try:
        sys.stdout.reconfigure(errors="replace")           # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    try:
        return _lauf(args)
    except Exception as fehler:                            # letzte Absicherung: nur die Fehlerart
        print(f"Fehler: unerwarteter Abbruch ({gemeinsam.fehlerart(fehler)})", file=sys.stderr)
        return EXIT_FEHLER


if __name__ == "__main__":
    raise SystemExit(main())
