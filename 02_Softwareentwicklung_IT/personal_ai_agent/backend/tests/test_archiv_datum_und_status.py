"""Tests: Zitattag und Zustand des Wissensspeichers (Chat-Archive).

Anlass (Sebastian, 10.10.2026): „**Falsche Daten** in den Verweisen auf die
Chat-Archive (ChatGPT, Claude, Gemini): die Belegstellen nennen Zeitpunkte,
die nicht stimmen."

Gemessen am echten Index (447 MB, nur lesend):

  (a) ``chunks.beginn`` ist der Zeitstempel des ERSTEN, ``chunks.ende`` der des
      LETZTEN Eintrags eines Abschnitts; zitiert wurde bisher nur
      ``beginn[:10]``. Steht der gesuchte Satz spaeter im Abschnitt, nennt das
      Zitat einen falschen Tag. Betroffen sind 98 der 30.447 Chat-Chunks und
      9.165 von 21.788 WhatsApp-Chunks; der weiteste reicht vom 11.02. bis
      13.06.2025. Deshalb: gleicher Tag → ein Datum, sonst die Spanne.
  (b) ``archiv_service.status()`` las die Nachrichtentabelle ``messages`` — der
      echte Index heisst ``nachrichten`` (Schema in ``archiv_suche``). Folge:
      „no such table: messages", der Zustand meldete sich als **nicht
      verfuegbar**, obwohl die Suche einwandfrei lief.

Diese Datei baut sich ihre Indizes selbst im ``tmp_path``; das echte Archiv
wird nie geoeffnet oder veraendert.
"""

from __future__ import annotations

import os
import sqlite3
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from app.config import settings  # noqa: E402
from app.services.archiv_service import ArchivService, zeitraum_kurz  # noqa: E402
from app.services.archiv_suche import _datum_kurz  # noqa: E402


# ── Kuenstlicher Index (Format des Schwesternprojekts) ─────────────────────

def _index_bauen(pfad: str, nachrichtentabelle: str = "nachrichten") -> None:
    """Ein winziger Index: eine Tabelle chunks, FTS, zwei Nachrichten-Zeilen."""
    con = sqlite3.connect(pfad)
    con.executescript(
        f"""
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
            text TEXT NOT NULL, nachricht_ids TEXT NOT NULL, beginn TEXT, ende TEXT,
            title TEXT, project TEXT, teil INTEGER NOT NULL DEFAULT 0,
            quelldatei TEXT, hat_vektor INTEGER NOT NULL DEFAULT 0
        );
        CREATE VIRTUAL TABLE chunks_fts USING fts5(text);
        CREATE TABLE {nachrichtentabelle} (
            id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
            timestamp TEXT, role TEXT NOT NULL, text TEXT NOT NULL, title TEXT, project TEXT
        );
        """
    )
    # Ein Abschnitt ueber EINEN Tag und einer ueber vier Monate.
    con.execute(
        "INSERT INTO chunks VALUES (1,'c1','chatgpt',?,?,?,?,'EasyBank Probleme',NULL,0,NULL,0)",
        ("Die EasyBank hat die Ueberweisung am 12.03. abgelehnt, weil das Limit "
         "ueberschritten war.", "[1]", "2026-03-12T10:00:00+00:00",
         "2026-03-12T10:04:00+00:00"),
    )
    con.execute(
        "INSERT INTO chunks VALUES (2,'c2','claude-ai',?,?,?,?,'TwinCAT Projekt',NULL,0,NULL,0)",
        ("Antwort: Der Sprachchef-Teil laeuft wieder.", "[2,3]",
         "2026-02-11T21:19:51+00:00", "2026-06-13T23:54:23+00:00"),
    )
    con.execute("INSERT INTO chunks_fts(rowid, text) VALUES (1, ?)",
                ("Die EasyBank hat die Ueberweisung am 12.03. abgelehnt",))
    con.execute("INSERT INTO chunks_fts(rowid, text) VALUES (2, ?)",
                ("Antwort: Der Sprachchef-Teil laeuft wieder.",))
    con.execute(
        f"INSERT INTO {nachrichtentabelle} VALUES (1,'c1','chatgpt',?, 'user', ?, "
        "'EasyBank Probleme', NULL)",
        ("2026-03-12T10:00:00+00:00", "Die EasyBank hat die Ueberweisung abgelehnt"),
    )
    con.execute(
        f"INSERT INTO {nachrichtentabelle} VALUES (2,'c2','claude-ai',?, 'user', ?, "
        "'TwinCAT Projekt', NULL)",
        ("2026-02-11T21:19:56+00:00", "Sprachchef?"),
    )
    con.commit()
    con.close()


def _dienst(pfad: str, monkeypatch) -> ArchivService:
    monkeypatch.setattr(settings, "archiv_db_path", pfad)
    dienst = ArchivService()
    assert dienst.is_available, "Der kuenstliche Index muss gefunden werden."
    return dienst


# ── (a) Der Zitattag ───────────────────────────────────────────────────────

def test_zeitraum_kurz_gleicher_tag_bleibt_ein_datum():
    assert zeitraum_kurz("2026-03-12T10:00:00+00:00", "2026-03-12T10:04:00+00:00") == "2026-03-12"


def test_zeitraum_kurz_mehrere_tage_werden_zur_spanne():
    """Der Kern des Befunds: kein falscher Einzeltag mehr."""
    assert zeitraum_kurz("2026-02-11T21:19:51+00:00", "2026-06-13T23:54:23+00:00") == \
        "2026-02-11–2026-06-13"


def test_zeitraum_kurz_ohne_ende_bleibt_beim_einzeldatum():
    """Aeltere Aufrufer und Attrappen tragen kein `ende` — sie bleiben wie vorher."""
    assert zeitraum_kurz("2026-03-12T10:00:00", None) == "2026-03-12"
    assert zeitraum_kurz("2026-03-12T10:00:00", "") == "2026-03-12"
    assert zeitraum_kurz("", None) == ""
    assert zeitraum_kurz(None, None) == ""


def test_archiv_suche_rechnet_denselben_weg():
    """Der zweite Suchweg (Chronik) darf dasselbe Datum nennen — sonst zwei Wahrheiten."""
    assert _datum_kurz("2026-03-12T10:00:00+00:00", "2026-03-12T10:04:00+00:00") == "2026-03-12"
    assert _datum_kurz("2026-02-11T21:19:51+00:00", "2026-06-13T23:54:23+00:00") == \
        "2026-02-11–2026-06-13"
    assert _datum_kurz("2026-02-11T21:19:51+00:00") == "2026-02-11"
    assert _datum_kurz(None) is None


def test_zitat_in_der_chat_notiz_nennt_die_spanne(monkeypatch):
    """Die Notiz an das Modell (chat._archiv_tool) traegt Tag oder Spanne."""
    from app.router.chat import _archiv_tool

    class _FakeArchiv:
        is_available = True

        def hybrid(self, frage, top_k=None):
            return [
                {"text": "Die EasyBank hat die Ueberweisung abgelehnt.",
                 "source": "chatgpt", "beginn": "2026-03-12T10:00:00+00:00",
                 "ende": "2026-03-12T10:04:00+00:00", "title": "EasyBank",
                 "conversation_id": "c1"},
                {"text": "Antwort: Der Sprachchef-Teil laeuft wieder.",
                 "source": "claude-ai", "beginn": "2026-02-11T21:19:51+00:00",
                 "ende": "2026-06-13T23:54:23+00:00", "title": "TwinCAT",
                 "conversation_id": "c2"},
            ]

    ausgabe = _archiv_tool("Was weiss ich ueber EasyBank aus dem Archiv?", service=_FakeArchiv())
    assert "[chatgpt, 2026-03-12]" in ausgabe
    assert "[claude-ai, 2026-02-11–2026-06-13]" in ausgabe


def test_zitat_ohne_ende_bleibt_einzeldatum(monkeypatch):
    """Rueckwaertsvertraeglich: Treffer ohne `ende` zitieren genau wie vorher."""
    from app.router.chat import _archiv_tool

    class _FakeArchiv:
        is_available = True

        def hybrid(self, frage, top_k=None):
            return [{"text": "Die EasyBank hat abgelehnt.", "source": "gemini",
                     "beginn": "2026-04-02T09:30:00", "title": "EasyBank",
                     "conversation_id": "c3"}]

    ausgabe = _archiv_tool("Was weiss ich ueber EasyBank aus dem Archiv?", service=_FakeArchiv())
    assert "[gemini, 2026-04-02]" in ausgabe


def test_prompt_fundstelle_nennt_die_spanne():
    """Auch der System-Prompt (llm_service) nennt die Spanne, nicht den ersten Tag."""
    from app.services.llm_service import LLMService

    text = LLMService._build_archiv_context([
        {"text": "Antwort: Der Sprachchef-Teil laeuft wieder.", "source": "claude-ai",
         "beginn": "2026-02-11T21:19:51+00:00", "ende": "2026-06-13T23:54:23+00:00",
         "title": "TwinCAT Projekt"},
    ])
    assert "[claude-ai, 2026-02-11–2026-06-13]" in text


# ── (b) Der Zustand des Wissensspeichers ───────────────────────────────────

def test_suche_liefert_den_ende_stempel_mit(tmp_path, monkeypatch):
    """Ohne `ende` kann kein Zitat die Spanne bilden — also muss er mitkommen."""
    pfad = os.path.join(str(tmp_path), "archiv_index.db")
    _index_bauen(pfad)
    dienst = _dienst(pfad, monkeypatch)

    treffer = dienst.suche("EasyBank", 3)
    assert treffer, "Der Volltext-Weg muss den kuenstlichen Abschnitt finden."
    assert treffer[0]["beginn"].startswith("2026-03-12")
    assert treffer[0]["ende"].startswith("2026-03-12")


def test_status_liest_die_tabelle_nachrichten(tmp_path, monkeypatch):
    """Der echte Index heisst `nachrichten` — der Zustand muss das lesen."""
    pfad = os.path.join(str(tmp_path), "archiv_index.db")
    _index_bauen(pfad, nachrichtentabelle="nachrichten")
    dienst = _dienst(pfad, monkeypatch)

    stand = dienst.status()
    assert stand["verfuegbar"] is True
    assert stand["nachrichten"] == 2, stand
    assert stand["chunks"] == 2
    assert stand["nachrichten_tabelle"] == "nachrichten"


def test_status_liest_auch_die_alte_tabelle_messages(tmp_path, monkeypatch):
    """Der alte Stand (und die Handy-Heimkopie) hat `messages` — weiter lesbar."""
    pfad = os.path.join(str(tmp_path), "archiv_index.db")
    _index_bauen(pfad, nachrichtentabelle="messages")
    dienst = _dienst(pfad, monkeypatch)

    stand = dienst.status()
    assert stand["verfuegbar"] is True
    assert stand["nachrichten"] == 2, stand
    assert stand["nachrichten_tabelle"] == "messages"
