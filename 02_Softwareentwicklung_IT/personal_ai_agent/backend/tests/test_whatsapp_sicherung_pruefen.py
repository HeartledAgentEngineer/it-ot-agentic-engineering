"""Pruefungen fuer W2 Teil A: Vorpruefung der WhatsApp-Sicherung + Messprobe (22.10.2026).

Plan: ``.hermes/plans/2026-10-22_whatsapp-w2.md`` (Fassung 16, Teil A, W2a).

Nur erfundene Daten in ``tmp_path``. Rechte, Besitzer, Links, Python-Version und
``resource`` werden mit Attrappen nachgestellt (Windows kennt sie nicht nativ).
Der erfundene Schluessel darf nirgends in stdout/stderr auftauchen.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_whatsapp_sicherung_pruefen.py -q
"""

from __future__ import annotations

import ast
import builtins
import importlib
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJEKT = Path(__file__).resolve().parents[2]
HANDY = PROJEKT / "tools" / "handy"
WERKZEUG = HANDY / "whatsapp_sicherung_pruefen.py"

SCHLUESSEL = "5e0b7a1c93d2f4e8" "6a9c1d3b5f7e2048" "b1d3f5a79c2e4680" "13579bdf02468ace"
MELDUNG_KEIN_ZUGRIFF = "kein Zugriff auf die WhatsApp-Sicherung (termux-setup-storage)"


@pytest.fixture
def w2a(monkeypatch):
    monkeypatch.syspath_prepend(str(HANDY))
    return importlib.import_module("whatsapp_sicherung_pruefen")


# ── Schreib-Spy: alle Schreibwege, ueber den gesamten Lauf ──────────────────

class SchreibSpy:
    def __init__(self):
        self.schreib = []          # alles Schreibende ausser mkdir
        self.mkdirs = []
        self.geoeffnet = []        # jeder open/os.open-Pfad (auch lesend)
        self.listings = []

    def installieren(self, mp):
        spy = self
        echt_open, echt_osopen, echt_mkdir = builtins.open, os.open, os.mkdir
        echt_listdir = os.listdir

        def mein_open(datei, mode="r", *a, **k):
            spy.geoeffnet.append(str(datei))
            if any(c in str(mode) for c in "wax+"):
                spy.schreib.append(("open", str(datei), mode))
            return echt_open(datei, mode, *a, **k)

        def mein_osopen(pfad, flags, *a, **k):
            spy.geoeffnet.append(str(pfad))
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC):
                spy.schreib.append(("os.open", str(pfad), flags))
            return echt_osopen(pfad, flags, *a, **k)

        def mein_mkdir(pfad, *a, **k):
            spy.mkdirs.append(str(pfad))
            return echt_mkdir(pfad, *a, **k)

        def mein_listdir(pfad="."):
            spy.listings.append(str(pfad))
            return echt_listdir(pfad)

        mp.setattr(builtins, "open", mein_open)
        mp.setattr(os, "open", mein_osopen)
        mp.setattr(os, "mkdir", mein_mkdir)
        mp.setattr(os, "listdir", mein_listdir)

        def melder(name):
            def f(*a, **k):
                spy.schreib.append((name, a[:1], None))
                raise AssertionError("Schreibweg " + name)
            return f

        for modul, namen in (
                (os, ("makedirs", "replace", "rename", "renames", "remove", "unlink",
                      "rmdir", "removedirs", "symlink", "link", "truncate")),
                (tempfile, ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryFile",
                            "TemporaryDirectory", "SpooledTemporaryFile")),
                (shutil, ("copy", "copy2", "copyfile", "move", "rmtree", "copytree",
                          "copyfileobj"))):
            for name in namen:
                if hasattr(modul, name):
                    mp.setattr(modul, name, melder(modul.__name__ + "." + name))
        return self


# ── Fixture fuer den Normalbetrieb ───────────────────────────────────────────

class Rechte:
    def __init__(self):
        self.mode = stat.S_IFREG | 0o600
        self.nlink = 1
        self.uid = 1000
        self.nutzer = 1000
        self.link = False


@pytest.fixture
def umg(tmp_path, w2a, monkeypatch, capsys):
    db = tmp_path / "Databases"
    db.mkdir()
    sicherung = db / "msgstore.db.crypt15"
    sicherung.write_bytes(b"erfundene-verschluesselte-bytes" * 8)
    heim = tmp_path / "heim" / ".config" / "agent"
    heim.mkdir(parents=True)
    schluessel = heim / "wa_sicherung.key"
    schluessel.write_text(SCHLUESSEL + "\n", encoding="ascii")
    r = Rechte()
    echt_lstat = os.lstat
    echt_link = w2a._ist_link

    def lstat(pfad):
        st = echt_lstat(pfad)
        if str(pfad) == str(schluessel):
            return SimpleNamespace(st_mode=r.mode, st_nlink=r.nlink, st_uid=r.uid,
                                   st_size=st.st_size, st_mtime=st.st_mtime)
        return st

    monkeypatch.setattr(w2a, "_lstat", lstat)
    monkeypatch.setattr(w2a, "_aktueller_nutzer", lambda: r.nutzer)
    monkeypatch.setattr(w2a, "_ist_link",
                        lambda p: r.link if str(p) == str(schluessel) else echt_link(p))
    echt_spec = importlib.util.find_spec
    zustand = {"bibliothek": False}

    def spec(name, *a, **k):
        if name == "wa_crypt_tools":
            return object() if zustand["bibliothek"] else None
        return echt_spec(name, *a, **k)

    monkeypatch.setattr(importlib.util, "find_spec", spec)

    def lauf(*zusatz):
        code = w2a.main(["--datenbank-ordner", str(db), "--schluessel", str(schluessel),
                         *zusatz])
        aus = capsys.readouterr()
        return code, aus.out, aus.err

    return SimpleNamespace(db=db, sicherung=sicherung, schluessel=schluessel, r=r,
                           lauf=lauf, zustand=zustand, tmp=tmp_path, mp=monkeypatch)


def _zustand(pfad):
    st = os.stat(pfad)
    return Path(pfad).read_bytes(), st.st_mtime_ns


# ═══════════════════════════════════════════════════════════════════════════
# 1. Normalbetrieb
# ═══════════════════════════════════════════════════════════════════════════

def test_alles_da_exit_0_mit_meldezeilen(umg):
    code, out, err = umg.lauf()
    assert code == 0, out + err
    assert "Sicherungsordner: lesbar" in out
    assert "crypt15-Dateien: 1 " in out and "crypt14-Dateien: 0" in out
    assert "msgstore.db.crypt15: vorhanden ja" in out
    assert "Schluesseldatei: vorhanden ja · Schutz erfuellt ja · Form 64 Hex ja" in out
    assert "Bibliothek: fehlt - erst fuer Teil B noetig" in out
    assert err == ""
    assert SCHLUESSEL not in out + err


def test_zaehlt_crypt14_und_crypt15_dateien(umg):
    (umg.db / "msgstore-2026-10-20.1.db.crypt15").write_bytes(b"x")
    (umg.db / "msgstore.db.crypt14").write_bytes(b"x")
    (umg.db / "msgstore-2026-10-20.1.db.crypt14").write_bytes(b"x")
    (umg.db / "andere.txt").write_bytes(b"x")
    code, out, _ = umg.lauf()
    assert code == 0
    assert "crypt15-Dateien: 2" in out and "crypt14-Dateien: 2" in out


def test_ohne_messprobe_wird_nichts_geschrieben_und_nichts_veraendert(umg):
    sich = _zustand(umg.sicherung)
    key = _zustand(umg.schluessel)
    spy = SchreibSpy().installieren(umg.mp)
    code, out, err = umg.lauf()
    assert code == 0
    assert spy.schreib == [] and spy.mkdirs == []
    assert _zustand(umg.sicherung) == sich and _zustand(umg.schluessel) == key
    # die Sicherung selbst wird nie geoeffnet (nur stat)
    assert str(umg.sicherung) not in spy.geoeffnet


def test_schluesselinhalt_erscheint_nirgends(umg):
    for aendern in (lambda: None,
                    lambda: umg.schluessel.write_text("zz" * 32, encoding="ascii")):
        aendern()
        code, out, err = umg.lauf()
        assert SCHLUESSEL not in out + err and "zz" * 8 not in out + err


def test_lesefehler_am_schluessel_liefert_nur_feste_zeile(umg):
    echt = builtins.open

    def kaputt(datei, *a, **k):
        if str(datei) == str(umg.schluessel):
            raise OSError(SCHLUESSEL)
        return echt(datei, *a, **k)

    umg.mp.setattr(builtins, "open", kaputt)
    code, out, err = umg.lauf()
    assert code == 3
    assert SCHLUESSEL not in out + err
    assert "Schluesseldatei nicht lesbar" in err


# ── jede Voraussetzung einzeln fehlend -> feste Zeile, Exit 3 ───────────────

def test_ordner_fehlt_exit_3(umg):
    shutil.rmtree(umg.db)
    code, out, err = umg.lauf()
    assert code == 3 and MELDUNG_KEIN_ZUGRIFF in err
    assert str(umg.db) not in out + err


def test_ordner_nicht_lesbar_exit_3(umg):
    umg.mp.setattr(os, "access", lambda *a, **k: False)
    code, out, err = umg.lauf()
    assert code == 3 and MELDUNG_KEIN_ZUGRIFF in err


def test_nur_crypt14_exit_3_mit_e2e_hinweis(umg):
    umg.sicherung.unlink()
    (umg.db / "msgstore.db.crypt14").write_bytes(b"x")
    code, out, err = umg.lauf()
    assert code == 3
    assert ("Sicherung ohne Ende-zu-Ende-Schluessel - in WhatsApp die "
            "Ende-zu-Ende-Sicherung einschalten") in err


def test_keine_sicherung_exit_3(umg):
    umg.sicherung.unlink()
    code, out, err = umg.lauf()
    assert code == 3 and "keine WhatsApp-Sicherung gefunden" in err


def test_nur_datierte_crypt15_ohne_aktuelle_exit_3(umg):
    umg.sicherung.unlink()
    (umg.db / "msgstore-2026-10-20.1.db.crypt15").write_bytes(b"x")
    code, out, err = umg.lauf()
    assert code == 3 and "msgstore.db.crypt15 fehlt" in err


def test_sicherung_ist_ein_ordner_zaehlt_nicht_als_vorhanden(umg):
    umg.sicherung.unlink()
    umg.sicherung.mkdir()
    code, out, err = umg.lauf()
    assert code == 3 and "msgstore.db.crypt15 fehlt" in err


def test_schluessel_fehlt(umg):
    umg.schluessel.unlink()
    code, out, err = umg.lauf()
    assert code == 3 and "Schluesseldatei fehlt" in err
    assert "Schluesseldatei: vorhanden nein" in out


@pytest.mark.parametrize("aendern", [
    lambda u: setattr(u.r, "link", True),
    lambda u: setattr(u.r, "nlink", 2),
    lambda u: setattr(u.r, "mode", stat.S_IFREG | 0o644),
    lambda u: setattr(u.r, "mode", stat.S_IFREG | 0o400),
    lambda u: setattr(u.r, "mode", stat.S_IFREG | 0o700),
    lambda u: setattr(u.r, "mode", stat.S_IFDIR | 0o600),
    lambda u: setattr(u.r, "uid", 999),
    lambda u: setattr(u.r, "nutzer", None),
], ids=["link", "hartlink", "rechte644", "rechte400", "rechte700", "ordner", "fremder_besitzer",
        "nutzer_unbekannt"])
def test_schluessel_schutz_verletzt(umg, aendern):
    aendern(umg)
    code, out, err = umg.lauf()
    assert code == 3
    assert "Schluesseldatei nicht geschuetzt" in err
    assert "Schutz erfuellt nein" in out and "Form 64 Hex nicht geprueft" in out
    assert SCHLUESSEL not in out + err


@pytest.mark.parametrize("inhalt", [
    SCHLUESSEL[:63], SCHLUESSEL + "0", "g" * 64, "", SCHLUESSEL + "\n\n", " " + SCHLUESSEL,
    SCHLUESSEL + " ",
], ids=["63", "65", "keinhex", "leer", "zwei_zeilenenden", "leerzeichen_vorn", "leerzeichen_hinten"])
def test_schluessel_falsche_form(umg, inhalt):
    umg.schluessel.write_text(inhalt, encoding="ascii")
    code, out, err = umg.lauf()
    assert code == 3 and "Form 64 Hex nein" in out
    assert "Schluesseldatei hat nicht die Form 64 Hex-Zeichen" in err


@pytest.mark.parametrize("roh", [SCHLUESSEL, SCHLUESSEL + "\n", SCHLUESSEL + "\r\n",
                                 SCHLUESSEL.upper()])
def test_schluessel_gueltige_formen(umg, roh):
    umg.schluessel.write_bytes(roh.encode("ascii"))
    code, out, err = umg.lauf()
    assert code == 0, err


def test_schluessel_im_repo_angegeben(umg, w2a):
    repo = umg.tmp / "repo"
    (repo / ".git").mkdir(parents=True)
    ziel = repo / "sub" / "wa_sicherung.key"
    ziel.parent.mkdir()
    ziel.write_text(SCHLUESSEL, encoding="ascii")
    umg.r.link = False
    echt = w2a._lstat

    def lstat(pfad):
        if str(pfad) == str(ziel):
            st = os.lstat(pfad)
            return SimpleNamespace(st_mode=umg.r.mode, st_nlink=1, st_uid=1000,
                                   st_size=st.st_size, st_mtime=st.st_mtime)
        return echt(pfad)

    umg.mp.setattr(w2a, "_lstat", lstat)
    code = w2a.main(["--datenbank-ordner", str(umg.db), "--schluessel", str(ziel)])
    assert code == 3


def test_schluessel_aufgeloest_im_repo(umg, w2a):
    repo = umg.tmp / "repo2"
    (repo / ".git").mkdir(parents=True)
    umg.mp.setattr(w2a, "_realpath", lambda p: str(repo / "x" / "key"))
    code, out, err = umg.lauf()
    assert code == 3 and "Schluesseldatei nicht geschuetzt" in err


def test_schluessel_repo_pruefung_nicht_moeglich_zaehlt_als_verstoss(umg, w2a):
    def kaputt(p):
        raise OSError("Zaunstein")

    umg.mp.setattr(w2a, "_realpath", kaputt)
    code, out, err = umg.lauf()
    assert code == 3 and "Zaunstein" not in out + err


def test_python_zu_alt(umg, w2a):
    umg.mp.setattr(w2a, "_python_version", lambda: (3, 10))
    code, out, err = umg.lauf()
    assert code == 3 and "Python 3.11 oder neuer noetig" in err


def test_groesse_ueber_grenze(umg):
    umg.sicherung.write_bytes(b"0" * (2 * 1024 * 1024))
    code, out, err = umg.lauf("--max-mib", "1")
    assert code == 3 and "Sicherung ist groesser als die Grenze" in err
    code, out, err = umg.lauf("--max-mib", "2")
    assert code == 0


def test_groesse_und_alter_werden_gemeldet(umg, w2a):
    jetzt = umg.sicherung.stat().st_mtime + 3 * 3600
    umg.mp.setattr(w2a, "_jetzt", lambda: jetzt)
    code, out, _ = umg.lauf()
    assert "Alter 3.0 Stunden" in out and "MiB" in out


# ── Bibliothek ─────────────────────────────────────────────────────────────

def test_bibliothek_fehlt_teil_a_exit_0_teil_b_exit_3(umg):
    code, out, _ = umg.lauf()
    assert code == 0 and "Bibliothek: fehlt - erst fuer Teil B noetig" in out
    code, out, err = umg.lauf("--fuer-teil-b")
    assert code == 3 and "Bibliothek wa_crypt_tools fehlt" in err


def test_bibliothek_vorhanden_wird_nur_gemeldet_nicht_importiert(umg):
    umg.zustand["bibliothek"] = True
    echt = importlib.import_module
    importiert = []

    def import_module(name, *a, **k):
        importiert.append(name)
        return echt(name, *a, **k)

    umg.mp.setattr(importlib, "import_module", import_module)
    code, out, _ = umg.lauf("--fuer-teil-b")
    assert code == 0 and "Bibliothek: vorhanden" in out
    assert "wa_crypt_tools" not in importiert and "wa_crypt_tools" not in sys.modules


def test_find_spec_fehler_zaehlt_als_fehlend(umg):
    def spec(name, *a, **k):
        raise ValueError("Zaunstein")

    umg.mp.setattr(importlib.util, "find_spec", spec)
    code, out, err = umg.lauf()
    assert code == 0 and "Bibliothek: fehlt" in out and "Zaunstein" not in out + err


def test_aufrufe_ungueltig_exit_2_ohne_echo(umg, capsys, w2a):
    for argv in (["--unbekannt"], ["--max-mib", "abc"], ["--max-mib", "0"],
                 ["--stufen", "x"], ["Zaunstein"]):
        code = w2a.main(argv)
        aus = capsys.readouterr()
        assert code == 2 and "Zaunstein" not in aus.out + aus.err and "abc" not in aus.err


def test_help_ist_exit_0(umg, w2a, capsys):
    assert w2a.main(["--help"]) == 0
    assert "--messprobe" in capsys.readouterr().out


# ═══════════════════════════════════════════════════════════════════════════
# 2. Messprobe
# ═══════════════════════════════════════════════════════════════════════════

class VerbindungSpy:
    """Reicht alles an die echte Verbindung durch und protokolliert ``execute``."""

    def __init__(self, con, protokoll, ersatz=None):
        self._con, self.protokoll, self.ersatz = con, protokoll, ersatz or {}

    def execute(self, sql, *a):
        self.protokoll.append(sql)
        for muster, wert in self.ersatz.items():
            if sql.strip().upper().startswith(muster):
                return self._con.execute("SELECT ?", (wert,))
        return self._con.execute(sql, *a)

    def __getattr__(self, name):
        return getattr(self._con, name)


@pytest.fixture
def probe(tmp_path, w2a, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    foto = tmp_path / "foto_sortierung"
    foto.mkdir()
    tmpdir = tmp_path / "tmp_orig"
    tmpdir.mkdir()
    monkeypatch.setenv("TMPDIR", str(tmpdir))
    monkeypatch.delenv("SQLITE_TMPDIR", raising=False)
    zaehler = {"n": 0}

    def getrusage(_who):
        zaehler["n"] += 1
        return SimpleNamespace(ru_maxrss=100 * 1024 + zaehler["n"] * 1024)

    monkeypatch.setitem(sys.modules, "resource",
                        SimpleNamespace(RUSAGE_SELF=0, getrusage=getrusage))
    db = tmp_path / "Databases"
    db.mkdir()
    sich = db / "msgstore.db.crypt15"
    sich.write_bytes(b"sicherung")
    key = tmp_path / "wa.key"
    key.write_text(SCHLUESSEL, encoding="ascii")

    def lauf(*zusatz, stufen="1,2"):
        code = w2a.main(["--messprobe", "--stufen", stufen, "--arbeitsordner", str(foto),
                         "--datenbank-ordner", str(db), "--schluessel", str(key), *zusatz])
        aus = capsys.readouterr()
        return code, aus.out, aus.err

    return SimpleNamespace(foto=foto, tmpdir=tmpdir, db=db, sich=sich, key=key, lauf=lauf,
                           mp=monkeypatch, wa=foto / "whatsapp", leer=foto / "whatsapp" / "messprobe_leer",
                           tmp=tmp_path, w2a=w2a)


def test_messprobe_erfolg(probe):
    cwd, env = os.getcwd(), dict(os.environ)
    sich, key = _zustand(probe.sich), _zustand(probe.key)
    spy = SchreibSpy().installieren(probe.mp)
    code, out, err = probe.lauf()
    assert code == 0, out + err
    assert "Stufe 1 MiB: ok" in out and "Stufe 2 MiB: ok" in out
    assert "Hoechststand" in out and "Obergrenze: 2 MiB" in out
    assert "Zwischendatei: keine" in out and "SQLite-Version:" in out
    assert "TEMP_STORE=0 gesetzt: nein" in out or "TEMP_STORE=0 gesetzt: ja" in out
    # einzige Schreibzugriffe: die zwei Ordner
    assert spy.schreib == []
    assert spy.mkdirs == [str(probe.wa), str(probe.leer)]
    assert probe.wa.is_dir() and probe.leer.is_dir()
    assert list(probe.leer.iterdir()) == []
    # Umgebung und Arbeitsverzeichnis wie vorher
    assert os.getcwd() == cwd and dict(os.environ) == env
    # Sicherung und Schluessel weder geoeffnet noch aufgelistet noch veraendert
    assert str(probe.sich) not in spy.geoeffnet and str(probe.key) not in spy.geoeffnet
    assert str(probe.db) not in spy.listings
    assert _zustand(probe.sich) == sich and _zustand(probe.key) == key
    assert SCHLUESSEL not in out + err


def test_messprobe_laeuft_ohne_schluessel_sicherung_und_bibliothek(probe):
    probe.sich.unlink()
    probe.key.unlink()
    code, out, err = probe.lauf()
    assert code == 0, err
    assert "Unveraendert: Sicherung nicht vorhanden" in out


def test_messprobe_meldet_unveraendert(probe):
    code, out, _ = probe.lauf()
    assert "Unveraendert: Sicherung ja · Schluessel ja" in out


def test_messprobe_umgebung_waehrend_der_probe(probe):
    gesehen = {}

    def stufe(mib):
        gesehen["sqlite"] = os.environ.get("SQLITE_TMPDIR")
        gesehen["tmpdir"] = os.environ.get("TMPDIR")
        gesehen["cwd"] = os.getcwd()

    probe.mp.setattr(probe.w2a, "_probe_stufe", stufe)
    code, out, err = probe.lauf()
    assert code == 0
    leer = str(probe.leer)
    assert gesehen["sqlite"] == leer and gesehen["tmpdir"] == leer
    assert os.path.realpath(gesehen["cwd"]) == os.path.realpath(leer)


def test_messprobe_stellt_umgebung_auch_bei_vorhandenem_sqlite_tmpdir_wieder_her(probe):
    probe.mp.setenv("SQLITE_TMPDIR", "/irgendwo/erfunden")
    code, _, _ = probe.lauf()
    assert code == 0 and os.environ["SQLITE_TMPDIR"] == "/irgendwo/erfunden"


def test_messprobe_arbeitsordner_fehlt_exit_3_ohne_mkdir(probe):
    shutil.rmtree(probe.foto)
    spy = SchreibSpy().installieren(probe.mp)
    code, out, err = probe.lauf()
    assert code == 3 and "Arbeitsordner ~/foto_sortierung fehlt" in err
    assert spy.mkdirs == [] and spy.schreib == []


def test_messprobe_arbeitsordner_ist_datei_exit_3(probe):
    shutil.rmtree(probe.foto)
    probe.foto.write_text("x")
    spy = SchreibSpy().installieren(probe.mp)
    code, _, err = probe.lauf()
    assert code == 3 and spy.mkdirs == []


def test_messprobe_arbeitsordner_link_exit_3(probe):
    echt = probe.w2a._ist_link
    probe.mp.setattr(probe.w2a, "_ist_link",
                     lambda p: True if str(p) == str(probe.foto) else echt(p))
    spy = SchreibSpy().installieren(probe.mp)
    code, _, _ = probe.lauf()
    assert code == 3 and spy.mkdirs == []


def test_messprobe_whatsapp_ist_link_exit_2_kein_mkdir(probe):
    probe.wa.mkdir()
    echt = probe.w2a._ist_link
    probe.mp.setattr(probe.w2a, "_ist_link",
                     lambda p: True if str(p) == str(probe.wa) else echt(p))
    spy = SchreibSpy().installieren(probe.mp)
    code, _, err = probe.lauf()
    assert code == 2 and spy.mkdirs == [] and "Ordner" in err


def test_messprobe_probeordner_ist_link_exit_2(probe):
    probe.leer.mkdir(parents=True)
    echt = probe.w2a._ist_link
    probe.mp.setattr(probe.w2a, "_ist_link",
                     lambda p: True if str(p) == str(probe.leer) else echt(p))
    spy = SchreibSpy().installieren(probe.mp)
    code, _, _ = probe.lauf()
    assert code == 2 and spy.mkdirs == []


def test_messprobe_whatsapp_ist_datei_exit_2(probe):
    probe.wa.write_text("x")
    spy = SchreibSpy().installieren(probe.mp)
    code, _, _ = probe.lauf()
    assert code == 2 and spy.mkdirs == []


def test_messprobe_probeordner_ist_datei_exit_2(probe):
    probe.wa.mkdir()
    probe.leer.write_text("x")
    spy = SchreibSpy().installieren(probe.mp)
    code, _, _ = probe.lauf()
    assert code == 2 and spy.mkdirs == []


def test_messprobe_whatsapp_aufgeloest_im_repo_exit_2(probe):
    repo = probe.tmp / "repo"
    (repo / ".git").mkdir(parents=True)
    echt = probe.w2a._realpath
    probe.mp.setattr(probe.w2a, "_realpath",
                     lambda p: str(repo / "x") if str(p) == str(probe.wa) else echt(p))
    spy = SchreibSpy().installieren(probe.mp)
    code, _, _ = probe.lauf()
    assert code == 2 and spy.mkdirs == []


def test_messprobe_whatsapp_angegeben_im_repo_exit_2(probe):
    (probe.tmp / ".git").mkdir()          # tmp_path selbst ist dann 'Repo'
    spy = SchreibSpy().installieren(probe.mp)
    code, _, _ = probe.lauf()
    assert code == 2 and spy.mkdirs == []


def _baum_stand(wurzel):
    return sorted(str(p.relative_to(wurzel)) for p in wurzel.rglob("*"))


@pytest.mark.parametrize("form", ["ordner", "datei"])
@pytest.mark.parametrize("wo", ["arbeit", "whatsapp", "probe"])
def test_messprobe_vorhandener_ordner_ist_selbst_repo_wurzel_exit_2(probe, wo, form):
    """Nachbesserung Befund 1: ein bestehender Ordner, der selbst ``.git`` enthaelt (Ordner oder
    Datei wie bei einem Worktree), ist die Repo-Wurzel und wird nie zugelassen."""
    if wo in ("whatsapp", "probe"):
        probe.wa.mkdir()
    if wo == "probe":
        probe.leer.mkdir()
    ziel = {"arbeit": probe.foto, "whatsapp": probe.wa, "probe": probe.leer}[wo]
    if form == "ordner":
        (ziel / ".git").mkdir()
    else:
        (ziel / ".git").write_text("gitdir: /erfunden/worktree\n", encoding="utf-8")
    vorher = _baum_stand(probe.foto)
    aufrufe = []
    probe.mp.setattr(probe.w2a, "_probe_stufe", lambda mib: aufrufe.append(mib))
    spy = SchreibSpy().installieren(probe.mp)
    code, out, err = probe.lauf()
    assert code == 2 and "Ordner" in err, out + err
    assert aufrufe == [] and spy.mkdirs == [] and spy.schreib == []
    assert _baum_stand(probe.foto) == vorher           # nichts angelegt, nichts veraendert


def test_ordner_status_erkennt_repo_wurzel_im_ordner_selbst(probe):
    w2a = probe.w2a
    probe.wa.mkdir()
    assert w2a.ordner_status(str(probe.wa)) == "ok"
    (probe.wa / ".git").mkdir()
    assert w2a.ordner_status(str(probe.wa)) == "repo"
    # nicht vorhandener Ordner unterhalb einer Repo-Wurzel bleibt "repo" (Elternpruefung)
    assert w2a.ordner_status(str(probe.wa / "messprobe_leer")) == "repo"


def test_dateipruefung_schluessel_bleibt_unveraendert_nur_elternordner(umg, w2a, tmp_path):
    """Gegenprobe: bei DATEIEN zaehlt nur der Elternbaum; eine Datei namens ``.git`` im
    Schluesselordner waere bereits der Elternordner (also Repo) - und eine Datei ohne ``.git``
    im Baum ist weiterhin nicht im Repo."""
    schluessel = tmp_path / "heim" / ".config" / "agent" / "wa_sicherung.key"
    assert w2a.im_repo(str(schluessel)) is False
    (schluessel.parent / ".git").mkdir()
    assert w2a.im_repo(str(schluessel)) is True


def test_messprobe_bestehende_ordner_werden_angenommen(probe):
    probe.leer.mkdir(parents=True)
    spy = SchreibSpy().installieren(probe.mp)
    code, out, err = probe.lauf()
    assert code == 0, err
    assert spy.mkdirs == []              # nichts anzulegen


def test_messprobe_nur_probeordner_fehlt_legt_nur_ihn_an(probe):
    probe.wa.mkdir()
    spy = SchreibSpy().installieren(probe.mp)
    code, _, _ = probe.lauf()
    assert code == 0 and spy.mkdirs == [str(probe.leer)]


def test_messprobe_probeordner_vorher_nicht_leer_exit_3_ohne_probe(probe):
    probe.leer.mkdir(parents=True)
    rest = probe.leer / "alt.tmp"
    rest.write_bytes(b"x")
    aufrufe = []
    probe.mp.setattr(probe.w2a, "_probe_stufe", lambda mib: aufrufe.append(mib))
    code, out, err = probe.lauf()
    assert code == 3 and "Probeordner nicht leer" in err
    assert aufrufe == [] and rest.read_bytes() == b"x"


def test_messprobe_zwischendatei_waehrend_der_probe_exit_3_datei_bleibt(probe):
    def stufe(mib):
        Path(os.environ["SQLITE_TMPDIR"], "etilqs_erfunden").write_bytes(b"x")

    probe.mp.setattr(probe.w2a, "_probe_stufe", stufe)
    code, out, err = probe.lauf()
    assert code == 3 and "SQLite legt Zwischendateien an" in err
    assert (probe.leer / "etilqs_erfunden").exists()


def test_messprobe_tmpdir_anzahl_aendert_sich_exit_3(probe):
    probe.mp.setattr(probe.w2a, "_probe_stufe",
                     lambda mib: (probe.tmpdir / "neu.tmp").write_bytes(b"x"))
    code, out, err = probe.lauf()
    assert code == 3
    assert "moeglicherweise Zwischendatei ausserhalb des Probeordners" in err
    assert (probe.tmpdir / "neu.tmp").exists()      # nichts wird geloescht


def _zaehlung_ausfall(probe, ziel_pfad, ab_stufe):
    """``_eintraege_zaehlen`` liefert fuer ``ziel_pfad`` ``None`` — vor (``ab_stufe`` False) oder
    nach der ersten Stufe (True). Gibt die Liste der gestarteten Stufen zurueck."""
    echt = probe.w2a._eintraege_zaehlen
    zustand = {"nach": False}
    stufen = []

    def stufe(mib):
        stufen.append(mib)
        zustand["nach"] = True

    def zaehlen(pfad):
        if str(pfad) == str(ziel_pfad) and zustand["nach"] == ab_stufe:
            return None
        return echt(pfad)

    probe.mp.setattr(probe.w2a, "_probe_stufe", stufe)
    probe.mp.setattr(probe.w2a, "_eintraege_zaehlen", zaehlen)
    return stufen


def test_messprobe_probeordner_nach_stufe_nicht_pruefbar_exit_3(probe):
    stufen = _zaehlung_ausfall(probe, probe.leer, ab_stufe=True)
    code, out, err = probe.lauf()
    assert code == 3 and "Probeordner nicht pruefbar" in err
    assert stufen == [1]                              # keine weitere Stufe
    assert "Zwischendatei: keine" not in out + err and "Obergrenze" not in out


def test_messprobe_probeordner_vor_der_probe_nicht_pruefbar_exit_3(probe):
    stufen = _zaehlung_ausfall(probe, probe.leer, ab_stufe=False)
    code, out, err = probe.lauf()
    assert code == 3 and "Probeordner nicht pruefbar" in err
    assert stufen == [] and "Zwischendatei: keine" not in out + err


def test_messprobe_tmpdir_nach_stufe_nicht_pruefbar_exit_3(probe):
    stufen = _zaehlung_ausfall(probe, probe.tmpdir, ab_stufe=True)
    code, out, err = probe.lauf()
    assert code == 3 and "TMPDIR nicht pruefbar" in err
    assert stufen == [1] and "Zwischendatei: keine" not in out + err


def test_messprobe_tmpdir_nicht_pruefbar_exit_3(probe):
    shutil.rmtree(probe.tmpdir)
    code, out, err = probe.lauf()
    assert code == 3 and "TMPDIR nicht pruefbar" in err


def test_messprobe_temp_store_nicht_2_exit_3_ohne_abfrage(probe):
    protokoll = []
    echt = probe.w2a._verbinden
    probe.mp.setattr(probe.w2a, "_verbinden",
                     lambda *a, **k: VerbindungSpy(echt(*a, **k), protokoll,
                                                   {"PRAGMA TEMP_STORE;": 0, "PRAGMA TEMP_STORE": 0}))
    code, out, err = probe.lauf()
    assert code == 3 and "SQLite dieses Geraets kann nicht nur im Speicher arbeiten" in err
    assert protokoll and all(s.strip().upper().startswith("PRAGMA") for s in protokoll)
    assert not any("Stufe" in z for z in out.splitlines())


def test_messprobe_kompilieroption_temp_store_0_exit_3_ohne_abfrage(probe):
    protokoll = []
    echt = probe.w2a._verbinden
    probe.mp.setattr(probe.w2a, "_verbinden",
                     lambda *a, **k: VerbindungSpy(echt(*a, **k), protokoll,
                                                   {"PRAGMA COMPILE_OPTIONS": "TEMP_STORE=0"}))
    code, out, err = probe.lauf()
    assert code == 3 and "nicht nur im Speicher arbeiten" in err
    assert all(s.strip().upper().startswith("PRAGMA") for s in protokoll)


def test_messprobe_temp_store_1_kompilieroption_laeuft(probe):
    echt = probe.w2a._verbinden
    probe.mp.setattr(probe.w2a, "_verbinden",
                     lambda *a, **k: VerbindungSpy(echt(*a, **k), [],
                                                   {"PRAGMA COMPILE_OPTIONS": "TEMP_STORE=1"}))
    code, out, err = probe.lauf()
    assert code == 0, err


def test_messprobe_reihenfolge_pragmas_vor_abfragen_und_abfragen_erzwingen_zwischenspeicher(probe):
    verbindungen = []
    echt = probe.w2a._verbinden

    def verbinden(*a, **k):
        spy = VerbindungSpy(echt(*a, **k), [])
        verbindungen.append(spy)
        return spy

    probe.mp.setattr(probe.w2a, "_verbinden", verbinden)
    code, out, err = probe.lauf(stufen="1")
    assert code == 0, err
    assert len(verbindungen) >= 2
    for v in verbindungen:
        erste_daten = next((i for i, s in enumerate(v.protokoll)
                            if not s.strip().upper().startswith("PRAGMA")), len(v.protokoll))
        vorher = [s.upper() for s in v.protokoll[:erste_daten]]
        assert any("TEMP_STORE=MEMORY" in s.replace(" ", "") for s in vorher)
        assert any(s.replace(" ", "").endswith("TEMP_STORE") or s.strip().upper().endswith("TEMP_STORE;")
                   for s in vorher)
        assert any("COMPILE_OPTIONS" in s for s in vorher)
    letzte = verbindungen[-1].protokoll
    gesamt = " ".join(letzte).upper()
    for baustein in ("ORDER BY", "GROUP BY", "DISTINCT", "IN (SELECT"):
        assert baustein in gesamt, baustein
    assert any("QUERY_ONLY=ON" in s.replace(" ", "").upper() for s in letzte)


def test_messprobe_stufe_abgebrochen_spaetere_stufe(probe):
    def stufe(mib):
        if mib == 2:
            raise MemoryError("Zaunstein")

    probe.mp.setattr(probe.w2a, "_probe_stufe", stufe)
    code, out, err = probe.lauf()
    assert code == 0
    assert "Stufe 1 MiB: ok" in out and "Stufe 2 MiB: abgebrochen" in out
    assert "Obergrenze: 1 MiB" in out and "Zaunstein" not in out + err


def test_messprobe_erste_stufe_abgebrochen_exit_1(probe):
    def stufe(mib):
        raise RuntimeError("Zaunstein")

    probe.mp.setattr(probe.w2a, "_probe_stufe", stufe)
    code, out, err = probe.lauf()
    assert code == 1 and "keine Stufe erfolgreich" in out + err
    assert "Zaunstein" not in out + err and list(probe.leer.iterdir()) == []


def test_messprobe_python_zu_alt_exit_3(probe):
    probe.mp.setattr(probe.w2a, "_python_version", lambda: (3, 10))
    spy = SchreibSpy().installieren(probe.mp)
    code, _, err = probe.lauf()
    assert code == 3 and spy.mkdirs == []


def test_messprobe_ohne_resource_exit_3(probe):
    probe.mp.setitem(sys.modules, "resource", None)       # import -> ImportError
    spy = SchreibSpy().installieren(probe.mp)
    code, _, err = probe.lauf()
    assert code == 3 and "resource" in err and spy.mkdirs == []


@pytest.mark.parametrize("stufen", ["", "x", "0", "-1", "2,1", "1,1", "1,,2", "1.5",
                                    "1,2,3,4,5,6,7,8,9", "99999"])
def test_messprobe_stufen_ungueltig_exit_2(probe, stufen):
    spy = SchreibSpy().installieren(probe.mp)
    code, _, _ = probe.lauf(stufen=stufen)
    assert code == 2 and spy.mkdirs == []


def test_messprobe_mit_fuer_teil_b_ist_exit_2(probe):
    code, _, _ = probe.lauf("--fuer-teil-b")
    assert code == 2


def test_messprobe_ohne_option_legt_keinen_ordner_an(umg):
    spy = SchreibSpy().installieren(umg.mp)
    umg.lauf()
    assert spy.mkdirs == []


# ═══════════════════════════════════════════════════════════════════════════
# 3. Waechter (AST) und frischer Prozess
# ═══════════════════════════════════════════════════════════════════════════

def _baum():
    return ast.parse(WERKZEUG.read_text(encoding="utf-8"))


def test_waechter_kopf_import_sys_und_kein_bytecode():
    koerper = list(_baum().body)
    if (isinstance(koerper[0], ast.Expr) and isinstance(koerper[0].value, ast.Constant)
            and isinstance(koerper[0].value.value, str)):
        koerper = koerper[1:]
    erste, zweite = koerper[0], koerper[1]
    assert isinstance(erste, ast.Import) and [a.name for a in erste.names] == ["sys"]
    assert (isinstance(zweite, ast.Assign) and ast.unparse(zweite.targets[0]) == "sys.dont_write_bytecode"
            and isinstance(zweite.value, ast.Constant) and zweite.value.value is True)
    for knoten in ast.walk(ast.parse(WERKZEUG.read_text(encoding="utf-8"))):
        if isinstance(knoten, (ast.Import, ast.ImportFrom)) and knoten.lineno < zweite.lineno:
            assert knoten.lineno == erste.lineno


def test_waechter_kein_raise_mit_ausnahme_im_except():
    for handler in ast.walk(_baum()):
        if isinstance(handler, ast.ExceptHandler):
            for stmt in handler.body:
                for k in ast.walk(stmt):
                    assert not (isinstance(k, ast.Raise) and k.exc is not None), k.lineno


def test_waechter_keine_verbotenen_schreib_und_loeschwege():
    verboten_attr = {"rename", "renames", "remove", "unlink", "rmdir", "rmtree", "removedirs",
                     "move", "replace", "makedirs", "mkstemp", "mkdtemp", "NamedTemporaryFile",
                     "TemporaryFile", "TemporaryDirectory", "copy", "copy2", "copyfile",
                     "copytree", "symlink", "link", "chmod", "write_text", "write_bytes"}
    for k in ast.walk(_baum()):
        if isinstance(k, ast.Attribute):
            assert k.attr not in verboten_attr, (k.attr, k.lineno)
        if isinstance(k, ast.Import):
            assert not {a.name for a in k.names} & {"shutil", "tempfile", "wa_crypt_tools"}
        if isinstance(k, ast.ImportFrom):
            assert (k.module or "").split(".")[0] not in {"shutil", "tempfile", "wa_crypt_tools"}


def test_waechter_open_nur_lesend_und_mkdir_nur_an_einer_stelle():
    mkdirs = 0
    for k in ast.walk(_baum()):
        if isinstance(k, ast.Call) and isinstance(k.func, ast.Name) and k.func.id == "open":
            modus = k.args[1] if len(k.args) > 1 else None
            assert isinstance(modus, ast.Constant) and modus.value == "rb", k.lineno
        if isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute) and k.func.attr == "mkdir":
            mkdirs += 1
    assert mkdirs == 1            # eine einzige Stelle, die beide Ordner anlegt


def test_waechter_gegenprobe_findet_raise_im_handler(tmp_path):
    datei = tmp_path / "x.py"
    datei.write_text("def f():\n    try:\n        pass\n    except Exception:\n"
                     "        raise ValueError('x')\n", encoding="utf-8")
    handler = [h for h in ast.walk(ast.parse(datei.read_text())) if isinstance(h, ast.ExceptHandler)][0]
    assert any(isinstance(k, ast.Raise) and k.exc is not None
               for s in handler.body for k in ast.walk(s))


def _sauberes_env():
    return {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}


def test_frischer_prozess_help_hinterlaesst_nichts(tmp_path):
    kopie = tmp_path / "kopie"
    kopie.mkdir()
    shutil.copy(WERKZEUG, kopie / WERKZEUG.name)
    lauf = subprocess.run([sys.executable, str(kopie / WERKZEUG.name), "--help"],
                          capture_output=True, text=True, env=_sauberes_env(), cwd=str(tmp_path))
    assert lauf.returncode == 0, lauf.stderr
    assert sorted(p.name for p in kopie.rglob("*")) == [WERKZEUG.name]


def test_import_setzt_das_flag_und_fremde_module_bekommen_kein_pyc(tmp_path):
    """Die Datei des Werkzeugs selbst wird schon VOR dem Lauf des Moduls uebersetzt (das ist
    bei jedem Python so); das Flag schuetzt alles, was danach importiert wird."""
    kopie = tmp_path / "kopie"
    kopie.mkdir()
    shutil.copy(WERKZEUG, kopie / WERKZEUG.name)
    (kopie / "hilfsmodul_erfunden.py").write_text("WERT = 1\n", encoding="utf-8")
    lauf_ = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, sys.argv[1]); "
         "assert sys.dont_write_bytecode is False; import whatsapp_sicherung_pruefen; "
         "assert sys.dont_write_bytecode is True; import hilfsmodul_erfunden",
         str(kopie)], capture_output=True, text=True, env=_sauberes_env(), cwd=str(tmp_path))
    assert lauf_.returncode == 0, lauf_.stderr
    assert not [p.name for p in kopie.rglob("*") if p.name.startswith("hilfsmodul_erfunden")
                and p.suffix == ".pyc"]



def test_frischer_prozess_messprobe_nur_erlaubte_ordner(tmp_path):
    kopie = tmp_path / "kopie"
    kopie.mkdir()
    shutil.copy(WERKZEUG, kopie / WERKZEUG.name)
    lib = tmp_path / "lib"                    # Attrappe fuer ``resource`` (Windows kennt es nicht)
    lib.mkdir()
    (lib / "resource.py").write_text(
        "import types\nRUSAGE_SELF = 0\n"
        "def getrusage(w):\n    return types.SimpleNamespace(ru_maxrss=100000)\n",
        encoding="utf-8")
    foto = tmp_path / "foto_sortierung"
    foto.mkdir()
    tmpdir = tmp_path / "tmp_orig"
    tmpdir.mkdir()
    env = _sauberes_env()
    env["PYTHONPATH"] = str(lib)
    env["TMPDIR"] = str(tmpdir)
    env.pop("SQLITE_TMPDIR", None)
    lauf = subprocess.run(
        [sys.executable, str(kopie / WERKZEUG.name), "--messprobe", "--stufen", "1",
         "--arbeitsordner", str(foto), "--datenbank-ordner", str(tmp_path / "nein"),
         "--schluessel", str(tmp_path / "nein.key")],
        capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert sorted(p.name for p in kopie.rglob("*")) == [WERKZEUG.name]
    neu = sorted(str(p.relative_to(foto)) for p in foto.rglob("*"))
    assert neu == ["whatsapp", os.path.join("whatsapp", "messprobe_leer")]
    assert list(tmpdir.iterdir()) == []


@pytest.mark.parametrize("modus", ["import_mit_b", "skriptstart_mit_b", "skriptstart_ohne_b"])
def test_bytecode_grenze_beide_startarten(tmp_path, modus):
    """Skriptstart (mit und ohne -B) und Import mit -B legen weder __pycache__ noch .pyc an."""
    kopie = tmp_path / "kopie"
    kopie.mkdir()
    shutil.copy(WERKZEUG, kopie / WERKZEUG.name)
    if modus == "import_mit_b":
        argv = [sys.executable, "-B", "-c", "import %s" % WERKZEUG.stem]
    else:
        argv = [sys.executable] + (["-B"] if modus == "skriptstart_mit_b" else []) + [
            str(kopie / WERKZEUG.name), "--help"]
    env = _sauberes_env()
    env["PYTHONPATH"] = str(kopie)
    lauf_ = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=str(kopie))
    assert lauf_.returncode == 0, lauf_.stderr
    assert sorted(p.name for p in kopie.rglob("*")) == [WERKZEUG.name]


# ── Audit-Hook vor dem Import (Nachbesserung Befund 2) ──────────────────────

KIND_SKRIPT = r'''
import os
import sys

ereignisse = {"schreib": [], "mkdir": [], "sonst": [], "connect": []}
SCHREIB_FLAGS = (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC)
NAMEN = {
    "os.rename": "rename", "os.remove": "remove", "os.rmdir": "rmdir",
    "os.symlink": "symlink", "os.link": "link", "os.truncate": "truncate",
    "os.chmod": "chmod", "os.chown": "chown", "os.utime": "utime", "os.mkfifo": "mkfifo",
    "tempfile.mkstemp": "mkstemp", "tempfile.mkdtemp": "mkdtemp",
}


def haken(ereignis, args):
    if ereignis == "open":
        pfad, modus, flags = args
        modus = modus if isinstance(modus, str) else ""
        flags = flags if isinstance(flags, int) else 0
        if any(c in modus for c in "wax+") or (flags & SCHREIB_FLAGS):
            ereignisse["schreib"].append(["open", str(pfad), modus, flags])
    elif ereignis == "os.mkdir":
        ereignisse["mkdir"].append(str(args[0]))
    elif ereignis == "sqlite3.connect":
        ereignisse["connect"].append(str(args[0]))
    elif ereignis in NAMEN or ereignis.startswith("shutil."):
        ereignisse["sonst"].append([ereignis, [str(a) for a in args[:2]]])


sys.addaudithook(haken)          # VOR dem Import des Werkzeugs und all seiner Importe

import contextlib
import io
import json

sys.path.insert(0, sys.argv[1])
import whatsapp_sicherung_pruefen as werkzeug        # noqa: E402

ausgabe, fehler = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(ausgabe), contextlib.redirect_stderr(fehler):
    code = werkzeug.main(sys.argv[2:])
print(json.dumps({"code": code, "ereignisse": ereignisse, "out": ausgabe.getvalue(),
                  "err": fehler.getvalue(), "bytecode": sys.dont_write_bytecode}))
'''


def _kind_lauf(tmp_path, vorhanden):
    """Frischer ``python -B``-Prozess; Audit-Hook sitzt vor dem Import des Werkzeugs."""
    kopie = tmp_path / "kopie"
    kopie.mkdir()
    shutil.copy(WERKZEUG, kopie / WERKZEUG.name)
    lib = tmp_path / "lib"                    # Attrappe fuer ``resource`` (Windows kennt es nicht)
    lib.mkdir()
    (lib / "resource.py").write_text(
        "import types\nRUSAGE_SELF = 0\n"
        "def getrusage(w):\n    return types.SimpleNamespace(ru_maxrss=100000)\n",
        encoding="utf-8")
    foto = tmp_path / "foto_sortierung"
    foto.mkdir()
    if vorhanden:
        (foto / "whatsapp" / "messprobe_leer").mkdir(parents=True)
    tmpdir = tmp_path / "tmp_orig"
    tmpdir.mkdir()
    skript = tmp_path / "kind.py"
    skript.write_text(KIND_SKRIPT, encoding="utf-8")
    env = _sauberes_env()
    env["PYTHONPATH"] = str(lib)
    env["TMPDIR"] = str(tmpdir)
    env.pop("SQLITE_TMPDIR", None)
    lauf_ = subprocess.run(
        [sys.executable, "-B", str(skript), str(kopie), "--messprobe", "--stufen", "1,2",
         "--arbeitsordner", str(foto), "--datenbank-ordner", str(tmp_path / "nein"),
         "--schluessel", str(tmp_path / "nein.key")],
        capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert lauf_.returncode == 0, lauf_.stdout + lauf_.stderr
    import json
    return json.loads(lauf_.stdout.strip().splitlines()[-1]), foto, kopie


@pytest.mark.parametrize("vorhanden", [False, True])
def test_audit_hook_vor_dem_import_messprobe_schreibt_nur_die_zwei_ordner(tmp_path, vorhanden):
    """Plan: Schreibueberwachung einschliesslich aller Importe - der Hook steht im frischen
    Prozess VOR ``import whatsapp_sicherung_pruefen``."""
    bericht, foto, kopie = _kind_lauf(tmp_path, vorhanden)
    assert bericht["code"] == 0, bericht["out"] + bericht["err"]
    assert bericht["bytecode"] is True
    ereignisse = bericht["ereignisse"]
    assert ereignisse["schreib"] == [], ereignisse["schreib"]      # kein open/os.open zum Schreiben
    assert ereignisse["sonst"] == [], ereignisse["sonst"]          # kein rename/remove/shutil/tempfile ...
    erlaubt = [] if vorhanden else [str(foto / "whatsapp"), str(foto / "whatsapp" / "messprobe_leer")]
    assert ereignisse["mkdir"] == erlaubt
    assert set(ereignisse["connect"]) == {":memory:"}              # SQLite nur im Speicher
    assert sorted(p.name for p in kopie.rglob("*")) == [WERKZEUG.name]
    assert sorted(str(p.relative_to(foto)) for p in foto.rglob("*")) == [
        "whatsapp", os.path.join("whatsapp", "messprobe_leer")]


def test_audit_hook_gegenprobe_erkennt_schreibzugriffe(tmp_path):
    """Der Hook im Kindprozess meldet echte Schreibwege (sonst waere der Test blind)."""
    skript = tmp_path / "gegenprobe.py"
    ziel = tmp_path / "gegen"
    skript.write_text(
        KIND_SKRIPT.split("sys.addaudithook(haken)")[0] + "sys.addaudithook(haken)\n"
        "import json\nos.mkdir(sys.argv[1])\n"
        "open(os.path.join(sys.argv[1], 'a.txt'), 'w').close()\n"
        "fd = os.open(os.path.join(sys.argv[1], 'b.bin'), os.O_WRONLY | os.O_CREAT)\nos.close(fd)\n"
        "os.rename(os.path.join(sys.argv[1], 'b.bin'), os.path.join(sys.argv[1], 'c.bin'))\n"
        "print(json.dumps(ereignisse))\n", encoding="utf-8")
    lauf_ = subprocess.run([sys.executable, "-B", str(skript), str(ziel)],
                           capture_output=True, text=True, env=_sauberes_env(), cwd=str(tmp_path))
    assert lauf_.returncode == 0, lauf_.stderr
    import json
    bericht = json.loads(lauf_.stdout.strip().splitlines()[-1])
    assert bericht["mkdir"] == [str(ziel)]
    assert len(bericht["schreib"]) == 2
    assert [e[0] for e in bericht["sonst"]] == ["os.rename"]
