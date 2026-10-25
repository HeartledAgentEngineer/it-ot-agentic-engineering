"""Pruefungen fuer W2 Teil A1: Strukturbeleg ``tools/whatsapp/aufbau_beleg.py`` (22.10.2026).

Plan: ``.hermes/plans/2026-10-22_whatsapp-w2.md`` (Fassung 16, Teil A1).

Die Testdatenbank ist erfunden (Namen, Nummern, Texte, Pfade) und absichtlich locker
gebaut (keine Primaerschluessel, keine Typen), damit Doppel, NULL, Text statt Zahl und
Bytes vorkommen koennen. Nichts davon darf in der Ausgabe stehen.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_aufbau_beleg.py -q
"""

from __future__ import annotations

import ast
import base64
import importlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parents[2]
WA = PROJEKT / "tools" / "whatsapp"
WERKZEUG = WA / "aufbau_beleg.py"

JETZT = 1_760_000_000          # fest, damit "heute + 1 Tag" reproduzierbar ist
SENSIBEL = ("Zaunstein", "boesewicht", "Passwort", "491700000000", "Vorname_Zaunstein",
            "Anna_Zaunstein", "Treffen", "IMG-", ".jpg", "Familie")

HASH_OK = base64.b64encode(bytes(range(32))).decode()
HASH_31 = base64.b64encode(bytes(range(31))).decode()
HASH_33 = base64.b64encode(bytes(range(33))).decode()
PFAD_MEDIA = "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Media/"
PFAD_ALT = "/storage/emulated/0/WhatsApp/Media/"


@pytest.fixture
def beleg(monkeypatch):
    monkeypatch.syspath_prepend(str(WA))
    modul = importlib.import_module("aufbau_beleg")
    monkeypatch.setattr(modul, "_jetzt", lambda: JETZT)
    return modul


def baue_db(pfad, ohne_spalte=None, ohne_tabelle=None):
    """Erfundene Datenbank. Erwartete Zaehlungen stehen in den Tests."""
    con = sqlite3.connect(str(pfad))
    # Spalten ohne Typ: SQLite speichert die Werte unveraendert (keine Affinitaet)
    tabellen = {
        "chat": ["_id", "Anna_Zaunstein"],
        "jid": ["_id", "user", "raw_string"],
        "message": ["_id", "chat_row_id", "timestamp", "from_me", "sender_jid_row_id",
                    "text_data"],
        "message_media": ["message_row_id", "chat_row_id", "file_path", "file_hash",
                          "file_size", "Vorname_Zaunstein"],
    }
    for name, spalten in tabellen.items():
        if name == ohne_tabelle:
            continue
        spalten = [s for s in spalten if f"{name}.{s}" != ohne_spalte]
        con.execute(f"CREATE TABLE {name} ({', '.join(spalten)})")
    namen = lambda t: [s for s in tabellen[t] if f"{t}.{s}" != ohne_spalte]  # noqa: E731

    def einfuegen(tabelle, zeilen):
        if tabelle == ohne_tabelle:
            return
        voll = tabellen[tabelle]
        vorhanden = namen(tabelle)
        for z in zeilen:
            wert = dict(zip(voll, z))
            con.execute(f"INSERT INTO {tabelle} ({', '.join(vorhanden)}) "
                        f"VALUES ({', '.join('?' * len(vorhanden))})",
                        [wert[s] for s in vorhanden])

    einfuegen("chat", [(1, "x"), (2, "x"), (3, "x"), (3, "x"), (0, "x"), (-5, "x")])
    einfuegen("jid", [(10, "Anna-Zaunstein", "491700000000@s.whatsapp.net"),
                      (11, "u", "r"), (12, "u", "r"), (None, "u", "r")])
    txt = "Treffen bei Familie_Zaunstein, Passwort ist boesewicht"
    einfuegen("message", [
        (1, 1, 1600000000000, 0, 10, txt),
        (2, 1, 1600000001000, 1, 0, txt),
        (3, 2, 1600000002000, 0, 11, txt),
        (4, 2, 1600000003, 2, None, txt),
        (5, 3, "abc", 0, 99, txt),
        (6, 9, 1100000000000, 1, None, txt),
        (7, None, 9999999999999, None, 12, txt),
        (8, 1, None, 0, -1, txt),
        (3, 2, 1600000004000, 0, 11, txt),
        (0, 1, 1600000005000, "x", 10, txt),
    ])
    einfuegen("message_media", [
        (1, 1, PFAD_MEDIA + "WhatsApp Images/IMG-20200101-WA0001.jpg", HASH_OK, 1000, "n"),
        (2, 1, PFAD_ALT + "WhatsApp Images/Sent/IMG-20200101-WA0002.jpg", HASH_OK, 2000, "n"),
        (3, 2, "Media/WhatsApp Images/Private/IMG-3.jpg", "", 3000, "n"),
        (4, 2, "Media/WhatsApp Images/sent/IMG-4.jpg", "kein base64!!", "x", "n"),
        (5, 3, "", None, None, "n"),
        (6, 7, "/sdcard/komisch/Foto.jpg", b"\x01" * 32, -1, "n"),
        (7, None, "Media/WhatsApp Images/Sub/Deep/IMG-7.jpg", HASH_31, 5, "n"),
        (1, 1, PFAD_MEDIA + "WhatsApp Video/VID-8.mp4", HASH_33, 7, "n"),
        (777, 1, "Media/WhatsApp Images/IMG-9-Zaunstein.jpg", HASH_OK, 8, "n"),
        (8, 1, b"/x", HASH_OK, 9, "n"),
    ])
    con.commit()
    con.close()
    return pfad


@pytest.fixture
def db(tmp_path):
    return baue_db(tmp_path / "msgstore.db")


def lauf(beleg, db, capsys):
    code = beleg.main([str(db)])
    aus = capsys.readouterr()
    return code, aus.out, aus.err


def zeile(text, praefix):
    treffer = [z for z in text.splitlines() if z.startswith(praefix + ":")]
    assert len(treffer) == 1, (praefix, treffer)
    return treffer[0]


def zahlen(text, praefix):
    rest = zeile(text, praefix)[len(praefix) + 1:].strip()
    ergebnis = {}
    for teil in rest.split(" · "):
        schluessel, wert = teil.rsplit(" ", 1)
        ergebnis[schluessel] = int(wert)
    return ergebnis


# ═══════════════════════════════════════════════════════════════════════════
# 1. Zaehlungen je Klasse
# ═══════════════════════════════════════════════════════════════════════════

def test_tabellen_und_weitere_spalten(beleg, db, capsys):
    code, out, err = lauf(beleg, db, capsys)
    assert code == 0, out + err
    assert zahlen(out, "Tabelle message") == {"Zeilen": 10, "weitere Spalten": 1}
    assert zahlen(out, "Tabelle message_media") == {"Zeilen": 10, "weitere Spalten": 1}
    assert zahlen(out, "Tabelle chat") == {"Zeilen": 6, "weitere Spalten": 1}
    assert zahlen(out, "Tabelle jid") == {"Zeilen": 4, "weitere Spalten": 2}
    for tabelle, spalten in (("message", ("_id", "chat_row_id", "timestamp", "from_me",
                                           "sender_jid_row_id")),
                             ("message_media", ("message_row_id", "chat_row_id", "file_path",
                                                "file_hash", "file_size")),
                             ("chat", ("_id",)), ("jid", ("_id",))):
        for s in spalten:
            assert f"vorhanden: {tabelle}.{s}" in out.splitlines()
    assert "fehlt:" not in out


def test_typverteilung_je_pflichtfeld(beleg, db, capsys):
    out = lauf(beleg, db, capsys)[1]
    def t(feld):
        z = zahlen(out, f"Typen {feld}")
        return {k: z[k] for k in ("int", "str", "bytes", "NULL", "sonst")}
    assert t("message._id") == dict(int=10, str=0, bytes=0, NULL=0, sonst=0)
    assert t("message.chat_row_id") == dict(int=9, str=0, bytes=0, NULL=1, sonst=0)
    assert t("message.timestamp") == dict(int=8, str=1, bytes=0, NULL=1, sonst=0)
    assert t("message.from_me") == dict(int=8, str=1, bytes=0, NULL=1, sonst=0)
    assert t("message.sender_jid_row_id") == dict(int=8, str=0, bytes=0, NULL=2, sonst=0)
    assert t("message_media.message_row_id") == dict(int=10, str=0, bytes=0, NULL=0, sonst=0)
    assert t("message_media.chat_row_id") == dict(int=9, str=0, bytes=0, NULL=1, sonst=0)
    assert t("message_media.file_path") == dict(int=0, str=9, bytes=1, NULL=0, sonst=0)
    assert t("message_media.file_hash") == dict(int=0, str=8, bytes=1, NULL=1, sonst=0)
    assert t("message_media.file_size") == dict(int=8, str=1, bytes=0, NULL=1, sonst=0)
    assert t("chat._id") == dict(int=6, str=0, bytes=0, NULL=0, sonst=0)
    assert t("jid._id") == dict(int=3, str=0, bytes=0, NULL=1, sonst=0)


def test_kennungen_kleiner_gleich_null_und_doppelte(beleg, db, capsys):
    out = lauf(beleg, db, capsys)[1]
    assert zahlen(out, "Kennungen message._id") == {"kleiner_gleich_0": 1, "doppelt": 1}
    assert zahlen(out, "Kennungen chat._id") == {"kleiner_gleich_0": 2, "doppelt": 1}
    assert zahlen(out, "Kennungen jid._id") == {"kleiner_gleich_0": 0, "doppelt": 0}
    assert zahlen(out, "Kennungen message_media.message_row_id") == {
        "kleiner_gleich_0": 0, "doppelt": 1}
    assert zahlen(out, "Kennungen message.chat_row_id")["kleiner_gleich_0"] == 0
    assert zahlen(out, "Kennungen message_media.chat_row_id")["kleiner_gleich_0"] == 0
    assert zahlen(out, "Kennungen message.sender_jid_row_id")["kleiner_gleich_0"] == 2


def test_zeit_stellenzahl_und_bereich(beleg, db, capsys):
    out = lauf(beleg, db, capsys)[1]
    assert zahlen(out, "Zeit message.timestamp") == {
        "10_Stellen": 1, "13_Stellen": 7, "sonst": 2, "ausserhalb": 3}


def test_from_me_verteilung(beleg, db, capsys):
    out = lauf(beleg, db, capsys)[1]
    assert zahlen(out, "from_me") == {"0": 5, "1": 2, "sonst": 3}


def test_file_path_klassen_und_unterordner(beleg, db, capsys):
    out = lauf(beleg, db, capsys)[1]
    assert zahlen(out, "file_path") == {"absolut_media": 2, "absolut_alt": 1, "relativ": 4,
                                        "leer": 1, "sonst": 2}
    assert zahlen(out, "Images_Unterordner") == {"Ebene-0": 2, "Sent": 2, "Private": 1,
                                                 "sonst": 1, "ohne_Images": 1}


def test_file_hash_klassen(beleg, db, capsys):
    out = lauf(beleg, db, capsys)[1]
    assert zahlen(out, "file_hash") == {"leer": 2, "base64_32": 4, "sonst": 4}


def test_verknuepfung(beleg, db, capsys):
    out = lauf(beleg, db, capsys)[1]
    assert zahlen(out, "Verknuepfung") == {"ohne_message": 1, "chat_abweichend": 2,
                                           "chat_fehlt": 1, "jid_fehlt": 1}


def test_speicherbetrieb_und_version_werden_gemeldet(beleg, db, capsys):
    out = lauf(beleg, db, capsys)[1]
    assert "SQLite-Version: " + sqlite3.sqlite_version in out
    assert "temp_store 2" in zeile(out, "Speicherbetrieb")
    assert "TEMP_STORE=0 gesetzt: nein" in zeile(out, "Speicherbetrieb")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Datenschutz: keine Werte, keine Namen, keine Pfade
# ═══════════════════════════════════════════════════════════════════════════

def test_ausgabe_enthaelt_keine_erfundenen_werte_oder_namen(beleg, db, capsys, tmp_path):
    code, out, err = lauf(beleg, db, capsys)
    text = out + err
    for wort in SENSIBEL + (str(tmp_path), "msgstore", HASH_OK[:12]):
        assert wort not in text, wort


def test_zusaetzliche_spalte_mit_sensiblem_namen_nur_als_anzahl(beleg, tmp_path, capsys):
    pfad = baue_db(tmp_path / "x.db")
    con = sqlite3.connect(str(pfad))
    con.execute("ALTER TABLE message ADD COLUMN Vorname_Zaunstein_Passwort TEXT")
    con.commit()
    con.close()
    code, out, err = lauf(beleg, pfad, capsys)
    assert code == 0
    assert zahlen(out, "Tabelle message")["weitere Spalten"] == 2
    assert "Zaunstein" not in out + err and "Passwort" not in out + err


def test_fehlende_spalte_wird_als_fehlt_zeile_gemeldet(beleg, tmp_path, capsys):
    pfad = baue_db(tmp_path / "x.db", ohne_spalte="message.timestamp")
    code, out, err = lauf(beleg, pfad, capsys)
    assert code == 0
    assert "fehlt: message.timestamp" in out.splitlines()
    assert "vorhanden: message._id" in out.splitlines()
    assert "Zeit message.timestamp" not in out
    assert zahlen(out, "Tabelle message")["weitere Spalten"] == 1
    assert "Zaunstein" not in out + err


def test_fehlende_tabelle_wird_gemeldet(beleg, tmp_path, capsys):
    pfad = baue_db(tmp_path / "x.db", ohne_tabelle="jid")
    code, out, err = lauf(beleg, pfad, capsys)
    assert code == 0
    assert "fehlt: jid._id" in out.splitlines()
    assert "Tabelle jid: Tabelle fehlt" in out.splitlines()


def test_leere_tabellen_liefern_nullen(beleg, tmp_path, capsys):
    con = sqlite3.connect(str(tmp_path / "leer.db"))
    for t, s in (("message", "_id, chat_row_id, timestamp, from_me, sender_jid_row_id"),
                 ("chat", "_id"), ("jid", "_id"),
                 ("message_media", "message_row_id, chat_row_id, file_path, file_hash, file_size")):
        con.execute(f"CREATE TABLE {t} ({s})")
    con.commit()
    con.close()
    code, out, _ = lauf(beleg, tmp_path / "leer.db", capsys)
    assert code == 0 and zahlen(out, "Tabelle message")["Zeilen"] == 0
    assert zahlen(out, "file_hash") == {"leer": 0, "base64_32": 0, "sonst": 0}


# ═══════════════════════════════════════════════════════════════════════════
# 3. Nur lesend
# ═══════════════════════════════════════════════════════════════════════════

def test_datenbank_bleibt_unveraendert_und_ohne_nebendateien(beleg, db, capsys):
    roh = db.read_bytes()
    mtime = os.stat(db).st_mtime_ns
    vorher = sorted(p.name for p in db.parent.iterdir())
    assert lauf(beleg, db, capsys)[0] == 0
    assert db.read_bytes() == roh and os.stat(db).st_mtime_ns == mtime
    assert sorted(p.name for p in db.parent.iterdir()) == vorher
    assert not any(n.endswith(("-wal", "-shm", "-journal")) for n in os.listdir(db.parent))


def test_schreibversuch_ueber_die_verbindung_scheitert(beleg, db):
    con = beleg.verbindung_oeffnen(str(db))
    with pytest.raises(sqlite3.OperationalError):
        con.execute("INSERT INTO chat (_id) VALUES (99)")
    with pytest.raises(sqlite3.OperationalError):
        con.execute("CREATE TABLE neu (a)")
    con.close()
    con = sqlite3.connect(str(db))
    assert con.execute("SELECT COUNT(*) FROM chat").fetchone()[0] == 6
    con.close()


def test_uri_wird_mit_ro_und_immutable_geoeffnet(beleg, db, monkeypatch):
    gesehen = []
    echt = beleg._verbinden

    def verbinden(ziel, **kw):
        gesehen.append((ziel, kw))
        return echt(ziel, **kw)

    monkeypatch.setattr(beleg, "_verbinden", verbinden)
    beleg.verbindung_oeffnen(str(db)).close()
    ziel, kw = gesehen[0]
    assert ziel.startswith("file:") and ziel.endswith("?mode=ro&immutable=1")
    assert kw.get("uri") is True


@pytest.mark.parametrize("nach", ["fehlt", "ordner", "link"])
def test_keine_regulaere_datei_exit_3_ohne_pfad(beleg, db, capsys, tmp_path, monkeypatch, nach):
    ziel = tmp_path / "nichts.db"
    if nach == "ordner":
        ziel.mkdir()
    if nach == "link":
        ziel = db
        monkeypatch.setattr(beleg, "_ist_link", lambda p: True)
    code, out, err = lauf(beleg, ziel, capsys)
    assert code == 3 and "Datenbankdatei" in err
    assert str(tmp_path) not in out + err and out == ""


def test_keine_sqlite_datei_exit_1_mit_fester_zeile(beleg, tmp_path, capsys):
    pfad = tmp_path / "zufall.db"
    pfad.write_bytes(b"Zaunstein-kein-sqlite" * 200)
    code, out, err = lauf(beleg, pfad, capsys)
    assert code == 1 and "Datenbank nicht lesbar" in err
    assert "Zaunstein" not in out + err


def test_ausnahmetext_der_datenbank_erscheint_nicht(beleg, db, capsys, monkeypatch):
    echt = beleg._verbinden

    class Kaputt:
        def __init__(self, con):
            self._c = con

        def execute(self, sql, *a):
            if sql.upper().startswith("SELECT"):
                raise sqlite3.OperationalError("Zaunstein Passwort boesewicht")
            return self._c.execute(sql, *a)

        def __getattr__(self, n):
            return getattr(self._c, n)

    monkeypatch.setattr(beleg, "_verbinden", lambda *a, **k: Kaputt(echt(*a, **k)))
    code, out, err = lauf(beleg, db, capsys)
    assert code == 1
    assert "Zaunstein" not in out + err and "boesewicht" not in out + err


# ═══════════════════════════════════════════════════════════════════════════
# 4. Speicherbetrieb verbindlich vor jeder Datenabfrage
# ═══════════════════════════════════════════════════════════════════════════

class VerbindungSpy:
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


def _mit_spy(beleg, monkeypatch, ersatz=None):
    protokoll = []
    echt = beleg._verbinden
    monkeypatch.setattr(beleg, "_verbinden",
                        lambda *a, **k: VerbindungSpy(echt(*a, **k), protokoll, ersatz))
    return protokoll


@pytest.mark.parametrize("ersatz", [
    {"PRAGMA TEMP_STORE": 0},
    {"PRAGMA TEMP_STORE": 1},
    {"PRAGMA COMPILE_OPTIONS": "TEMP_STORE=0"},
], ids=["temp_store_0", "temp_store_1", "kompilieroption_0"])
def test_kein_speicherbetrieb_exit_3_ohne_tabellenabfrage(beleg, db, capsys, monkeypatch, ersatz):
    protokoll = _mit_spy(beleg, monkeypatch, ersatz)
    code, out, err = lauf(beleg, db, capsys)
    assert code == 3
    assert "SQLite dieses Rechners kann nicht nur im Speicher arbeiten" in err
    assert protokoll and all(s.strip().upper().startswith("PRAGMA") for s in protokoll)
    assert not any("table_info" in s.lower() for s in protokoll)
    assert out == ""


def test_temp_store_1_kompilieroption_plus_pragma_laeuft(beleg, db, capsys, monkeypatch):
    protokoll = _mit_spy(beleg, monkeypatch, {"PRAGMA COMPILE_OPTIONS": "TEMP_STORE=1"})
    code, out, err = lauf(beleg, db, capsys)
    assert code == 0, err
    assert "TEMP_STORE=0 gesetzt: nein" in out


def test_pragmas_stehen_vor_der_ersten_datenabfrage(beleg, db, capsys, monkeypatch):
    protokoll = _mit_spy(beleg, monkeypatch)
    assert lauf(beleg, db, capsys)[0] == 0
    erste = next(i for i, s in enumerate(protokoll) if not s.strip().upper().startswith("PRAGMA"))
    vorher = " ".join(protokoll[:erste]).upper().replace(" ", "")
    for baustein in ("QUERY_ONLY=ON", "TEMP_STORE=MEMORY", "COMPILE_OPTIONS"):
        assert baustein in vorher
    # auch das Schema (table_info) wird erst nach der Speicherpruefung gelesen
    erst_info = next(i for i, x in enumerate(protokoll) if "TABLE_INFO" in x.upper())
    letzte_pruefung = max(i for i, x in enumerate(protokoll) if "COMPILE_OPTIONS" in x.upper())
    assert letzte_pruefung < erst_info


# ═══════════════════════════════════════════════════════════════════════════
# 5. Waechter und frischer Prozess
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
    assert (isinstance(zweite, ast.Assign)
            and ast.unparse(zweite.targets[0]) == "sys.dont_write_bytecode"
            and isinstance(zweite.value, ast.Constant) and zweite.value.value is True)
    for k in ast.walk(ast.parse(WERKZEUG.read_text(encoding="utf-8"))):
        if isinstance(k, (ast.Import, ast.ImportFrom)) and k.lineno < zweite.lineno:
            assert k.lineno == erste.lineno


def test_waechter_kein_raise_mit_ausnahme_im_except():
    for handler in ast.walk(_baum()):
        if isinstance(handler, ast.ExceptHandler):
            for stmt in handler.body:
                for k in ast.walk(stmt):
                    assert not (isinstance(k, ast.Raise) and k.exc is not None), k.lineno


def test_waechter_nur_lesen_kein_open_kein_schreib_oder_loeschweg():
    verboten = {"rename", "renames", "remove", "unlink", "rmdir", "rmtree", "move", "replace",
                "mkdir", "makedirs", "mkstemp", "mkdtemp", "write_text", "write_bytes",
                "copy", "copyfile", "chmod", "executescript", "executemany", "commit"}
    for k in ast.walk(_baum()):
        if isinstance(k, ast.Attribute):
            assert k.attr not in verboten, (k.attr, k.lineno)
        if isinstance(k, ast.Call) and isinstance(k.func, ast.Name):
            assert k.func.id != "open", k.lineno
        if isinstance(k, ast.Import):
            assert not {a.name for a in k.names} & {"shutil", "tempfile"}


def test_waechter_connect_nur_ueber_die_eine_stelle_mit_ro_immutable():
    quelle = WERKZEUG.read_text(encoding="utf-8")
    assert quelle.count("sqlite3.connect(") == 1
    assert "mode=ro&immutable=1" in quelle


def test_waechter_sql_nur_lesend():
    for k in ast.walk(_baum()):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            kopf = k.value.strip().split(" ")[0].upper() if k.value.strip() else ""
            assert kopf not in {"INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
                                "REPLACE", "VACUUM", "ATTACH"}, k.value


def _sauberes_env():
    return {k: v for k, v in os.environ.items() if k != "PYTHONDONTWRITEBYTECODE"}


def test_frischer_prozess_hinterlaesst_kein_pycache(tmp_path):
    kopie = tmp_path / "kopie"
    kopie.mkdir()
    shutil.copy(WERKZEUG, kopie / WERKZEUG.name)
    db = baue_db(tmp_path / "msgstore.db")
    for argv in (["--help"], [str(db)]):
        lauf_ = subprocess.run([sys.executable, str(kopie / WERKZEUG.name), *argv],
                               capture_output=True, text=True, env=_sauberes_env(),
                               cwd=str(tmp_path))
        assert lauf_.returncode == 0, lauf_.stderr
    assert sorted(p.name for p in kopie.rglob("*")) == [WERKZEUG.name]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["kopie", "msgstore.db"]


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
         "assert sys.dont_write_bytecode is False; import aufbau_beleg; "
         "assert sys.dont_write_bytecode is True; import hilfsmodul_erfunden",
         str(kopie)], capture_output=True, text=True, env=_sauberes_env(), cwd=str(tmp_path))
    assert lauf_.returncode == 0, lauf_.stderr
    assert not [p.name for p in kopie.rglob("*") if p.name.startswith("hilfsmodul_erfunden")
                and p.suffix == ".pyc"]



def test_aufruf_ohne_pfad_exit_2_ohne_echo(beleg, capsys):
    assert beleg.main([]) == 2
    assert beleg.main(["--unbekannt"]) == 2
    aus = capsys.readouterr()
    assert "unbekannt" not in aus.out + aus.err


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
import aufbau_beleg as werkzeug        # noqa: E402

ausgabe, fehler = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(ausgabe), contextlib.redirect_stderr(fehler):
    code = werkzeug.main(sys.argv[2:])
print(json.dumps({"code": code, "ereignisse": ereignisse, "out": ausgabe.getvalue(),
                  "err": fehler.getvalue(), "bytecode": sys.dont_write_bytecode}))
'''


def test_audit_hook_vor_dem_import_strukturbeleg_schreibt_nichts(tmp_path):
    """Frischer ``python -B``-Prozess, Hook VOR ``import aufbau_beleg``: kein einziger Schreibweg,
    SQLite wird nur schreibgeschuetzt (``mode=ro&immutable=1``) geoeffnet, keine Nebendateien."""
    import json
    kopie = tmp_path / "kopie"
    kopie.mkdir()
    shutil.copy(WERKZEUG, kopie / WERKZEUG.name)
    db = baue_db(tmp_path / "msgstore.db")
    vorher = (db.read_bytes(), db.stat().st_mtime_ns)
    skript = tmp_path / "kind.py"
    skript.write_text(KIND_SKRIPT, encoding="utf-8")
    lauf_ = subprocess.run([sys.executable, "-B", str(skript), str(kopie), str(db)],
                           capture_output=True, text=True, env=_sauberes_env(), cwd=str(tmp_path))
    assert lauf_.returncode == 0, lauf_.stdout + lauf_.stderr
    bericht = json.loads(lauf_.stdout.strip().splitlines()[-1])
    assert bericht["code"] == 0, bericht["out"] + bericht["err"]
    assert bericht["bytecode"] is True
    ereignisse = bericht["ereignisse"]
    assert ereignisse["schreib"] == [], ereignisse["schreib"]
    assert ereignisse["mkdir"] == [] and ereignisse["sonst"] == [], ereignisse
    assert len(ereignisse["connect"]) == 1
    assert "mode=ro" in ereignisse["connect"][0] and "immutable=1" in ereignisse["connect"][0]
    assert (db.read_bytes(), db.stat().st_mtime_ns) == vorher
    assert sorted(p.name for p in tmp_path.iterdir()) == ["kind.py", "kopie", "msgstore.db"]
    assert sorted(p.name for p in kopie.rglob("*")) == [WERKZEUG.name]
