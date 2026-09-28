"""Pruefungen fuer ``backend/scripts/archiv_index_ergaenzen.py``.

Alles OHNE Netz, OHNE echte Daten und OHNE die private Archivdatei: die
Datenbanken sind Attrappen in ``tmp_path`` (Schema wie im Bestand), der
Einbetter ist eine Attrappe. Inhalte und Namen sind erfunden.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_archiv_index_ergaenzen.py -q
"""

from __future__ import annotations

import hashlib
import io
import os
import sqlite3

import pytest

from scripts import archiv_index_ergaenzen as aie
from scripts.archiv_index_bauen import SCHEMA_SQL, ZEICHEN_JE_TOKEN, _vektor_blob

MEMORY_SCHEMA = """
CREATE TABLE messages (id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL,
  source TEXT NOT NULL, timestamp TEXT, role TEXT, text TEXT, title TEXT, project TEXT);
CREATE TABLE chunks (id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
  text TEXT, nachricht_ids TEXT, beginn TEXT, ende TEXT, title TEXT, project TEXT,
  teil INTEGER DEFAULT 0, hat_vektor INTEGER DEFAULT 0);
CREATE TABLE chunks_fts USING_PLACEHOLDER;
"""

# Fuer die Attrappe ohne FTS reicht das hier:
MEMORY_SCHEMA = MEMORY_SCHEMA.replace("CREATE TABLE chunks_fts USING_PLACEHOLDER;", "")


ALT_VEKTOR = [0.1, 0.2, 0.3, 0.4]


class StubEinbetter:
    """Liefert feste Vektoren und zaehlt Token — wie ``EinbetterOpenRouter``."""

    modell = "attrappe"

    def __init__(self, tokens_je_text: int = 12, dimension: int = 4):
        self.tokens_je_text = tokens_je_text
        self.dimension = dimension
        self.token_gesamt = 0
        self.aufrufe = 0

    def __call__(self, texte):
        self.token_gesamt += len(texte) * self.tokens_je_text
        self.aufrufe += 1
        return [[0.25] * self.dimension for _ in texte], len(texte) * self.tokens_je_text


# ── Attrappen ───────────────────────────────────────────────────────────────

def _memory_db(pfad: str, neue_nachrichten: int = 2, neue_chunks: int = 2) -> str:
    """memory.db mit zwei bestehenden und N neuen Zeilen."""
    con = sqlite3.connect(pfad)
    con.executescript(MEMORY_SCHEMA)
    con.executemany(
        "INSERT INTO messages (id, conversation_id, source, timestamp, role, text, title, project)"
        " VALUES (?,?,?,?,?,?,?,NULL)",
        [
            (0, "beispiel-a", "chatgpt", "2021-01-01T10:00:00+00:00", "user", "alte Frage", "Titel A"),
            (1, "beispiel-a", "chatgpt", "2021-01-01T10:01:00+00:00", "assistant", "alte Antwort", "Titel A"),
        ],
    )
    for i in range(neue_nachrichten):
        con.execute(
            "INSERT INTO messages (id, conversation_id, source, timestamp, role, text, title, project)"
            " VALUES (?,?,?,?,?,?,?,NULL)",
            (2 + i, "beispiel-b" if i % 2 == 0 else "beispiel-a", "whatsapp",
             f"2026-09-01T10:0{i}:00+00:00", "user", f"neue Nachricht {i}", "Titel B"),
        )
    con.execute(
        "INSERT INTO chunks (id, conversation_id, source, text, nachricht_ids, beginn, ende,"
        " title, project, teil, hat_vektor) VALUES (1,'beispiel-a','chatgpt','alte Frage',"
        "'[0]','2021-01-01T10:00:00+00:00','2021-01-01T10:00:00+00:00','Titel A',NULL,0,1)",
    )
    for i in range(neue_chunks):
        con.execute(
            "INSERT INTO chunks (id, conversation_id, source, text, nachricht_ids, beginn, ende,"
            " title, project, teil, hat_vektor) VALUES (?,?,?,?,?,?,?,?,NULL,0,0)",
            (2 + i, "beispiel-b", "whatsapp", f"neuer Chunktext {i}", "[2]", 
             "2026-09-01T10:00:00+00:00", "2026-09-01T10:00:00+00:00", "Titel B"),
        )
    con.commit()
    con.close()
    return pfad


def _index_db(pfad: str) -> str:
    """archiv_index.db mit dem Altbestand (eine Nachricht, ein Chunk, ein Vektor)."""
    con = sqlite3.connect(pfad)
    con.executescript(SCHEMA_SQL)
    con.executemany(
        "INSERT INTO nachrichten (id, conversation_id, source, timestamp, role, text, title, project)"
        " VALUES (?,?,?,?,?,?,?,NULL)",
        [
            (0, "beispiel-a", "chatgpt", "2021-01-01T10:00:00+00:00", "user", "alte Frage", "Titel A"),
            (1, "beispiel-a", "chatgpt", "2021-01-01T10:01:00+00:00", "assistant", "alte Antwort", "Titel A"),
        ],
    )
    con.execute(
        "INSERT INTO chunks (id, conversation_id, source, text, nachricht_ids, beginn, ende,"
        " title, project, teil, quelldatei, hat_vektor) VALUES (1,'beispiel-a','chatgpt','alte Frage',"
        "'[0]','2021-01-01T10:00:00+00:00','2021-01-01T10:00:00+00:00','Titel A',NULL,0,"
        "'raw/chatgpt/conversations-000.json',1)"
    )
    con.execute("INSERT INTO chunks_fts (rowid, text) VALUES (1, 'alte Frage')")
    con.execute(
        "INSERT INTO vektoren (chunk_id, dimension, modell, vektor) VALUES (1, 4, 'attrappe', ?)",
        (_vektor_blob(ALT_VEKTOR),),
    )
    con.execute(
        "INSERT INTO gespraeche (conversation_id, source, title, quelldatei, von, bis,"
        " anzahl_nachrichten, anzahl_chunks) VALUES ('beispiel-a','chatgpt','Titel A',"
        "'raw/chatgpt/conversations-000.json','2021-01-01T10:00:00+00:00',"
        "'2021-01-01T10:01:00+00:00',2,1)"
    )
    con.execute("INSERT INTO meta (schluessel, wert) VALUES ('kosten_usd','0.2')")
    con.execute("INSERT INTO meta (schluessel, wert) VALUES ('tokens_gezaehlt','10000')")
    con.execute("INSERT INTO meta (schluessel, wert) VALUES ('modell','attrappe')")
    con.commit()
    con.close()
    return pfad


def _datei_hash(pfad: str) -> str:
    with open(pfad, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _lauf(tmp_path, schreiben=False, einbetter=None, budget=1.0, **kwargs):
    """Fixtures anlegen und den Index-Lauf starten: (Bericht, Indexpfad, memory-Pfad)."""
    memory = _memory_db(str(tmp_path / "memory.db"))
    index = _index_db(str(tmp_path / "archiv_index.db"))
    z = aie.index_erweitern(index, memory, None, schreiben=schreiben,
                            einbetter=einbetter, budget_usd=budget, **kwargs)
    return z, index, memory


def _inhalt(pfad: str, sql: str):
    con = sqlite3.connect(pfad)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


# ── Trockenlauf ─────────────────────────────────────────────────────────────

def test_trockenlauf_schreibt_nichts(tmp_path):
    z, index, memory = _lauf(tmp_path, schreiben=False, einbetter=StubEinbetter())
    vorher = _datei_hash(index)          # nach dem Anlegen der Attrappe
    aie.index_erweitern(index, memory, None, schreiben=False,
                        einbetter=StubEinbetter(), budget_usd=1.0)
    assert _datei_hash(index) == vorher
    assert z["neue_nachrichten"] == 2 and z["neue_chunks"] == 2
    assert z["offene_vektoren"] == 2
    assert z["tokens_offen_geschaetzt"] > 0


def test_zaehlt_nur_die_neuen_zeilen(tmp_path):
    z, _, _ = _lauf(tmp_path, schreiben=False, einbetter=StubEinbetter())
    assert z["neue_nachrichten"] == 2
    assert z["neue_chunks"] == 2
    assert z["offene_vorher"] == 0


def test_vorschau_gilt_im_trockenlauf(tmp_path):
    # memory.db ist noch nicht erweitert -> der Index zaehlt nichts;
    # die Vorschau aus der Textschicht traegt die Zahlen.
    index = _index_db(str(tmp_path / "archiv_index.db"))
    memory = _memory_db(str(tmp_path / "memory.db"), neue_nachrichten=0, neue_chunks=0)
    z = aie.index_erweitern(index, memory, None, schreiben=False,
                            einbetter=StubEinbetter(), vorschau=(5, 3, 3000))
    assert z["neue_nachrichten"] == 5 and z["neue_chunks"] == 3
    assert z["offene_vektoren"] == 3


# ── Schreiben ───────────────────────────────────────────────────────────────

def test_schreiben_haengt_an_und_laesst_alten_bestand_in_ruhe(tmp_path):
    z, index, _ = _lauf(tmp_path, schreiben=True, einbetter=StubEinbetter())
    assert z["neue_nachrichten"] == 2 and z["neue_chunks"] == 2
    assert z["neue_vektoren"] == 2
    assert _inhalt(index, "SELECT count(*) FROM nachrichten")[0][0] == 4
    assert _inhalt(index, "SELECT count(*) FROM chunks")[0][0] == 3
    assert _inhalt(index, "SELECT count(*) FROM vektoren")[0][0] == 3
    assert _inhalt(index, "SELECT count(*) FROM chunks_fts")[0][0] == 3
    # Altbestand unveraendert: Text, Quelldatei, Vektor-Bytes, hat_vektor
    zeile = _inhalt(index, "SELECT text, quelldatei, hat_vektor FROM chunks WHERE id = 1")[0]
    assert zeile == ("alte Frage", "raw/chatgpt/conversations-000.json", 1)
    roh = _inhalt(index, "SELECT vektor FROM vektoren WHERE chunk_id = 1")[0][0]
    assert roh == _vektor_blob(ALT_VEKTOR)
    assert _inhalt(index, "SELECT text FROM nachrichten WHERE id = 0")[0][0] == "alte Frage"
    assert _inhalt(index, "SELECT text FROM nachrichten WHERE id = 1")[0][0] == "alte Antwort"


def test_neue_zeilen_haben_vektoren_und_markierung(tmp_path):
    _, index, _ = _lauf(tmp_path, schreiben=True, einbetter=StubEinbetter())
    assert _inhalt(index, "SELECT count(*) FROM chunks WHERE hat_vektor = 0")[0][0] == 0
    assert _inhalt(index, "SELECT count(*) FROM vektoren WHERE dimension = 4")[0][0] == 3
    # Neuer Vektor: 4 Halb-Floats = 8 Bytes
    assert _inhalt(index, "SELECT length(vektor) FROM vektoren WHERE chunk_id = 2")[0][0] == 8


def test_gespraeche_werden_aufgefrischt(tmp_path):
    _, index, _ = _lauf(tmp_path, schreiben=True, einbetter=StubEinbetter())
    zeilen = dict(
        (r[0], r[1]) for r in _inhalt(
            index, "SELECT conversation_id, anzahl_nachrichten FROM gespraeche")
    )
    assert zeilen["beispiel-a"] == 3        # zwei alte + eine neue Nachricht
    assert zeilen["beispiel-b"] == 1
    assert _inhalt(index, "SELECT count(*) FROM gespraeche")[0][0] == 2


def test_meta_zaehlt_kosten_zusammen(tmp_path):
    z, index, _ = _lauf(tmp_path, schreiben=True, einbetter=StubEinbetter(tokens_je_text=1000))
    meta = dict(_inhalt(index, "SELECT schluessel, wert FROM meta"))
    assert meta["nachrichten"] == "4" and meta["chunks"] == "3" and meta["vektoren"] == "3"
    assert meta["gespraeche"] == "2"
    assert float(meta["kosten_ergaenzung_usd"]) == pytest.approx(z["kosten_usd"])
    assert float(meta["kosten_usd"]) == pytest.approx(0.2 + z["kosten_usd"])
    assert int(meta["tokens_gezaehlt"]) == 10000 + z["tokens_gezaehlt"]
    assert meta.get("ergaenzt_am")


def test_sicherungskopie_liegt_daneben(tmp_path):
    index = _index_db(str(tmp_path / "archiv_index.db"))
    _memory_db(str(tmp_path / "memory.db"))
    alt = _datei_hash(index)
    z = aie.index_erweitern(index, str(tmp_path / "memory.db"), None, schreiben=True,
                            einbetter=StubEinbetter(), budget_usd=1.0)
    assert os.path.isfile(z["sicherung"])
    assert _datei_hash(z["sicherung"]) == alt


def test_wiederholter_lauf_haengt_nichts_doppelt_an(tmp_path):
    index = _index_db(str(tmp_path / "archiv_index.db"))
    memory = _memory_db(str(tmp_path / "memory.db"))
    z1 = aie.index_erweitern(index, memory, None, schreiben=True,
                             einbetter=StubEinbetter(), budget_usd=1.0)
    z2 = aie.index_erweitern(index, memory, None, schreiben=True,
                             einbetter=StubEinbetter(), budget_usd=1.0)
    assert z1["neue_vektoren"] == 2
    assert z2["neue_nachrichten"] == 0 and z2["neue_chunks"] == 0 and z2["neue_vektoren"] == 0
    assert _inhalt(index, "SELECT count(*) FROM nachrichten")[0][0] == 4
    assert _inhalt(index, "SELECT count(*) FROM chunks")[0][0] == 3
    assert _inhalt(index, "SELECT count(*) FROM vektoren")[0][0] == 3
    assert _inhalt(index, "SELECT count(*) FROM chunks_fts")[0][0] == 3
    # Kosten des zweiten Laufs: nichts dazugekommen
    assert float(dict(_inhalt(index, "SELECT schluessel, wert FROM meta"))["kosten_usd"]) \
        == pytest.approx(0.2 + z1["kosten_usd"])


def test_alte_luecke_wird_mitgerechnet(tmp_path):
    # Ein Chunk ohne Vektor aus einem frueheren Abbruch wird nachgeholt.
    index = _index_db(str(tmp_path / "archiv_index.db"))
    con = sqlite3.connect(index)
    con.execute(
        "INSERT INTO chunks (id, conversation_id, source, text, nachricht_ids, beginn, ende,"
        " title, project, teil, quelldatei, hat_vektor) VALUES (2,'beispiel-a','chatgpt',"
        "'alte Luecke','[0]','2021-01-01T10:00:00+00:00','2021-01-01T10:00:00+00:00',"
        "'Titel A',NULL,0,NULL,0)"
    )
    con.commit()
    con.close()
    einbetter = StubEinbetter()
    z = aie.index_erweitern(index, _memory_db(str(tmp_path / "memory.db")), None,
                            schreiben=True, einbetter=einbetter, budget_usd=1.0)
    assert z["offene_vorher"] == 1
    # Luecke (id 2, kennt der Index schon) + neuer Chunk (id 3) = 2 Vektoren
    assert z["neue_vektoren"] == 2
    assert _inhalt(index, "SELECT count(*) FROM chunks WHERE hat_vektor = 0")[0][0] == 0


# ── Budget ──────────────────────────────────────────────────────────────────

def test_budget_vorab_abgelehnt(tmp_path):
    index = str(tmp_path / "archiv_index.db")
    memory = str(tmp_path / "memory.db")
    _index_db(index)
    _memory_db(memory)
    vorher = _datei_hash(index)
    with pytest.raises(aie.BudgetUeberschritten):
        aie.index_erweitern(index, memory, None, schreiben=True,
                            einbetter=StubEinbetter(), budget_usd=0.0)
    assert _datei_hash(index) == vorher      # nichts angefasst, keine Sicherung


def test_budget_waehrend_des_laufs_bricht_ab_und_ist_fortsetzbar(tmp_path):
    index = str(tmp_path / "archiv_index.db")
    memory = str(tmp_path / "memory.db")
    _index_db(index)
    _memory_db(memory, neue_chunks=4)
    teuer = StubEinbetter(tokens_je_text=1_000_000)   # ein Text = 0,02 USD
    z = aie.index_erweitern(index, memory, None, schreiben=True, einbetter=teuer,
                            budget_usd=0.015, stapel=1)
    assert z["abgebrochen"] is True
    assert z["neue_vektoren"] == 1
    assert _inhalt(index, "SELECT count(*) FROM chunks WHERE hat_vektor = 0")[0][0] == 3
    # Fortsetzung mit normalem Satz rechnet den Rest
    einbetter = StubEinbetter()
    z2 = aie.index_erweitern(index, memory, None, schreiben=True, einbetter=einbetter,
                             budget_usd=1.0, stapel=10)
    assert z2["neue_vektoren"] == 3
    assert _inhalt(index, "SELECT count(*) FROM chunks WHERE hat_vektor = 0")[0][0] == 0


# ── Bericht ─────────────────────────────────────────────────────────────────

def test_bericht_enthaelt_nur_zahlen(tmp_path):
    memory_z = {"nachrichten_vorher": 2, "nachrichten_nachher": 4, "chunks_vorher": 1,
                "chunks_nachher": 3, "neue_nachrichten": 2, "neue_chunks": 2, "behalten": 2,
                "chunk_dubletten": 0, "ohne_vektor": 0}
    index_z = {"neue_nachrichten": 2, "neue_chunks": 2, "neue_vektoren": 2, "offene_vektoren": 2,
               "tokens_offen_geschaetzt": 300, "tokens_gezaehlt": 300, "kosten_usd": 0.0001,
               "budget_usd": 1.0, "dauer_s": 0.5}
    text = aie.bericht_text(memory_z, index_z, "Trockenlauf")
    for geheim in ("alte Frage", "alte Antwort", "Chunktext Nr", "Titel A", "Titel B",
                   "Nachricht Nr", "beispiel-a", "beispiel-b"):
        assert geheim not in text
    assert "0.0001" in text


def test_main_ohne_archiv_meldet_fehler(capsys):
    assert aie.main(["--archiv", os.path.join("gibt", "es", "nicht"), "--trocken"]) == 2


def test_zeichenschaetzung_ist_begruendet():
    # 3,6 Zeichen je Token — dieselbe vorsichtige Schaetzung wie im Bautool.
    assert ZEICHEN_JE_TOKEN == 3.6
    assert int(3600 / ZEICHEN_JE_TOKEN) == 1000
