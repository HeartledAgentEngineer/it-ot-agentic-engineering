"""Pruefungen fuer ``tools/archiv/suchumfang_messen.py`` (15.10.2026).

Offline: erfundene Kennungen und erfundene Texte in winzigen SQLite-Dateien, keine echten
Archivdaten, kein Netz, kein Modell, kein Bild. Geprueft wird, dass nur Zahlen entstehen,
kein Archivtext im Bericht landet und fehlende Dateien ehrlich gemeldet werden.
"""
from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "archiv" / "suchumfang_messen.py"

spez = importlib.util.spec_from_file_location("suchumfang_messen", WERKZEUG)
assert spez is not None and spez.loader is not None
sm = importlib.util.module_from_spec(spez)
spez.loader.exec_module(sm)


# ── Hilfen ───────────────────────────────────────────────────────────────────

NACHRICHTEN_SQL = """
CREATE TABLE nachrichten (
    id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
    timestamp TEXT, role TEXT NOT NULL, text TEXT NOT NULL, title TEXT, project TEXT);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, source TEXT NOT NULL,
    text TEXT NOT NULL, hat_vektor INTEGER NOT NULL DEFAULT 0);
CREATE TABLE meta (schluessel TEXT PRIMARY KEY, wert TEXT);
"""


def _archiv(pfad: Path, nachrichten, chunks, meta=None) -> Path:
    """Winzige Archivdatei mit erfundenen Zeilen. ``nachrichten`` = (chat, quelle, text)."""
    con = sqlite3.connect(pfad)
    con.executescript(NACHRICHTEN_SQL)
    con.executemany(
        "INSERT INTO nachrichten (conversation_id, source, role, text) VALUES (?, ?, 'user', ?)",
        nachrichten)
    for i, (chat, quelle, mit_vektor) in enumerate(chunks, start=1):
        con.execute("INSERT INTO chunks (id, conversation_id, source, text, hat_vektor) "
                    "VALUES (?, ?, ?, ?, ?)", (i, chat, quelle, "erfundener chunk", mit_vektor))
    for schluessel, wert in (meta or {}).items():
        con.execute("INSERT INTO meta VALUES (?, ?)", (schluessel, wert))
    con.commit()
    con.close()
    return pfad


def _bildindex(pfad: Path, bilder, spalten=("fileid", "beschreibung", "vektor"), meta=None) -> Path:
    con = sqlite3.connect(pfad)
    con.executescript(
        "CREATE TABLE bilder (" + ", ".join(f"{s} TEXT" for s in spalten) + ");"
        "CREATE TABLE meta (schluessel TEXT PRIMARY KEY, wert TEXT);")
    for eintrag in bilder:
        werte = [eintrag.get(s) for s in spalten]
        con.execute(f"INSERT INTO bilder VALUES ({', '.join('?' * len(spalten))})", werte)
    for schluessel, wert in (meta or {}).items():
        con.execute("INSERT INTO meta VALUES (?, ?)", (schluessel, wert))
    con.commit()
    con.close()
    return pfad


# ── 1. Suchindex: Zahlen je Quelle ───────────────────────────────────────────

def test_quellen_zaehlt_gespraeche_nachrichten_und_vektoren(tmp_path):
    pfad = _archiv(tmp_path / "a.db",
                   [("c1", "whatsapp", "hallo"), ("c1", "whatsapp", "noch was"),
                    ("c2", "whatsapp", "drittes"), ("c3", "chatgpt", "vier")],
                   [("c1", "whatsapp", 1), ("c2", "whatsapp", 1), ("c3", "chatgpt", 0)])
    con = sm.index_oeffnen(pfad)
    try:
        quellen = {q["quelle"]: q for q in sm.quellen_zaehlen(con)}
    finally:
        con.close()
    assert quellen["whatsapp"]["gespraeche"] == 2
    assert quellen["whatsapp"]["nachrichten"] == 3
    assert quellen["whatsapp"]["chunks"] == 2
    assert quellen["whatsapp"]["chunks_mit_vektor"] == 2
    assert quellen["chatgpt"]["chunks"] == 1
    assert quellen["chatgpt"]["chunks_mit_vektor"] == 0


def test_nur_lesend_geoeffnet(tmp_path):
    pfad = _archiv(tmp_path / "b.db", [("c1", "whatsapp", "hallo")], [("c1", "whatsapp", 1)])
    con = sm.index_oeffnen(pfad)
    try:  # ein Schreibversuch muss scheitern — die Verbindung ist read-only
        try:
            con.execute("INSERT INTO nachrichten (conversation_id, source, role, text) "
                        "VALUES ('x', 'y', 'user', 'z')")
            geschrieben = True
        except sqlite3.OperationalError:
            geschrieben = False
    finally:
        con.close()
    assert not geschrieben


# ── 2. Gespraechsgroessen ────────────────────────────────────────────────────

def test_verlauf_umfang_zaehlt_die_zu_langen_gespraeche(tmp_path):
    nachrichten = [("kurz", "chatgpt", "a")] + [("lang", "whatsapp", f"n{i}") for i in range(30)]
    pfad = _archiv(tmp_path / "c.db", nachrichten, [("lang", "whatsapp", 1)])
    con = sm.index_oeffnen(pfad)
    try:
        umfang = sm.verlauf_umfang(con, grenze=21)
    finally:
        con.close()
    assert umfang["gespraeche"] == 2
    assert umfang["groesstes"] == 30
    assert umfang["nachrichten"] == 31
    assert umfang["ueber_grenze"] == 1        # "lang" hat 30 > 21
    assert umfang["grenze"] == 21


def test_verlauf_umfang_ohne_nachrichten(tmp_path):
    pfad = _archiv(tmp_path / "d.db", [], [])
    con = sm.index_oeffnen(pfad)
    try:
        umfang = sm.verlauf_umfang(con, grenze=21)
    finally:
        con.close()
    assert umfang["gespraeche"] == 0 and umfang["groesstes"] == 0


# ── 3. Bildindex ─────────────────────────────────────────────────────────────

def test_bildindex_zaehlt_bilder_vektoren_und_beschreibungen(tmp_path):
    pfad = _bildindex(tmp_path / "bild.db", [
        {"fileid": "1", "beschreibung": "ein Text", "vektor": "abc"},
        {"fileid": "2", "beschreibung": "  ", "vektor": "abc"},
        {"fileid": "3", "beschreibung": "ein Text", "vektor": ""},
    ], meta={"stand": "2026-10-10T22:30:25+00:00", "modell": "openai/text-embedding-3-small"})
    zahlen = sm.bildindex_zaehlen(pfad)
    assert zahlen["bilder"] == 3
    assert zahlen["mit_vektor"] == 2
    assert zahlen["mit_beschreibung"] == 2
    assert zahlen["meta"]["modell"] == "openai/text-embedding-3-small"


def test_bildindex_fehlend_und_ohne_tabelle_werden_gemeldet(tmp_path):
    assert sm.bildindex_zaehlen(tmp_path / "gibtsnicht.db")["fehlt"] is True
    leer = tmp_path / "leer.db"
    con = sqlite3.connect(leer)
    con.execute("CREATE TABLE etwas_anderes (x TEXT)")
    con.commit()
    con.close()
    zahlen = sm.bildindex_zaehlen(leer)
    assert zahlen["tabelle_fehlt"] is True
    assert "etwas_anderes" in zahlen["tabellen"]


# ── 4. Beschreibungszeilen ───────────────────────────────────────────────────

def test_beschreibungszeilen_zaehlt_und_meldet_fehlende(tmp_path):
    (tmp_path / "da.jsonl").write_text('{"a":1}\n\n{"a":2}\n', encoding="utf-8")
    gesamt, fehlend = sm.beschreibungszeilen(tmp_path, ("da.jsonl", "weg.jsonl"))
    assert gesamt == 2                      # Leerzeile zaehlt nicht
    assert fehlend == ["weg.jsonl"]


# ── 5. Deckel: Musterlesen und der echte Code ────────────────────────────────

def test_zahl_aus_quelle_mit_datei_und_zeile(tmp_path):
    quelle = tmp_path / "probe.py"
    quelle.write_text("x = 1\n    k = top_k or 7\n", encoding="utf-8")
    wert, ort = sm._treffer(quelle, r"^\s*k = top_k or (\d+)")
    assert wert == 7 and ort == "probe.py:2"
    assert sm._treffer(tmp_path / "gibtsnicht.py", r"(\d+)") is None


def test_alle_zahlen_einer_zeile(tmp_path):
    quelle = tmp_path / "probe2.py"
    quelle.write_text('    anzahl = _ganzzahl(args.get("anzahl"), 5, 1, 8)\n', encoding="utf-8")
    werte, ort = sm._alle_treffer(
        quelle, r'_ganzzahl\(args\.get\("anzahl"\),\s*(\d+),\s*(\d+),\s*(\d+)\)')
    assert werte == [5, 1, 8] and ort == "probe2.py:1"


def test_deckel_liest_den_echten_code():
    """Regression: die gemessenen Zahlen muessen im geltenden Code stehen."""
    deckel = {was: wert for was, wert, _ in sm.deckel_lesen()}
    assert deckel["Fundstellen im Chat (Standardweg, Voreinstellung)"] == "5"
    assert deckel["Fundstellen im Werkzeug archiv_suchen (Voreinstellung)"] == "5"
    assert deckel["Fundstellen im Werkzeug archiv_suchen (Hoechstwert)"] == "8"
    assert deckel["Nachlesen: Voreinstellung Kontextnachrichten"] == "1"
    assert deckel["Nachlesen: Hoechstwert Kontextnachrichten"] == "10"
    assert deckel["Zeichenkuerzung je Fundstelle im Prompt"] == "1200"
    assert deckel["/api/archiv/suche (Hoechstwert)"] == "20"
    assert deckel["/api/archiv/wissen/frage (Hoechstwert)"] == "20"
    # Jede Zeile traegt eine nachpruefbare Fundstelle (Datei:Zeile) oder den Grund.
    for _, wert, ort in sm.deckel_lesen():
        assert wert != "nicht gefunden", ort
        assert ":" in ort


# ── 6. Bericht ───────────────────────────────────────────────────────────────

def test_bericht_enthaelt_nur_zahlen_und_keinen_archivtext(tmp_path):
    geheim = "RezeptverlaufMitGeheimwort"
    archiv = _archiv(tmp_path / "e.db",
                     [("c1", "whatsapp", geheim), ("c1", "whatsapp", "zweite")],
                     [("c1", "whatsapp", 1)])
    bild = _bildindex(tmp_path / "f.db", [{"fileid": "1", "beschreibung": geheim, "vektor": "a"}])
    (tmp_path / "bild_beschreibungen.jsonl").write_text('{"x":1}\n', encoding="utf-8")

    text = "\n".join(sm.bericht(archiv, bild, tmp_path, ("bild_beschreibungen.jsonl",)))
    assert geheim not in text                    # weder Chattext noch Beschreibungstext
    assert "whatsapp: 1 Gespraeche" in text
    assert "1 Bilder" in text
    assert "Beschreibungszeilen in den JSONL-Dateien: 1" in text
    assert "Quellen mit Bilderbezug: 0" in text
    assert "ueber 21 Nachrichten" in text


def test_bericht_meldet_fehlende_dateien_ohne_abbruch(tmp_path):
    text = "\n".join(sm.bericht(tmp_path / "gibtsnicht.db", tmp_path / "auchnicht.db",
                                tmp_path, ("fehlt.jsonl",)))
    assert "Datei fehlt" in text
    assert "Im Suchindex des Chats: keine Bilder-Quelle" in text
    assert "Deckel im Antwortweg" in text


def test_bilderquelle_wird_erkannt(tmp_path):
    archiv = _archiv(tmp_path / "g.db", [("c1", "bildbeschreibungen", "text")],
                     [("c1", "bildbeschreibungen", 1)])
    text = "\n".join(sm.bericht(archiv, tmp_path / "keine.db", tmp_path, ()))
    assert "Quellen mit Bilderbezug: 1 (bildbeschreibungen)" in text


# ── 7. Kommandozeile ─────────────────────────────────────────────────────────

def test_main_laeuft_und_meldet_fehlen_hinweis(tmp_path, capsys):
    assert sm.main(["--archiv", str(tmp_path / "weg.db"),
                    "--bildindex", str(tmp_path / "weg2.db"),
                    "--ordner", str(tmp_path), "--beschreibungen"]) == 0
    ausgabe = capsys.readouterr().out
    assert "Archivindex nicht gefunden" in ausgabe
    assert "Deckel im Antwortweg" in ausgabe
