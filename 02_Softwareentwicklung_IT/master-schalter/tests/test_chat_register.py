"""Tests für das Chat-Register – ausschließlich mit Attrappen unter `tmp_path`, nie mit echten Quellen."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_schalter import chat_register

JETZT = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
UUID_A = "11111111-1111-4111-8111-111111111111"
UUID_B = "22222222-2222-4222-8222-222222222222"
UUID_C = "33333333-3333-4333-8333-333333333333"
ECHT_SQLITE_CONNECT = sqlite3.connect


def _ms(zeit: datetime) -> int:
    return int(zeit.timestamp() * 1000)


def _vor(**kwargs) -> datetime:
    return JETZT - timedelta(**kwargs)


@pytest.fixture
def desktop(tmp_path, monkeypatch) -> Path:
    wurzel = tmp_path / "desktop"
    wurzel.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_DESKTOP", str(wurzel))
    return wurzel


@pytest.fixture
def projekte(tmp_path, monkeypatch) -> Path:
    wurzel = tmp_path / "projekte"
    wurzel.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_CLAUDE_PROJEKTE", str(wurzel))
    return wurzel


@pytest.fixture
def codex_pfad(tmp_path, monkeypatch) -> Path:
    pfad = tmp_path / "codex.sqlite"
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_STATE", str(pfad))
    return pfad


@pytest.fixture
def hermes_pfad(tmp_path, monkeypatch) -> Path:
    pfad = tmp_path / "hermes.db"
    monkeypatch.setenv("MASTER_SCHALTER_HERMES_STATE", str(pfad))
    return pfad


def desktop_datei(wurzel: Path, name: str, **felder) -> Path:
    ordner = wurzel / "konto" / "claude-code-sessions" / "unter"
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"local_{name}.json"
    pfad.write_text(json.dumps(felder), encoding="utf-8")
    return pfad


def cli_datei(wurzel: Path, kennung: str, zeilen: list[str], alter: timedelta = timedelta(hours=1),
              projekt: str = "proj") -> Path:
    ordner = wurzel / projekt
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"{kennung}.jsonl"
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    zeit = (JETZT - alter).timestamp()
    os.utime(pfad, (zeit, zeit))
    return pfad


def codex_db(pfad: Path, zeilen: list[tuple], mit_name: bool = False, spalten: str | None = None) -> None:
    with closing(ECHT_SQLITE_CONNECT(pfad)) as db:
        name = ", name TEXT" if mit_name else ""
        db.execute(spalten or f"CREATE TABLE threads (id TEXT, cwd TEXT, title TEXT, updated_at_ms INTEGER, "
                              f"archived INTEGER{name})")
        db.execute("CREATE TABLE messages (thread_id TEXT, inhalt TEXT)")
        db.execute("INSERT INTO messages VALUES ('x', 'GEHEIMER NACHRICHTENTEXT')")
        if spalten is None:
            marken = ", ".join("?" for _ in zeilen[0]) if zeilen else ""
            for zeile in zeilen:
                db.execute(f"INSERT INTO threads VALUES ({marken})", zeile)
        db.commit()


def hermes_db(pfad: Path, zeilen: list[tuple], erweitert: bool = True, spalten: str | None = None) -> None:
    with closing(ECHT_SQLITE_CONNECT(pfad)) as db:
        extra = ", last_activity_at REAL, archived INTEGER, hidden INTEGER" if erweitert else ""
        db.execute(spalten or f"CREATE TABLE sessions (id TEXT, source TEXT, title TEXT, cwd TEXT, "
                              f"started_at REAL{extra})")
        db.execute("CREATE TABLE messages (session_id TEXT, inhalt TEXT)")
        db.execute("INSERT INTO messages VALUES ('x', 'GEHEIMER NACHRICHTENTEXT')")
        if spalten is None:
            for zeile in zeilen:
                db.execute(f"INSERT INTO sessions VALUES ({', '.join('?' for _ in zeile)})", zeile)
        db.commit()


# --- Standardzustand ---------------------------------------------------------------

def test_alle_quellen_fehlen_ergibt_leeres_register():
    erg = chat_register.lesen(JETZT)
    assert erg.chats == ()
    assert erg.quellen == {"claude-desktop": "fehlt", "claude-cli": "fehlt", "codex": "fehlt",
                           "hermes": "fehlt", "agy": "fehlt"}


def test_naive_zeit_wird_als_utc_gelesen(desktop):
    desktop_datei(desktop, "a", cliSessionId=UUID_A, lastActivityAt=_ms(_vor(hours=1)))
    erg = chat_register.lesen(JETZT.replace(tzinfo=None))
    assert [c.kennung for c in erg.chats] == [UUID_A]


# --- Claude Desktop ------------------------------------------------------------------

def test_desktop_liest_nur_erlaubte_felder(desktop):
    desktop_datei(desktop, "a", cliSessionId=UUID_A, title="Mein\nTitel", cwd="C:/Arbeit",
                  lastActivityAt=_ms(_vor(hours=2)), nachricht="GEHEIM")
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["claude-desktop"] == "ok"
    (chat,) = erg.chats
    assert (chat.werkzeug, chat.kennung, chat.titel, chat.ordner, chat.quelle) == (
        "claude", UUID_A, "Mein Titel", "C:/Arbeit", "claude-desktop")
    assert chat.zuletzt == _vor(hours=2)
    assert "GEHEIM" not in repr(chat)


def test_desktop_titel_wird_auf_200_zeichen_gekuerzt(desktop):
    desktop_datei(desktop, "a", cliSessionId=UUID_A, title="x" * 500, lastActivityAt=_ms(_vor(hours=1)))
    assert len(chat_register.lesen(JETZT).chats[0].titel) == 200


def test_desktop_archiviert_ohne_kennung_und_ungueltige_kennung_werden_uebersprungen(desktop):
    zeit = _ms(_vor(hours=1))
    desktop_datei(desktop, "arch", cliSessionId=UUID_A, isArchived=True, lastActivityAt=zeit)
    desktop_datei(desktop, "ohne", title="t", lastActivityAt=zeit)
    desktop_datei(desktop, "boese", cliSessionId="../../etc", lastActivityAt=zeit)
    desktop_datei(desktop, "lang", cliSessionId="a" * 81, lastActivityAt=zeit)
    desktop_datei(desktop, "lf", cliSessionId="abc\n", lastActivityAt=zeit)
    desktop_datei(desktop, "gut", cliSessionId=UUID_B, isArchived=False, lastActivityAt=zeit)
    erg = chat_register.lesen(JETZT)
    assert [c.kennung for c in erg.chats] == [UUID_B]
    assert erg.quellen["claude-desktop"] == "ok"


def test_desktop_24_stunden_grenze(desktop):
    desktop_datei(desktop, "innen", cliSessionId=UUID_A, lastActivityAt=_ms(_vor(hours=23, minutes=59)))
    desktop_datei(desktop, "aussen", cliSessionId=UUID_B, lastActivityAt=_ms(_vor(hours=24, minutes=1)))
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == [UUID_A]


def test_desktop_zu_grosse_datei_wird_uebersprungen(desktop):
    desktop_datei(desktop, "gross", cliSessionId=UUID_A, lastActivityAt=_ms(_vor(hours=1)),
                  fuell="x" * (chat_register.DESKTOP_DATEI_MAX_BYTES + 10))
    desktop_datei(desktop, "klein", cliSessionId=UUID_B, lastActivityAt=_ms(_vor(hours=1)))
    erg = chat_register.lesen(JETZT)
    assert [c.kennung for c in erg.chats] == [UUID_B]
    assert erg.quellen["claude-desktop"] == "ok"


def test_desktop_kaputte_datei_ist_nicht_lesbar(desktop):
    ordner = desktop / "konto" / "claude-code-sessions"
    ordner.mkdir(parents=True)
    (ordner / "local_kaputt.json").write_text("{kein json", encoding="utf-8")
    erg = chat_register.lesen(JETZT)
    assert erg.chats == ()
    assert erg.quellen["claude-desktop"].startswith("nicht lesbar: ")
    assert "kein json" not in erg.quellen["claude-desktop"]


def test_desktop_eine_kaputte_datei_neben_guten_stoert_nicht(desktop):
    desktop_datei(desktop, "gut", cliSessionId=UUID_A, lastActivityAt=_ms(_vor(hours=1)))
    (desktop / "konto" / "claude-code-sessions" / "local_kaputt.json").write_text("[", encoding="utf-8")
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["claude-desktop"] == "ok"
    assert len(erg.chats) == 1


def test_desktop_gleiche_kennung_zweimal_gewinnt_die_juengere(desktop):
    desktop_datei(desktop, "alt", cliSessionId=UUID_A, title="alt", lastActivityAt=_ms(_vor(hours=5)))
    desktop_datei(desktop, "neu", cliSessionId=UUID_A, title="neu", lastActivityAt=_ms(_vor(hours=1)))
    (chat,) = chat_register.lesen(JETZT).chats
    assert chat.titel == "neu"


# --- Claude CLI (jsonl) -----------------------------------------------------------------

def test_cli_liest_titel_und_zeit_aus_mtime(projekte):
    cli_datei(projekte, UUID_A, ['{"type":"ai-title","aiTitle":"KI-Titel"}'], alter=timedelta(hours=3))
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["claude-cli"] == "ok"
    (chat,) = erg.chats
    assert (chat.kennung, chat.titel, chat.ordner, chat.quelle) == (UUID_A, "KI-Titel", "", "claude-cli")
    assert chat.zuletzt == _vor(hours=3)


def test_cli_custom_title_hat_vorrang_und_letzter_zaehlt(projekte):
    cli_datei(projekte, UUID_A, [
        '{"type":"custom-title","customTitle":"erster"}',
        '{"type":"ai-title","aiTitle":"ki"}',
        '{"type":"custom-title","customTitle":"zweiter"}',
        '{"type":"ai-title","aiTitle":"ki spaeter"}',
    ])
    assert chat_register.lesen(JETZT).chats[0].titel == "zweiter"


def test_cli_titel_fallback_auf_feld_title(projekte):
    cli_datei(projekte, UUID_A, ['{"type":"ai-title","title":"ersatz"}'])
    assert chat_register.lesen(JETZT).chats[0].titel == "ersatz"


def test_cli_ignoriert_unterordner_und_falsche_namen(projekte):
    cli_datei(projekte, UUID_A, ['{"type":"ai-title","aiTitle":"gut"}'])
    unter = projekte / "proj" / "subagents"
    unter.mkdir()
    (unter / f"{UUID_B}.jsonl").write_text("{}\n", encoding="utf-8")
    (projekte / "proj" / "notizen.jsonl").write_text("{}\n", encoding="utf-8")
    (projekte / f"{UUID_C}.jsonl").write_text("{}\n", encoding="utf-8")  # direkt unter der Wurzel: kein Projektordner
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == [UUID_A]


def test_cli_nur_dateien_im_zeitfenster_werden_geoeffnet(projekte, monkeypatch):
    cli_datei(projekte, UUID_A, ["{}"], alter=timedelta(hours=1))
    cli_datei(projekte, UUID_B, ["{}"], alter=timedelta(hours=25))
    geoeffnet: list[str] = []
    echt = Path.open

    def spion(self, *args, **kwargs):
        geoeffnet.append(self.name)
        return echt(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", spion)
    erg = chat_register.lesen(JETZT)
    assert [c.kennung for c in erg.chats] == [UUID_A]
    assert [n for n in geoeffnet if n.endswith(".jsonl")] == [f"{UUID_A}.jsonl"]


def test_cli_parst_nur_titelzeilen(projekte, monkeypatch):
    cli_datei(projekte, UUID_A, [
        '{"type":"user","message":{"content":"GEHEIMER NACHRICHTENTEXT"}}',
        '{"type":"assistant","message":{"content":"auch geheim"}}',
        '{"type":"ai-title","aiTitle":"Titel"}',
        '{"type":"user","message":"mit custom-title ohne Anfuehrungszeichen"}',
        '{"type":"user","liste":["custom-title"],"text":"GEHEIMER ZUSATZ"}',
        '{"type":"user","message":{"content":"zitiert {\\"type\\":\\"ai-title\\"} GEHEIM"}}',
    ])
    aufrufe: list[bytes | str] = []
    echt = chat_register.json.loads

    def spion(text, *args, **kwargs):
        aufrufe.append(text)
        return echt(text, *args, **kwargs)

    monkeypatch.setattr(chat_register.json, "loads", spion)
    (chat,) = chat_register.lesen(JETZT).chats
    assert chat.titel == "Titel"
    assert len(aufrufe) == 1  # nur die echte Titelzeile; Nachrichten mit dem Stichwort bleiben ungeparst
    assert aufrufe[0].startswith(b'{"type":"ai-title"')
    assert not any(b"GEHEIM" in z for z in aufrufe)


def test_cli_kaputte_titelzeile_wird_uebersprungen(projekte):
    cli_datei(projekte, UUID_A, ['{"type":"ai-title","aiTitle":', '{"type":"ai-title","aiTitle":"heil"}'])
    assert chat_register.lesen(JETZT).chats[0].titel == "heil"


def test_desktop_kennung_verdraengt_dieselbe_cli_kennung(desktop, projekte):
    desktop_datei(desktop, "a", cliSessionId=UUID_A, title="Desktop", cwd="C:/x", lastActivityAt=_ms(_vor(hours=2)))
    cli_datei(projekte, UUID_A, ['{"type":"ai-title","aiTitle":"CLI"}'], alter=timedelta(minutes=5))
    cli_datei(projekte, UUID_B, ['{"type":"ai-title","aiTitle":"nur CLI"}'], alter=timedelta(hours=1))
    erg = chat_register.lesen(JETZT)
    nach_kennung = {c.kennung: c for c in erg.chats}
    assert set(nach_kennung) == {UUID_A, UUID_B}
    assert nach_kennung[UUID_A].quelle == "claude-desktop"
    assert nach_kennung[UUID_A].titel == "Desktop"
    assert nach_kennung[UUID_B].quelle == "claude-cli"


def test_archivierte_desktop_sitzung_kommt_nicht_ueber_cli_zurueck(desktop, projekte):
    # Archiviert und alt (außerhalb des Fensters) – die CLI-Datei derselben Sitzung ist aber frisch.
    desktop_datei(desktop, "a", cliSessionId=UUID_A, title="Archiv", isArchived=True,
                  lastActivityAt=_ms(_vor(days=3)))
    cli_datei(projekte, UUID_A, ['{"type":"ai-title","aiTitle":"CLI"}'], alter=timedelta(minutes=5))
    cli_datei(projekte, UUID_B, ['{"type":"ai-title","aiTitle":"nur CLI"}'], alter=timedelta(minutes=5))
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == [UUID_B]


def test_zeiten_in_der_zukunft_werden_verworfen_kleine_abweichung_bleibt(desktop):
    desktop_datei(desktop, "a", cliSessionId=UUID_A, lastActivityAt=_ms(JETZT + timedelta(minutes=10)))
    desktop_datei(desktop, "b", cliSessionId=UUID_B, lastActivityAt=_ms(JETZT + timedelta(minutes=1)))
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == [UUID_B]


def test_gesperrte_datenbank_meldet_gesperrt(codex_pfad, monkeypatch):
    codex_db(codex_pfad, [(UUID_A, "", "x", _ms(_vor(hours=1)), 0)])

    def gesperrt(pfad):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(chat_register, "_sqlite_oeffnen", gesperrt)
    assert chat_register.lesen(JETZT).quellen["codex"] == "gesperrt"


# --- Codex -----------------------------------------------------------------------------------

def test_codex_liest_threads(codex_pfad):
    codex_db(codex_pfad, [(UUID_A, "C:/code", "Codex-Titel", _ms(_vor(hours=1)), 0),
                          (UUID_B, "C:/alt", "alt", _ms(_vor(hours=30)), 0),
                          (UUID_C, "C:/arch", "archiviert", _ms(_vor(hours=1)), 1)])
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["codex"] == "ok"
    (chat,) = erg.chats
    assert (chat.werkzeug, chat.kennung, chat.titel, chat.ordner, chat.quelle) == (
        "codex", UUID_A, "Codex-Titel", "C:/code", "codex")
    assert chat.zuletzt == _vor(hours=1)


def test_codex_name_hat_vorrang_vor_title_und_praefix_wird_entfernt(codex_pfad):
    codex_db(codex_pfad, [(UUID_A, "\\\\?\\C:\\code", "title", _ms(_vor(hours=1)), 0, "name"),
                          (UUID_B, "C:/x", "nur title", _ms(_vor(hours=1)), 0, None)], mit_name=True)
    nach_kennung = {c.kennung: c for c in chat_register.lesen(JETZT).chats}
    assert nach_kennung[UUID_A].titel == "name"
    assert nach_kennung[UUID_A].ordner == "C:\\code"
    assert nach_kennung[UUID_B].titel == "nur title"


def test_codex_24_stunden_grenze(codex_pfad):
    codex_db(codex_pfad, [(UUID_A, "", "innen", _ms(_vor(hours=23, minutes=59)), 0),
                          (UUID_B, "", "aussen", _ms(_vor(hours=24, minutes=1)), 0)])
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == [UUID_A]


def test_codex_nur_chats_von_sebastian_wenn_thread_source_vorhanden(codex_pfad):
    codex_db(codex_pfad, [], spalten="CREATE TABLE threads (id TEXT, cwd TEXT, title TEXT, updated_at_ms INTEGER, "
                                     "archived INTEGER, thread_source TEXT)")
    with closing(ECHT_SQLITE_CONNECT(codex_pfad)) as db:
        for kennung, herkunft in ((UUID_A, "user"), (UUID_B, "guardian_review"),
                                  ("00000000-0000-4000-8000-0000000000c3", "subagent"),
                                  ("00000000-0000-4000-8000-0000000000c4", "agent_created_thread")):
            db.execute("INSERT INTO threads VALUES (?, '', 'x', ?, 0, ?)", (kennung, _ms(_vor(hours=1)), herkunft))
        db.commit()
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == [UUID_A]


def test_codex_ungueltige_kennung_wird_uebersprungen(codex_pfad):
    codex_db(codex_pfad, [("../boese", "", "x", _ms(_vor(hours=1)), 0), (UUID_A, "", "ok", _ms(_vor(hours=1)), 0)])
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == [UUID_A]


def test_codex_falsches_schema_ohne_datenabfrage(codex_pfad, monkeypatch):
    codex_db(codex_pfad, [], spalten="CREATE TABLE threads (id TEXT, cwd TEXT, title TEXT)")
    sqls = _sql_spion(monkeypatch)
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["codex"] == "schema unbekannt"
    assert erg.chats == ()
    assert not any(s.lstrip().upper().startswith("SELECT") for s in sqls)


def test_codex_fehlende_tabelle_ist_schema_unbekannt(codex_pfad):
    with closing(ECHT_SQLITE_CONNECT(codex_pfad)) as db:
        db.execute("CREATE TABLE andere (x TEXT)")
    assert chat_register.lesen(JETZT).quellen["codex"] == "schema unbekannt"


def test_codex_kaputte_datei_ist_nicht_lesbar(codex_pfad):
    codex_pfad.write_bytes(b"das ist keine sqlite-datei" * 100)
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["codex"].startswith("nicht lesbar: ")
    assert erg.chats == ()


# --- Hermes ------------------------------------------------------------------------------------

def _hermes_zeile(kennung, quelle="cli", titel="t", cwd="C:/h", gestartet=None, letzte=None, arch=0, hidden=0):
    return (kennung, quelle, titel, cwd, (gestartet or _vor(days=3)).timestamp(),
            letzte.timestamp() if letzte else None, arch, hidden)


def test_hermes_quellen_archiviert_und_hidden(hermes_pfad):
    zeit = _vor(hours=1)
    hermes_db(hermes_pfad, [
        _hermes_zeile("h-cli", "cli", letzte=zeit),
        _hermes_zeile("h-desktop", "desktop", letzte=zeit),
        _hermes_zeile("h-telegram", "telegram", letzte=zeit),
        _hermes_zeile("h-api", "api_server", letzte=zeit),
        _hermes_zeile("h-cron", "cron", letzte=zeit),
        _hermes_zeile("h-sub", "subagent", letzte=zeit),
        _hermes_zeile("h-arch", "cli", letzte=zeit, arch=1),
        _hermes_zeile("h-hidden", "cli", letzte=zeit, hidden=1),
        ("h-null", "cli", "null-flags", "", zeit.timestamp(), zeit.timestamp(), None, None),
    ])
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["hermes"] == "ok"
    assert {c.kennung for c in erg.chats} == {"h-cli", "h-desktop", "h-telegram", "h-api", "h-null"}
    assert {c.werkzeug for c in erg.chats} == {"hermes"}


def test_hermes_zeit_ist_last_activity_sonst_started_at(hermes_pfad):
    hermes_db(hermes_pfad, [
        _hermes_zeile("a", gestartet=_vor(days=5), letzte=_vor(hours=2)),
        _hermes_zeile("b", gestartet=_vor(hours=3), letzte=None),
        _hermes_zeile("c", gestartet=_vor(hours=1), letzte=_vor(days=2)),  # zuletzt aktiv zu lange her
    ])
    nach_kennung = {c.kennung: c for c in chat_register.lesen(JETZT).chats}
    assert set(nach_kennung) == {"a", "b"}
    assert nach_kennung["a"].zuletzt == _vor(hours=2)
    assert nach_kennung["b"].zuletzt == _vor(hours=3)


def test_hermes_24_stunden_grenze(hermes_pfad):
    hermes_db(hermes_pfad, [_hermes_zeile("innen", letzte=_vor(hours=23, minutes=59)),
                            _hermes_zeile("aussen", letzte=_vor(hours=24, minutes=1))])
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == ["innen"]


def test_hermes_ohne_optionale_spalten(hermes_pfad):
    hermes_db(hermes_pfad, [("a", "cli", "t", "C:/h", _vor(hours=1).timestamp())], erweitert=False)
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["hermes"] == "ok"
    assert [c.kennung for c in erg.chats] == ["a"]


def test_hermes_ungueltige_kennung_wird_uebersprungen(hermes_pfad):
    hermes_db(hermes_pfad, [_hermes_zeile("bo/ese", letzte=_vor(hours=1)),
                            _hermes_zeile("gut", letzte=_vor(hours=1))])
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == ["gut"]


def test_hermes_falsches_schema_ohne_datenabfrage(hermes_pfad, monkeypatch):
    hermes_db(hermes_pfad, [], spalten="CREATE TABLE sessions (id TEXT, source TEXT)")
    sqls = _sql_spion(monkeypatch)
    assert chat_register.lesen(JETZT).quellen["hermes"] == "schema unbekannt"
    assert not any(s.lstrip().upper().startswith("SELECT") for s in sqls)


def test_hermes_kaputte_datei_ist_nicht_lesbar(hermes_pfad):
    hermes_pfad.write_bytes(b"kaputt" * 500)
    assert chat_register.lesen(JETZT).quellen["hermes"].startswith("nicht lesbar: ")


def test_hermes_home_bestimmt_standardpfad(tmp_path, monkeypatch):
    monkeypatch.delenv("MASTER_SCHALTER_HERMES_STATE")
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hh"))
    assert chat_register._hermes_pfad() == tmp_path / "hh" / "state.db"
    monkeypatch.delenv("HERMES_HOME")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "la"))
    assert chat_register._hermes_pfad() == tmp_path / "la" / "hermes" / "state.db"


# --- Zusammenspiel ----------------------------------------------------------------------------

# --- Antigravity (agy) -------------------------------------------------------------------------

@pytest.fixture
def agy_heim(tmp_path, monkeypatch) -> Path:
    heim = tmp_path / "gemini"
    monkeypatch.setenv("MASTER_SCHALTER_AGY_HEIM", str(heim))
    return heim


ARBEIT = '["file:///c:/Users/sebas/Desktop/workspace%20agentic%20engineering"]'


def _agy_db(heim: Path, auspraegung: str, zeilen: list[tuple], spalten: str | None = None) -> None:
    ordner = heim / auspraegung
    ordner.mkdir(parents=True, exist_ok=True)
    with closing(ECHT_SQLITE_CONNECT(ordner / "conversation_summaries.db")) as db:
        db.execute(spalten or "CREATE TABLE conversation_summaries (conversation_id TEXT, title TEXT, "
                              "last_modified_time TEXT, workspace_uris TEXT)")
        if zeilen:
            db.executemany("INSERT INTO conversation_summaries VALUES (?, ?, ?, ?)", zeilen)
        db.commit()


def _agy_zeile(kennung: str = UUID_A, titel: str = "Master Schalter", zeit: datetime | None = None,
               arbeit: str = ARBEIT) -> tuple:
    """Zeile wie Antigravity sie schreibt: Zeit als ISO-Text mit Leerzeichen statt `T`."""
    zeit = zeit or _vor(hours=1)
    return (kennung, titel, zeit.astimezone(timezone.utc).isoformat(sep=" "), arbeit)


def test_agy_findet_titel_zeit_und_arbeitsordner(agy_heim):
    _agy_db(agy_heim, "antigravity", [_agy_zeile()])
    erg = chat_register.lesen(JETZT)

    assert erg.quellen["agy"] == "ok"
    (chat,) = erg.chats
    assert chat.werkzeug == "agy" and chat.quelle == "agy"
    assert chat.kennung == UUID_A
    assert chat.titel == "Master Schalter"
    assert chat.ordner == "C:\\Users\\sebas\\Desktop\\workspace agentic engineering"
    assert chat.zuletzt == _vor(hours=1)


def test_agy_liest_app_cli_und_ide_zusammen(agy_heim):
    _agy_db(agy_heim, "antigravity", [_agy_zeile(UUID_A)])
    _agy_db(agy_heim, "antigravity-cli", [_agy_zeile(UUID_B, zeit=_vor(hours=2))])
    _agy_db(agy_heim, "antigravity-ide", [_agy_zeile(UUID_C, zeit=_vor(hours=3))])
    erg = chat_register.lesen(JETZT)

    assert erg.quellen["agy"] == "ok"
    assert [c.kennung for c in erg.chats] == [UUID_A, UUID_B, UUID_C]


def test_agy_ueberspringt_alte_und_unbrauchbare_zeiten(agy_heim):
    _agy_db(agy_heim, "antigravity", [
        _agy_zeile(UUID_A, zeit=_vor(days=3)),                       # älter als das Fenster
        _agy_zeile(UUID_B, zeit=_vor(hours=1)),
        (UUID_C, "kaputt", "gestern", ARBEIT),                       # kein ISO-Zeitstempel
        ("../boese", "pfad", _vor(hours=1).isoformat(), ARBEIT),     # unzulässige Kennung
        ("44444444-4444-4444-8444-444444444444", "ohne Zone",
         _vor(hours=2).replace(tzinfo=None).isoformat(sep=" "), ARBEIT),   # naiv = UTC
    ])
    assert [c.kennung for c in chat_register.lesen(JETZT).chats] == [UUID_B, "44444444-4444-4444-8444-444444444444"]


def test_agy_unbrauchbare_arbeitsordner_ergeben_leer(agy_heim):
    _agy_db(agy_heim, "antigravity", [
        (UUID_A, "kein json", _vor(hours=1).isoformat(), "kein json"),
        (UUID_B, "kein feld", _vor(hours=2).isoformat(), '"file:///c:/x"'),
        (UUID_C, "leer", _vor(hours=3).isoformat(), "[]"),
    ])
    ordner = {c.kennung: c.ordner for c in chat_register.lesen(JETZT).chats}
    assert ordner == {UUID_A: "", UUID_B: "", UUID_C: ""}


def test_agy_falsches_schema_ist_schema_unbekannt(agy_heim):
    _agy_db(agy_heim, "antigravity", [], spalten="CREATE TABLE andere (x TEXT)")
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["agy"] == "schema unbekannt"
    assert erg.chats == ()


def test_agy_kaputte_datei_ist_nicht_lesbar(agy_heim):
    ordner = agy_heim / "antigravity"
    ordner.mkdir(parents=True)
    (ordner / "conversation_summaries.db").write_bytes(b"das ist keine sqlite-datei" * 100)
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["agy"].startswith("nicht lesbar: ")
    assert erg.chats == ()


def test_agy_fehlende_uebersicht_ist_fehlt(agy_heim):
    assert chat_register.lesen(JETZT).quellen["agy"] == "fehlt"


def test_agy_vorhandene_quelle_traegt_eine_kaputte_mit(agy_heim):
    """Eine unlesbare Ausprägung darf die lesbare nicht verdrängen."""
    _agy_db(agy_heim, "antigravity", [_agy_zeile()])
    kaputt = agy_heim / "antigravity-cli"
    kaputt.mkdir(parents=True)
    (kaputt / "conversation_summaries.db").write_bytes(b"kaputt" * 200)
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["agy"] == "ok"
    assert [c.kennung for c in erg.chats] == [UUID_A]


def test_agy_legt_fehlende_datenbank_nicht_an(agy_heim):
    chat_register.lesen(JETZT)
    assert not (agy_heim / "antigravity" / "conversation_summaries.db").exists()


def test_sortierung_neueste_zuerst_und_eine_kaputte_quelle_stoppt_die_anderen_nicht(
        desktop, projekte, codex_pfad, hermes_pfad):
    desktop_datei(desktop, "a", cliSessionId=UUID_A, lastActivityAt=_ms(_vor(hours=4)))
    cli_datei(projekte, UUID_B, ["{}"], alter=timedelta(hours=1))
    codex_pfad.write_bytes(b"kaputt" * 500)
    hermes_db(hermes_pfad, [_hermes_zeile("h", letzte=_vor(hours=2))])
    erg = chat_register.lesen(JETZT)
    assert [c.kennung for c in erg.chats] == [UUID_B, "h", UUID_A]
    assert erg.quellen["codex"].startswith("nicht lesbar: ")
    assert [erg.quellen[q] for q in ("claude-desktop", "claude-cli", "hermes")] == ["ok", "ok", "ok"]


def test_ausnahme_einer_quelle_wird_zum_status(desktop, hermes_pfad, monkeypatch):
    hermes_db(hermes_pfad, [_hermes_zeile("h", letzte=_vor(hours=1))])

    def kaputt(grenze, archiviert=None):
        raise RuntimeError("C:/geheimer/pfad")

    monkeypatch.setattr(chat_register, "_claude_desktop", kaputt)
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["claude-desktop"] == "nicht lesbar: RuntimeError"
    assert "geheim" not in erg.quellen["claude-desktop"]
    assert [c.kennung for c in erg.chats] == ["h"]


def test_gleiche_kennung_verschiedener_werkzeuge_bleibt_getrennt(codex_pfad, hermes_pfad):
    codex_db(codex_pfad, [("gleich", "", "c", _ms(_vor(hours=1)), 0)])
    hermes_db(hermes_pfad, [_hermes_zeile("gleich", letzte=_vor(hours=2))])
    assert sorted(c.werkzeug for c in chat_register.lesen(JETZT).chats) == ["codex", "hermes"]


# --- SQL-Spion --------------------------------------------------------------------------------------

class _Spur(list):
    adressen: list[str]


def _sql_spion(monkeypatch) -> _Spur:
    """Umhüllt `sqlite3.connect`: sammelt alle Verbindungsadressen und ausgeführten SQL-Texte."""
    sqls = _Spur()
    adressen: list[str] = []

    def spion(adresse, *args, **kwargs):
        adressen.append(str(adresse))
        verbindung = ECHT_SQLITE_CONNECT(adresse, *args, **kwargs)
        verbindung.set_trace_callback(sqls.append)
        return verbindung

    monkeypatch.setattr(chat_register.sqlite3, "connect", spion)
    sqls.adressen = adressen
    return sqls


def test_sql_spion_nur_lesend_ohne_stern_und_ohne_messages(codex_pfad, hermes_pfad, monkeypatch):
    codex_db(codex_pfad, [(UUID_A, "C:/c", "t", _ms(_vor(hours=1)), 0)], mit_name=False)
    hermes_db(hermes_pfad, [_hermes_zeile("h", letzte=_vor(hours=1))])
    sqls = _sql_spion(monkeypatch)
    erg = chat_register.lesen(JETZT)
    assert len(erg.chats) == 2
    assert len(sqls.adressen) == 2
    assert all(a.startswith("file:") and "mode=ro" in a for a in sqls.adressen)
    assert sqls, "es wurde kein SQL aufgezeichnet"
    for sql in sqls:
        assert "*" not in sql
        assert "messages" not in sql.lower()
    tabellen = {t for sql in sqls for t in ("threads", "sessions") if t in sql}
    assert tabellen == {"threads", "sessions"}
    selects = [s for s in sqls if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 2
    assert all(not s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP"))
               for s in sqls)


def test_sqlite_verbindung_ist_schreibgeschuetzt(codex_pfad):
    codex_db(codex_pfad, [])
    with closing(chat_register._sqlite_oeffnen(codex_pfad)) as db:
        with pytest.raises(sqlite3.OperationalError):
            db.execute("INSERT INTO threads VALUES ('a', 'b', 'c', 1, 0)")


def test_fehlende_datenbank_wird_nicht_angelegt(codex_pfad):
    chat_register.lesen(JETZT)
    assert not codex_pfad.exists()


def test_sonderzeichen_im_pfad_werden_kodiert(tmp_path, monkeypatch):
    ordner = tmp_path / "ä b#c"
    ordner.mkdir()
    pfad = ordner / "codex.sqlite"
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_STATE", str(pfad))
    codex_db(pfad, [(UUID_A, "", "t", _ms(_vor(hours=1)), 0)])
    erg = chat_register.lesen(JETZT)
    assert erg.quellen["codex"] == "ok"
    assert len(erg.chats) == 1
