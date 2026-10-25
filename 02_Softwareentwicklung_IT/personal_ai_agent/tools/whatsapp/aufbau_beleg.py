"""W2 Teil A1: Strukturbeleg einer entschluesselten WhatsApp-Datenbank (22.10.2026).

Plan: ``.hermes/plans/2026-10-22_whatsapp-w2.md`` (Fassung 16, Teil A1).

Handpruefung am PC: ``python -B tools\\whatsapp\\aufbau_beleg.py <msgstore.db>``. Das Werkzeug
liest die Datenbank **nur schreibgeschuetzt** (URI ``mode=ro&immutable=1``, danach
``query_only=ON`` und ``temp_store=MEMORY``) und gibt **nur feste Pflichtspaltennamen und
Zahlen** aus: nie Werte, Namen, Nummern, Texte, Pfade oder Dateinamen. Spalten, die nicht zu
den fest vorgegebenen Pflichtspalten gehoeren, werden nur gezaehlt (ein Spaltenname koennte
Klartext enthalten).

Vor jeder Tabellenabfrage wird der Speicherbetrieb verbindlich geprueft: ``PRAGMA temp_store``
muss 2 liefern und ``PRAGMA compile_options`` darf nicht ``TEMP_STORE=0`` enthalten, sonst
Exit 3 "SQLite dieses Rechners kann nicht nur im Speicher arbeiten" ohne Tabellenabfrage.

Ausgabe: je Tabelle (message, chat, message_media, jid) Zeilenzahl und Anzahl weiterer
Spalten; je Pflichtspalte "vorhanden:"/"fehlt:"; je Pflichtfeld die Typverteilung
(int/str/bytes/NULL/sonst); bei Kennungen die Anzahl <= 0 und (bei eindeutigen Kennungen) die
Anzahl doppelter Werte; Zeitstempel (Stellenzahl 10/13/sonst, Anzahl ausserhalb 2009 bis
heute + 1 Tag in Millisekunden); from_me (0/1/sonst); file_path-Musterklassen und Klassen der
Unterordner unter ``Media/WhatsApp Images/``; file_hash-Klassen; Verknuepfungs-Zaehler.

Exit: 0 = ok (auch bei fehlender Tabelle/Spalte: dann steht eine "fehlt:"-Zeile da);
1 = Datenbank nicht lesbar; 2 = Aufruffehler; 3 = Voraussetzung fehlt (keine regulaere Datei,
Speicherbetrieb nicht moeglich).
"""
import sys
sys.dont_write_bytecode = True

import argparse
import base64
import os
import sqlite3
import stat as stat_modul
import time
import urllib.parse
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple

EXIT_OK = 0
EXIT_FEHLER = 1
EXIT_AUFRUF = 2
EXIT_VORAUSSETZUNG = 3

M_KEINE_DATEI = "Datenbankdatei nicht lesbar oder keine regulaere Datei"
M_SPEICHER = "SQLite dieses Rechners kann nicht nur im Speicher arbeiten"
M_DB = "Datenbank nicht lesbar oder beschaedigt"
M_AUFRUF = "Aufruf ungueltig (--help zeigt die Optionen)."

# Fest vorgegebene Pflichtspalten (W2b.4) — nur diese Namen werden je ausgegeben.
TABELLEN: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("message", ("_id", "chat_row_id", "timestamp", "from_me", "sender_jid_row_id")),
    ("chat", ("_id",)),
    ("message_media", ("message_row_id", "chat_row_id", "file_path", "file_hash", "file_size")),
    ("jid", ("_id",)),
)
# (Tabelle, Spalte, eindeutig?) — Kennungen: Anzahl <= 0, bei eindeutigen auch Doppelte
KENNUNGEN: Tuple[Tuple[str, str, bool], ...] = (
    ("message", "_id", True),
    ("message", "chat_row_id", False),
    ("message", "sender_jid_row_id", False),
    ("chat", "_id", True),
    ("jid", "_id", True),
    ("message_media", "message_row_id", True),
    ("message_media", "chat_row_id", False),
)
ZEIT_UNTEN_MS = 1230768000000          # 01.01.2009 00:00 UTC in Millisekunden
PRAEFIX_MEDIA = "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/"
PRAEFIX_ALT = "/storage/emulated/0/WhatsApp/"
IMAGES = "Media/WhatsApp Images/"
TYPEN = ("int", "str", "bytes", "NULL", "sonst")


# ── Duenne Huellen (fuer Tests austauschbar) ───────────────────────────────

def _ist_link(pfad: str) -> bool:
    return os.path.islink(pfad)


def _lstat(pfad: str) -> Any:
    return os.lstat(pfad)


def _jetzt() -> float:
    return time.time()


def _verbinden(ziel: str, **kw: Any) -> Any:
    return sqlite3.connect(ziel, **kw)


class Abbruch(Exception):
    """Ein Lauf endet mit ``code`` und einer festen Zeile (nie mit Pfad oder Inhalt)."""

    def __init__(self, code: int, meldung: str) -> None:
        super().__init__(meldung)
        self.code = code
        self.meldung = meldung


# ── Oeffnen: nur lesend, nur im Speicher ───────────────────────────────────

def datei_pruefen(pfad: str) -> None:
    """Der Pfad muss eine regulaere Datei sein (kein Link, kein Ordner, vorhanden)."""
    ok = False
    try:
        ok = (not _ist_link(pfad)) and stat_modul.S_ISREG(_lstat(pfad).st_mode)
    except Exception:
        ok = False
    if not ok:
        raise Abbruch(EXIT_VORAUSSETZUNG, M_KEINE_DATEI)


def _uri(abs_pfad: str) -> str:
    teile = abs_pfad.split("\\")
    pfad = "/".join(teile)
    if not pfad.startswith("/"):
        pfad = "/" + pfad                         # Windows: file:/C:/...
    return "file:" + urllib.parse.quote(pfad) + "?mode=ro&immutable=1"


def speicherbetrieb(con: Any) -> Tuple[bool, bool]:
    """``(ok, TEMP_STORE=0 gesetzt)`` — nur PRAGMAs, keine Tabellendaten."""
    zeile = con.execute("PRAGMA temp_store").fetchone()
    optionen = con.execute("PRAGMA compile_options").fetchall()
    null_gesetzt = any(str(z[0]).upper() == "TEMP_STORE=0" for z in optionen)
    ok = zeile is not None and zeile[0] == 2 and not null_gesetzt
    return ok, null_gesetzt


def verbindung_oeffnen(pfad: str) -> Any:
    """Schreibgeschuetzt oeffnen, Speicherbetrieb erzwingen und pruefen (sonst Abbruch)."""
    con: Any = None
    fehlgeschlagen = False
    try:
        con = _verbinden(_uri(os.path.abspath(pfad)), uri=True)
        con.execute("PRAGMA query_only=ON")
        con.execute("PRAGMA temp_store=MEMORY")
        ok, _null = speicherbetrieb(con)
    except Exception:
        fehlgeschlagen = True
        ok = False
    if fehlgeschlagen:
        raise Abbruch(EXIT_FEHLER, M_DB)
    if not ok:
        con.close()
        raise Abbruch(EXIT_VORAUSSETZUNG, M_SPEICHER)
    return con


# ── Klassifizierung (rein, ohne Ausgabe von Werten) ────────────────────────

def typ_von(wert: Any) -> str:
    if wert is None:
        return "NULL"
    art = type(wert)
    if art is int:
        return "int"
    if art is str:
        return "str"
    if art is bytes:
        return "bytes"
    return "sonst"


def pfad_klasse(wert: Any) -> Tuple[str, Optional[str]]:
    """``(Klasse, Rest ab Media/)`` fuer ``file_path``."""
    if wert is None or wert == "":
        return "leer", None
    if type(wert) is not str:
        return "sonst", None
    if wert.startswith(PRAEFIX_MEDIA):
        return "absolut_media", wert[len(PRAEFIX_MEDIA):]
    if wert.startswith(PRAEFIX_ALT):
        return "absolut_alt", wert[len(PRAEFIX_ALT):]
    if wert.startswith("Media/"):
        return "relativ", wert
    return "sonst", None


def unterordner_klasse(rest: str) -> str:
    """Klasse des Unterordners direkt unter ``Media/WhatsApp Images/``."""
    if not rest.startswith(IMAGES):
        return "ohne_Images"
    segmente = rest[len(IMAGES):].split("/")
    if len(segmente) == 1:
        return "Ebene-0" if segmente[0] else "sonst"
    erstes = segmente[0].casefold()
    if erstes == "sent":
        return "Sent"
    if erstes == "private":
        return "Private"
    return "sonst"


def hash_klasse(wert: Any) -> str:
    if wert is None or wert == "":
        return "leer"
    if type(wert) is not str:
        return "sonst"
    roh: Optional[bytes] = None
    try:
        roh = base64.b64decode(wert, validate=True)
    except Exception:
        roh = None
    return "base64_32" if roh is not None and len(roh) == 32 else "sonst"


def _ganz(wert: Any) -> bool:
    return type(wert) is int


# ── Der Bericht ────────────────────────────────────────────────────────────

def _zeile(name: str, werte: List[Tuple[str, Any]]) -> str:
    return name + ": " + " · ".join(f"{k} {v}" for k, v in werte)


def bericht(con: Any) -> List[str]:
    """Alle Ausgabezeilen — nur feste Namen und Zahlen."""
    zeilen: List[str] = ["Strukturbeleg (nur lesend, nur feste Namen und Zahlen)",
                         f"SQLite-Version: {sqlite3.sqlite_version}"]
    _ok, null_gesetzt = speicherbetrieb(con)
    zeilen.append(f"Speicherbetrieb: temp_store 2 · TEMP_STORE=0 gesetzt: "
                  f"{'ja' if null_gesetzt else 'nein'}")

    vorhanden: Dict[Tuple[str, str], bool] = {}
    for tabelle, pflicht in TABELLEN:
        infos = con.execute(f"PRAGMA table_info({tabelle})").fetchall()
        namen = {str(z[1]).casefold() for z in infos}
        gefunden = 0
        for spalte in pflicht:
            da = spalte.casefold() in namen
            vorhanden[(tabelle, spalte)] = da
            gefunden += 1 if da else 0
        if not infos:
            zeilen.append(f"Tabelle {tabelle}: Tabelle fehlt")
        else:
            anzahl = con.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]
            zeilen.append(_zeile(f"Tabelle {tabelle}", [
                ("Zeilen", anzahl), ("weitere Spalten", len(infos) - gefunden)]))
        for spalte in pflicht:
            zeilen.append(("vorhanden: " if vorhanden[(tabelle, spalte)] else "fehlt: ")
                          + f"{tabelle}.{spalte}")

    def da(tabelle: str, *spalten: str) -> bool:
        return all(vorhanden[(tabelle, s)] for s in spalten)

    typen: Dict[Tuple[str, str], Counter] = {}
    klein: Counter = Counter()
    gesehen: Dict[Tuple[str, str], Set[Any]] = {}
    doppelt: Dict[Tuple[str, str], Set[Any]] = {}
    eindeutig = {(t, s) for t, s, e in KENNUNGEN if e}
    kennungs_felder = {(t, s) for t, s, _e in KENNUNGEN}
    zeit: Counter = Counter()
    von_mir: Counter = Counter()
    pfade: Counter = Counter()
    unterordner: Counter = Counter()
    hashes: Counter = Counter()
    verkn: Counter = Counter()
    chat_ids: Set[Any] = set()
    jid_ids: Set[Any] = set()
    nachrichten: Dict[Any, Tuple[Any, Any, Any]] = {}
    obere_ms = (int(_jetzt()) + 86400) * 1000

    def lesen(tabelle: str, pflicht: Tuple[str, ...]):
        """Roh lesen: eine Abfrage ohne Join, nur die vorhandenen Pflichtspalten."""
        spalten = [s for s in pflicht if vorhanden[(tabelle, s)]]
        if not spalten:
            return spalten, iter(())
        return spalten, con.execute(f"SELECT {', '.join(spalten)} FROM {tabelle}")

    def zaehlen(tabelle: str, spalte: str, wert: Any) -> None:
        typen.setdefault((tabelle, spalte), Counter())[typ_von(wert)] += 1
        if (tabelle, spalte) in kennungs_felder:
            if _ganz(wert):
                if wert <= 0:
                    klein[(tabelle, spalte)] += 1
                if (tabelle, spalte) in eindeutig:
                    schon = gesehen.setdefault((tabelle, spalte), set())
                    if wert in schon:
                        doppelt.setdefault((tabelle, spalte), set()).add(wert)
                    schon.add(wert)

    pflicht_von = dict(TABELLEN)
    for tabelle in ("chat", "jid", "message", "message_media"):
        spalten, zeilen_roh = lesen(tabelle, pflicht_von[tabelle])
        for roh in zeilen_roh:
            reihe = dict(zip(spalten, roh))
            for spalte, wert in reihe.items():
                zaehlen(tabelle, spalte, wert)
            if tabelle == "chat" and _ganz(reihe.get("_id")):
                chat_ids.add(reihe["_id"])
            if tabelle == "jid" and _ganz(reihe.get("_id")):
                jid_ids.add(reihe["_id"])
            if tabelle == "message":
                stempel = reihe.get("timestamp")
                if "timestamp" in reihe:
                    if _ganz(stempel) and stempel > 0 and len(str(stempel)) in (10, 13):
                        zeit[f"{len(str(stempel))}_Stellen"] += 1
                    else:
                        zeit["sonst"] += 1
                    if _ganz(stempel) and not ZEIT_UNTEN_MS <= stempel <= obere_ms:
                        zeit["ausserhalb"] += 1
                if "from_me" in reihe:
                    wert = reihe["from_me"]
                    von_mir[str(wert) if _ganz(wert) and wert in (0, 1) else "sonst"] += 1
                if _ganz(reihe.get("_id")) and reihe["_id"] not in nachrichten:
                    nachrichten[reihe["_id"]] = (reihe.get("chat_row_id"), reihe.get("from_me"),
                                                 reihe.get("sender_jid_row_id"))
            if tabelle == "message_media":
                if "file_path" in reihe:
                    klasse, rest = pfad_klasse(reihe["file_path"])
                    pfade[klasse] += 1
                    if rest is not None:
                        unterordner[unterordner_klasse(rest)] += 1
                if "file_hash" in reihe:
                    hashes[hash_klasse(reihe["file_hash"])] += 1
                if da("message", "_id", "chat_row_id", "from_me", "sender_jid_row_id") \
                        and da("chat", "_id") and da("jid", "_id") \
                        and da("message_media", "message_row_id", "chat_row_id"):
                    kennung = reihe.get("message_row_id")
                    treffer = nachrichten.get(kennung) if _ganz(kennung) else None
                    if treffer is None:
                        verkn["ohne_message"] += 1
                        continue
                    chat_msg, mir, absender = treffer
                    if not (_ganz(reihe.get("chat_row_id")) and _ganz(chat_msg)
                            and reihe["chat_row_id"] == chat_msg):
                        verkn["chat_abweichend"] += 1
                    if _ganz(chat_msg) and chat_msg not in chat_ids:
                        verkn["chat_fehlt"] += 1
                    if _ganz(mir) and mir == 0 and _ganz(absender) and absender > 0 \
                            and absender not in jid_ids:
                        verkn["jid_fehlt"] += 1

    for tabelle, pflicht in TABELLEN:
        for spalte in pflicht:
            if vorhanden[(tabelle, spalte)]:
                z = typen.get((tabelle, spalte), Counter())
                zeilen.append(_zeile(f"Typen {tabelle}.{spalte}", [(t, z[t]) for t in TYPEN]))
    for tabelle, spalte, ist_eindeutig in KENNUNGEN:
        if vorhanden[(tabelle, spalte)]:
            werte: List[Tuple[str, Any]] = [("kleiner_gleich_0", klein[(tabelle, spalte)])]
            if ist_eindeutig:
                werte.append(("doppelt", len(doppelt.get((tabelle, spalte), set()))))
            zeilen.append(_zeile(f"Kennungen {tabelle}.{spalte}", werte))
    if da("message", "timestamp"):
        zeilen.append(_zeile("Zeit message.timestamp", [
            ("10_Stellen", zeit["10_Stellen"]), ("13_Stellen", zeit["13_Stellen"]),
            ("sonst", zeit["sonst"]), ("ausserhalb", zeit["ausserhalb"])]))
    if da("message", "from_me"):
        zeilen.append(_zeile("from_me", [("0", von_mir["0"]), ("1", von_mir["1"]),
                                         ("sonst", von_mir["sonst"])]))
    if da("message_media", "file_path"):
        zeilen.append(_zeile("file_path", [(k, pfade[k]) for k in (
            "absolut_media", "absolut_alt", "relativ", "leer", "sonst")]))
        zeilen.append(_zeile("Images_Unterordner", [(k, unterordner[k]) for k in (
            "Ebene-0", "Sent", "Private", "sonst", "ohne_Images")]))
    if da("message_media", "file_hash"):
        zeilen.append(_zeile("file_hash", [(k, hashes[k]) for k in (
            "leer", "base64_32", "sonst")]))
    if da("message", "_id", "chat_row_id", "from_me", "sender_jid_row_id") and da("chat", "_id") \
            and da("jid", "_id") and da("message_media", "message_row_id", "chat_row_id"):
        zeilen.append(_zeile("Verknuepfung", [(k, verkn[k]) for k in (
            "ohne_message", "chat_abweichend", "chat_fehlt", "jid_fehlt")]))
    return zeilen


# ── Aufruf ─────────────────────────────────────────────────────────────────

class LeiserParser(argparse.ArgumentParser):
    """``argparse`` ohne Echo der falschen Eingabe (kann ein Pfad oder Name sein)."""

    def error(self, message: str) -> None:        # type: ignore[override]
        print(M_AUFRUF, file=sys.stderr)
        raise SystemExit(EXIT_AUFRUF)


def _argumente(argv: Optional[List[str]]) -> Any:
    p = LeiserParser(description="Strukturbeleg einer entschluesselten WhatsApp-Datenbank "
                                 "(nur lesend, nur feste Namen und Zahlen).")
    p.add_argument("datenbank", help="Pfad zur entschluesselten msgstore.db")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _argumente(argv)
    except SystemExit as ende:
        return int(ende.code or 0)
    con: Any = None
    zeilen: List[str] = []
    fehlgeschlagen = False
    try:
        datei_pruefen(args.datenbank)
        con = verbindung_oeffnen(args.datenbank)
    except Abbruch as ende:
        print(ende.meldung, file=sys.stderr)
        return ende.code
    try:
        zeilen = bericht(con)
    except Exception:
        fehlgeschlagen = True
    try:
        con.close()
    except Exception:
        pass
    if fehlgeschlagen:
        print(M_DB, file=sys.stderr)
        return EXIT_FEHLER
    for zeile in zeilen:
        print(zeile)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
