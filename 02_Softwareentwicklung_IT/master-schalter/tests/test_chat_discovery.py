"""Tests für automatische Erkennung aktiver Chats (Antigravity, Codex etc.)."""
import sqlite3
from master_schalter import chat_discovery as cd


def test_thema_bereinigen_erzeugt_saubere_slugs():
    assert cd.thema_bereinigen("Thema: personal-ai-agent") == "personal-ai-agent"
    assert cd.thema_bereinigen("Azure AI App Development Course") == "azure-ai-app-development-course"
    assert cd.thema_bereinigen("Überblick über IT & OT!") == "ueberblick-ueber-it-ot"
    assert cd.thema_bereinigen("   ") == "neues-thema"


def test_antigravity_chats_finden_aus_sqlite_db(tmp_path):
    db_datei = tmp_path / "conv_test.db"
    con = sqlite3.connect(db_datei)
    con.execute("""
        CREATE TABLE conversation_summaries (
            conversation_id text PRIMARY KEY,
            title text NOT NULL,
            last_modified_time datetime NOT NULL
        )
    """)
    con.execute("INSERT INTO conversation_summaries VALUES ('c1', 'Thema: Mein Test', '2026-10-30 03:00:00')")
    con.execute("INSERT INTO conversation_summaries VALUES ('c2', '', '2026-10-30 02:00:00')")
    con.commit()
    con.close()

    chats = cd.antigravity_chats_finden(db_datei)
    assert len(chats) == 1
    assert chats[0].thema == "mein-test"
    assert chats[0].quelle == "Antigravity"
    assert chats[0].sitzung_id == "c1"


def test_neue_themen_vorschlaege_filtert_bestehende_themen(tmp_path):
    db_datei = tmp_path / "conv_test.db"
    con = sqlite3.connect(db_datei)
    con.execute("""
        CREATE TABLE conversation_summaries (
            conversation_id text PRIMARY KEY,
            title text NOT NULL,
            last_modified_time datetime NOT NULL
        )
    """)
    con.execute("INSERT INTO conversation_summaries VALUES ('c1', 'bestehendes-thema', '2026-10-30 03:00:00')")
    con.execute("INSERT INTO conversation_summaries VALUES ('c2', 'ganz-neu', '2026-10-30 02:00:00')")
    con.commit()
    con.close()

    bestehend = {"bestehendes-thema"}
    vorschlaege = cd.neue_themen_vorschlaege(bestehend, db_datei=db_datei, codex_ordner=tmp_path / "leer")
    assert len(vorschlaege) == 1
    assert vorschlaege[0].thema == "ganz-neu"
