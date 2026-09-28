"""Pruefungen fuer ``backend/scripts/whatsapp_db_import.py`` (msgstore -> Archiv).

Alles OHNE Netz und OHNE echte Daten: die Datenbank ist eine In-Memory-Attrappe
mit dem nachgebauten Schema, die Archivdatei liegt in ``tmp_path``. Es kommen
ausschliesslich erfundene Beispielnamen, -nummern und -texte vor.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_whatsapp_db_import.py -q
"""

from __future__ import annotations

import io
import json
import sqlite3

from scripts import whatsapp_db_import as wdi


# ── Erfundene Fixture-Daten ─────────────────────────────────────────────────

TEXT_ANNA = "Hallo aus der Beispieldatei"
TEXT_BERT = "Antwort aus der Beispieldatei"
TEXT_GRUPPE = "Beispielbeitrag in der Gruppe"
TEXT_SYSTEM = "Beispiel-Systemtext mit Inhalt"

# Minutenraster: 2020-09-13T12:26:40Z = 1.600.000.000.000 ms
BASIS_MS = 1_600_000_000_000


def _db_bauen() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(
        """
        CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT, server TEXT, agent INTEGER,
                          type INTEGER, raw_string TEXT, device INTEGER);
        CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT,
                           hidden INTEGER DEFAULT 0, archived INTEGER DEFAULT 0);
        CREATE TABLE newsletter (chat_row_id INTEGER, name TEXT, name_id TEXT);
        CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER, from_me INTEGER,
                              sender_jid_row_id INTEGER, timestamp INTEGER, text_data TEXT,
                              message_type INTEGER);
        CREATE TABLE message_media (message_row_id INTEGER, file_path TEXT, media_name TEXT);
        CREATE TABLE message_revoked (message_row_id INTEGER, revoked_key_id TEXT);
        CREATE TABLE message_system (message_row_id INTEGER, action_type INTEGER);
        CREATE TABLE message_call_log (message_row_id INTEGER, call_log_row_id INTEGER);
        CREATE TABLE call_log (_id INTEGER PRIMARY KEY, video_call INTEGER, duration INTEGER);
        CREATE TABLE message_location (message_row_id INTEGER, url TEXT);
        """
    )
    return con


def _fixture_db() -> sqlite3.Connection:
    """Drei Chats (Einzel, Gruppe, Kanal) plus ein verwaister Chat-Rest."""
    con = _db_bauen()
    jids = [
        (1, "491510000001", "s.whatsapp.net", 0),
        (2, "8001", "g.us", 1),
        (3, "9999", "newsletter", 21),
        (4, "9001", "lid", 18),
    ]
    con.executemany(
        "INSERT INTO jid (_id, user, server, agent, type, raw_string, device) "
        "VALUES (?,?,?,NULL,?,?,0)",
        [(i, u, s, t, f"{u}@{s}") for i, u, s, t in jids],
    )
    con.executemany(
        "INSERT INTO chat (_id, jid_row_id, subject) VALUES (?,?,?)",
        [(1, 1, None), (2, 2, "Beispielgruppe"), (3, 3, None), (4, 4, None)],
    )
    con.execute("INSERT INTO newsletter (chat_row_id, name) VALUES (3, 'Beispielkanal')")

    m = [
        # (mid, chat, von_mir, ts, text)
        (1, 1, 1, BASIS_MS, TEXT_ANNA),
        (2, 1, 0, BASIS_MS + 61_000, TEXT_BERT),
        (3, 1, 0, BASIS_MS + 120_000, None),          # Anhang
        (4, 1, 0, BASIS_MS + 180_000, None),          # geloescht (fremd)
        (5, 1, 1, BASIS_MS + 240_000, None),          # geloescht (eigen)
        (6, 2, 0, BASIS_MS + 300_000, None),          # System ohne Text
        (7, 2, 1, BASIS_MS + 360_000, TEXT_GRUPPE),
        (8, 3, 0, BASIS_MS + 420_000, None),          # Anruf verpasst
        (9, 3, 1, BASIS_MS + 480_000, None),          # Anruf gefuehrt
        (10, 1, 0, BASIS_MS + 540_000, None),         # Standort
        (11, 1, 1, BASIS_MS + 600_000, "\u200eRandvoll\u200f"),  # unsichtbare Zeichen
        (12, 2, 0, BASIS_MS + 660_000, TEXT_SYSTEM),  # System MIT Text
        (13, 1, 0, None, "Ohne Zeitstempel"),         # faellt raus, wird gezaehlt
        (14, 4, 1, BASIS_MS + 720_000, "\u200eBeitrag aus LID-Chat\u200f"),
        (15, 1, 0, BASIS_MS + 780_000, None),         # Anhang ohne file_path
        (99, 9999, 0, BASIS_MS + 840_000, "verwaiste Nachricht"),
    ]
    con.executemany(
        "INSERT INTO message (_id, chat_row_id, from_me, sender_jid_row_id, timestamp,"
        " text_data, message_type) VALUES (?,?,?,NULL,?,?,0)",
        m,
    )
    con.executemany(
        "INSERT INTO message_media (message_row_id, file_path, media_name) VALUES (?,?,?)",
        [
            (3, "Media/WhatsApp Images/IMG-BEISPIEL-001.jpg", None),
            (15, None, "beispiel.pdf"),
        ],
    )
    con.execute("INSERT INTO message_revoked (message_row_id) VALUES (4)")
    con.execute("INSERT INTO message_revoked (message_row_id) VALUES (5)")
    con.execute("INSERT INTO message_system (message_row_id, action_type) VALUES (6, 1)")
    con.execute("INSERT INTO message_system (message_row_id, action_type) VALUES (12, 1)")
    con.executemany(
        "INSERT INTO call_log (_id, video_call, duration) VALUES (?,?,?)",
        [(1, 0, 0), (2, 1, 42)],
    )
    con.executemany(
        "INSERT INTO message_call_log (message_row_id, call_log_row_id) VALUES (?,?)",
        [(8, 1), (9, 2)],
    )
    con.execute(
        "INSERT INTO message_location (message_row_id, url) VALUES (10, 'https://maps.google.com/?q=1,2')"
    )
    con.commit()
    return con


def _zuordnung_schreiben(tmp_path):
    """Erfundene Zuordnung: Name fuer Chat 1, WhatsApp-Name fuer Chat 4, Maske fuer Chat 2?"""
    daten = {
        "erstellt": "2026-09-28",
        "statistik": {},
        "geburtstage": [],
        "chats": [
            {"art": "einzel", "chat_row_id": 1, "kontakt_treffer": True,
             "telefonbuch_namen": ["Beispiel Anna"], "whatsapp_name": None,
             "nummer_maske": "***0001"},
            {"art": "einzel", "chat_row_id": 4, "kontakt_treffer": False,
             "telefonbuch_namen": [], "whatsapp_name": "Beispiel Bert",
             "nummer_maske": "***9001"},
            {"art": "gruppe", "chat_row_id": 2, "kontakt_treffer": False,
             "anzahl_mitglieder": 0, "mitglieder_mit_kontakt": 0, "teilnehmer": []},
        ],
    }
    pfad = tmp_path / "zuordnung.json"
    pfad.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    return str(pfad)


def _ziel_schreiben(tmp_path, zeilen):
    pfad = tmp_path / "messages.jsonl"
    with io.open(pfad, "w", encoding="utf-8", newline="\n") as f:
        for r in zeilen:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return str(pfad)


def _bestehende_zeilen():
    """Drei Zeilen im Chat 1, die zu den Datenbankzeilen 1, 2 und 11 passen."""
    return [
        {"conversation_id": "whatsapp-Beispiel Anna", "source": "whatsapp",
         "timestamp": "2020-09-13T12:26:00+00:00", "role": "user", "text": TEXT_ANNA,
         "title": "WhatsApp mit Beispiel Anna", "project": None},
        {"conversation_id": "whatsapp-Beispiel Anna", "source": "whatsapp",
         "timestamp": "2020-09-13T12:27:00+00:00", "role": "kontakt", "text": TEXT_BERT,
         "title": "WhatsApp mit Beispiel Anna", "project": None},
        {"conversation_id": "whatsapp-Beispiel Anna", "source": "whatsapp",
         "timestamp": "2020-09-13T12:36:00+00:00", "role": "user", "text": "Randvoll",
         "title": "WhatsApp mit Beispiel Anna", "project": None},
        {"conversation_id": "beispiel@google.com", "source": "google-kalender",
         "timestamp": "2021-01-01T00:00:00+00:00", "role": "termin", "text": "Beispiel",
         "title": "Beispiel", "project": None},
    ]


def _lauf(tmp_path, db=None, zeilen=None, zuordnung=True, ziel=None):
    """Kompletter Trockenlauf gegen die Attrappen."""
    con = db or _fixture_db()
    if ziel is None:
        ziel = _ziel_schreiben(
            tmp_path, zeilen if zeilen is not None else _bestehende_zeilen())
    best = wdi.lade_bestehende(ziel)
    chats = wdi.lade_chats(con)
    zu = wdi.lade_zuordnung(_zuordnung_schreiben(tmp_path) if zuordnung else None)
    zusatz = wdi.lade_zusatz(con)
    ergebnis = wdi.baue_zeilen(con, best, chats, zu, zusatz)
    return ergebnis, best, chats, ziel


def _texte(ergebnis):
    return [r["text"] for r in ergebnis["zeilen"]]


# ── Einordnung ──────────────────────────────────────────────────────────────

def test_text_und_rollen(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    zeilen = {r["text"]: r for r in ergebnis["zeilen"]}
    assert zeilen[TEXT_GRUPPE]["role"] == "user"
    assert zeilen["Beitrag aus LID-Chat"]["role"] == "user"


def test_fremder_text_ist_kontakt(tmp_path):
    # Nicht uebersprungene Fremdzeilen (Anhang, geloescht) tragen Rolle kontakt.
    ergebnis, _, _, _ = _lauf(tmp_path)
    zeilen = {r["text"]: r for r in ergebnis["zeilen"]}
    assert zeilen["IMG-BEISPIEL-001.jpg (Datei angehängt)"]["role"] == "kontakt"
    assert zeilen[wdi.TEXT_GELOESCHT_FREMD]["role"] == "kontakt"


def test_anhang_platzhalter_mit_dateiname(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    assert "IMG-BEISPIEL-001.jpg (Datei angehängt)" in _texte(ergebnis)


def test_anhang_ohne_pfad_nutzt_media_name(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    assert "beispiel.pdf (Datei angehängt)" in _texte(ergebnis)


def test_geloeschte_nachrichten_wortlaut(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    zeilen = {r["text"]: r for r in ergebnis["zeilen"]}
    assert zeilen[wdi.TEXT_GELOESCHT_FREMD]["role"] == "kontakt"
    assert zeilen[wdi.TEXT_GELOESCHT_EIGEN]["role"] == "user"


def test_anrufe_verpasst_und_gefuehrt(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    zeilen = {r["text"]: r for r in ergebnis["zeilen"]}
    assert zeilen["Verpasster Sprachanruf"]["role"] == "kontakt"
    assert zeilen["Videoanruf"]["role"] == "user"


def test_standort_mit_url(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    assert "Standort: https://maps.google.com/?q=1,2" in _texte(ergebnis)


def test_system_ohne_text_wird_uebersprungen(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    z = ergebnis["zahlen"]
    assert z["uebersprungen_system"] == 1
    assert z["system_text"] == 1
    # Systemzeile mit Text bleibt, mit Systemrolle
    zeilen = {r["text"]: r for r in ergebnis["zeilen"]}
    assert zeilen[TEXT_SYSTEM]["role"] == "system"


def test_unsichtbare_zeichen_verschwinden(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    # Fuehrende/abschliessende Steuerzeichen (U+200E/U+200F) fallen weg
    assert "Beitrag aus LID-Chat" in _texte(ergebnis)
    assert all("\u200e" not in t and "\u200f" not in t for t in _texte(ergebnis))


def test_ohne_zeitstempel_wird_gezaehlt(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    assert ergebnis["zahlen"]["ohne_zeit"] == 1
    assert "Ohne Zeitstempel" not in _texte(ergebnis)


def test_verwaiste_nachricht_wird_gezaehlt(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    assert ergebnis["zahlen"]["ohne_chat"] == 1
    assert "verwaiste Nachricht" not in _texte(ergebnis)


def test_zeitstempel_sind_iso_utc(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    for r in ergebnis["zeilen"]:
        assert r["timestamp"].endswith("+00:00")
        assert r["source"] == "whatsapp"
        assert r["project"] is None


def test_zeilen_sind_chronologisch(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    zeiten = [r["timestamp"] for r in ergebnis["zeilen"]]
    assert zeiten == sorted(zeiten)


# ── Kennungen und Titel ─────────────────────────────────────────────────────

def test_einzelchat_kennung_und_titel(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    assert any(r["conversation_id"] == "whatsapp-Beispiel Anna" for r in ergebnis["zeilen"])
    assert any(r["title"] == "WhatsApp mit Beispiel Anna" for r in ergebnis["zeilen"])


def test_gruppenkennung_aus_subject(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    zeilen = {r["text"]: r for r in ergebnis["zeilen"]}
    assert zeilen[TEXT_GRUPPE]["conversation_id"] == "whatsapp-gruppe-Beispielgruppe"
    assert zeilen[TEXT_GRUPPE]["title"] == "WhatsApp-Gruppe: Beispielgruppe"


def test_kanalkennung_aus_newsletter(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    zeilen = {r["text"]: r for r in ergebnis["zeilen"]}
    assert zeilen["Verpasster Sprachanruf"]["conversation_id"] == "whatsapp-kanal-Beispielkanal"


def test_lid_name_aus_zuordnung(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    zeilen = {r["text"]: r for r in ergebnis["zeilen"]}
    assert zeilen["Beitrag aus LID-Chat"]["conversation_id"] == "whatsapp-Beispiel Bert"


def test_ohne_zuordnung_bleibt_die_zeile(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path, zuordnung=False)
    zeilen = {r["text"]: r for r in ergebnis["zeilen"]}
    # Ohne Zuordnung: Ersatzkennung nach chat_row_id statt Name
    assert zeilen[TEXT_GRUPPE]["conversation_id"] == "whatsapp-gruppe-Beispielgruppe"
    assert zeilen["Beitrag aus LID-Chat"]["conversation_id"] == "whatsapp-unbekannt-4"


def test_kollision_bekommt_ziffer(tmp_path):
    con = _fixture_db()
    # Zweiter Chat mit demselben Telefonbuch-Namen
    con.execute("INSERT INTO jid (_id, user, server, agent, type, raw_string, device) "
                "VALUES (5, '491510000005', 's.whatsapp.net', NULL, 0, 'x', 0)")
    con.execute("INSERT INTO chat (_id, jid_row_id, subject) VALUES (5, 5, NULL)")
    con.execute("INSERT INTO message (_id, chat_row_id, from_me, sender_jid_row_id, timestamp,"
                " text_data, message_type) VALUES (50, 5, 0, NULL, ?, 'Zweiter Kanal', 0)",
                (BASIS_MS + 900_000,))
    con.commit()
    zuordnung = {
        "chats": [
            {"art": "einzel", "chat_row_id": 1, "telefonbuch_namen": ["Beispiel Anna"]},
            {"art": "einzel", "chat_row_id": 4, "whatsapp_name": "Beispiel Bert"},
            {"art": "einzel", "chat_row_id": 5, "telefonbuch_namen": ["Beispiel Anna"]},
        ]
    }
    p = tmp_path / "zu2.json"
    p.write_text(json.dumps(zuordnung, ensure_ascii=False), encoding="utf-8")
    ziel = _ziel_schreiben(tmp_path, _bestehende_zeilen())
    best = wdi.lade_bestehende(ziel)
    chats = wdi.lade_chats(con)
    zu = wdi.lade_zuordnung(str(p))
    ergebnis = wdi.baue_zeilen(con, best, chats, zu, wdi.lade_zusatz(con))
    ids = {r["text"]: r["conversation_id"] for r in ergebnis["zeilen"]}
    assert ids["Zweiter Kanal"] == "whatsapp-Beispiel Anna-2"


# ── Abgleich, Wiederholbarkeit, Schreiben ───────────────────────────────────

def test_verknuepfung_findet_chat_und_ueberspringt_duplikate(tmp_path):
    ergebnis, _, _, _ = _lauf(tmp_path)
    bericht = ergebnis["verknuepfung"]["bericht"]
    assert any(b["chat"] == 1 and b["treffer"] == 3 for b in bericht)
    assert ergebnis["zahlen"]["duplikat"] >= 3
    assert TEXT_ANNA not in _texte(ergebnis)
    assert TEXT_BERT not in _texte(ergebnis)


def test_trockenlauf_schreibt_nichts(tmp_path):
    _, _, _, ziel = _lauf(tmp_path)
    vorher = io.open(ziel, encoding="utf-8").read()
    rc = wdi.main(["--db", "fehlt.db", "--ziel", ziel, "--trocken"])
    assert rc == 2  # fehlende Datenbank -> sauberer Abbruch, nichts geschrieben
    assert io.open(ziel, encoding="utf-8").read() == vorher


def test_schreiben_haengt_an_und_sichert(tmp_path):
    con = _fixture_db()
    ergebnis, best, chats, ziel = _lauf(tmp_path, db=con)
    vorher = io.open(ziel, encoding="utf-8").read()
    bericht = dict(ergebnis["zahlen"])
    wdi.schreibe_anhaengen(ziel, ergebnis["zeilen"], bericht, jetzt="20260928-1200")
    nachher = io.open(ziel, encoding="utf-8").read()
    assert nachher.startswith(vorher)                    # nichts geaendert, nur angehaengt
    sicherung = ziel.replace(".jsonl", "_vor_import_20260928-1200.jsonl")
    assert io.open(sicherung, encoding="utf-8").read() == vorher
    neue = [z for z in nachher.splitlines() if z.strip()][len(vorher.splitlines()):]
    assert len(neue) == ergebnis["zahlen"]["neue_zeilen"]
    with io.open(ziel, "rb") as f:
        roh = f.read()
    assert b"\r\n" in roh[-500:]                          # CRLF wie der Vorbestand


def test_zweiter_lauf_findet_nichts_neues(tmp_path):
    con = _fixture_db()
    ergebnis, best, chats, ziel = _lauf(tmp_path, db=con)
    bericht = dict(ergebnis["zahlen"])
    wdi.schreibe_anhaengen(ziel, ergebnis["zeilen"], bericht, jetzt="20260928-1200")
    # Zweiter Lauf gegen den neuen Stand (dieselbe Datei, nicht neu geschrieben)
    ergebnis2, _, _, _ = _lauf(tmp_path, db=_fixture_db(), ziel=ziel)
    assert ergebnis2["zahlen"]["neue_zeilen"] == 0
    assert ergebnis2["zahlen"]["duplikat"] == ergebnis["zahlen"]["neue_zeilen"] + 3
    assert ergebnis2["zeilen"] == []


def test_bericht_zaehlt_nur(tmp_path):
    ergebnis, best, chats, _ = _lauf(tmp_path)
    text = wdi.bericht_text(ergebnis, best, "Trockenlauf", chats)
    for geheim in ("Beispiel Anna", "Beispiel Bert", "491510000001", "***9001",
                   "Beispielgruppe", "Beispielkanal", "IMG-BEISPIEL-001.jpg"):
        assert geheim not in text


def test_hauptlauf_schreibt_und_berichtet(tmp_path, capsys):
    con = _fixture_db()
    ziel = _ziel_schreiben(tmp_path, _bestehende_zeilen())
    zu = _zuordnung_schreiben(tmp_path)
    db_pfad = str(tmp_path / "msgstore.db")
    con2 = sqlite3.connect(db_pfad)
    con.backup(con2)
    con2.close()
    vorher = io.open(ziel, encoding="utf-8").read()

    rc = wdi.main(["--db", db_pfad, "--ziel", ziel, "--zuordnung", zu, "--schreiben"])
    assert rc == 0
    ausgabe = capsys.readouterr().out
    assert "Angehaengt" in ausgabe
    for geheim in ("Beispiel Anna", "Beispiel Bert", "491510000001", "***9001",
                   "Beispielgruppe", "Beispielkanal"):
        assert geheim not in ausgabe

    nachher = io.open(ziel, encoding="utf-8").read()
    assert nachher.startswith(vorher)                     # nur angehaengt
    neue = [z for z in nachher[len(vorher):].splitlines() if z.strip()]
    assert len(neue) >= 1
    assert all(json.loads(z)["source"] == "whatsapp" for z in neue)
    # Sicherungskopie der Datei liegt daneben
    sicherungen = list(tmp_path.glob("*_vor_import_*.jsonl"))
    assert len(sicherungen) == 1
    assert io.open(sicherungen[0], encoding="utf-8").read() == vorher
