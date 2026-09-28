"""Pruefungen fuer ``tools/whatsapp/zuordnung_bauen.py`` (Zuordnung Chat <-> Person).

Alles OHNE Netz und OHNE echte Daten: die Datenbank ist eine In-Memory-Attrappe
mit dem nachgebauten Schema, das Telefonbuch kommt als erfundener Roh-Text
(``content query``-Format). **Nur erfundene Beispielnamen/-nummern** - echte
Kontakte kommen hier nicht vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_whatsapp_zuordnung.py -q
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "whatsapp" / "zuordnung_bauen.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


z = _laden(WERKZEUG, "zuordnung_bauen")


# ── Erfundene Fixture-Daten ─────────────────────────────────────────────────

TELEFONBUCH_ROH = """\
Row: 0 display_name=Beispiel Anna, data1=+49 151 0000001
Row: 1 display_name=Beispiel Bert, data1=0049 151 0000002
Row: 2 display_name=Beispiel Cem, data1=0151 0000003
Row: 3 display_name=Beispiel, Emil, data1=+49 151 0000004
"""

EVENTS_ROH = """\
Row: 0 display_name=Beispiel Anna, data1=1990-05-12, data2=3, data3=Geburtstag, mimetype=vnd.android.cursor.item/contact_event
Row: 1 display_name=Beispiel Bert, data1=--11-03, data2=3, data3=Geburtstag, mimetype=vnd.android.cursor.item/contact_event
Row: 2 display_name=Beispiel Cem, data1=2000-01-01, data2=0, data3=Jahrestag, mimetype=vnd.android.cursor.item/contact_event
Row: 3 display_name=Beispiel Defekt, data1=kein-datum, data2=3, data3=Geburtstag, mimetype=vnd.android.cursor.item/contact_event
"""


def _db_bauen() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, server TEXT, agent INTEGER,
                          type INTEGER, raw_string TEXT, device INTEGER);
        CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT);
        CREATE TABLE jid_map (lid_row_id INTEGER, jid_row_id INTEGER, sort_id INTEGER);
        CREATE TABLE lid_display_name (lid_row_id INTEGER, display_name TEXT, username TEXT);
        CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, from_me INTEGER,
                              sender_jid_row_id INTEGER);
        CREATE TABLE message_system_chat_participant (message_row_id INTEGER,
                                                      user_jid_row_id INTEGER);
        """
    )
    return con


def _jid(con, jid_id, user, server, typ):
    con.execute(
        "INSERT INTO jid (_id, user, server, agent, type, raw_string, device) "
        "VALUES (?,?,?,NULL,?,?,0)",
        (jid_id, user, server, typ, f"{user}@{server}"))


def _fixture_db(mit_gpu: bool = True) -> sqlite3.Connection:
    """Nachgebautes Schema mit erfundenen Chats, jids, LIDs und Verlaufszeilen."""
    con = _db_bauen()
    if mit_gpu:
        con.executescript(
            """
            CREATE TABLE group_participant_user (_id INTEGER PRIMARY KEY,
                group_jid_row_id INTEGER, user_jid_row_id INTEGER, rank INTEGER,
                pending INTEGER, add_timestamp INTEGER, label TEXT, join_method INTEGER,
                group_history_send_state INTEGER);
            """
        )
    _jid(con, 1, "491510000001", "s.whatsapp.net", 0)   # Anna (Nummer)
    _jid(con, 2, "9001", "lid", 18)                     # Anna (LID)
    _jid(con, 3, "491510000009", "s.whatsapp.net", 0)   # Dora - nicht im Telefonbuch
    _jid(con, 4, "491510000002", "s.whatsapp.net", 0)   # Bert (Nummer)
    _jid(con, 5, "9002", "lid", 18)                     # Bert (LID -> Nummer)
    _jid(con, 6, "9003", "lid", 18)                     # Cem - LID ohne Zuordnung
    _jid(con, 7, "9004", "lid", 18)                     # unbekannte LID
    _jid(con, 8, "9000", "lid_me", 11)                  # Sebastian selbst
    _jid(con, 8001, "8001", "g.us", 1)                  # Gruppe 4
    _jid(con, 8002, "8002", "g.us", 1)                  # Gruppe 5 (ohne Mitgliederzeilen)
    _jid(con, 8003, "8003", "g.us", 1)                  # Gruppe 6 (nur Unbekannte)
    _jid(con, 900, "123456", "newsletter", 21)          # Kanal 7
    con.executemany("INSERT INTO jid_map (lid_row_id, jid_row_id, sort_id) VALUES (?,?,0)",
                    [(2, 1), (5, 4)])
    con.executemany(
        "INSERT INTO lid_display_name (lid_row_id, display_name, username) VALUES (?,?,NULL)",
        [(2, "AnnaBeispielWA"), (5, "BertBeispielWA"), (6, "CemBeispielWA")])
    con.executemany("INSERT INTO chat (_id, jid_row_id, subject) VALUES (?,?,?)", [
        (1, 1, None),                       # Einzelchat Anna
        (2, 5, None),                       # Einzelchat Bert (LID)
        (3, 3, None),                       # Einzelchat Dora (kein Treffer)
        (4, 8001, "Beispielgruppe"),        # Gruppe mit Mitgliederzeilen
        (5, 8002, "Beispielgruppe Zwei"),   # Gruppe nur ueber den Verlauf
        (6, 8003, "Beispielgruppe Drei"),   # Gruppe nur Unbekannte
        (7, 900, "Beispielkanal"),          # Newsletter
    ])
    if mit_gpu:
        con.executemany(
            "INSERT INTO group_participant_user (group_jid_row_id, user_jid_row_id) "
            "VALUES (?,?)",
            [(8001, 1), (8001, 5), (8001, 6), (8001, 8), (8003, 7)])
    con.executemany(
        "INSERT INTO message (_id, chat_row_id, from_me, sender_jid_row_id) VALUES (?,?,?,?)",
        [(50, 5, 1, 0), (51, 5, 0, 4)])
    con.execute(
        "INSERT INTO message_system_chat_participant (message_row_id, user_jid_row_id) "
        "VALUES (50, 1)")
    return con


def _baue(con=None, telefonbuch_roh=TELEFONBUCH_ROH, events_roh=EVENTS_ROH) -> dict:
    con = con or _fixture_db()
    telefonbuch = z.parse_telefonbuch(telefonbuch_roh)
    geburtstage = z.parse_geburtstage(events_roh)
    return z.baue_zuordnung(con, telefonbuch, geburtstage)


def _eintrag(daten: dict, chat_row_id: int) -> dict:
    for eintrag in daten["chats"]:
        if eintrag["chat_row_id"] == chat_row_id:
            return eintrag
    raise AssertionError(f"Chat {chat_row_id} fehlt")


# ── Nummern ─────────────────────────────────────────────────────────────────

def test_nummer_normalisieren():
    assert z.normalisiere_nummer("+49 (151) 0000001") == "491510000001"
    assert z.normalisiere_nummer("0049 151 0000001") == "491510000001"
    assert z.normalisiere_nummer("0151 0000001") == "491510000001"
    assert z.normalisiere_nummer("0049 (0) 151 0000001") == "491510000001"
    assert z.normalisiere_nummer("") is None
    assert z.normalisiere_nummer(None) is None
    assert z.normalisiere_nummer("keine ziffern") is None


def test_nummer_varianten_schnittmenge():
    schreibweisen = ["+49 151 0000001", "0049 151 0000001", "0151 0000001",
                     "491510000001", "1510000001", "+49 (0) 151 0000001"]
    for i, eine in enumerate(schreibweisen):
        for andere in schreibweisen[i + 1:]:
            assert z.nummer_varianten(eine) & z.nummer_varianten(andere), \
                f"keine Schnittmenge bei zwei Schreibweisen ({i})"


def test_maske_nummer():
    assert z.maske_nummer("+49 151 0000001") == "***0001"
    assert z.maske_nummer("0049 151 0000002") == "***0002"
    assert z.maske_nummer("") is None
    assert z.maske_nummer(None) is None
    assert z.maske_nummer("7") == "***7"


# ── Parsen ──────────────────────────────────────────────────────────────────

def test_parse_telefonbuch_mit_komma_im_namen():
    eintraege = z.parse_telefonbuch(TELEFONBUCH_ROH)
    assert [e["name"] for e in eintraege] == [
        "Beispiel Anna", "Beispiel Bert", "Beispiel Cem", "Beispiel, Emil"]
    assert eintraege[0]["nummer"] == "+49 151 0000001"
    assert eintraege[3]["nummer"] == "+49 151 0000004"


def test_parse_geburtstage_nur_typ3():
    geburtstage = z.parse_geburtstage(EVENTS_ROH)
    assert geburtstage == [
        {"name": "Beispiel Anna", "tag": 12, "monat": 5},
        {"name": "Beispiel Bert", "tag": 3, "monat": 11},
    ]


def test_datum_zerlegen():
    assert z._datum_zerlegen("1990-05-12") == (12, 5)
    assert z._datum_zerlegen("--11-03") == (3, 11)
    assert z._datum_zerlegen("--13-40") is None
    assert z._datum_zerlegen("kein-datum") is None
    assert z._datum_zerlegen("") is None


def test_parse_leere_eingabe():
    assert z.parse_telefonbuch("") == []
    assert z.parse_geburtstage("") == []
    assert z.parse_telefonbuch("Zeile ohne Row-Kennung") == []


# ── Einzelchats ─────────────────────────────────────────────────────────────

def test_einzelchat_net_mit_telefonbuch_und_waname():
    eintrag = _eintrag(_baue(), 1)
    assert eintrag["art"] == "einzel"
    assert eintrag["telefonbuch_namen"] == ["Beispiel Anna"]
    assert eintrag["whatsapp_name"] == "AnnaBeispielWA"
    assert eintrag["nummer_maske"] == "***0001"
    assert eintrag["kontakt_treffer"] is True


def test_einzelchat_lid_ueber_jid_map():
    eintrag = _eintrag(_baue(), 2)
    assert eintrag["telefonbuch_namen"] == ["Beispiel Bert"]
    assert eintrag["whatsapp_name"] == "BertBeispielWA"
    assert eintrag["nummer_maske"] == "***0002"
    assert eintrag["kontakt_treffer"] is True


def test_einzelchat_ohne_treffer():
    eintrag = _eintrag(_baue(), 3)
    assert eintrag["telefonbuch_namen"] == []
    assert eintrag["whatsapp_name"] is None
    assert eintrag["nummer_maske"] == "***0009"
    assert eintrag["kontakt_treffer"] is False


def test_newsletter_ohne_kontakt():
    eintrag = _eintrag(_baue(), 7)
    assert eintrag["art"] == "newsletter"
    assert eintrag["kontakt_treffer"] is False
    assert "telefonbuch_namen" not in eintrag


# ── Gruppen ─────────────────────────────────────────────────────────────────

def test_gruppe_aus_group_participant_user():
    eintrag = _eintrag(_baue(), 4)
    assert eintrag["art"] == "gruppe"
    assert eintrag["anzahl_mitglieder"] == 3  # Sebastian selbst zaehlt nicht
    assert eintrag["mitglieder_mit_kontakt"] == 2
    assert [t["name"] for t in eintrag["teilnehmer"]] == [
        "Beispiel Anna", "Beispiel Bert", "CemBeispielWA"]
    assert {t["_herkunft"] for t in eintrag["teilnehmer"]} == {"gruppe"}
    assert [t["im_telefonbuch"] for t in eintrag["teilnehmer"]] == [True, True, False]
    assert [t["nummer_maske"] for t in eintrag["teilnehmer"]] == ["***0001", "***0002", None]


def test_gruppe_fallback_ohne_participant_tabellen():
    daten = _baue(con=_fixture_db(mit_gpu=False))
    eintrag = _eintrag(daten, 5)
    assert eintrag["anzahl_mitglieder"] == 2
    assert [t["name"] for t in eintrag["teilnehmer"]] == ["Beispiel Anna", "Beispiel Bert"]
    assert {t["_herkunft"] for t in eintrag["teilnehmer"]} == {"verlauf"}
    assert daten["statistik"]["gruppen_vollstaendig"] == 1


def test_gruppe_textform_group_participants():
    con = _db_bauen()
    con.executescript(
        """
        CREATE TABLE group_participants (_id INTEGER PRIMARY KEY, gjid TEXT, jid TEXT,
            admin INTEGER, pending INTEGER, sent_sender_key INTEGER);
        """
    )
    _jid(con, 8001, "8001", "g.us", 1)
    _jid(con, 1, "491510000001", "s.whatsapp.net", 0)
    con.execute("INSERT INTO group_participants (gjid, jid) VALUES (?,?)",
                ("8001@g.us", "491510000001@s.whatsapp.net"))
    con.execute("INSERT INTO chat (_id, jid_row_id, subject) VALUES (?,?,?)",
                (4, 8001, "Beispielgruppe"))
    daten = _baue(con=con)
    eintrag = _eintrag(daten, 4)
    assert [t["name"] for t in eintrag["teilnehmer"]] == ["Beispiel Anna"]
    assert eintrag["teilnehmer"][0]["_herkunft"] == "gruppe"


def test_gruppe_mit_tabelle_group_participant():
    """Der exakte Name `group_participant` wird zuerst geprueft (falls vorhanden)."""
    con = _db_bauen()
    con.executescript(
        """
        CREATE TABLE group_participant (_id INTEGER PRIMARY KEY,
            group_jid_row_id INTEGER, user_jid_row_id INTEGER);
        """
    )
    _jid(con, 8001, "8001", "g.us", 1)
    _jid(con, 1, "491510000001", "s.whatsapp.net", 0)
    con.execute("INSERT INTO group_participant (group_jid_row_id, user_jid_row_id) "
                "VALUES (?,?)", (8001, 1))
    con.execute("INSERT INTO chat (_id, jid_row_id, subject) VALUES (?,?,?)",
                (4, 8001, "Beispielgruppe"))
    eintrag = _eintrag(_baue(con=con), 4)
    assert [t["name"] for t in eintrag["teilnehmer"]] == ["Beispiel Anna"]
    assert eintrag["teilnehmer"][0]["_herkunft"] == "gruppe"


def test_statistik_summen():
    statistik = _baue()["statistik"]
    assert statistik["chats_gesamt"] == 7
    assert statistik["chats_mit_kontakt"] == 4
    assert statistik["chats_ohne_kontakt"] == 3
    assert statistik["chats_einzel"] == 3
    assert statistik["chats_newsletter"] == 1
    assert statistik["gruppen_gesamt"] == 3
    assert statistik["gruppen_vollstaendig"] == 1
    assert statistik["gruppen_teilweise"] == 1
    assert statistik["gruppen_unbekannt"] == 1
    assert statistik["gruppen_ohne_mitgliederdaten"] == 0
    assert statistik["mitglieder_gesamt"] == 6
    assert statistik["mitglieder_mit_kontakt"] == 4
    assert statistik["mitglieder_ohne_kontakt"] == 2
    assert statistik["chats_mit_whatsapp_namen"] == 2
    assert statistik["geburtstage_im_telefonbuch"] == 2


def test_gruppen_ohne_mitgliederdaten_zaehlen_als_unbekannt():
    statistik = _baue(con=_fixture_db(mit_gpu=False))["statistik"]
    # Gruppe 5 hat nur Verlaufsdaten, Gruppe 4/6 haben ohne gpu keine Daten:
    # 8001 und 8003 tauchen dann nirgends auf -> ohne Mitgliederdaten.
    assert statistik["gruppen_gesamt"] == 3
    assert statistik["gruppen_ohne_mitgliederdaten"] == 2


# ── JSON-Ausgabe und Bericht ────────────────────────────────────────────────

def test_json_struktur_und_maske(tmp_path: Path):
    daten = _baue()
    ziel = z.schreibe_json(daten, tmp_path / "whatsapp_zuordnung.json")
    assert ziel.is_file()
    roh = ziel.read_text(encoding="utf-8")
    geladen = json.loads(roh)
    assert geladen["statistik"]["chats_gesamt"] == 7
    assert geladen["geburtstage"][0] == {"name": "Beispiel Anna", "tag": 12, "monat": 5}
    # Volle Nummern duerfen nirgends stehen, die Maske muss stehen.
    for verboten in ["491510000001", "491510000002", "491510000009", "491510000003",
                     "1510000001", "0049 151 0000002", "+49 151 0000001", "9001@" , "9002@"]:
        assert verboten not in roh, f"Nummer/Adresse leckt in die JSON: {verboten!r}"
    assert "***0001" in roh
    assert "***0002" in roh
    assert "AnnaBeispielWA" in roh


def test_bericht_nur_zahlen():
    daten = _baue()
    text = "\n".join(z.bericht_zeilen(daten["statistik"]))
    for verboten in ["Beispiel", "Anna", "Bert", "Cem", "Dora", "0001", "0002", "0009"]:
        assert verboten not in text, f"Privates Detail im Bericht: {verboten!r}"
    assert "7 gesamt" in text
    assert "4" in text and "3" in text


def test_leere_datenbank_und_kaputte_quellen():
    """Fehlen alle optionalen Tabellen, darf nichts abstuerzen."""
    con = _db_bauen()
    _jid(con, 1, "491510000001", "s.whatsapp.net", 0)
    con.execute("INSERT INTO chat (_id, jid_row_id, subject) VALUES (?,?,?)", (1, 1, None))
    daten = _baue(con=con)
    eintrag = _eintrag(daten, 1)
    assert eintrag["telefonbuch_namen"] == ["Beispiel Anna"]
    assert daten["statistik"]["gruppen_gesamt"] == 0


def test_kurze_kennung_ist_keine_nummer():
    """Der Systemkontakt 0@s.whatsapp.net bekommt keine Nummer und keine Maske."""
    con = _db_bauen()
    _jid(con, 1, "0", "s.whatsapp.net", 7)
    con.execute("INSERT INTO chat (_id, jid_row_id, subject) VALUES (?,?,?)", (1, 1, None))
    eintrag = _eintrag(_baue(con=con), 1)
    assert eintrag["art"] == "einzel"
    assert eintrag["nummer_maske"] is None
    assert eintrag["telefonbuch_namen"] == []
    assert eintrag["kontakt_treffer"] is False
