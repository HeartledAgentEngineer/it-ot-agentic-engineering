"""W2a: Vorpruefung der WhatsApp-Sicherung und Speicher-Messprobe (22.10.2026).

Plan: ``.hermes/plans/2026-10-22_whatsapp-w2.md`` (Fassung 16, Teil A, Schritt W2a).

Laeuft am Handy in Termux. **Nur lesend, nur feste Texte und Zahlen.** Das Werkzeug
oeffnet die Sicherung nie (nur ``stat``), entschluesselt nichts und gibt den Schluessel
nie aus. Es ist Teil A: Die Bibliothek ``wa_crypt_tools`` wird nur gemeldet (per
``importlib.util.find_spec``, ohne sie zu laden) und zaehlt erst mit ``--fuer-teil-b``.

Normalbetrieb prueft (jede fehlende Voraussetzung eine feste Zeile auf stderr, Exit 3):
    * Python 3.11 oder neuer,
    * Sicherungsordner lesbar; ``msgstore*.crypt15``/``.crypt14`` werden gezaehlt;
      ``msgstore.db.crypt15`` vorhanden (regulaere Datei), Groesse, Alter in Stunden,
      Groesse hoechstens ``--max-mib``,
    * Schluesseldatei: vorhanden, geschuetzt (kein Link, ``st_nlink`` 1, Besitzer =
      aktueller Nutzer, Rechte genau 600, nicht im Repo) und Form 64 Hex-Zeichen.

``--messprobe`` ist unabhaengig von Sicherung, Schluessel und Bibliothek (Voraussetzung nur
Python 3.11 und ``resource``): eine erfundene SQLite-Datenbank wachsender Groesse wird im
Speicher gebaut, gepackt, entpackt und per ``deserialize`` geoeffnet; je Stufe ok/abgebrochen
und der Hoechststand aus ``resource.getrusage``. Einzige Schreibzugriffe: das Anlegen von
``<Arbeitsordner>/whatsapp/`` und ``<Arbeitsordner>/whatsapp/messprobe_leer/`` (je einmal
``os.mkdir`` mit 0o700, nur wenn sie fehlen). Der Probeordner ist ``SQLITE_TMPDIR`` und
``TMPDIR`` der Probe und muss danach leer sein; es wird nie etwas geloescht.

Exit: 0 = ok; 1 = Fehler (zum Beispiel keine Messstufe erfolgreich); 2 = Aufruf- oder
Schutzfehler (Option, Link, Datei statt Ordner, Ordner im Repo); 3 = Voraussetzung fehlt.

Aufruf (am Handy, im Projektordner ``personal_ai_agent``):
    python -B tools/handy/whatsapp_sicherung_pruefen.py
    python -B tools/handy/whatsapp_sicherung_pruefen.py --messprobe
"""
import sys
sys.dont_write_bytecode = True

import argparse
import importlib
import importlib.util
import os
import re
import sqlite3
import stat as stat_modul
import time
import zlib
from typing import Any, Dict, List, Optional, Tuple

EXIT_OK = 0
EXIT_FEHLER = 1
EXIT_AUFRUF = 2
EXIT_VORAUSSETZUNG = 3

STANDARD_DATENBANKORDNER = "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases"
STANDARD_SCHLUESSEL = "~/.config/agent/wa_sicherung.key"
STANDARD_ARBEITSORDNER = "~/foto_sortierung"
SICHERUNG_NAME = "msgstore.db.crypt15"
STANDARD_MAX_MIB = 512
STANDARD_STUFEN = "64,256,512,1024"
MAX_STUFEN = 8
MAX_STUFE_MIB = 4096
MIB = 1024 * 1024
BIBLIOTHEK = "wa_crypt_tools"

M_KEIN_ZUGRIFF = "kein Zugriff auf die WhatsApp-Sicherung (termux-setup-storage)"
M_NUR_CRYPT14 = ("Sicherung ohne Ende-zu-Ende-Schluessel - in WhatsApp die "
                 "Ende-zu-Ende-Sicherung einschalten")
M_KEINE = "keine WhatsApp-Sicherung gefunden"
M_AKTUELL_FEHLT = "msgstore.db.crypt15 fehlt"
M_GROESSE = "Sicherung ist groesser als die Grenze (--max-mib)"
M_SCHL_FEHLT = "Schluesseldatei fehlt"
M_SCHL_SCHUTZ = ("Schluesseldatei nicht geschuetzt (kein Link, ein Name, Besitzer, "
                 "Rechte 600, nicht im Repo)")
M_SCHL_FORM = "Schluesseldatei hat nicht die Form 64 Hex-Zeichen"
M_SCHL_LESEN = "Schluesseldatei nicht lesbar"
M_PYTHON = "Python 3.11 oder neuer noetig"
M_BIBLIOTHEK = "Bibliothek wa_crypt_tools fehlt (noetig mit --fuer-teil-b)"
M_RESOURCE = "Python-Modul resource fehlt (nur unter Linux/Termux vorhanden)"
M_ARBEITSORDNER = "Arbeitsordner ~/foto_sortierung fehlt"
M_ORDNER_SCHUTZ = "Ordner nicht erlaubt (Link, kein Ordner oder im Repo)"
M_ORDNER_ANLEGEN = "Probeordner konnte nicht angelegt werden"
M_PROBE_NICHT_LEER = "Probeordner nicht leer - Messprobe nicht gestartet"
M_ZWISCHEN = "SQLite legt Zwischendateien an"
M_TMPDIR = "moeglicherweise Zwischendatei ausserhalb des Probeordners"
M_TMPDIR_PRUEFEN = "TMPDIR nicht pruefbar"
M_PROBE_PRUEFEN = "Probeordner nicht pruefbar"
M_SPEICHER = "SQLite dieses Geraets kann nicht nur im Speicher arbeiten"
M_KEINE_STUFE = "Messprobe: keine Stufe erfolgreich"
M_STUFEN = "Aufruf ungueltig: --stufen (aufsteigende ganze Zahlen 1 bis 4096, hoechstens 8)"
M_KOMBINATION = "Aufruf ungueltig: --messprobe gilt nicht zusammen mit --fuer-teil-b."
M_AUFRUF = "Aufruf ungueltig (--help zeigt die Optionen)."

_FORM = re.compile(rb"[0-9a-fA-F]{64}(\r?\n)?")


class Abbruch(Exception):
    """Ein Lauf endet mit ``code`` und einer festen Zeile (nie mit Pfad oder Inhalt)."""

    def __init__(self, code: int, meldung: str) -> None:
        super().__init__(meldung)
        self.code = code
        self.meldung = meldung


# ── Duenne Huellen (fuer Tests austauschbar) ───────────────────────────────

def _lstat(pfad: str) -> Any:
    return os.lstat(pfad)


def _ist_link(pfad: str) -> bool:
    return os.path.islink(pfad)


def _realpath(pfad: str) -> str:
    return os.path.realpath(pfad)


def _aktueller_nutzer() -> Optional[int]:
    getuid = getattr(os, "getuid", None)
    return int(getuid()) if getuid is not None else None


def _python_version() -> Tuple[int, int]:
    return (sys.version_info[0], sys.version_info[1])


def _jetzt() -> float:
    return time.time()


def _verbinden(ziel: str, **kw: Any) -> Any:
    return sqlite3.connect(ziel, **kw)


# ── Pfadschutz ─────────────────────────────────────────────────────────────

def _im_repo_einer(pfad: str, ordner_selbst: bool = False) -> bool:
    """``.git`` (Ordner oder Datei) im Elternbaum des Pfads; bei ``ordner_selbst`` auch im Pfad selbst."""
    kandidat = pfad if os.path.isabs(pfad) else os.path.join(os.getcwd(), pfad)
    ordner = kandidat if ordner_selbst else os.path.dirname(kandidat)
    while True:
        if os.path.exists(os.path.join(ordner, ".git")):
            return True
        eltern = os.path.dirname(ordner)
        if eltern == ordner:
            return False
        ordner = eltern


def im_repo(pfad: str, ordner_selbst: bool = False) -> Optional[bool]:
    """Liegt der angegebene ODER der aufgeloeste Pfad in einem Git-Repo? ``None``: nicht pruefbar.

    ``ordner_selbst``: der Pfad ist ein Ordner; dann ist er auch selbst die Repo-Wurzel, wenn er
    ``.git`` enthaelt (bei Dateien zaehlt nur der Elternbaum).
    """
    ergebnis: Optional[bool] = None
    try:
        ergebnis = bool(_im_repo_einer(pfad, ordner_selbst)
                        or _im_repo_einer(_realpath(pfad), ordner_selbst))
    except Exception:
        ergebnis = None
    return ergebnis


def _link_sicher(pfad: str) -> Optional[bool]:
    ergebnis: Optional[bool] = None
    try:
        ergebnis = bool(_ist_link(pfad))
    except Exception:
        ergebnis = None
    return ergebnis


def ordner_status(pfad: str) -> str:
    """Ordnerregel: ``ok`` | ``fehlt`` | ``link`` | ``kein_ordner`` | ``repo`` | ``unpruefbar``.

    Echter Ordner (``lstat`` + ``S_ISDIR``), kein symbolischer Link, nicht im Repo (angegebener
    und aufgeloester Pfad). Keine Hartlink-Pruefung: Ordner haben immer mehrere Links.
    """
    link = _link_sicher(pfad)
    if link is None:
        return "unpruefbar"
    if link:
        return "link"
    vorhanden = True
    unlesbar = False
    st = None
    try:
        st = _lstat(pfad)
    except FileNotFoundError:
        vorhanden = False
    except Exception:
        unlesbar = True
    if unlesbar:
        return "unpruefbar"
    if vorhanden and not stat_modul.S_ISDIR(st.st_mode):
        return "kein_ordner"
    repo = im_repo(pfad, ordner_selbst=True)
    if repo is None:
        return "unpruefbar"
    if repo:
        return "repo"
    return "ok" if vorhanden else "fehlt"


def _ordner_anlegen(pfad: str) -> None:
    """Die einzige Schreibstelle des Werkzeugs: ein Ordner mit 0o700."""
    fehlgeschlagen = False
    try:
        os.mkdir(pfad, 0o700)
    except Exception:
        fehlgeschlagen = True
    if fehlgeschlagen or ordner_status(pfad) != "ok":
        raise Abbruch(EXIT_FEHLER, M_ORDNER_ANLEGEN)


# ── Normalbetrieb ──────────────────────────────────────────────────────────

def _ordner_lesen(pfad: str) -> Optional[List[str]]:
    ergebnis: Optional[List[str]] = None
    try:
        if os.path.isdir(pfad) and os.access(pfad, os.R_OK | os.X_OK):
            ergebnis = list(os.listdir(pfad))
    except Exception:
        ergebnis = None
    return ergebnis


def _sicherung_info(pfad: str) -> Optional[Any]:
    """``stat`` der Sicherung, nur wenn sie eine regulaere Datei (kein Link) ist."""
    st = None
    try:
        st = _lstat(pfad)
    except Exception:
        st = None
    if st is None or not stat_modul.S_ISREG(st.st_mode):
        return None
    return st


def _schluessel_pruefen(pfad: str) -> Dict[str, Any]:
    """Schluesseldatei: vorhanden / Schutz / Form. Der Inhalt wird gelesen und verworfen."""
    marke: Dict[str, Any] = {"vorhanden": False, "schutz": False, "form": None,
                             "lesefehler": False}
    st = None
    fehlt = False
    unlesbar = False
    try:
        st = _lstat(pfad)
    except FileNotFoundError:
        fehlt = True
    except Exception:
        unlesbar = True
    if fehlt:
        return marke
    marke["vorhanden"] = True
    if unlesbar:
        return marke
    link = _link_sicher(pfad)
    repo = im_repo(pfad)
    nutzer: Optional[int] = None
    try:
        nutzer = _aktueller_nutzer()
    except Exception:
        nutzer = None
    marke["schutz"] = bool(
        link is False and repo is False and nutzer is not None
        and stat_modul.S_ISREG(st.st_mode) and st.st_nlink == 1
        and st.st_uid == nutzer and stat_modul.S_IMODE(st.st_mode) == 0o600)
    if not marke["schutz"]:
        return marke
    daten: Optional[bytes] = None
    try:
        with open(pfad, "rb") as datei:
            daten = datei.read(70)
    except Exception:
        daten = None
    if daten is None:
        marke["lesefehler"] = True
        return marke
    marke["form"] = bool(_FORM.fullmatch(daten))
    return marke


def _bibliothek_da() -> bool:
    """Nur ``find_spec`` — die Bibliothek wird nie geladen."""
    ergebnis = False
    try:
        ergebnis = importlib.util.find_spec(BIBLIOTHEK) is not None
    except Exception:
        ergebnis = False
    return ergebnis


def _ja(wert: bool) -> str:
    return "ja" if wert else "nein"


def _normal(args: Any) -> int:
    aus: List[str] = []
    fehlend: List[str] = []
    version = _python_version()
    py_ok = tuple(version) >= (3, 11)
    aus.append(f"Python: {version[0]}.{version[1]} ({'ok' if py_ok else 'zu alt'})")
    if not py_ok:
        fehlend.append(M_PYTHON)

    ordner = os.path.expanduser(args.datenbank_ordner)
    namen = _ordner_lesen(ordner)
    if namen is None:
        aus.append("Sicherungsordner: nicht lesbar")
        fehlend.append(M_KEIN_ZUGRIFF)
    else:
        aus.append("Sicherungsordner: lesbar")
        n15 = sum(1 for n in namen if n.startswith("msgstore") and n.endswith(".crypt15"))
        n14 = sum(1 for n in namen if n.startswith("msgstore") and n.endswith(".crypt14"))
        aus.append(f"crypt15-Dateien: {n15} · crypt14-Dateien: {n14}")
        st = _sicherung_info(os.path.join(ordner, SICHERUNG_NAME))
        if st is None:
            aus.append(f"{SICHERUNG_NAME}: vorhanden nein")
            if n15 == 0 and n14 > 0:
                fehlend.append(M_NUR_CRYPT14)
            elif n15 == 0:
                fehlend.append(M_KEINE)
            else:
                fehlend.append(M_AKTUELL_FEHLT)
        else:
            alter = max(0.0, (_jetzt() - st.st_mtime) / 3600.0)
            aus.append(f"{SICHERUNG_NAME}: vorhanden ja · Groesse "
                       f"{st.st_size / MIB:.1f} MiB · Alter {alter:.1f} Stunden")
            klein = st.st_size <= args.max_mib * MIB
            aus.append(f"Groesse unter Grenze: {_ja(klein)} (Grenze {args.max_mib} MiB)")
            if not klein:
                fehlend.append(M_GROESSE)

    schl = _schluessel_pruefen(os.path.expanduser(args.schluessel))
    if not schl["vorhanden"]:
        aus.append("Schluesseldatei: vorhanden nein")
        fehlend.append(M_SCHL_FEHLT)
    else:
        form = "nicht geprueft" if schl["form"] is None else _ja(schl["form"])
        aus.append(f"Schluesseldatei: vorhanden ja · Schutz erfuellt {_ja(schl['schutz'])}"
                   f" · Form 64 Hex {form}")
        if not schl["schutz"]:
            fehlend.append(M_SCHL_SCHUTZ)
        elif schl["lesefehler"]:
            fehlend.append(M_SCHL_LESEN)
        elif schl["form"] is False:
            fehlend.append(M_SCHL_FORM)

    bibliothek = _bibliothek_da()
    aus.append("Bibliothek: vorhanden" if bibliothek
               else "Bibliothek: fehlt - erst fuer Teil B noetig")
    if args.fuer_teil_b and not bibliothek:
        fehlend.append(M_BIBLIOTHEK)

    for zeile in aus:
        print(zeile)
    for zeile in fehlend:
        print(zeile, file=sys.stderr)
    if fehlend:
        return EXIT_VORAUSSETZUNG
    print("Vorpruefung Teil A: bestanden")
    return EXIT_OK


# ── Messprobe ──────────────────────────────────────────────────────────────

def _resource_laden() -> Optional[Any]:
    modul = None
    try:
        modul = importlib.import_module("resource")
    except Exception:
        modul = None
    return modul


def _hoechststand_mib(resource: Any) -> Optional[int]:
    wert: Optional[int] = None
    try:
        wert = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024)   # Linux: KiB
    except Exception:
        wert = None
    return wert


def _speicherbetrieb(con: Any) -> Tuple[bool, bool]:
    """Speicherbetrieb erzwingen und pruefen: ``(ok, TEMP_STORE=0 gesetzt)``.

    Nur PRAGMAs, keine Tabellendaten. ``ok`` heisst: ``temp_store`` liefert 2 und die
    Kompilieroptionen enthalten nicht ``TEMP_STORE=0`` (dann waere die PRAGMA wirkungslos).
    """
    con.execute("PRAGMA temp_store=MEMORY")
    zeile = con.execute("PRAGMA temp_store").fetchone()
    optionen = con.execute("PRAGMA compile_options").fetchall()
    null_gesetzt = any(str(z[0]).upper() == "TEMP_STORE=0" for z in optionen)
    ok = zeile is not None and zeile[0] == 2 and not null_gesetzt
    return ok, null_gesetzt


def _speicherbetrieb_erzwingen(con: Any) -> None:
    ok, _null = _speicherbetrieb(con)
    if not ok:
        raise Abbruch(EXIT_VORAUSSETZUNG, M_SPEICHER)


def _probe_stufe(mib: int) -> None:
    """Eine Stufe: erfundene Datenbank bauen, packen, entpacken, per ``deserialize`` oeffnen."""
    bau = _verbinden(":memory:")
    _speicherbetrieb_erzwingen(bau)
    bau.execute("CREATE TABLE t (i INTEGER PRIMARY KEY, a TEXT, b INTEGER, c BLOB)")
    bau.execute("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < ?) "
                "INSERT INTO t SELECT i, hex(randomblob(8)), i % 97, randomblob(900) FROM n",
                (mib * 1024,))                       # etwa 1 KiB je Zeile
    roh = bau.serialize()
    bau.close()
    gepackt = zlib.compress(roh, 1)
    del roh
    entpacker = zlib.decompressobj()
    teile: List[bytes] = []
    daten = gepackt
    while True:
        teile.append(entpacker.decompress(daten, 16 * MIB))
        daten = entpacker.unconsumed_tail
        if not daten:
            break
    teile.append(entpacker.flush())
    if not entpacker.eof or entpacker.unused_data:
        raise ValueError("Strom unvollstaendig")
    del gepackt
    klartext = b"".join(teile)
    del teile
    con = _verbinden(":memory:")
    con.deserialize(klartext)
    del klartext
    con.execute("PRAGMA query_only=ON")
    _speicherbetrieb_erzwingen(con)
    # Abfragen, die Zwischenspeicher erzwingen (Sortieren, Gruppieren, Duplikate, Unterabfrage)
    for _zeile in con.execute("SELECT i FROM t ORDER BY a"):
        pass
    con.execute("SELECT b, COUNT(*) FROM t GROUP BY b").fetchall()
    con.execute("SELECT DISTINCT b FROM t").fetchall()
    con.execute("SELECT COUNT(*) FROM t WHERE b IN "
                "(SELECT DISTINCT b FROM t WHERE i % 5 = 0)").fetchall()
    con.close()


def _eintraege_zaehlen(pfad: str) -> Optional[int]:
    anzahl: Optional[int] = None
    try:
        anzahl = len(os.listdir(pfad))
    except Exception:
        anzahl = None
    return anzahl


def _marke(pfad: str) -> Optional[Tuple[int, int]]:
    ergebnis: Optional[Tuple[int, int]] = None
    try:
        st = os.stat(pfad)
        ergebnis = (int(st.st_size), int(st.st_mtime_ns))
    except Exception:
        ergebnis = None
    return ergebnis


def _unveraendert(vorher: Optional[Tuple[int, int]], nachher: Optional[Tuple[int, int]]) -> str:
    if vorher is None and nachher is None:
        return "nicht vorhanden"
    return _ja(vorher == nachher)


def _stufen_parsen(text: str) -> Optional[Tuple[int, ...]]:
    teile = text.split(",")
    if not 1 <= len(teile) <= MAX_STUFEN:
        return None
    werte: List[int] = []
    for teil in teile:
        if not re.fullmatch(r"[0-9]{1,5}", teil):
            return None
        wert = int(teil)
        if wert < 1 or wert > MAX_STUFE_MIB:
            return None
        werte.append(wert)
    if any(b <= a for a, b in zip(werte, werte[1:])):
        return None
    return tuple(werte)


def _ordnerregel_pruefen(pfad: str) -> str:
    status = ordner_status(pfad)
    if status in ("link", "kein_ordner", "repo", "unpruefbar"):
        raise Abbruch(EXIT_AUFRUF, M_ORDNER_SCHUTZ)
    return status


def _messprobe(args: Any, stufen: Tuple[int, ...]) -> int:
    if tuple(_python_version()) < (3, 11):
        raise Abbruch(EXIT_VORAUSSETZUNG, M_PYTHON)
    resource = _resource_laden()
    if resource is None:
        raise Abbruch(EXIT_VORAUSSETZUNG, M_RESOURCE)

    arbeit = os.path.expanduser(args.arbeitsordner)
    status = ordner_status(arbeit)
    if status in ("repo", "unpruefbar"):
        raise Abbruch(EXIT_AUFRUF, M_ORDNER_SCHUTZ)
    if status != "ok":
        raise Abbruch(EXIT_VORAUSSETZUNG, M_ARBEITSORDNER)

    ursprung_tmp = os.environ.get("TMPDIR") or "/tmp"
    tmp_vorher = _eintraege_zaehlen(ursprung_tmp)
    if tmp_vorher is None:
        raise Abbruch(EXIT_VORAUSSETZUNG, M_TMPDIR_PRUEFEN)

    whatsapp = os.path.join(arbeit, "whatsapp")
    probe = os.path.join(whatsapp, "messprobe_leer")
    if _ordnerregel_pruefen(whatsapp) == "fehlt":
        _ordner_anlegen(whatsapp)
    if _ordnerregel_pruefen(probe) == "fehlt":
        _ordner_anlegen(probe)
    inhalt = _eintraege_zaehlen(probe)
    if inhalt is None:
        raise Abbruch(EXIT_VORAUSSETZUNG, M_PROBE_PRUEFEN)
    if inhalt > 0:
        raise Abbruch(EXIT_VORAUSSETZUNG, M_PROBE_NICHT_LEER)

    sicherung = os.path.join(os.path.expanduser(args.datenbank_ordner), SICHERUNG_NAME)
    schluessel = os.path.expanduser(args.schluessel)
    sicherung_vorher, schluessel_vorher = _marke(sicherung), _marke(schluessel)

    print(f"SQLite-Version: {sqlite3.sqlite_version}")
    ergebnisse: List[Tuple[int, Optional[int]]] = []
    ursprung = {name: os.environ.get(name) for name in ("SQLITE_TMPDIR", "TMPDIR")}
    cwd_alt: Optional[str] = None
    try:
        cwd_alt = os.getcwd()
    except Exception:
        cwd_alt = None
    try:
        os.environ["SQLITE_TMPDIR"] = probe
        os.environ["TMPDIR"] = probe
        os.chdir(probe)
        frueh = _verbinden(":memory:")
        ok, null_gesetzt = _speicherbetrieb(frueh)
        frueh.close()
        print(f"TEMP_STORE=0 gesetzt: {_ja(null_gesetzt)}")
        if not ok:
            raise Abbruch(EXIT_VORAUSSETZUNG, M_SPEICHER)
        for mib in stufen:
            abbruch: Optional[Abbruch] = None
            art: Optional[str] = None
            try:
                _probe_stufe(mib)
            except Abbruch as problem:
                abbruch = problem
            except MemoryError:
                art = "Speicher"
            except Exception:
                art = "Fehler"
            if abbruch is not None:
                raise abbruch
            im_probeordner = _eintraege_zaehlen(probe)
            if im_probeordner is None:
                raise Abbruch(EXIT_VORAUSSETZUNG, M_PROBE_PRUEFEN)
            if im_probeordner > 0:
                raise Abbruch(EXIT_VORAUSSETZUNG, M_ZWISCHEN)
            tmp_nachher = _eintraege_zaehlen(ursprung_tmp)
            if tmp_nachher is None:
                raise Abbruch(EXIT_VORAUSSETZUNG, M_TMPDIR_PRUEFEN)
            if tmp_nachher != tmp_vorher:
                raise Abbruch(EXIT_VORAUSSETZUNG, M_TMPDIR)
            if art is not None:
                print(f"Stufe {mib} MiB: abgebrochen ({art})", flush=True)
                break
            hoch = _hoechststand_mib(resource)
            ergebnisse.append((mib, hoch))
            print(f"Stufe {mib} MiB: ok - Hoechststand "
                  f"{hoch if hoch is not None else 'unbekannt'} MiB", flush=True)
    finally:
        for name, wert in ursprung.items():
            if wert is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = wert
        if cwd_alt is not None:
            os.chdir(cwd_alt)

    if not ergebnisse:
        print(M_KEINE_STUFE, file=sys.stderr)
        return EXIT_FEHLER
    print(f"Obergrenze: {ergebnisse[-1][0]} MiB")
    print("Zwischendatei: keine")
    print(f"TMPDIR-Eintraege: vorher {tmp_vorher} · nachher {_eintraege_zaehlen(ursprung_tmp)}")
    print(f"Unveraendert: Sicherung {_unveraendert(sicherung_vorher, _marke(sicherung))}"
          f" · Schluessel {_unveraendert(schluessel_vorher, _marke(schluessel))}")
    return EXIT_OK


# ── Aufruf ─────────────────────────────────────────────────────────────────

class LeiserParser(argparse.ArgumentParser):
    """``argparse`` ohne Echo der falschen Eingabe (kann ein Pfad oder Name sein)."""

    def error(self, message: str) -> None:        # type: ignore[override]
        print(M_AUFRUF, file=sys.stderr)
        raise SystemExit(EXIT_AUFRUF)


def _positiv(text: str) -> int:
    if not re.fullmatch(r"[0-9]{1,6}", text) or int(text) < 1:
        raise argparse.ArgumentTypeError("ungueltig")
    return int(text)


def _argumente(argv: Optional[List[str]]) -> Any:
    p = LeiserParser(description="WhatsApp-Sicherung vorpruefen (nur lesend) und "
                                 "Speicher-Messprobe (nur mit --messprobe).")
    p.add_argument("--messprobe", action="store_true",
                   help="Speicher-Messprobe mit erfundenen Daten statt der Vorpruefung")
    p.add_argument("--fuer-teil-b", action="store_true", dest="fuer_teil_b",
                   help="auch die Bibliothek wa_crypt_tools verlangen")
    p.add_argument("--stufen", default=STANDARD_STUFEN,
                   help="Stufen der Messprobe in MiB, aufsteigend, mit Komma getrennt")
    p.add_argument("--max-mib", type=_positiv, default=STANDARD_MAX_MIB, dest="max_mib",
                   help="groesste erlaubte Sicherungsdatei in MiB")
    p.add_argument("--datenbank-ordner", default=STANDARD_DATENBANKORDNER,
                   dest="datenbank_ordner", help="Ordner der WhatsApp-Sicherung")
    p.add_argument("--schluessel", default=STANDARD_SCHLUESSEL, help="Schluesseldatei")
    p.add_argument("--arbeitsordner", default=STANDARD_ARBEITSORDNER,
                   help="Arbeitsordner (nur Messprobe)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _argumente(argv)
    except SystemExit as ende:
        return int(ende.code or 0)
    stufen = _stufen_parsen(args.stufen)
    if stufen is None:
        print(M_STUFEN, file=sys.stderr)
        return EXIT_AUFRUF
    if args.messprobe and args.fuer_teil_b:
        print(M_KOMBINATION, file=sys.stderr)
        return EXIT_AUFRUF
    try:
        if args.messprobe:
            return _messprobe(args, stufen)
        return _normal(args)
    except Abbruch as ende:
        print(ende.meldung, file=sys.stderr)
        return ende.code
    except Exception as fehler:                      # letzte Absicherung: nur der Klassenname
        print(f"Fehler: unerwarteter Abbruch ({fehler.__class__.__name__})", file=sys.stderr)
        return EXIT_FEHLER


if __name__ == "__main__":
    raise SystemExit(main())
