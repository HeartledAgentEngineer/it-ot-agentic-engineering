"""Offline-Tests fuer die inkrementelle Archiv-Nachpflege (N22, 2026-09-29).

Was hier geprueft wird
======================

``scripts/archiv_nachpflege.py`` pflegt einen **bestehenden** Index nach:
nur anhaengen, idempotent, nie loeschen. Diese Datei baut dafuer im
``tmp_path`` eine winzige Quell- und Zieldatenbank aus
``app.services.archiv_suche.SCHEMA_SQL`` und prueft das Verhalten ohne Netz,
ohne Schluessel und ohne echte Daten. Alle Texte sind **erfunden**
(„Probe-Nachricht", „Probe-Gespraech").

Der Einbetter ist eine Attrappe: Sie zaehlt ihre Aufrufe und liefert feste
Vektoren. So kann geprueft werden, dass **nur neue** Chunks eingebettet
werden.
"""

import hashlib
import inspect
import os
import sqlite3
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.archiv_suche import SCHEMA_SQL  # noqa: E402
import scripts.archiv_nachpflege as mn  # noqa: E402


# ── Quell-Schema (memory.db — ohne quelldatei) ─────────────────────────────
QUELLE_SCHEMA = """
CREATE TABLE messages (
    id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
    timestamp TEXT, role TEXT NOT NULL, text TEXT NOT NULL, title TEXT, project TEXT
);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
    text TEXT NOT NULL, nachricht_ids TEXT NOT NULL, beginn TEXT, ende TEXT,
    title TEXT, project TEXT, teil INTEGER NOT NULL DEFAULT 0,
    hat_vektor INTEGER NOT NULL DEFAULT 0
);
"""

# ── Erfundene Basisdaten ───────────────────────────────────────────────────
NA_BASIS = [
    (0, "gespraech-probe-1", "probe", "2024-01-01T00:00:00+00:00", "user",
     "Probe-Nachricht eins.", "Probe-Gespraech", None),
    (1, "gespraech-probe-1", "probe", "2024-01-01T01:00:00+00:00", "assistant",
     "Probe-Antwort zwei.", "Probe-Gespraech", None),
    (2, "gespraech-probe-2", "probe", "2024-02-01T00:00:00+00:00", "user",
     "Anderes Probe-Gespraech.", "Zweites Probe-Thema", None),
]

CH_BASIS = [
    (1, "gespraech-probe-1", "probe", "Probe-Nachricht eins. Probe-Antwort zwei.",
     "[0, 1]", "2024-01-01T00:00:00+00:00", "2024-01-01T01:00:00+00:00",
     "Probe-Gespraech", None, 0),
    (2, "gespraech-probe-2", "probe", "Anderes Probe-Gespraech.",
     "[2]", "2024-02-01T00:00:00+00:00", "2024-02-01T00:00:00+00:00",
     "Zweites Probe-Thema", None, 0),
]

QUELLDATEI = {
    "gespraech-probe-1": "export/probe-1.jsonl",
    "gespraech-probe-2": "export/probe-2.jsonl",
}

GESPRAECHE_BASIS = [
    ("gespraech-probe-1", "probe", "Probe-Gespraech", "export/probe-1.jsonl",
     "2024-01-01T00:00:00+00:00", "2024-01-01T01:00:00+00:00", 2, 1),
    ("gespraech-probe-2", "probe", "Zweites Probe-Thema", "export/probe-2.jsonl",
     "2024-02-01T00:00:00+00:00", "2024-02-01T00:00:00+00:00", 1, 1),
]

META_BASIS = [
    ("modell", "openai/text-embedding-3-small"),
    ("dimension", "1536"),
    ("vektor_speicher", "float16"),
    ("gebaut_am", "2026-09-01T00:00:00+00:00"),
]


# ── Bauhelfer ──────────────────────────────────────────────────────────────
def _quelle_bauen(pfad: str, nachrichten, chunks) -> str:
    con = sqlite3.connect(pfad)
    con.executescript(QUELLE_SCHEMA)
    con.executemany(
        "INSERT INTO messages (id, conversation_id, source, timestamp, role, text, "
        "title, project) VALUES (?,?,?,?,?,?,?,?)",
        [tuple(n) for n in nachrichten],
    )
    con.executemany(
        "INSERT INTO chunks (id, conversation_id, source, text, nachricht_ids, "
        "beginn, ende, title, project, teil, hat_vektor) VALUES (?,?,?,?,?,?,?,?,?,?,0)",
        [tuple(c) for c in chunks],
    )
    con.commit()
    con.close()
    return pfad


def _index_bauen(pfad: str, nachrichten, chunks) -> str:
    con = sqlite3.connect(pfad)
    con.executescript(SCHEMA_SQL)
    con.executemany(
        "INSERT INTO nachrichten (id, conversation_id, source, timestamp, role, text, "
        "title, project) VALUES (?,?,?,?,?,?,?,?)",
        [tuple(n) for n in nachrichten],
    )
    for c in chunks:
        con.execute(
            "INSERT INTO chunks (id, conversation_id, source, text, nachricht_ids, "
            "beginn, ende, title, project, teil, quelldatei, hat_vektor) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8], c[9],
             QUELLDATEI.get(c[1]), 0),
        )
        con.execute("INSERT INTO chunks_fts(rowid, text) VALUES (?, ?)", (c[0], c[3]))
    con.executemany(
        "INSERT INTO gespraeche (conversation_id, source, title, quelldatei, von, bis, "
        "anzahl_nachrichten, anzahl_chunks) VALUES (?,?,?,?,?,?,?,?)",
        [tuple(g) for g in GESPRAECHE_BASIS],
    )
    con.executemany("INSERT INTO meta (schluessel, wert) VALUES (?,?)", META_BASIS)
    # Eine Alt-Vektorzeile, damit vektoren nicht leer startet (dimension 4).
    con.execute(
        "INSERT INTO vektoren (chunk_id, dimension, modell, vektor) VALUES (?,?,?,?)",
        (1, 4, "alt/modell", b"\x00" * 8),
    )
    con.execute("UPDATE chunks SET hat_vektor = 1 WHERE id = 1")
    con.commit()
    con.close()
    return pfad


def _q_nachricht(pfad, nid, cid, ts, role, text, title=None, source="probe"):
    con = sqlite3.connect(pfad)
    con.execute(
        "INSERT INTO messages (id, conversation_id, source, timestamp, role, text, "
        "title, project) VALUES (?,?,?,?,?,?,?,?)",
        (nid, cid, source, ts, role, text, title, None),
    )
    con.commit()
    con.close()


def _q_chunk(pfad, cid, conv, text, beginn, ende, teil=0, nachricht_ids="[9]",
             source="probe"):
    con = sqlite3.connect(pfad)
    con.execute(
        "INSERT INTO chunks (id, conversation_id, source, text, nachricht_ids, "
        "beginn, ende, title, project, teil, hat_vektor) VALUES (?,?,?,?,?,?,?,?,?,?,0)",
        (cid, conv, source, text, nachricht_ids, beginn, ende, None, None, teil),
    )
    con.commit()
    con.close()


def _sha(pfad: str) -> str:
    with open(pfad, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _fingerabdruck(pfad: str):
    return _sha(pfad), os.stat(pfad).st_mtime_ns


def _scalar(pfad, sql, args=()):
    con = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    try:
        return con.execute(sql, args).fetchone()[0]
    finally:
        con.close()


def _meta(pfad):
    con = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
    try:
        return dict(con.execute("SELECT schluessel, wert FROM meta"))
    finally:
        con.close()


class _FakeEinbetter:
    """Attrappe: feste Vektoren, gezaehlte Aufrufe — kein Netz, kein Schluessel."""

    def __init__(self, dimension=8):
        self.modell = "probe/embed"
        self.dimension = dimension
        self.aufrufe = 0
        self.texte = []
        self.token_gesamt = 0

    def __call__(self, texte):
        self.aufrufe += 1
        self.texte.extend(texte)
        vektoren = [[0.5] * self.dimension for _ in texte]
        token = 1000 * len(texte)
        self.token_gesamt += token
        return vektoren, token


# ── Fixture ────────────────────────────────────────────────────────────────
@pytest.fixture
def umgebung(tmp_path):
    q = os.path.join(str(tmp_path), "memory.db")
    i = os.path.join(str(tmp_path), "archiv_index.db")
    _quelle_bauen(q, NA_BASIS, CH_BASIS)
    _index_bauen(i, NA_BASIS, CH_BASIS)
    return {"quelle": q, "index": i, "tmp": str(tmp_path)}


# ══════════════════════════ 1. Schluesselfunktionen ════════════════════════
def test_schluessel_gleicher_inhalt_gleich():
    a = mn.schluessel_nachricht("c1", "t", "user", "Text A")
    b = mn.schluessel_nachricht("c1", "t", "user", "Text A")
    assert a == b


def test_schluessel_geaenderter_text_anders():
    a = mn.schluessel_nachricht("c1", "t", "user", "Text A")
    b = mn.schluessel_nachricht("c1", "t", "user", "Text B")
    assert a != b


def test_schluessel_laenge_16_hex():
    s = mn.schluessel_nachricht("c1", "t", "user", "Text")
    assert len(s) == 16
    assert all(z in "0123456789abcdef" for z in s)


def test_schluessel_chunk_teil_zaehlt():
    a = mn.schluessel_chunk("c1", 0, "b", "e", "Text")
    b = mn.schluessel_chunk("c1", 1, "b", "e", "Text")
    assert a != b


def test_schluessel_feldgrenzen_kein_quirlen():
    # Ohne Trennzeichen koennten "ab"+"c" und "a"+"bc" denselben Schluessel geben.
    a = mn.schluessel_nachricht("ab", "c", "user", "x")
    b = mn.schluessel_nachricht("a", "bc", "user", "x")
    assert a != b


def test_schluessel_none_und_leer_gleich_behandelt():
    assert mn.schluessel_nachricht("c", None, "user", "x") == \
        mn.schluessel_nachricht("c", "", "user", "x")


# ══════════════════════════ 2. Repo-Schutz ═════════════════════════════════
def test_ist_im_repo_erkennt_projektpfad(tmp_path, monkeypatch):
    monkeypatch.setattr(mn, "PROJEKT_WURZEL", str(tmp_path))
    drin = os.path.join(str(tmp_path), "personal_ai_agent", "archiv_index.db")
    assert mn.ist_im_repo(drin) is True


def test_ist_im_repo_ausserhalb_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(mn, "PROJEKT_WURZEL", str(tmp_path))
    draussen = os.path.join(str(tmp_path), "db", "archiv_index.db")
    assert mn.ist_im_repo(draussen) is False


# ══════════════════════════ 3. Erkennung „neu" ═════════════════════════════
def test_bestand_ohne_rueckstand(umgebung):
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"])
    assert z["neu_nachrichten"] == 0
    assert z["neu_chunks"] == 0
    assert z["uebersprungen_nachrichten"] == 3
    assert z["uebersprungen_chunks"] == 2


def test_neue_nachricht_wird_erkannt(umgebung):
    _q_nachricht(umgebung["quelle"], 3, "gespraech-probe-1",
                 "2024-01-02T00:00:00+00:00", "user", "Probe-Nachricht neu.")
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"])
    assert z["neu_nachrichten"] == 1
    assert z["uebersprungen_nachrichten"] == 3
    assert z["neu_chunks"] == 0


def test_neuer_chunk_wird_erkannt(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Probe-Chunk neu.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"])
    assert z["neu_chunks"] == 1
    assert z["uebersprungen_chunks"] == 2


def test_defekte_zeile_zaehlt_als_fehler(umgebung):
    # Leere conversation_id ergibt keinen stabilen Schluessel — gezaehlt, nicht
    # geworfen.
    _q_nachricht(umgebung["quelle"], 3, "",
                 "2024-01-02T00:00:00+00:00", "user", "Text ohne Gespraech.")
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    assert z["fehler"] == 1
    assert z["neu_nachrichten"] == 0


def test_leerer_text_ist_kein_fehler(umgebung):
    # Leerer Text kommt im echten Bestand vor (Claude-Export) und ist zulaessig.
    _q_nachricht(umgebung["quelle"], 3, "gespraech-probe-3",
                 "2024-01-02T00:00:00+00:00", "user", "")
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"])
    assert z["fehler"] == 0
    assert z["neu_nachrichten"] == 1


# ══════════════════════════ 4. Trockenlauf schreibt nichts ═════════════════
def test_trockenlauf_schreibt_nichts(umgebung):
    _q_nachricht(umgebung["quelle"], 3, "gespraech-probe-1",
                 "2024-01-02T00:00:00+00:00", "user", "Probe-Nachricht neu.")
    vorher = _fingerabdruck(umgebung["index"])
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"])  # Standard: trocken
    nachher = _fingerabdruck(umgebung["index"])
    assert z["neu_nachrichten"] == 1
    assert vorher == nachher


def test_trockenlauf_kein_journal(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-1", "Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"])
    assert not os.path.exists(umgebung["index"] + "-journal")
    assert not os.path.exists(umgebung["index"] + "-wal")


# ══════════════════════════ 5. Anhaengen ═══════════════════════════════════
def test_neue_zeile_haengt_hinten_an(umgebung):
    _q_nachricht(umgebung["quelle"], 3, "gespraech-probe-1",
                 "2024-01-02T00:00:00+00:00", "user", "Probe-Nachricht neu.")
    vor_max = _scalar(umgebung["index"], "SELECT max(id) FROM nachrichten")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    nach_max = _scalar(umgebung["index"], "SELECT max(id) FROM nachrichten")
    assert vor_max == 2 and nach_max == 3


def test_neuer_chunk_haengt_hinten_an(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Probe-Chunk neu.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    assert _scalar(umgebung["index"], "SELECT max(id) FROM chunks") == 3


def test_bestehende_zeilen_unveraendert(umgebung):
    vor = _scalar(umgebung["index"], "SELECT text FROM nachrichten WHERE id = 0")
    _q_nachricht(umgebung["quelle"], 3, "gespraech-probe-1",
                 "2024-01-02T00:00:00+00:00", "user", "Probe-Nachricht neu.")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    nach = _scalar(umgebung["index"], "SELECT text FROM nachrichten WHERE id = 0")
    assert vor == nach


def test_anzahl_waechst_nur_um_neue(umgebung):
    vor = _scalar(umgebung["index"], "SELECT count(*) FROM nachrichten")
    _q_nachricht(umgebung["quelle"], 3, "gespraech-probe-1",
                 "2024-01-02T00:00:00+00:00", "user", "Probe-Nachricht neu.")
    _q_nachricht(umgebung["quelle"], 4, "gespraech-probe-1",
                 "2024-01-02T01:00:00+00:00", "user", "Probe-Nachricht noch neu.")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    assert _scalar(umgebung["index"], "SELECT count(*) FROM nachrichten") == vor + 2


# ══════════════════════════ 6. Volltextindex ═══════════════════════════════
def test_fts_findet_neuen_text(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2",
             "Hier steht der Probebegriff N22 im Text.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    treffer = _scalar(
        umgebung["index"],
        "SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'probebegriff'",
    )
    assert treffer == 1


def test_fts_alte_treffer_bleiben(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Probe-Chunk neu.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    # Der alte Text (id 1) ist weiterhin auffindbar.
    assert _scalar(
        umgebung["index"],
        "SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'antwort'",
    ) == 1


# ══════════════════════════ 7. Vektoren ════════════════════════════════════
def test_vektorzeile_entsteht_laenge_dimension_x2(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Probe-Chunk mit Vektor.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    einbetter = _FakeEinbetter(dimension=8)
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                   einbetter=einbetter)
    laenge = _scalar(umgebung["index"],
                     "SELECT length(vektor) FROM vektoren WHERE chunk_id = 3")
    assert laenge == 8 * 2  # float16 = 2 Byte je Dimension


def test_vektor_dimension_gespeichert(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Probe-Chunk mit Vektor.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                   einbetter=_FakeEinbetter(dimension=8))
    assert _scalar(umgebung["index"],
                   "SELECT dimension FROM vektoren WHERE chunk_id = 3") == 8


def test_hat_vektor_wird_eins(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Probe-Chunk mit Vektor.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    vor = _scalar(umgebung["index"], "SELECT count(*) FROM chunks WHERE id = 3")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                   einbetter=_FakeEinbetter())
    nach = _scalar(umgebung["index"], "SELECT hat_vektor FROM chunks WHERE id = 3")
    assert vor == 0 and nach == 1


def test_einbetter_nur_fuer_neue_chunks(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    einbetter = _FakeEinbetter()
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                       einbetter=einbetter)
    assert einbetter.aufrufe == 1
    assert einbetter.texte == ["Neuer Probe-Chunk."]
    assert z["vektoren_gerechnet"] == 1


def test_ohne_vektoren_zaehlt_ohne_vektor(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    assert z["vektoren_gerechnet"] == 0
    assert z["ohne_vektor"] == 1
    assert _scalar(umgebung["index"],
                   "SELECT hat_vektor FROM chunks WHERE id = 3") == 0


def test_vektoren_nur_fuer_neue_nicht_alte(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                   einbetter=_FakeEinbetter())
    # Der alte Vektor (chunk 1) wurde nicht neu gerechnet oder ersetzt.
    assert _scalar(umgebung["index"],
                   "SELECT modell FROM vektoren WHERE chunk_id = 1") == "alt/modell"


# ══════════════════════════ 8. Kosten und Token ════════════════════════════
def test_tokens_und_kosten_aus_der_antwort(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                       einbetter=_FakeEinbetter())
    assert z["tokens"] == 1000
    assert z["kosten_usd"] == round(1000 / 1_000_000 * 0.02, 8)


# ══════════════════════════ 9. gespraeche ══════════════════════════════════
def test_gespraeche_zahlen_wachsen(umgebung):
    _q_nachricht(umgebung["quelle"], 3, "gespraech-probe-1",
                 "2024-01-02T00:00:00+00:00", "user", "Probe-Nachricht neu.")
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-1", "Neuer Probe-Chunk.",
             "2024-01-02T00:00:00+00:00", "2024-01-02T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    assert _scalar(umgebung["index"],
                   "SELECT anzahl_nachrichten FROM gespraeche "
                   "WHERE conversation_id = 'gespraech-probe-1'") == 3
    assert _scalar(umgebung["index"],
                   "SELECT anzahl_chunks FROM gespraeche "
                   "WHERE conversation_id = 'gespraech-probe-1'") == 2


def test_gespraeche_von_bis_stimmen(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-1", "Spaeterer Chunk.",
             "2025-06-01T00:00:00+00:00", "2025-06-02T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    zeile = None
    con = sqlite3.connect(f"file:{umgebung['index']}?mode=ro", uri=True)
    try:
        zeile = con.execute(
            "SELECT von, bis FROM gespraeche WHERE conversation_id = 'gespraech-probe-1'"
        ).fetchone()
    finally:
        con.close()
    assert zeile[0] == "2024-01-01T00:00:00+00:00"
    assert zeile[1] == "2025-06-02T00:00:00+00:00"


def test_gespraeche_nur_beruehrte(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-1", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    assert z["gespraeche_beruehrt"] == 1


def test_neues_gespraech_erzeugt_zeile(umgebung):
    _q_nachricht(umgebung["quelle"], 3, "gespraech-probe-3",
                 "2024-04-01T00:00:00+00:00", "user", "Ganz neues Probe-Gespraech.")
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-3", "Ganz neuer Probe-Chunk.",
             "2024-04-01T00:00:00+00:00", "2024-04-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    assert _scalar(umgebung["index"],
                   "SELECT anzahl_chunks FROM gespraeche "
                   "WHERE conversation_id = 'gespraech-probe-3'") == 1


# ══════════════════════════ 10. meta ═══════════════════════════════════════
def test_meta_behaelt_alte_schluessel(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    m = _meta(umgebung["index"])
    for schluessel, wert in META_BASIS:
        assert m.get(schluessel) == wert


def test_meta_setzt_nachpflege_schluessel(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    m = _meta(umgebung["index"])
    assert m["nachpflege_neu_chunks"] == "1"
    assert "nachpflege_zuletzt" in m
    assert "nachpflege_lauf" in m


def test_stand_friert_meta_zeitstempel(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    fest = "2026-09-29T00:00:00+00:00"
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True, stand=fest)
    assert _meta(umgebung["index"])["nachpflege_zuletzt"] == fest


def test_trockenlauf_setzt_kein_meta(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"])
    assert "nachpflege_zuletzt" not in _meta(umgebung["index"])


# ══════════════════════════ 11. Idempotenz ═════════════════════════════════
def test_zweiter_lauf_null_neu(umgebung):
    _q_nachricht(umgebung["quelle"], 3, "gespraech-probe-1",
                 "2024-01-02T00:00:00+00:00", "user", "Probe-Nachricht neu.")
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-1", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    erst = mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                          einbetter=_FakeEinbetter())
    zweit = mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                           einbetter=_FakeEinbetter())
    assert erst["neu_nachrichten"] == 1 and erst["neu_chunks"] == 1
    assert zweit["neu_nachrichten"] == 0
    assert zweit["neu_chunks"] == 0
    assert zweit["vektoren_gerechnet"] == 0


def test_zweiter_lauf_sha_gleich(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-2", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                   einbetter=_FakeEinbetter())
    vorher = _sha(umgebung["index"])
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True,
                   einbetter=_FakeEinbetter())
    assert _sha(umgebung["index"]) == vorher


# ══════════════════════════ 12. Quelldatei-Uebernahme ══════════════════════
def test_quelldatei_aus_bestand_uebernommen(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-1", "Neuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    assert _scalar(umgebung["index"],
                   "SELECT quelldatei FROM chunks WHERE id = 3") == "export/probe-1.jsonl"


def test_quelldatei_null_wenn_unbekannt(umgebung):
    _q_chunk(umgebung["quelle"], 3, "gespraech-probe-neu", "Brandneuer Probe-Chunk.",
             "2024-03-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00")
    mn.nachpflegen(umgebung["quelle"], umgebung["index"], schreiben=True)
    assert _scalar(umgebung["index"],
                   "SELECT quelldatei FROM chunks WHERE id = 3") is None


# ══════════════════════════ 13. CLI und Sicherheit ═════════════════════════
def test_repo_ziel_exit_2(umgebung, monkeypatch, tmp_path):
    repo = os.path.join(str(tmp_path), "personal_ai_agent")
    os.makedirs(repo, exist_ok=True)
    idx = _index_bauen(os.path.join(repo, "archiv_index.db"), NA_BASIS, CH_BASIS)
    monkeypatch.setattr(mn, "PROJEKT_WURZEL", str(tmp_path))
    rc = mn.main(["--quelle-db", umgebung["quelle"], "--index", idx, "--schreiben"])
    assert rc == 2
    assert "nachpflege_zuletzt" not in _meta(idx)  # nichts geschrieben


def test_repo_ziel_wirft_im_kern(umgebung, monkeypatch, tmp_path):
    repo = os.path.join(str(tmp_path), "personal_ai_agent")
    os.makedirs(repo, exist_ok=True)
    idx = _index_bauen(os.path.join(repo, "archiv_index.db"), NA_BASIS, CH_BASIS)
    monkeypatch.setattr(mn, "PROJEKT_WURZEL", str(tmp_path))
    with pytest.raises(ValueError):
        mn.nachpflegen(umgebung["quelle"], idx, schreiben=True)


def test_fehlende_quelle_exit_2(umgebung, tmp_path):
    fehlt = os.path.join(str(tmp_path), "gibt-es-nicht.db")
    assert mn.main(["--quelle-db", fehlt, "--index", umgebung["index"]]) == 2


def test_fehlender_index_exit_2(umgebung, tmp_path):
    fehlt = os.path.join(str(tmp_path), "kein-index.db")
    assert mn.main(["--quelle-db", umgebung["quelle"], "--index", fehlt]) == 2


def test_fehlende_quelle_wirft_im_kern(umgebung, tmp_path):
    fehlt = os.path.join(str(tmp_path), "nichts.db")
    with pytest.raises(FileNotFoundError):
        mn.nachpflegen(fehlt, umgebung["index"])


def test_fehlender_index_wirft_im_kern(umgebung, tmp_path):
    fehlt = os.path.join(str(tmp_path), "nichts.db")
    with pytest.raises(FileNotFoundError):
        mn.nachpflegen(umgebung["quelle"], fehlt)


# ══════════════════════════ 14. Quelltext-Grenzen ══════════════════════════
def _modul_text() -> str:
    return inspect.getsource(mn)


def test_quelltext_kein_delete_drop():
    text = _modul_text().upper()
    assert "DELETE" not in text
    assert "DROP" not in text


def test_quelltext_kein_pcloud_oder_fremdnetz():
    klein = _modul_text().lower()
    assert "pcloud" not in klein
    assert "urlopen" not in klein
    assert "requests." not in klein


def test_quelltext_haengt_nur_an():
    text = _modul_text()
    assert "INSERT INTO nachrichten" in text
    assert "INSERT INTO chunks" in text
    assert "INSERT INTO chunks_fts" in text
    # kein Neuschreiben der ganzen Datei
    assert "os.replace" not in text


# ══════════════════════════ 15. Bericht ════════════════════════════════════
def test_bericht_enthaelt_zahlen(umgebung):
    z = mn.nachpflegen(umgebung["quelle"], umgebung["index"])
    text = mn.bericht(z)
    assert str(z["neu_nachrichten"]) in text
    assert "Nachrichten" in text


# ══════════════════════════ 16. Grosser Bestand ════════════════════════════
def test_grosser_bestand_idempotent(tmp_path):
    n = 500
    q = os.path.join(str(tmp_path), "gross.db")
    i = os.path.join(str(tmp_path), "gross_index.db")
    alle_na = [
        (k, "gespraech-gross", "probe", f"2024-05-01T00:00:{k % 60:02d}+00:00",
         "user", f"Probe-Nachricht Nummer {k}.", "Grosser Probe-Bestand", None)
        for k in range(n)
    ]
    alle_ch = [
        (k + 1, "gespraech-gross", "probe", f"Probe-Chunk Nummer {k}.",
         f"[{k}]", f"2024-05-01T00:00:{k % 60:02d}+00:00",
         f"2024-05-01T00:00:{k % 60:02d}+00:00", "Grosser Probe-Bestand", None, 0)
        for k in range(n)
    ]
    _quelle_bauen(q, alle_na, alle_ch)
    # Index kennt nur die ersten 5 Nachrichten und Chunks.
    _index_bauen(i, alle_na[:5], alle_ch[:5])

    einbetter = _FakeEinbetter()
    erst = mn.nachpflegen(q, i, schreiben=True, einbetter=einbetter)
    assert erst["neu_nachrichten"] == n - 5
    assert erst["neu_chunks"] == n - 5
    assert erst["vektoren_gerechnet"] == n - 5

    zweit = mn.nachpflegen(q, i, schreiben=True, einbetter=einbetter)
    assert zweit["neu_nachrichten"] == 0
    assert zweit["neu_chunks"] == 0
    assert zweit["uebersprungen_nachrichten"] == n
    assert zweit["uebersprungen_chunks"] == n
