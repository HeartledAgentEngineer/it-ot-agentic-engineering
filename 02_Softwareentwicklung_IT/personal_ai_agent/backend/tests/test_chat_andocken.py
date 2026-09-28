"""Pruefungen fuer ``tools/foto_sortierung/chat_andocken.py`` (N27 Schritt 2, 28.09.2026).

Alles OHNE Netz und OHNE echte Daten: die Datenbank ist eine **In-Memory-
Attrappe** mit den vier nachgebauten Tabellen ``message``, ``chat``, ``jid`` und
``message_media``; Ereignisse und Zuordnung sind erfundene Dateien in
``tmp_path``. **Nur erfundene Beispielnamen und -kennungen** — echte Kontakte,
Gruppen, Nummern und Nachrichteninhalte kommen hier nicht vor. Kein Test
oeffnet ``msgstore.db`` oder eine Datei unter ``~/foto_sortierung/``.

Geprueft werden: die exakten Fenstergrenzen, das strengere Gruppenfenster, das
undatierte Ereignis, die Kuerzung auf 25 Kennungen, die Namensaufloesung
(eindeutig/mehrdeutig/fehlend), die Zaehl-Invarianten, das eingefrorene Schema
(**kein Textfeld**), die feste Sortierung, das atomare Schreiben nur ausserhalb
des Repos, die Trockenlauf-Garantien, das Fehlen von Schreib-Anweisungen im
Quelltext und die Idempotenz (bei vorgegebenem ``stand`` byte-gleich).

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_chat_andocken.py -q
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "chat_andocken.py"

STAND = "2026-09-28T20:00:00+02:00"

UTC = datetime.timezone.utc


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None, f"nicht gefunden: {pfad}"
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


ca = _laden(WERKZEUG, "chat_andocken")


# ── Erfundene Beispielwerte ────────────────────────────────────────────────

TAG = "2020-01-15"
TAG_ZWEI = "2020-02-10"

# Chat-Kennungen (erfunden).
CHAT_EINZEL = 1
CHAT_GRUPPE = 2
CHAT_KANAL = 3
CHAT_OHNE = 4          # nicht in der Zuordnung
CHAT_KUERZUNG = 5

# Absender-JIDs (erfunden).
JID_ANNA = 101         # Einzelchat-Partner
JID_BERT = 201         # Gruppenmitglied, eindeutig
JID_CEM = 202          # Gruppenmitglied, eindeutig
JID_ZWEIDEUTIG = 203   # Gruppenmitglied, zwei Namen auf derselben Maske
JID_FREMD = 204        # Gruppenabsender ausserhalb der Mitgliederliste


def _ts(jahr, monat, tag, stunde, minute, sekunde) -> int:
    zeit = datetime.datetime(jahr, monat, tag, stunde, minute, sekunde, tzinfo=UTC)
    return int(zeit.timestamp() * 1000)


# Fenstergrenzen (Einzelchat: [Vortag 00:00, datum+2 Tage 00:00)).
T_FRUEH = _ts(2020, 1, 13, 23, 59, 59)         # zwei Tage vor dem Tag: raus
T_VORTAG = _ts(2020, 1, 14, 23, 59, 59)        # letzte Sekunde des Vortags: drin (Einzel)
T_VORTAG_MITTE = _ts(2020, 1, 14, 12, 0, 0)    # Vortag, nicht am Ereignistag (Gruppe: raus)
T_TAG = _ts(2020, 1, 15, 12, 0, 0)             # der Ereignistag: drin
T_NACH = _ts(2020, 1, 16, 23, 59, 59)          # letzte Sekunde vor dem +2. Tag: drin
T_PLUS2 = _ts(2020, 1, 17, 0, 0, 0)            # 00:00 des +2. Tages: raus
T_TAG2 = _ts(2020, 2, 10, 12, 0, 0)            # zweites Ereignis


def _db_bauen(ziel: str = ":memory:") -> sqlite3.Connection:
    con = sqlite3.connect(ziel)
    con.executescript(
        """
        CREATE TABLE message (_id INTEGER PRIMARY KEY, chat_row_id INTEGER,
                              from_me INTEGER, sender_jid_row_id INTEGER,
                              timestamp INTEGER);
        CREATE TABLE chat (_id INTEGER PRIMARY KEY, jid_row_id INTEGER, subject TEXT);
        CREATE TABLE jid (_id INTEGER PRIMARY KEY, user TEXT);
        CREATE TABLE message_media (message_row_id INTEGER, chat_row_id INTEGER);
        """
    )
    return con


def _fixture_db(ziel: str = ":memory:") -> sqlite3.Connection:
    con = _db_bauen(ziel)
    con.executemany("INSERT INTO jid (_id, user) VALUES (?,?)", [
        (JID_ANNA, "491510000001"),
        (JID_BERT, "491510000002"),
        (JID_CEM, "491510000003"),
        (JID_ZWEIDEUTIG, "491510000004"),
        (JID_FREMD, "491510000009"),
    ])
    con.executemany("INSERT INTO chat (_id, jid_row_id, subject) VALUES (?,?,?)", [
        (CHAT_EINZEL, JID_ANNA, None),
        (CHAT_GRUPPE, 300, "Beispielgruppe"),
        (CHAT_KANAL, 400, "Beispielkanal"),
        (CHAT_OHNE, 500, None),
        (CHAT_KUERZUNG, JID_ANNA, None),
    ])
    con.executemany(
        "INSERT INTO message (_id, chat_row_id, from_me, sender_jid_row_id, timestamp) "
        "VALUES (?,?,?,?,?)",
        [
            # Einzelchat 1: 4 Nachrichten im Fenster (11,12,13,16), 2 ausserhalb.
            (11, CHAT_EINZEL, 1, None, T_TAG),
            (12, CHAT_EINZEL, 0, JID_ANNA, T_TAG),
            (13, CHAT_EINZEL, 0, JID_ANNA, T_VORTAG),
            (14, CHAT_EINZEL, 0, JID_ANNA, T_FRUEH),
            (15, CHAT_EINZEL, 0, JID_ANNA, T_PLUS2),
            (16, CHAT_EINZEL, 0, JID_ANNA, T_NACH),
            # Gruppe 2: 6 Nachrichten am Tag (21..26); Vortag und +2. Tag raus.
            (21, CHAT_GRUPPE, 0, JID_BERT, T_TAG),
            (22, CHAT_GRUPPE, 0, JID_CEM, T_TAG),
            (23, CHAT_GRUPPE, 0, JID_ZWEIDEUTIG, T_TAG),
            (24, CHAT_GRUPPE, 0, JID_FREMD, T_TAG),
            (25, CHAT_GRUPPE, 0, None, T_TAG),
            (26, CHAT_GRUPPE, 1, None, T_TAG),
            (27, CHAT_GRUPPE, 0, JID_BERT, T_VORTAG_MITTE),
            (28, CHAT_GRUPPE, 0, JID_BERT, T_PLUS2),
            # Newsletter/Kanal 3: ±1 Tag, ohne Kontakt.
            (31, CHAT_KANAL, 0, JID_ANNA, T_TAG),
            (32, CHAT_KANAL, 0, JID_ANNA, T_VORTAG),
            # Chat 4 ohne Zuordnung: unbekannte Art = wie Einzelchat.
            (41, CHAT_OHNE, 0, None, T_TAG),
        ])
    # Kuerzung: 26 Nachrichten an einem zweiten Ereignistag.
    con.executemany(
        "INSERT INTO message (_id, chat_row_id, from_me, sender_jid_row_id, timestamp) "
        "VALUES (?,?,?,?,?)",
        [(100 + i, CHAT_KUERZUNG, 0, JID_ANNA, T_TAG2) for i in range(26)])
    # Medien: im Fenster (12, 21) und ausserhalb (14).
    con.executemany(
        "INSERT INTO message_media (message_row_id, chat_row_id) VALUES (?,?)",
        [(12, CHAT_EINZEL), (21, CHAT_GRUPPE), (14, CHAT_EINZEL)])
    con.commit()
    return con


def _zuordnung_dict() -> dict:
    """Erfundene Zuordnung (Struktur wie ``whatsapp_zuordnung.json``)."""
    return {
        "chats": [
            {"chat_row_id": CHAT_EINZEL, "art": "einzel", "kontakt_treffer": True,
             "telefonbuch_namen": ["Beispiel Anna"], "whatsapp_name": None,
             "nummer_maske": "***0001"},
            {"chat_row_id": CHAT_GRUPPE, "art": "gruppe", "kontakt_treffer": False,
             "anzahl_mitglieder": 4, "mitglieder_mit_kontakt": 3,
             "teilnehmer": [
                 {"name": "Beispiel Bert", "nummer_maske": "***0002"},
                 {"name": "Beispiel Cem", "nummer_maske": "***0003"},
                 {"name": "Beispiel Doppelt", "nummer_maske": "***0004"},
                 {"name": "Beispiel Zwilling", "nummer_maske": "***0004"},
                 {"name": None, "nummer_maske": None},
             ]},
            {"chat_row_id": CHAT_KANAL, "art": "newsletter", "kontakt_treffer": False},
            {"chat_row_id": CHAT_KUERZUNG, "art": "einzel", "kontakt_treffer": True,
             "telefonbuch_namen": ["Beispiel Anna"], "whatsapp_name": None,
             "nummer_maske": "***0001"},
        ]
    }


def _zuordnung_geladen() -> dict:
    """Die Zuordnung in der Form, die ``andocken`` erwartet (je ``chat_row_id``).

    Wird gegen ``zuordnung_laden`` geprueft (``test_zuordnung_laden_liest_chats``),
    damit Handform und Ladefunktion nicht auseinanderlaufen.
    """
    return {
        CHAT_EINZEL: {"art": "einzel", "telefonbuch_namen": ["Beispiel Anna"],
                      "whatsapp_name": "", "nummer_maske": "***0001",
                      "teilnehmer": []},
        CHAT_GRUPPE: {"art": "gruppe", "telefonbuch_namen": [],
                      "whatsapp_name": "", "nummer_maske": "",
                      "teilnehmer": [
                          {"name": "Beispiel Bert", "nummer_maske": "***0002"},
                          {"name": "Beispiel Cem", "nummer_maske": "***0003"},
                          {"name": "Beispiel Doppelt", "nummer_maske": "***0004"},
                          {"name": "Beispiel Zwilling", "nummer_maske": "***0004"},
                          {"name": "", "nummer_maske": ""},
                      ]},
        CHAT_KANAL: {"art": "newsletter", "telefonbuch_namen": [],
                     "whatsapp_name": "", "nummer_maske": "", "teilnehmer": []},
        CHAT_KUERZUNG: {"art": "einzel", "telefonbuch_namen": ["Beispiel Anna"],
                        "whatsapp_name": "", "nummer_maske": "***0001",
                        "teilnehmer": []},
    }


def _events() -> list:
    return [
        {"kennung": "E-" + TAG + "_Probe-01", "anlass_id": TAG + "_Probe-01",
         "datum": TAG, "art": "ereignis"},
        {"kennung": "E-" + TAG_ZWEI + "_Probe-02", "anlass_id": TAG_ZWEI + "_Probe-02",
         "datum": TAG_ZWEI, "art": "ereignis"},
    ]


def _baue(ereignisse=None, zuordnung=None, *, stand=STAND):
    con = _fixture_db()
    ereignisse = _events() if ereignisse is None else ereignisse
    ordnung = _zuordnung_geladen() if zuordnung is None else zuordnung
    nachrichten = ca.nachrichten_lesen(con)
    medien = ca.medien_lesen(con)
    namen = ca.namen_lesen(con)
    daten = ca.andocken(ereignisse, ordnung, nachrichten, medien, namen, stand=stand)
    return con, daten


def _knoten(daten, kennung):
    return next(k for k in daten["ereignisse"] if k["kennung"] == kennung)


# ── Schema und Inhalt ─────────────────────────────────────────────────────

def test_schema_schluessel_sind_eingefroren():
    _, daten = _baue()
    knoten = _knoten(daten, "E-" + TAG + "_Probe-01")
    assert set(knoten) == set(ca.KNOTEN_SCHLUESSEL)
    assert knoten["art"] == "chat_andockung"
    assert set(knoten["fenster"]) == set(ca.FENSTER_SCHLUESSEL)
    for chat in knoten["chats"]:
        assert set(chat) == set(ca.CHAT_SCHLUESSEL)
        for b in chat["beteiligte"]:
            assert set(b) == set(ca.BETEILIGTER_SCHLUESSEL)


def test_kein_textfeld_im_schema_oder_in_der_ausgabe():
    _, daten = _baue()
    roh = json.dumps(daten, ensure_ascii=True)
    # Kein Schluessel trägt Nachrichteninhalt — weder "text" noch "inhalt".
    def _pruefe(obj):
        if isinstance(obj, dict):
            for schluessel, wert in obj.items():
                niedrig = str(schluessel).lower()
                assert "text" not in niedrig, f"Textfeld im Schema: {schluessel}"
                assert "inhalt" not in niedrig, f"Inhaltsfeld: {schluessel}"
                _pruefe(wert)
        elif isinstance(obj, list):
            for eintrag in obj:
                _pruefe(eintrag)
    _pruefe(daten)
    assert "text" not in roh.lower()


def test_fenstergrenzen_exakt():
    _, daten = _baue()
    einzel = next(c for c in _knoten(daten, "E-" + TAG + "_Probe-01")["chats"]
                  if c["chat_row_id"] == CHAT_EINZEL)
    # 23:59:59 des Vortags faellt hinein, 00:00 des +2. Tages nicht.
    assert einzel["nachrichten"] == 4
    assert einzel["nachrichten_kennungen"] == [11, 12, 13, 16]
    assert einzel["erste"] == "2020-01-14T23:59:59+00:00"
    assert einzel["letzte"] == "2020-01-16T23:59:59+00:00"
    assert einzel["fenster_tage"] == 1


def test_gruppe_strenger_als_einzelchat():
    _, daten = _baue()
    knoten = _knoten(daten, "E-" + TAG + "_Probe-01")
    gruppe = next(c for c in knoten["chats"] if c["chat_row_id"] == CHAT_GRUPPE)
    # Der Vortags-Mittag (27) faellt nur bei der Gruppe raus.
    assert gruppe["fenster_tage"] == 0
    assert gruppe["nachrichten"] == 6
    assert 27 not in gruppe["nachrichten_kennungen"]
    assert gruppe["erste"] == "2020-01-15T12:00:00+00:00"
    # Und das aeussere Fenster des Ereignisses bleibt ±1 Tag.
    assert knoten["fenster"]["tage"] == 1
    assert knoten["fenster"]["von"] == "2020-01-14T00:00:00+00:00"
    assert knoten["fenster"]["bis"] == "2020-01-17T00:00:00+00:00"


def test_undatiertes_ereignis_wird_gefuehrt():
    ereignis = {"kennung": "E-ohne", "anlass_id": "ohne", "datum": None,
                "art": "ereignis"}
    _, daten = _baue(ereignisse=[ereignis])
    knoten = daten["ereignisse"][0]
    assert knoten["fenster"] is None
    assert knoten["nachrichten_gesamt"] == 0
    assert knoten["chats"] == [] and knoten["chats_anzahl"] == 0
    assert knoten["datum"] is None
    # Undatiert steht hinter datiert.
    _, daten2 = _baue(ereignisse=_events() + [ereignis])
    assert daten2["ereignisse"][-1]["kennung"] == "E-ohne"


def test_kuerzung_auf_25_kennungen():
    _, daten = _baue()
    chat = next(c for c in _knoten(daten, "E-" + TAG_ZWEI + "_Probe-02")["chats"]
                if c["chat_row_id"] == CHAT_KUERZUNG)
    assert chat["nachrichten"] == 26
    assert chat["gekuerzt"] is True
    assert len(chat["nachrichten_kennungen"]) == 25
    assert chat["nachrichten_kennungen"] == sorted(chat["nachrichten_kennungen"])
    assert chat["von_mir"] == 0 and chat["von_anderen"] == 26


def test_namensaufloesung_eindeutig_mehrdeutig_fehlend():
    _, daten = _baue()
    gruppe = next(c for c in _knoten(daten, "E-" + TAG + "_Probe-01")["chats"]
                  if c["chat_row_id"] == CHAT_GRUPPE)
    treffer = {(b["name"], b["nummer_maske"]) for b in gruppe["beteiligte"]}
    # Eindeutig: Bert (***0002) und Cem (***0003).
    assert ("Beispiel Bert", "***0002") in treffer
    assert ("Beispiel Cem", "***0003") in treffer
    # Mehrdeutig (zwei Namen auf ***0004): unbekannt, Maske bleibt stehen.
    assert ("unbekannt", "***0004") in treffer
    # Fehlend (Absender nicht in der Mitgliederliste): unbekannt + Maske.
    assert ("unbekannt", "***0009") in treffer
    # Kein Klartext einer Nummer irgendwo in der Ausgabe.
    roh = json.dumps(daten, ensure_ascii=True)
    assert "4915100000" not in roh


def test_chatname_regeln():
    _, daten = _baue()
    knoten = _knoten(daten, "E-" + TAG + "_Probe-01")
    nach_id = {c["chat_row_id"]: c for c in knoten["chats"]}
    assert nach_id[CHAT_EINZEL]["chat_name"] == "Beispiel Anna"   # Telefonbuch
    assert nach_id[CHAT_GRUPPE]["chat_name"] == "Beispielgruppe"  # chat.subject
    assert nach_id[CHAT_KANAL]["chat_name"] == "unbekannt"        # Newsletter
    assert nach_id[CHAT_OHNE]["chat_name"] == "unbekannt"         # nicht in Zuordnung


def test_from_me_zaehlt_nur_in_von_mir():
    _, daten = _baue()
    knoten = _knoten(daten, "E-" + TAG + "_Probe-01")
    for chat in knoten["chats"]:
        assert chat["von_mir"] + chat["von_anderen"] == chat["nachrichten"]
    einzel = next(c for c in knoten["chats"] if c["chat_row_id"] == CHAT_EINZEL)
    assert einzel["von_mir"] == 1 and einzel["von_anderen"] == 3
    # Der eigene Absender erscheint nie unter beteiligte.
    namen = [b["name"] for b in einzel["beteiligte"]]
    assert namen == ["Beispiel Anna"]


def test_newsletter_traegt_keinen_kontakt():
    _, daten = _baue()
    kanal = next(c for c in _knoten(daten, "E-" + TAG + "_Probe-01")["chats"]
                 if c["chat_row_id"] == CHAT_KANAL)
    assert kanal["nachrichten"] == 2
    assert kanal["beteiligte"] == []


def test_medien_werden_gezaehlt():
    _, daten = _baue()
    knoten = _knoten(daten, "E-" + TAG + "_Probe-01")
    nach_id = {c["chat_row_id"]: c for c in knoten["chats"]}
    assert nach_id[CHAT_EINZEL]["medien"] == 1   # Zeile 12 im Fenster, 14 aussen
    assert nach_id[CHAT_GRUPPE]["medien"] == 1


def test_zaehl_invarianten():
    _, daten = _baue()
    knoten = _knoten(daten, "E-" + TAG + "_Probe-01")
    assert knoten["chats_anzahl"] == len(knoten["chats"])
    assert knoten["nachrichten_gesamt"] == sum(c["nachrichten"] for c in knoten["chats"])
    assert knoten["nachrichten_gesamt"] == 13     # 4 + 6 + 2 + 1
    # Kontakte: Beispiel Anna, Bert, Cem — "unbekannt" zaehlt nicht.
    assert knoten["kontakte_gesamt"] == 3


def test_leere_zuordnung():
    _, daten = _baue(zuordnung={})
    knoten = _knoten(daten, "E-" + TAG + "_Probe-01")
    # Ohne Zuordnung: alle Chats unbekannt, aber die Zaehlungen bleiben.
    for chat in knoten["chats"]:
        assert chat["chat_name"] == "unbekannt"
        # Ohne bekannte Art gilt das ±1-Tag-Fenster — die Gruppe steht dann
        # nicht mehr strenger, deshalb 14 statt 13 (Vortags-Mittag dabei).
        assert chat["fenster_tage"] == 1
    assert knoten["nachrichten_gesamt"] == 14


def test_sortierung_stabil():
    events = [
        {"kennung": "E-b", "anlass_id": "b", "datum": TAG, "art": "ereignis"},
        {"kennung": "E-a", "anlass_id": "a", "datum": TAG, "art": "ereignis"},
        {"kennung": "E-spaet", "anlass_id": "spaet", "datum": TAG_ZWEI,
         "art": "ereignis"},
    ]
    _, daten = _baue(ereignisse=events)
    assert [k["kennung"] for k in daten["ereignisse"]] == ["E-a", "E-b", "E-spaet"]


def test_idempotenz_bei_vorgegebenem_stand(tmp_path):
    _, daten1 = _baue()
    _, daten2 = _baue()
    ziel1 = tmp_path / "a1.jsonl"
    ziel2 = tmp_path / "a2.jsonl"
    ca.andockung_schreiben(str(ziel1), daten1)
    ca.andockung_schreiben(str(ziel2), daten2)
    assert ziel1.read_bytes() == ziel2.read_bytes()


def test_zeile_ohne_stand_unterscheidet_nur_stand(tmp_path):
    _, daten1 = _baue(stand="2026-09-28T20:00:00+02:00")
    _, daten2 = _baue(stand="2026-09-28T21:00:00+02:00")
    z1 = [ca.knoten_zeile(k) for k in daten1["ereignisse"]]
    z2 = [ca.knoten_zeile(k) for k in daten2["ereignisse"]]
    for a, b in zip(z1, z2):
        oa = json.loads(a)
        ob = json.loads(b)
        oa.pop("stand")
        ob.pop("stand")
        assert oa == ob


# ── Laden, Fehler, Schutz ─────────────────────────────────────────────────

def test_fehlende_db_ergibt_deutsche_meldung_und_exit(tmp_path, capsys):
    ereignis_pfad = tmp_path / "e.jsonl"
    ereignis_pfad.write_text(json.dumps(_events()[0]) + "\n", encoding="utf-8")
    zuordnung_pfad = tmp_path / "z.json"
    zuordnung_pfad.write_text(json.dumps(_zuordnung_dict()), encoding="utf-8")
    fehlt = tmp_path / "gibtsnicht.db"
    code = ca.haupt(["--ereignisse", str(ereignis_pfad), "--zuordnung",
                     str(zuordnung_pfad), "--db", str(fehlt),
                     "--ausgabe", str(tmp_path / "out.jsonl")])
    assert code != 0
    assert "nicht gefunden" in capsys.readouterr().err.lower()


def test_repo_ziel_ergibt_exit_2(tmp_path, capsys):
    ziel = REPO / "nicht_erlaubt_chat_andockung.jsonl"
    code = ca.haupt(["--ausgabe", str(ziel)])
    assert code == 2
    assert "repo" in capsys.readouterr().err.lower()
    assert not ziel.exists()


def test_trockenlauf_schreibt_nichts(tmp_path):
    ausgabe = tmp_path / "out.jsonl"
    pfade = _cli_eingaben(tmp_path)
    code = ca.haupt(pfade + ["--trocken", "--ausgabe", str(ausgabe)])
    assert code == 0
    assert not ausgabe.exists()


def _cli_eingaben(tmp_path) -> list:
    """Legt echte (erfundene) Dateien fuer die Kommandozeilen-Tests an."""
    db = tmp_path / "attrappe.db"
    con = _fixture_db(str(db))
    con.close()
    ereignis_pfad = tmp_path / "e.jsonl"
    with open(ereignis_pfad, "w", encoding="utf-8") as datei:
        for eintrag in _events():
            datei.write(json.dumps(eintrag) + "\n")
    zuordnung_pfad = tmp_path / "z.json"
    zuordnung_pfad.write_text(json.dumps(_zuordnung_dict()), encoding="utf-8")
    return ["--ereignisse", str(ereignis_pfad), "--zuordnung", str(zuordnung_pfad),
            "--db", str(db)]


def test_schreiben_atomar_und_ohne_tmp_rest(tmp_path):
    ausgabe = tmp_path / "out.jsonl"
    pfade = _cli_eingaben(tmp_path)
    code = ca.haupt(pfade + ["--schreiben", "--ausgabe", str(ausgabe)])
    assert code == 0
    assert ausgabe.exists()
    assert not list(tmp_path.glob("*.tmp"))
    zeilen = [z for z in ausgabe.read_text(encoding="utf-8").splitlines() if z.strip()]
    assert len(zeilen) == len(_events())
    for zeile in zeilen:
        obj = json.loads(zeile)
        assert obj["art"] == "chat_andockung"


def test_ereignisse_laden_fehler_deutsch(tmp_path):
    with pytest.raises(ValueError, match="nicht gefunden"):
        ca.ereignisse_laden(str(tmp_path / "fehlt.jsonl"))


def test_zuordnung_laden_fehler_deutsch(tmp_path):
    with pytest.raises(ValueError, match="nicht gefunden"):
        ca.zuordnung_laden(str(tmp_path / "fehlt.json"))


def test_zuordnung_laden_liest_chats(tmp_path):
    pfad = tmp_path / "z.json"
    pfad.write_text(json.dumps(_zuordnung_dict()), encoding="utf-8")
    geladen = ca.zuordnung_laden(str(pfad))
    # Der Lader liefert genau die Form, die ``andocken`` erwartet.
    assert geladen == _zuordnung_geladen()


def test_db_oeffnen_nur_lesend(tmp_path):
    db = tmp_path / "attrappe.db"
    con = _fixture_db(str(db))
    con.close()
    lesend = ca.db_oeffnen(str(db))
    try:
        with pytest.raises(sqlite3.OperationalError):
            lesend.execute("CREATE TABLE verboten (x INTEGER)")
    finally:
        lesend.close()


def test_schreibsperre_ist_belegt(tmp_path):
    """Die Verbindung aus ``db_oeffnen`` laesst **kein** Schreiben zu.

    Attrappen-Datei im ``tmp_path`` mit erfundenen Tabellen und Zeilen: jeder
    Schreibversuch (``INSERT``, ``UPDATE``, ``CREATE TABLE``) muss ueber diese
    Verbindung als ``sqlite3.OperationalError`` scheitern — die Schreibsperre
    ist damit dauerhaft abgesichert, nicht nur einmal per Live-Pruefung.
    """
    db = tmp_path / "attrappe.db"
    con = _fixture_db(str(db))
    con.close()
    assert db.stat().st_size > 0
    lesend = ca.db_oeffnen(str(db))
    try:
        for anweisung in (
            "INSERT INTO message (_id, chat_row_id, from_me, sender_jid_row_id, "
            "timestamp) VALUES (999, 1, 0, NULL, 0)",
            "UPDATE message SET from_me = 1 WHERE _id = 11",
            "CREATE TABLE verboten (x INTEGER)",
        ):
            with pytest.raises(sqlite3.OperationalError):
                lesend.execute(anweisung)
    finally:
        lesend.close()


def _eingabedateien(pfade: list) -> list:
    """Die Dateipfade hinter den ``--``-Schaltern einer ``haupt``-Argumentliste."""
    return [Path(pfade[i + 1]) for i, wert in enumerate(pfade)
            if isinstance(wert, str) and wert.startswith("--")]


def test_eingaben_bleiben_byte_und_mtime_identisch(tmp_path):
    """Der volle Lauf (Laden + Andocken + Schreiben) ruehrt die Eingaben nicht an.

    Attrappen-Dateien im ``tmp_path`` (Kopie einer selbst erzeugten kleinen
    SQLite-Datei, erfundene Ereignisse/Zuordnung). Nach dem Lauf mit
    ``--schreiben`` muessen **Bytes und mtime** jeder Eingabedatei exakt
    unveraendert sein — insbesondere der SQLite-Attrappe. So kann der Lauf
    eine Eingabe nie stillschweigend veraendern.
    """
    ausgabe = tmp_path / "out.jsonl"
    pfade = _cli_eingaben(tmp_path)
    eingaben = _eingabedateien(pfade)
    assert eingaben, "keine Eingabedateien in der Argumentliste gefunden"
    assert len(eingaben) == 3
    vorher = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in eingaben}

    code = ca.haupt(pfade + ["--schreiben", "--ausgabe", str(ausgabe)])
    assert code == 0
    assert ausgabe.exists()

    for pfad, (bytes_vorher, mtime_vorher) in vorher.items():
        assert pfad.read_bytes() == bytes_vorher, f"Bytes veraendert: {pfad.name}"
        assert pfad.stat().st_mtime_ns == mtime_vorher, f"mtime veraendert: {pfad.name}"


# ── Quelltext-Garantien ───────────────────────────────────────────────────

def test_quelltext_ohne_schreib_anweisungen():
    quelltext = WERKZEUG.read_text(encoding="utf-8")
    for verboten in ("INSERT", "UPDATE", "DELETE"):
        assert verboten not in quelltext, f"verbotene Anweisung im Quelltext: {verboten}"
    assert "SELECT" in quelltext
    # Kein Netz und kein Loeschen ausser der eigenen temp-Datei.
    assert "import requests" not in quelltext
    assert "import httpx" not in quelltext
    assert "urllib" not in quelltext
    assert quelltext.count("os.remove") == 1
    # Nur die erlaubten Standardbibliotheken.
    for modul in ("import argparse", "import bisect", "import datetime",
                  "import json", "import os", "import sqlite3", "import sys"):
        assert modul in quelltext


def test_keine_klartext_nummer_in_der_knotenzeile():
    _, daten = _baue()
    roh = "\n".join(ca.knoten_zeile(k) for k in daten["ereignisse"])
    # Masken sind erlaubt, vollstaendige Ziffernketten nicht.
    assert "***0001" in roh or "***0002" in roh
    assert "491510000001" not in roh
    assert "491510000002" not in roh
