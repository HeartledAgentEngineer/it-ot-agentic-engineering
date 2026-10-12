"""Tests: Bestandspruefung (nur Zahlen) und Gruppen-Uebergabe per Kabel (01.10.2026).

Offline, erfundene Dateien in tmp_path, nachgebautes adb.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_bestand_und_handy_uebergabe.py -q
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import sqlite3

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJEKT = os.path.dirname(BACKEND)


def _laden(name, ordner):
    spez = importlib.util.spec_from_file_location(name, os.path.join(PROJEKT, "tools", ordner, name + ".py"))
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


bp = _laden("bestand_pruefen", "foto_sortierung")
gh = _laden("gruppen_aufs_handy", "handy")


def _jsonl(pfad, zeilen):
    pfad.write_text("\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")


def _bestand(tmp_path, mit_gruppen=True):
    # Plan 1: Fotos 1-4 (Kennung als Zahl!), Video 9; Plan 2: Fotos 5-6
    (tmp_path / "sortierplan.json").write_text(json.dumps({"zuege": [
        {"fileid": i, "von_name": f"IMG_{i}.jpg"} for i in (1, 2, 3, 4)] + [
        {"fileid": 9, "von_name": "VID_9.mp4"}]}), encoding="utf-8")
    (tmp_path / "sortierplan_bildervideos.json").write_text(json.dumps({"zuege": [
        {"fileid": 5, "von_name": "a.jpg"}, {"fileid": 6, "von_name": "b.JPG"}]}), encoding="utf-8")
    _jsonl(tmp_path / "personen_vektoren_n0929_voll.jsonl", [
        {"bild_id": "1", "gesichter": [{"bbox": [1, 2, 3, 4]}, {"bbox": [5, 6, 7, 8]}]},
        {"bild_id": "2", "gesichter": []},
        {"bild_id": "3", "gesichter": [], "fehler": "nicht dekodierbar"},
        {"bild_id": "77", "gesichter": []},                  # ausserhalb aller Plaene
    ])
    (tmp_path / "personen_vektoren_n0929_bildervideos.jsonl").write_text(
        json.dumps({"bild_id": "5", "gesichter": [{"bbox": [1, 1, 1, 1]}]}) + "\nkaputt\n", encoding="utf-8")
    _jsonl(tmp_path / "video_vektoren_bildervideos.jsonl",
           [{"bild_id": "9#t=2", "gesichter": [{"bbox": [1, 1, 1, 1]}]}])
    _jsonl(tmp_path / "bild_beschreibungen.jsonl", [
        {"fileid": 1, "beschreibung": "x", "kosten_usd": 0.0002},
        {"fileid": 5, "beschreibung": "y", "kosten_usd": 0.0002},
        {"fileid": 6, "beschreibung": ""},
    ])
    if mit_gruppen:
        ordner = tmp_path / "personen_gruppen"
        ordner.mkdir()
        (ordner / "personen_beispiele.json").write_text(json.dumps({"stand": "2026-10-01", "gruppen": [
            {"kennung": "Person_1001", "groesse": 60, "zwilling_kandidaten": [{"kennung": "Person_1002"}]},
            {"kennung": "Person_1002", "groesse": 30, "name": "Tim"},
            {"kennung": "Person_1003", "groesse": 10}]}), encoding="utf-8")
        _jsonl(ordner / "gesicht_zuordnung.jsonl", [{"kennung": "Person_1001"}, {"kennung": None}])


def test_bestand_zaehlt_ehrlich_und_findet_luecken(tmp_path):
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Plan sortierplan.json: 5 Eintraege = 4 Fotos + 1 Videos" in text
    assert "Gesichter Fotos:  3 von 4 (75,0 %), davon 1 mit Gesicht, 1 mit Fehler" in text
    assert "Gesichter Videos: 1 von 1 (100,0 %)" in text
    assert "Beschreibungen:   1 von 4 Fotos (25,0 %)" in text
    assert "Gesichter Fotos:  1 von 2 (50,0 %)" in text                  # Plan 2
    assert "Vektorzeilen ausserhalb aller Plaene: 1" in text
    assert "1 kaputte Zeilen" in text and "1 leer" in text
    assert "3 Gruppen mit 100 Gesichtern, benannt 1" in text
    assert "1 Gruppen >= 50 Gesichter, 3 >= 10, 0 unter 10; 1 mit Zwillingsverdacht" in text
    assert "die groessten 1 Gruppen = 50 % der Gesichter, 2 = 80 %, 2 = 90 %" in text   # 60+30 = 90 %
    assert "Zuordnung: 2 Gesichter, davon 1 in einer Gruppe (50,0 %)" in text
    assert "sortierplan.json: 1 Fotos ohne Gesichtszeile" in luecken
    assert "sortierplan_bildervideos.json: 1 Fotos ohne Gesichtszeile" in luecken
    assert "sortierplan_bildervideos.json: 1 Fotos ohne Beschreibung" in luecken


def _papa(tmp_path):
    """Papas Plan traegt die Feldnamen name/ordner (nicht von_name/von_ordner)."""
    (tmp_path / "sortierplan_papa.json").write_text(json.dumps({"zuege": [
        {"fileid": 101, "name": "P1.jpg"}, {"fileid": 102, "name": "P2.JPG"},
        {"fileid": 103, "name": "VID.mp4"}]}), encoding="utf-8")
    _jsonl(tmp_path / "personen_vektoren_papa.jsonl", [
        {"bild_id": "101", "gesichter": [{"bbox": [1, 2, 3, 4]}]},
        {"bild_id": "102", "gesichter": []}])
    _jsonl(tmp_path / "bild_beschreibungen_papa_reich.jsonl", [
        {"fileid": 101, "beschreibung": "ein Junge am Strand", "kosten_usd": 0.0004}])


def test_bestand_prueft_papas_plan_und_mehrere_beschreibungsdateien(tmp_path):
    _bestand(tmp_path)
    _papa(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    # Papas Plan wird ueberhaupt erst geprueft (frueher fehlte er ganz).
    assert "Plan sortierplan_papa.json: 3 Eintraege = 2 Fotos + 1 Videos" in text
    assert "Gesichter Fotos:  2 von 2 (100,0 %), davon 1 mit Gesicht, 0 mit Fehler" in text
    # Beschreibungen aus der zweiten (Papa-)Datei werden mitgezaehlt.
    assert "bild_beschreibungen_papa_reich.jsonl: 1 Zeilen, 1 Fotos" in text
    assert "sortierplan_papa.json: 1 Videos ohne Gesichter-Lauf" in luecken
    assert "sortierplan_papa.json: 1 Fotos ohne Beschreibung" in luecken
    # Der Dateiname traegt einen Punkt — nicht zu Komma verstuemmeln.
    assert "bild_beschreibungen,jsonl" not in text
    assert "bild_beschreibungen.jsonl: 3 Zeilen" in text


def _gedreht(tmp_path, mit_vektoren=True, ohne=1):
    """Neuausrichtung (gedreht_plan.json) + ihre neue Vektorzeilen-Datei.

    Die Planzeilen tragen nur `fileid` (kein Name) — genau wie in der echten
    Datei. `ohne` = so viele Zielfotos bekommen absichtlich keine neue Zeile.
    """
    kennungen = [201, 202, 203]
    (tmp_path / "gedreht_plan.json").write_text(
        json.dumps({"zuege": [{"fileid": k} for k in kennungen]}), encoding="utf-8")
    if mit_vektoren:
        _jsonl(tmp_path / "personen_vektoren_gedreht_neu.jsonl",
               [{"bild_id": str(k), "gesichter": []} for k in kennungen[:len(kennungen) - ohne]])


def test_nachweis_prueft_die_neuausrichtung(tmp_path):
    _bestand(tmp_path)
    _gedreht(tmp_path, ohne=1)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    # Der Plan ohne Namensfeld zaehlt trotzdem (nur fileid), 3 Bilder.
    assert "Rotierte Bilder (gedreht_plan.json): 3 Bilder" in text
    assert "davon 2 mit neuer Vektorzeile (66,7 %), ohne 1" in text
    assert "gedreht_plan.json: 1 Bilder ohne neue Vektorzeile" in luecken


def test_nachweis_neuausrichtung_vollstaendig_ohne_luecke(tmp_path):
    _bestand(tmp_path)
    _gedreht(tmp_path, ohne=0)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Rotierte Bilder (gedreht_plan.json): 3 Bilder, davon 3 mit neuer Vektorzeile (100,0 %), ohne 0" in text
    assert not any("ohne neue Vektorzeile" in l for l in luecken)


def test_nachweis_neuausrichtung_fehlende_dateien_ehrlich(tmp_path):
    _bestand(tmp_path)
    # Plan fehlt ganz: eine ehrliche Zeile, kein Wurf, keine Luecke.
    zeilen, luecken = bp.pruefen(str(tmp_path))
    assert "Rotierte Bilder (gedreht_plan.json): fehlt - Neuausrichtung nicht pruefbar" in "\n".join(zeilen)
    assert not any("ohne neue Vektorzeile" in l for l in luecken)
    # Plan da, Vektordatei fehlt: eigene Zeile UND eine benannte Luecke.
    _gedreht(tmp_path, mit_vektoren=False)
    zeilen2, luecken2 = bp.pruefen(str(tmp_path))
    assert "personen_vektoren_gedreht_neu.jsonl fehlt - neue Zeilen nicht pruefbar" in "\n".join(zeilen2)
    assert "personen_vektoren_gedreht_neu.jsonl fehlt (rotierte Bilder ohne neue Zeile)" in luecken2
    # Abschaltbar: kein Abschnitt mehr.
    zeilen3, _ = bp.pruefen(str(tmp_path), gedreht_plan=None)
    assert "Rotierte Bilder" not in "\n".join(zeilen3)


def _gesamtplan(tmp_path):
    """Union-Plan mit GEMISCHTEN Feldnamen (Sammlung: von_name, Papa: name)."""
    (tmp_path / "sortierplan_reich_gesamt.json").write_text(json.dumps({"zuege": [
        {"fileid": 1, "von_name": "IMG_1.jpg"},        # Sammlung, beschrieben
        {"fileid": 102, "name": "P2.jpg"},             # Papa-Form, NICHT beschrieben
        {"fileid": 9, "von_name": "VID_9.mp4"},        # Video
        {"fileid": 500},                               # ohne Namen (Fotobuch-Scan)
        {"von_name": "IMG_ohne_id.jpg"},               # ohne Kennung
    ]}), encoding="utf-8")


def test_gesamtplan_deckung_liest_beide_feldnamen(tmp_path):
    """Die Deckung ueber ALLE Beschreibungsdateien geht nur, wenn der Union-Plan
    auch Papas Feldnamen liest (sonst fehlten 6.336 Fotos still)."""
    _bestand(tmp_path)
    _papa(tmp_path)
    _gesamtplan(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert ("Gesamtplan sortierplan_reich_gesamt.json: 5 Eintraege = 2 Fotos + 1 Videos "
            "+ 1 ohne Namen + 1 ohne Kennung") in text
    # 2 Fotos nur moeglich, wenn `name` (Papas Form) mitgelesen wird.
    assert "Beschreibungen:   1 von 2 Fotos (50,0 %) - in keiner Beschreibungsdatei fehlen 1" in text
    assert "sortierplan_reich_gesamt.json: 1 Fotos ohne Beschreibung" in luecken


def test_gesamtplan_fehlt_wird_ehrlich_gemeldet(tmp_path):
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Gesamtplan sortierplan_reich_gesamt.json: fehlt" in text
    assert not any("ohne Beschreibung" in l for l in luecken if "gesamtplan" in l)
    # abschaltbar (z. B. fuer andere Bestaende)
    zeilen2, _ = bp.pruefen(str(tmp_path), gesamtplan=None)
    assert "Gesamtplan" not in "\n".join(zeilen2)


def test_gesamtplan_luecke_wird_benannt_mit_grund(tmp_path):
    """Die Luecke wird nicht nur gezaehlt, sondern mit Kennung und Grund benannt.

    Kennung 102 (Papas Feldnamenform) hat eine Vektorzeile, aber keine
    Bildmasse (Breite/Hoehe fehlen) -> das Bild war nicht ladbar.
    """
    _bestand(tmp_path)
    _papa(tmp_path)
    _gesamtplan(tmp_path)
    zeilen, _ = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Fehlende Fotos (1), mit Kennung und Grund:" in text
    assert "102: ohne Bildmasse (Bild nicht ladbar, keine Vorschau)" in text
    assert "Ursachen: 0 ohne Vektorzeile, 1 ohne Bildmasse, 0 ohne Beschreibungseintrag" in text
    # abschaltbar: dann steht nur noch die Zahl, keine Kennung
    text2 = "\n".join(bp.pruefen(str(tmp_path), luecken_details_max=0)[0])
    assert "Fehlende Fotos (1), mit Kennung und Grund:" in text2
    assert "102:" not in text2
    assert "--luecken-details 0" in text2


def _gesamtplan_mit_massen(tmp_path):
    """Derselbe Dateiname zweimal (Dublette), dazu ein Bild ohne Masse."""
    (tmp_path / "sortierplan_reich_gesamt.json").write_text(json.dumps({"zuege": [
        {"fileid": 11, "von_name": "gleich.jpg"},
        {"fileid": 12, "von_name": "gleich.jpg"},     # gleicher Name, andere Kennung
        {"fileid": 13, "von_name": "allein.jpg"}]}), encoding="utf-8")
    _jsonl(tmp_path / "personen_vektoren_n0929_voll.jsonl", [
        {"bild_id": "11", "breite": 100, "hoehe": 200, "gesichter": []},
        {"bild_id": "12", "breite": 100, "hoehe": 200, "gesichter": []},
        {"bild_id": "13", "breite": 0, "hoehe": 0, "gesichter": []}])


def test_luecken_details_klassifiziert_masse_und_dubletten(tmp_path):
    """Drei Gruende sauber getrennt: geladen / ohne Masse / ohne Vektorzeile,
    dazu der Dubletten-Hinweis — und nie ein Dateiname im Text."""
    _bestand(tmp_path, mit_gruppen=False)
    _gesamtplan_mit_massen(tmp_path)
    _jsonl(tmp_path / "bild_beschreibungen.jsonl", [])          # nichts beschrieben
    zeilen, _ = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "11: Bild geladen, kein Beschreibungseintrag; Name mehrfach im Plan (Dublette)" in text
    assert "12: Bild geladen, kein Beschreibungseintrag; Name mehrfach im Plan (Dublette)" in text
    assert "13: ohne Bildmasse (Bild nicht ladbar, keine Vorschau)" in text
    assert "Ursachen: 0 ohne Vektorzeile, 1 ohne Bildmasse, 2 ohne Beschreibungseintrag" in text
    assert "2 mit mehrfach vorkommendem Namen" in text
    for verboten in ("gleich.jpg", "allein.jpg"):
        assert verboten not in text
    # Masse-Erkennung direkt
    assert bp.masse_da({"breite": 10, "hoehe": 10}) is True
    assert bp.masse_da({"breite": 0, "hoehe": 100}) is False
    assert bp.masse_da({}) is False


def test_luecken_details_deckelt_die_ausgabe():
    fehlende = {str(i) for i in range(25)}
    zeilen, zaehler = bp.luecken_details(fehlende, set(), set(), max_kennungen=20)
    assert len(zeilen) == 21 and zeilen[-1] == "    ... und 5 weitere"
    assert zaehler["ohne_vektorzeile"] == 25
    assert bp.luecken_details(fehlende, set(), set(), max_kennungen=0)[0] == []


def test_bestand_meldet_trockenlauf_ohne_gruppendateien(tmp_path):
    _bestand(tmp_path, mit_gruppen=False)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    assert "Gruppen nicht gespeichert (nur Trockenlauf)" in luecken
    assert any("--schreiben" in z for z in zeilen)


def test_bestand_gibt_keine_inhalte_aus(tmp_path):
    _bestand(tmp_path)
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    for verboten in ("Tim", "IMG_", "bbox", str(tmp_path)):
        assert verboten not in text


def test_bestand_schreibt_nichts(tmp_path):
    _bestand(tmp_path)
    vorher = sorted((p.name, p.stat().st_size) for p in tmp_path.rglob("*"))
    assert bp.main(["--basis", str(tmp_path)]) == 0
    assert sorted((p.name, p.stat().st_size) for p in tmp_path.rglob("*")) == vorher
    assert bp.main(["--basis", str(tmp_path / "gibtsnicht")]) == 2


def test_abdeckung():
    assert bp.abdeckung([50, 30, 20]) == {0.5: 1, 0.8: 2, 0.9: 3}
    assert bp.abdeckung([]) == {0.5: 0, 0.8: 0, 0.9: 0}


# ── Orte (OpenStreetMap) im Nachweis ────────────────────────────────────────

def _orte(tmp_path):
    """bild_orte.csv nachgebaut: mit GPS, ohne GPS, im Flug, ohne Kennung."""
    (tmp_path / "bild_orte.csv").write_text(
        "fileid,aufnahme,adresse,hausnummer,ort_osm,landmarke,landmarke_art,hinweise,abstand_m\n"
        "1,2020-01-01,Lauenburger Strasse,41,Hamburg,Alster,fluss,fluss:Alster|0.10,100\n"
        "2,2020-01-02,,,,,,ohne GPS,\n"
        "3,2020-01-03,,,Berlin,,flug,flug,\n"
        "4,,,,,,,restaurant:X|0.20,50\n",
        encoding="utf-8")


def test_nachweis_zaehlt_bild_orte(tmp_path):
    """Der Karten-Zweig stand in KEINEM Nachweis — jetzt wird er gezaehlt."""
    _bestand(tmp_path)
    _orte(tmp_path)
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert ("Orte (OSM): bild_orte.csv: 4 Zeilen (eine je Bild) = 2 mit GPS + 1 ohne GPS "
            "+ 1 im Flug") in text
    assert "Ortsname 2, Landmarke 1, Strasse 1, Hausnummer 1" in text


def test_nachweis_meldet_fehlende_bild_orte_ehrlich(tmp_path):
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    assert "Orte (OSM): bild_orte.csv fehlt" in "\n".join(zeilen)
    assert "bild_orte.csv fehlt (Kartenauswertung nicht zugeordnet)" in luecken
    # abschaltbar (z. B. fuer einen Bestand ohne Karten)
    assert "Orte (OSM)" not in "\n".join(bp.pruefen(str(tmp_path), bild_orte=None)[0])


def test_nachweis_zeigt_keine_ortsnamen_und_zaehlt_nur_fertige_gebiete(tmp_path):
    """Ein Gebiet zaehlt nur mit BEIDEN Tabellen; keine Namen/Koordinaten im Text."""
    _bestand(tmp_path)
    _orte(tmp_path)
    ordner = tmp_path / "osm" / "csv"
    voll = ordner / "hamburg-latest"
    voll.mkdir(parents=True)
    (voll / "osm_orte.csv").write_text("breite,laenge,art,name,zusatz\n", encoding="utf-8")
    (voll / "osm_adressen.csv").write_text("breite,laenge,strasse,hausnummer,ort,region\n",
                                           encoding="utf-8")
    halb = ordner / "bayern-latest"          # nur eine Tabelle = nicht fertig
    halb.mkdir()
    (halb / "osm_orte.csv").write_text("breite,laenge,art,name,zusatz\n", encoding="utf-8")
    (ordner / "osm_orte.csv").write_text("breite,laenge,art,name,zusatz\na\nb\n",
                                         encoding="utf-8")
    (ordner / "osm_adressen.csv").write_text("breite,laenge,strasse,hausnummer,ort,region\nc\n",
                                             encoding="utf-8")
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert "Karten: 1 Gebiete mit beiden Tabellen (osm/csv)" in text
    assert "Gesamttabellen: 2 Orte, 1 Adressen" in text
    assert bp.karten_gebiete(str(ordner)) == 1
    assert bp.karten_gebiete(str(tmp_path / "gibtsnicht")) == 0
    for verboten in ("Hamburg", "Berlin", "Alster", "Lauenburger"):
        assert verboten not in text


# ── Bildindex (Bildsuche) im Nachweis ───────────────────────────────────────

def _bildindex(tmp_path, ids, meta=None):
    """``bild_index.db`` nachgebaut: Tabelle ``bilder`` + ``meta`` (echte Mini-SQLite)."""
    import sqlite3
    db = tmp_path / "bild_index.db"
    con = sqlite3.connect(str(db))
    con.executescript(
        "CREATE TABLE bilder (fileid INTEGER PRIMARY KEY,"
        " datum TEXT NOT NULL DEFAULT '', ordner TEXT NOT NULL DEFAULT '',"
        " beschreibung TEXT NOT NULL DEFAULT '', vektor BLOB);"
        "CREATE TABLE meta (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL DEFAULT '');")
    con.executemany("INSERT INTO bilder (fileid, datum, ordner, beschreibung, vektor)"
                    " VALUES (?,?,?,?,?)",
                    [(k, "", "geheim/ordner", "eine Beschreibung", b"\x00\x01") for k in ids])
    for schluessel, wert in (meta or {}).items():
        con.execute("INSERT INTO meta (schluessel, wert) VALUES (?,?)", (schluessel, wert))
    con.commit()
    con.close()
    return db


def test_nachweis_zaehlt_den_bildindex(tmp_path):
    """Der Bildindex stand in KEINEM Nachweis, obwohl er der Schluss der Kette ist."""
    _bestand(tmp_path)
    _bildindex(tmp_path, [1, 5], {"modell": "openai/text-embedding-3-small",
                                  "dimension": "1536", "tokens_gezaehlt": "947779",
                                  "kosten_usd": "0.018956", "stand": "2026-10-10T14:32"})
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert ("Bildindex (Bildsuche): bild_index.db: 2 Bilder, 2 mit Vektor, 2 mit Beschreibung"
            ) in text
    assert ("openai/text-embedding-3-small; 1536 Dimensionen; 947.779 Token; 0,02 USD; "
            "Stand 2026-10-10T14:32") in text
    # Beschrieben sind in _bestand nur die Kennungen 1 und 5 -> beide im Index.
    assert "Beschrieben, aber ohne Vektor im Index: 0; im Index, aber nicht beschrieben: 0" in text


def test_nachweis_meldet_fehlenden_bildindex_ehrlich(tmp_path):
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    assert "Bildindex (Bildsuche): bild_index.db fehlt" in "\n".join(zeilen)
    assert "bild_index.db fehlt (Bildsuche nicht eingebettet)" in luecken
    # abschaltbar (z. B. fuer einen Bestand ohne Bildsuche)
    assert "Bildindex" not in "\n".join(bp.pruefen(str(tmp_path), bild_index=None)[0])


def test_nachweis_benennt_fehlende_vektoren_im_index(tmp_path):
    """Ein beschriebenes Foto ohne Vektor im Index ist eine offene Luecke."""
    _bestand(tmp_path)
    _bildindex(tmp_path, [1])                     # Kennung 5 (beschrieben) fehlt im Index
    zeilen, luecken = bp.pruefen(str(tmp_path))
    assert ("Beschrieben, aber ohne Vektor im Index: 1; im Index, aber nicht beschrieben: 0"
            ) in "\n".join(zeilen)
    assert "bild_index.db: 1 beschriebene Fotos ohne Vektor (Bildsuche unvollstaendig)" in luecken


def test_nachweis_zeigt_keine_inhalte_aus_dem_index(tmp_path):
    _bestand(tmp_path)
    _bildindex(tmp_path, [1], {"modell": "m"})
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    for verboten in ("eine Beschreibung", "geheim"):
        assert verboten not in text


def test_bildindex_kaputte_datei_wird_ehrlich_gemeldet(tmp_path):
    kaputt = tmp_path / "kaputt.db"
    kaputt.write_text("kein sqlite", encoding="utf-8")
    erg = bp.bildindex_lesen(str(kaputt))
    assert erg.get("fehlt") is True
    assert bp.bildindex_lesen(str(tmp_path / "gibtsnicht.db")) == {"fehlt": True}


# ── Uebergabe per Kabel ─────────────────────────────────────────────────────

class AdbAttrappe:
    def __init__(self, geraet=True, groesse_falsch=False):
        self.befehle = []
        self.geraet = geraet
        self.groesse_falsch = groesse_falsch
        self.abgelegt = {}

    def __call__(self, befehl):
        self.befehle.append(befehl)
        if befehl[1:] == ["devices"]:
            return 0, "List of devices attached\n" + ("ZY22K9\tdevice\n" if self.geraet else "")
        if befehl[1] == "push":
            self.abgelegt[befehl[3]] = os.path.getsize(befehl[2])
            return 0, "1 file pushed"
        if befehl[1:4] == ["shell", "stat", "-c"]:
            g = self.abgelegt.get(befehl[5])
            return 0, str(g + 1 if self.groesse_falsch else g)
        return 1, "unbekannt"


def _gruppen_dateien(tmp_path):
    for n in gh.DATEIEN:
        (tmp_path / n).write_text("{}" if n.endswith(".json") else "{}\n{}\n", encoding="utf-8")


def test_uebergabe_trockenlauf_sendet_nichts(tmp_path):
    _gruppen_dateien(tmp_path)
    adb = AdbAttrappe()
    code, zeilen = gh.senden(str(tmp_path), "/sdcard/Download", adb, wirklich=False)
    assert code == 0 and adb.befehle == [] and "Trockenlauf" in zeilen[-1]


def test_uebergabe_sendet_und_prueft_groesse(tmp_path):
    _gruppen_dateien(tmp_path)
    adb = AdbAttrappe()
    code, zeilen = gh.senden(str(tmp_path), "/sdcard/Download", adb, wirklich=True)
    assert code == 0
    assert sorted(adb.abgelegt) == ["/sdcard/Download/gesicht_zuordnung.jsonl",
                                    "/sdcard/Download/personen_beispiele.json"]
    assert all(b[1] in ("devices", "push", "shell") for b in adb.befehle)
    assert not any("rm" in b for b in adb.befehle)                  # nie loeschen
    assert "Widget" in zeilen[-1]


def test_uebergabe_erkennt_falsche_groesse_und_fehlendes_geraet(tmp_path):
    _gruppen_dateien(tmp_path)
    assert gh.senden(str(tmp_path), "/sdcard/Download", AdbAttrappe(groesse_falsch=True), wirklich=True)[0] == 1
    assert gh.senden(str(tmp_path), "/sdcard/Download", AdbAttrappe(geraet=False), wirklich=True)[0] == 2


def test_uebergabe_ohne_dateien_und_falsches_ziel(tmp_path):
    code, zeilen = gh.senden(str(tmp_path), "/sdcard/Download", AdbAttrappe(), wirklich=True)
    assert code == 2 and "--schreiben" in zeilen[0]
    assert gh.main(["--ziel", "/data/data/com.termux", "--basis", str(tmp_path)]) == 2


# ── Telefonbuch -> kontakte.json (02.10.2026, Issue #3 Teil A) — erfundene Daten ──

kh = _laden("kontakte_aufs_handy", "handy")

TELEFON_ROH = """Row: 0 contact_id=11, display_name=Leon Müller, data1=+49 170 000-0001
Row: 1 contact_id=11, display_name=Leon Müller, data1=(040) 000 0002
Row: 2 contact_id=11, display_name=Leon Müller, data1=+49 170 000-0001
Row: 3 contact_id=12, display_name=Lea, Schulz, data1=0170 0000003
Row: 4 contact_id=abc, display_name=Kaputt, data1=123
"""
EVENT_ROH = """Row: 0 contact_id=11, display_name=Leon Müller, data1=--03-14, data2=3, mimetype=vnd.android.cursor.item/contact_event
Row: 1 contact_id=11, display_name=Leon Müller, data1=1997-03-14, data2=3, mimetype=vnd.android.cursor.item/contact_event
Row: 2 contact_id=12, display_name=Lea, Schulz, data1=2010-06-01, data2=0, mimetype=vnd.android.cursor.item/contact_event
Row: 3 contact_id=14, display_name=Nur Geburtstag, data1=--13-40, data2=3, mimetype=vnd.android.cursor.item/contact_event
"""


class TelefonbuchAdb:
    def __init__(self, ok=True):
        self.ok = ok
        self.befehle = []
        self.abgelegt = {}

    def __call__(self, befehl):
        self.befehle.append(befehl)
        if befehl[1] == "shell" and "content query" in befehl[2]:
            if not self.ok:
                return 1, "error"
            return 0, (EVENT_ROH if "contact_event" in befehl[2] else TELEFON_ROH)
        if befehl[1] == "push":
            self.abgelegt[befehl[3]] = os.path.getsize(befehl[2])
            return 0, "1 file pushed"
        if befehl[1:4] == ["shell", "stat", "-c"]:
            return 0, str(self.abgelegt.get(befehl[5]))
        return 1, "?"


def test_kontakte_bauen_je_kennung_nummern_geburtstag():
    zerleger = kh._zuordnung()._zeilen_zerlegen
    k = kh.kontakte_bauen(TELEFON_ROH, EVENT_ROH, zerleger)
    assert [x["id"] for x in k] == ["12", "11"]                       # nach Name sortiert
    leon = k[1]
    assert leon["name"] == "Leon Müller"
    assert leon["nummern"] == ["+491700000001", "0400000002"]          # gesaeubert, ohne Doppelte
    assert leon["geburtstag"] == "1997-03-14"                          # mit Jahr bevorzugt
    assert k[0]["name"] == "Lea, Schulz" and k[0]["geburtstag"] is None   # Jahrestag (Typ 0) zaehlt nicht


def test_trockenlauf_zeigt_nur_zahlen(tmp_path, capsys):
    adb = TelefonbuchAdb()
    rc = kh.main(["--ausgabe", str(tmp_path / "kontakte.json")], ausfuehren=adb)
    aus = capsys.readouterr().out
    assert rc == 0 and "Kontakte: 2" in aus and "mit Geburtstag: 1 (davon mit Jahr: 1)" in aus
    for privat in ("Leon", "Müller", "Schulz", "0001", "+49"):
        assert privat not in aus
    assert not (tmp_path / "kontakte.json").exists()
    assert not any(b[1] == "push" for b in adb.befehle)


def test_senden_schreibt_ausserhalb_und_legt_aufs_handy(tmp_path):
    ziel = tmp_path / "kontakte.json"
    adb = TelefonbuchAdb()
    assert kh.main(["--ausgabe", str(ziel), "--senden"], ausfuehren=adb) == 0
    daten = json.loads(ziel.read_text(encoding="utf-8"))
    assert daten["quelle"] == "telefonbuch-adb" and len(daten["kontakte"]) == 2
    assert list(adb.abgelegt) == ["/sdcard/Download/kontakte.json"]
    assert not any("rm" in b for b in adb.befehle)


def test_kontakte_nie_ins_repo_und_ehrlicher_fehler(tmp_path):
    assert kh.main(["--ausgabe", os.path.join(PROJEKT, "kontakte.json"), "--schreiben"],
                   ausfuehren=TelefonbuchAdb()) == 2
    assert not os.path.exists(os.path.join(PROJEKT, "kontakte.json"))
    assert kh.main(["--ausgabe", str(tmp_path / "k.json")], ausfuehren=TelefonbuchAdb(ok=False)) == 3
    assert kh.main(["--ausgabe", str(tmp_path / "k.json"), "--ziel", "/data/x"],
                   ausfuehren=TelefonbuchAdb()) == 2


def test_geburtstag_und_nummer_saeubern():
    assert kh.geburtstag_text("1997-03-14") == "1997-03-14"
    assert kh.geburtstag_text("--03-14") == "--03-14"
    assert kh.geburtstag_text("--13-01") is None and kh.geburtstag_text("gestern") is None
    assert kh.nummer_saeubern("+49 (0) 170/123-45") == "+49017012345"
    assert kh.nummer_saeubern("0170 12 34") == "01701234"


# ── Anlaesse im Nachweis ────────────────────────────────────────────────────
# Die Anlass-Datei (ordner_ereignisse.jsonl, Ketten-Schritt 5) traegt „Anlaesse
# einer Person" und das Erzaehlen — und stand bisher in KEINEM Nachweis. Sie ist
# der Stufe OSM (Journal 8) und dem Bildindex (Journal 12) gleichgestellt.

def _anlaesse(tmp_path, kaputt=False):
    """ordner_ereignisse.jsonl nachgebaut: zwei Anlaesse, drei Kennungen, ein Video.

    Die Titel/Kategorien sind ABSICHTLICH Fantasieworte — der Nachweis darf sie
    nie zeigen (Privatsphaere).
    """
    (tmp_path / "ordner_ereignisse.jsonl").write_text(
        json.dumps({"anlass_id": "O-1", "datei_kennungen": [1, 2], "videos": 0,
                    "datum": "2020-01-01", "jahr": 2020,
                    "event": "TITEL_DARF_NICHT_ERSCHEINEN",
                    "kategorie": "KATEGORIE_DARF_NICHT_ERSCHEINEN",
                    "quellen": {"datum": {"exif": 1}}}) + "\n"
        + json.dumps({"anlass_id": "O-2", "datei_kennungen": [5], "videos": 1,
                      "datum": None, "jahr": 2019,
                      "quellen": {"datum": {"dateiname": 1}}}) + "\n"
        + ("kaputt\n" if kaputt else ""),
        encoding="utf-8")


def test_nachweis_zaehlt_anlaesse(tmp_path):
    """Die Anlass-Stufe stand in KEINEM Nachweis — jetzt wird sie gezaehlt."""
    _bestand(tmp_path)
    _anlaesse(tmp_path)
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert "Anlaesse (ordner_ereignisse.jsonl): 2 Anlaesse, 3 Datei-Kennungen, davon 1 Videos" in text
    assert "Datum: 1 von 2 Anlaessen tragen eines (dateiname 1, exif 1)" in text
    assert "Jahre: 2019-2020" in text
    # Plan-Fotos sind 1..6, in Anlaessen sind 1, 2 und 5 -> 3 von 6.
    assert "Deckung: 3 von 6 Plan-Fotos liegen in einem Anlass (50,0 %)" in text


def test_nachweis_zeigt_keine_titel_und_zaehlt_kaputte_zeilen(tmp_path):
    """Nur Zahlen: kein Titel, keine Kategorie; eine kaputte Zeile wird gemeldet."""
    _bestand(tmp_path)
    _anlaesse(tmp_path, kaputt=True)
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert "TITEL_DARF_NICHT_ERSCHEINEN" not in text
    assert "KATEGORIE_DARF_NICHT_ERSCHEINEN" not in text
    assert "1 kaputte Zeilen" in text


def test_nachweis_meldet_fehlende_anlaesse_ehrlich(tmp_path):
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    assert "Anlaesse (ordner_ereignisse.jsonl): fehlt" in "\n".join(zeilen)
    assert "ordner_ereignisse.jsonl fehlt (Anlaesse nicht gebaut)" in luecken
    # abschaltbar (z. B. fuer einen Bestand ohne Anlass-Datei) — beide Anlass-Sichten
    assert "Anlaesse" not in "\n".join(
        bp.pruefen(str(tmp_path), anlaesse=None, erzaehl_quellen=None)[0])


def test_anlaesse_lesen_wirft_bei_kaputter_datei_nicht(tmp_path):
    """Fehlende Datei und ein Nicht-JSON-Zeile ergeben ehrliche Zahlen, keinen Wurf."""
    e = bp.anlaesse_lesen(str(tmp_path / "gibts_nicht.jsonl"))
    assert e["fehlt"] is True and e["anlaesse"] == 0
    (tmp_path / "halb.jsonl").write_text(
        json.dumps({"datei_kennungen": [7], "jahr": 2001}) + "\nnur text\n", encoding="utf-8")
    e2 = bp.anlaesse_lesen(str(tmp_path / "halb.jsonl"))
    assert e2["anlaesse"] == 1 and e2["kaputt"] == 1 and e2["kennungen"] == {"7"}
    assert e2["mit_datum"] == 0 and e2["jahr_min"] == 2001 and e2["jahr_max"] == 2001


# ── Ortsnamen (GeoNames) im Nachweis ────────────────────────────────────────
# Die Ortsnamen (orte.jsonl, Ketten-Schritt 3b) tragen die Auskunft „wo war das?"
# und die Ortsnamen fuer die Erzaehlung — und standen in KEINEM Nachweis. Sie
# sind der Stufe OSM (Journal 8), dem Bildindex (Journal 12) und den Anlaessen
# (Journal 19) gleichgestellt.

def _orte_namen(tmp_path, kaputt=False, doppelt=False):
    """orte.jsonl nachgebaut: Land/Region/Ort mit Aufnahmedatum, ein Bild ohne Ort.

    Die Ortsnamen sind ABSICHTLICH Fantasieworte — der Nachweis darf sie nie
    zeigen (Privatsphaere).
    """
    zeilen = [
        {"bild_id": 1, "land": "FANTASIELAND", "region": "REGION_A", "ort": "ORT_A",
         "aufnahme": "2020-01-01T10:00:00"},
        {"bild_id": 2, "land": "FANTASIELAND", "region": "REGION_A", "ort": "ORT_B",
         "aufnahme": "2021-02-02T10:00:00"},
        {"bild_id": 3, "land": "FANTASIELAND", "region": "REGION_B", "ort": None,
         "aufnahme": None},
    ]
    if doppelt:
        zeilen.append({"bild_id": 1, "land": "FANTASIELAND", "region": "REGION_A",
                       "ort": "ORT_A", "aufnahme": "2020-01-01T10:00:00"})
    text = "\n".join(json.dumps(z) for z in zeilen) + "\n" + ("kaputt\n" if kaputt else "")
    (tmp_path / "orte.jsonl").write_text(text, encoding="utf-8")


def test_nachweis_zaehlt_ortsnamen(tmp_path):
    """Die Ortsnamen-Stufe stand in KEINEM Nachweis — jetzt wird sie gezaehlt."""
    _bestand(tmp_path)
    _orte_namen(tmp_path)
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert "Orte (GeoNames): orte.jsonl: 3 Zeilen, 3 Bilder" in text
    assert "Namen: 1 Laender, 2 Regionen, 2 Orte; ohne Ortsnamen 1" in text
    assert "Aufnahme: 2 von 3 Zeilen tragen ein Datum (2 verschiedene Tage)" in text
    # Plan-Fotos sind 1..6, mit Ortsnamen sind 1, 2 und 3 -> 3 von 6.
    assert "Deckung: 3 von 6 Plan-Fotos haben einen Ortsnamen (50,0 %)" in text


def test_nachweis_zeigt_keine_ortsnamen_und_meldet_dubletten(tmp_path):
    """Nur Zahlen: kein Land/Region/Ort im Text; doppelte Zeilen werden gemeldet."""
    _bestand(tmp_path)
    _orte_namen(tmp_path, doppelt=True, kaputt=True)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    for verboten in ("FANTASIELAND", "REGION_A", "REGION_B", "ORT_A", "ORT_B"):
        assert verboten not in text
    assert "1 doppelt" in text and "1 kaputte Zeilen" in text
    assert "orte.jsonl: 1 doppelte Zeilen (anhaengender Lauf nicht idempotent)" in luecken


def test_nachweis_meldet_fehlende_ortsnamen_ehrlich(tmp_path):
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    assert "Orte (GeoNames): orte.jsonl fehlt" in "\n".join(zeilen)
    assert "orte.jsonl fehlt (Ortsnamen nicht zugeordnet)" in luecken
    # abschaltbar (z. B. fuer einen Bestand ohne Ortsnamen)
    assert "Orte (GeoNames)" not in "\n".join(bp.pruefen(str(tmp_path), orte_namen=None)[0])


def test_ortsnamen_lesen_wirft_bei_kaputter_datei_nicht(tmp_path):
    """Fehlende Datei und Nicht-JSON-Zeilen ergeben ehrliche Zahlen, keinen Wurf."""
    e = bp.ortsnamen_lesen(str(tmp_path / "gibts_nicht.jsonl"))
    assert e["fehlt"] is True and e["zeilen"] == 0 and e["kennungen"] == set()
    (tmp_path / "halb.jsonl").write_text(
        json.dumps({"bild_id": 7, "land": "X", "ort": "Y", "aufnahme": "2019-05-05T09:00:00"})
        + "\nnur text\n", encoding="utf-8")
    e2 = bp.ortsnamen_lesen(str(tmp_path / "halb.jsonl"))
    assert e2["zeilen"] == 1 and e2["kaputt"] == 1 and e2["kennungen"] == {"7"}
    assert e2["laender"] == 1 and e2["orte"] == 1 and e2["tage"] == 1 and e2["doppelt"] == 0


# ── Erzaehl-Quellen im Nachweis ─────────────────────────────────────────────
# `erzaehl_service._ereignisse_laden()` liest drei Dateien: fotobuch_ereignisse
# (Buchseiten, zuerst), ereignisse.jsonl (Anlaesse der Sammlung) und
# ordner_ereignisse.jsonl (Bau vom 10.10.). Nur die dritte hatte einen Nachweis —
# die zwei anderen trugen das Erzaehlen ohne jede Pruefzeile.

def _erzaehl_quellen(tmp_path, ohne_kennung=False):
    """ereignisse.jsonl + fotobuch_ereignisse.jsonl nachgebaut.

    Titel, Buchname und Buchtexte sind ABSICHTLICH Fantasieworte — der Nachweis
    darf sie nie zeigen (Privatsphaere).
    """
    zweiter: dict = {"kennung": "E-2", "datei_kennungen": [5], "datum": None,
                     "jahr": 2019, "quellen": {"datum": {"sortierplan": 1}}}
    if ohne_kennung:
        zweiter["kennung"] = None
    zeilen = [
        {"kennung": "E-1", "datei_kennungen": [1, 2], "datum": "2020-01-01", "jahr": 2020,
         "event": "TITEL_DARF_NICHT_ERSCHEINEN", "kategorie": "KATEGORIE_DARF_NICHT_ERSCHEINEN",
         "quellen": {"datum": {"exif": 1}}},
        zweiter,
    ]
    (tmp_path / "ereignisse.jsonl").write_text(
        "\n".join(json.dumps(z) for z in zeilen) + "\n", encoding="utf-8")
    (tmp_path / "fotobuch_ereignisse.jsonl").write_text(json.dumps(
        {"kennung": "buch-1", "datei_kennungen": [3], "datum": None, "jahr": None,
         "titel": "TITEL_DARF_NICHT_ERSCHEINEN", "buch": "BUCH_DARF_NICHT_ERSCHEINEN",
         "seite": 7, "texte": ["TEXT_DARF_NICHT_ERSCHEINEN"]}) + "\n", encoding="utf-8")


def test_nachweis_zaehlt_erzaehl_quellen(tmp_path):
    """Die zwei Erzaehl-Quellen standen in KEINEM Nachweis — jetzt werden sie gezaehlt."""
    _bestand(tmp_path)
    _erzaehl_quellen(tmp_path)
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert "Erzaehl-Anlaesse (ereignisse.jsonl): 2 Anlaesse, 3 Datei-Kennungen" in text
    assert "Erzaehl-Anlaesse (fotobuch_ereignisse.jsonl): 1 Anlaesse, 1 Datei-Kennungen" in text
    assert "  Datum: 1 von 2 tragen eines (exif 1, sortierplan 1)" in text
    assert "  Jahre: 2019-2020" in text
    # Plan-Fotos sind 1..6; ereignisse.jsonl traegt 1, 2, 5 -> 3 von 6,
    # fotobuch_ereignisse.jsonl traegt 3 -> ebenfalls 3 von 6.
    assert "  Deckung: 3 von 6 Plan-Fotos liegen in einem Anlass (50,0 %)" in text
    assert "  Erzaehl-Dienst: 2 von 2 dieser Quellen vorhanden (dazu ordner_ereignisse.jsonl)" in text


def test_nachweis_zeigt_keine_titel_und_zaehlt_anlaesse_ohne_kennung(tmp_path):
    """Nur Zahlen: kein Titel, kein Buchname, kein Buchtext; Zeile ohne Kennung gemeldet.

    Eine Anlass-Zeile ohne `kennung` verwirft `erzaehl_service` still — der Anlass
    verschwindet damit aus den Geschichten. Der Nachweis muss das zeigen.
    """
    _bestand(tmp_path)
    _erzaehl_quellen(tmp_path, ohne_kennung=True)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    for verboten in ("TITEL_DARF_NICHT_ERSCHEINEN", "KATEGORIE_DARF_NICHT_ERSCHEINEN",
                     "BUCH_DARF_NICHT_ERSCHEINEN", "TEXT_DARF_NICHT_ERSCHEINEN"):
        assert verboten not in text
    assert "1 ohne Kennung (wird nicht erzaehlt)" in text
    assert "ereignisse.jsonl: 1 Anlaesse ohne Kennung (werden nicht erzaehlt)" in luecken


def test_nachweis_meldet_fehlende_erzaehl_quellen_ehrlich(tmp_path):
    """Fehlt eine Erzaehl-Quelle, steht das als Luecke — nicht als stiller Nullwert."""
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Erzaehl-Anlaesse (ereignisse.jsonl): fehlt" in text
    assert "Erzaehl-Anlaesse (fotobuch_ereignisse.jsonl): fehlt" in text
    assert "  Erzaehl-Dienst: 0 von 2 dieser Quellen vorhanden (dazu ordner_ereignisse.jsonl)" in text
    assert "ereignisse.jsonl fehlt (Erzaehl-Anlaesse nicht gebaut)" in luecken
    assert "fotobuch_ereignisse.jsonl fehlt (Erzaehl-Anlaesse nicht gebaut)" in luecken
    assert "keine Erzaehl-Anlaesse vorhanden (Geschichten ohne Anlass)" in luecken
    # abschaltbar (z. B. fuer einen Bestand ohne diese Dateien)
    assert "Erzaehl-Anlaesse" not in "\n".join(
        bp.pruefen(str(tmp_path), erzaehl_quellen=None)[0])


def test_anlaesse_lesen_zaehlt_zeilen_ohne_kennung(tmp_path):
    """Eine Zeile ohne brauchbare kennung zaehlt als Anlass UND als ohne_kennung."""
    pfad = tmp_path / "quellen.jsonl"
    pfad.write_text(
        json.dumps({"kennung": "E-1", "datei_kennungen": [1], "jahr": 2020}) + "\n"
        + json.dumps({"kennung": None, "datei_kennungen": [2], "jahr": 2021}) + "\n"
        + json.dumps({"kennung": "   ", "datei_kennungen": [3], "jahr": 2022}) + "\n"
        # Quellenangabe als TEXT statt als Zaehler-Dict (Sammlungs-Anlaesse):
        # ohne diesen Zweig stuende im Bericht "keine Quellenangabe", obwohl die
        # Quelle dasteht.
        + json.dumps({"kennung": "E-4", "datei_kennungen": [4], "jahr": 2023,
                      "datum": "2023-01-01",
                      "quellen": {"datum": "sortierplan.json:anlaesse"}}) + "\n",
        encoding="utf-8")
    e = bp.anlaesse_lesen(str(pfad))
    assert e["anlaesse"] == 4 and e["ohne_kennung"] == 2 and e["kaputt"] == 0
    assert e["kennungen"] == {"1", "2", "3", "4"}
    assert e["mit_datum"] == 1 and e["datum_quellen"] == {"sortierplan.json": 1}


# ── Beziehungen („wer war mit wem wo") im Nachweis ──────────────────────────
# `beziehungen_service` (Antwortstufe N28) liest `beziehungen.jsonl` (15.051
# Aussagen) UND die Uebersicht `beziehungen.json` — beide standen in KEINEM
# Nachweis. Faellt die Aussagen-Datei weg oder halbiert sie sich, schweigt die
# Auskunft „wer war mit wem wo", ohne dass es auffiele.

def _beziehungen(tmp_path, uebersicht_summe=None):
    """``beziehungen.jsonl`` + ``beziehungen.json`` nachgebaut (Fantasienamen).

    Die Namen und Kategorien sind ABSICHTLICH Fantasieworte — der Nachweis darf
    sie nie zeigen (Privatsphaere). ``uebersicht_summe`` setzt eine abweichende
    Kennzahl, um die Reproduzierbarkeits-Pruefung zu belegen.
    """
    zeilen = [
        {"anlass_id": "2016-05-04_Anlass-01", "ereignis_kennung": "E-1", "datum": "2016-05-04",
         "unterart": "gemeinsam_im_chat", "kategorie": "KATEGORIE_DARF_NICHT_ERSCHEINEN",
         "beleg": {"chat_name": "CHAT_DARF_NICHT_ERSCHEINEN"},
         "personen": [{"bestaetigt": True, "kennung": "P-1", "name": "NAME_DARF_NICHT_ERSCHEINEN"},
                      {"bestaetigt": True, "kennung": None, "name": "NAME_DARF_NICHT_ERSCHEINEN"}]},
        {"anlass_id": "2016-05-04_Anlass-01", "ereignis_kennung": "E-1", "datum": "2016-05-04",
         "unterart": "fotos", "kategorie": "KATEGORIE_DARF_NICHT_ERSCHEINEN",
         "personen": [{"bestaetigt": False, "kennung": "P-2", "name": "NAME_DARF_NICHT_ERSCHEINEN"}]},
        {"anlass_id": "2020-01-01_Anlass-02", "ereignis_kennung": "E-2", "datum": "2020-01-01",
         "unterart": "fotos_und_chat",
         "personen": [{"bestaetigt": True, "kennung": "P-3", "name": "NAME_DARF_NICHT_ERSCHEINEN"}]},
    ]
    _jsonl(tmp_path / "beziehungen.jsonl", zeilen)
    summe = uebersicht_summe if uebersicht_summe is not None else 3
    (tmp_path / "beziehungen.json").write_text(json.dumps({
        "art": "beziehungen", "stand": "2026-09-29T01:42:52+02:00",
        "anzahl": {"fotos": 1, "fotos_und_chat": 1, "gemeinsam_im_chat": summe - 2},
        "anzahl_kontakte": 5, "anzahl_personen_kennungen": 3,
        "datum_von": "2016-05-04", "datum_bis": "2020-01-01"}), encoding="utf-8")


def test_nachweis_zaehlt_beziehungen(tmp_path):
    """Die Beziehungs-Stufe stand in KEINEM Nachweis — jetzt wird sie gezaehlt."""
    _bestand(tmp_path)
    _beziehungen(tmp_path)
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert "Beziehungen (beziehungen.jsonl): 3 Aussagen, 2 Anlaesse, 2 Tage, 1 Kategorien" in text
    assert "  Unterarten: fotos 1, fotos_und_chat 1, gemeinsam_im_chat 1" in text
    assert "  Personen-Eintraege: 4, davon 3 bestaetigt, 3 mit Kennung" in text
    assert "  Datum: 3 von 3 tragen eines; Jahre 2016-2020" in text
    assert ("  Uebersicht (beziehungen.json): nennt 3 Aussagen (fotos 1, fotos_und_chat 1, "
            "gemeinsam_im_chat 1); Kontakte 5, Kennungen 3; 2016-05-04 bis 2020-01-01") in text


def test_nachweis_zeigt_keine_namen_und_meldet_abweichung(tmp_path):
    """Nur Zahlen: kein Name, kein Chat-Name, keine Kategorie; Abweichung als Luecke."""
    _bestand(tmp_path)
    _beziehungen(tmp_path, uebersicht_summe=99)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    for verboten in ("NAME_DARF_NICHT_ERSCHEINEN", "CHAT_DARF_NICHT_ERSCHEINEN",
                     "KATEGORIE_DARF_NICHT_ERSCHEINEN"):
        assert verboten not in text
    assert "    Abweichung: Uebersicht nennt 99, gemessen 3" in text
    assert "beziehungen.jsonl: 3 Aussagen, Uebersicht nennt 99 (nicht reproduzierbar)" in luecken


def test_nachweis_meldet_fehlende_beziehungen_ehrlich(tmp_path):
    """Fehlen die Dateien, steht das als Luecke — nicht als stiller Nullwert."""
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Beziehungen (beziehungen.jsonl): fehlt" in text
    assert "  Uebersicht (beziehungen.json): fehlt" in text
    assert "beziehungen.jsonl fehlt (Beziehungen nicht abgeleitet)" in luecken
    assert "beziehungen.json fehlt (Beziehungs-Kennzahlen fehlen)" in luecken
    # abschaltbar (z. B. fuer einen Bestand ohne Beziehungen)
    assert "Beziehungen" not in "\n".join(
        bp.pruefen(str(tmp_path), beziehungen=None, beziehungen_uebersicht=None)[0])


def test_beziehungen_lesen_wirft_bei_kaputter_datei_nicht(tmp_path):
    """Fehlende und kaputte Dateien ergeben ehrliche Zahlen, keinen Wurf."""
    e = bp.beziehungen_lesen(str(tmp_path / "gibts_nicht.jsonl"))
    assert e["fehlt"] is True and e["zeilen"] == 0 and e["anlaesse"] == set()
    (tmp_path / "halb.jsonl").write_text(
        json.dumps({"anlass_id": "A-1", "datum": "2021-03-04", "unterart": "fotos",
                    "personen": [{"bestaetigt": True, "kennung": "P-1"}]}) + "\nnur text\n",
        encoding="utf-8")
    e2 = bp.beziehungen_lesen(str(tmp_path / "halb.jsonl"))
    assert e2["zeilen"] == 1 and e2["kaputt"] == 1
    assert e2["anlaesse"] == {"A-1"} and e2["tage"] == {"2021-03-04"}
    assert e2["personen_eintraege"] == 1 and e2["personen_bestaetigt"] == 1
    assert e2["personen_mit_kennung"] == 1 and e2["jahr_min"] == 2021 and e2["jahr_max"] == 2021
    # Uebersicht-Leser: fehlend und kaputt ergeben ehrliche Werte, keinen Wurf.
    u = bp.beziehungen_uebersicht_lesen(str(tmp_path / "keine.json"))
    assert u["fehlt"] is True and u["summe"] == 0 and u["anzahl"] == {}
    (tmp_path / "kaputt.json").write_text("{kein json", encoding="utf-8")
    u2 = bp.beziehungen_uebersicht_lesen(str(tmp_path / "kaputt.json"))
    assert u2["fehlt"] is False and u2["kaputt"] is True and u2["summe"] == 0


# ── Personen-Stufe (Quiz + Telefonbuch) im Nachweis ─────────────────────────
# Die Chat-Werkzeuge `personen_liste` / `person_auskunft` / `fotos_mit_person`
# lesen seit dem 10.10. die QUIZ-Quelle (`gruppen_quiz.personen()`): bestaetigte
# Namen, Vorgaben, Profile (Beziehung/Notizen/Kontakt) und das Telefonbuch.
# Gezaehlt wurden bisher nur die Gruppen — die NAMEN standen in KEINEM Nachweis.
# Faellt oder halbiert sich `personen_bestaetigt.json`, findet die
# Personen-Auskunft niemanden mehr, ohne dass es auffiele.

def _personen(tmp_path):
    """Quiz- und Telefonbuch-Dateien nachgebaut (Fantasienamen).

    Absichtlich Fantasieworte: der Nachweis darf NIE einen Personennamen, eine
    Telefonnummer oder einen Geburtstag zeigen. ``personen_bestaetigt.json`` und
    die Vorgaben liegen in ``personen_gruppen/`` (so schreibt der PC), die
    Profile und das Telefonbuch FLACH (so legt die Uebergabe sie am Handy ab) —
    damit ist der zweite Lesepfad aus ``gruppen_quiz._lesepfad`` mitgeprueft.
    """
    ordner = tmp_path / "personen_gruppen"
    ordner.mkdir(exist_ok=True)
    (ordner / "personen_bestaetigt.json").write_text(json.dumps({"bestaetigt": {
        "Person_1001": "NAME_DARF_NICHT_ERSCHEINEN_A",      # dieselbe Person
        "Person_1002": "NAME_DARF_NICHT_ERSCHEINEN_A",      # an zwei Kennungen
        "Person_9000": "NAME_DARF_NICHT_ERSCHEINEN_B",      # ohne Gruppe
        "Person_1003": "",                                  # ohne Namen
    }}), encoding="utf-8")
    (ordner / "personen_vorgaben.json").write_text(json.dumps({
        "gleich": [["Person_1001", "Person_1002"], ["Person_1001", "Person_9000"]],
        "verschieden": [["Person_1001", "Person_1003"]],
        "ausgeschlossen": [{"kennung": "Person_1001", "bild_id": "1", "index": 0},
                           {"kennung": "Person_1001", "bild_id": "2", "index": 0},
                           {"kennung": "Person_1002", "bild_id": "3", "index": 0}],
    }), encoding="utf-8")
    (tmp_path / "personen_profile.json").write_text(json.dumps({"profile": {
        "NAME_DARF_NICHT_ERSCHEINEN_A": {
            "beziehung": "BEZIEHUNG_DARF_NICHT_ERSCHEINEN",
            "notizen": [{"text": "NOTIZ_DARF_NICHT_ERSCHEINEN"},
                        {"text": "zurueckgenommen", "zurueckgenommen": True}],
            "kontakt": {"id": "1"}},
        "NAME_DARF_NICHT_ERSCHEINEN_B": {},
    }}), encoding="utf-8")
    (tmp_path / "kontakte.json").write_text(json.dumps({
        "stand": "2026-10-02", "quelle": "QUELLE_DARF_NICHT_ERSCHEINEN",
        "kontakte": [{"id": "1", "name": "KONTAKT_DARF_NICHT_ERSCHEINEN",
                      "nummern": ["0176 000000"], "geburtstag": "1990-01-01"},
                     {"id": "2", "name": "KONTAKT_2", "nummern": []}]}), encoding="utf-8")
    (tmp_path / "gruppen_quiz_stand.json").write_text(json.dumps(
        {"spaeter": ["Person_1004"], "unbekannt": ["Person_1005", "Person_1006"]}),
        encoding="utf-8")
    _jsonl(tmp_path / "gruppen_antworten.jsonl", [{"art": "name"}, {"art": "spaeter"}])


def test_nachweis_zaehlt_personen(tmp_path):
    """Die Personen-Stufe stand in KEINEM Nachweis — jetzt wird sie gezaehlt."""
    _bestand(tmp_path)
    _personen(tmp_path)
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert ("Personen (Quiz): personen_bestaetigt.json: 4 Kennungen mit Namen = 2 Personen, "
            "1 ohne Namen; 1 Kennungen ohne Gruppe") in text
    assert "  Vorgaben: gleich 2, verschieden 1, ausgeschlossen 3" in text
    assert ("  Profile (personen_profile.json): 2 Eintraege, davon 1 mit Beziehung, "
            "1 mit Notiz (1 Notizen), 1 mit Telefonbuch-Kontakt") in text
    assert "  Telefonbuch (kontakte.json): 2 Kontakte, davon 1 mit Geburtstag" in text
    assert "  Quiz-Stand: spaeter 1, unbekannt 2; Protokoll 2 Zeilen" in text


def test_nachweis_zeigt_keine_namen_nummern_geburtstage(tmp_path):
    """Nur Zahlen: kein Personenname, keine Nummer, kein Geburtstag, keine Notiz."""
    _bestand(tmp_path)
    _personen(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    for verboten in ("NAME_DARF_NICHT_ERSCHEINEN", "KONTAKT_DARF_NICHT_ERSCHEINEN",
                     "KONTAKT_2", "BEZIEHUNG_DARF_NICHT_ERSCHEINEN",
                     "NOTIZ_DARF_NICHT_ERSCHEINEN", "QUELLE_DARF_NICHT_ERSCHEINEN",
                     "0176", "1990-01-01"):
        assert verboten not in text
    # Der Name ohne Gruppe (Person_9000) ist ein echter Befund, kein stiller Wert.
    assert "personen_bestaetigt.json: 1 Kennungen ohne Gruppe (Namen ohne Gesichter)" in luecken
    # Und eine leere Namen-Datei meldet keine erfundenen Personen.
    (tmp_path / "personen_gruppen" / "personen_bestaetigt.json").write_text(
        json.dumps({"bestaetigt": {}}), encoding="utf-8")
    leer = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert "personen_bestaetigt.json: 0 Kennungen mit Namen = 0 Personen" in leer


def test_nachweis_meldet_fehlende_personen_ehrlich(tmp_path):
    """Fehlt die Namens-Datei, steht das als Luecke — nicht als stiller Nullwert."""
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Personen (Quiz): personen_bestaetigt.json fehlt" in text
    assert "personen_bestaetigt.json fehlt (Personen ohne Namen)" in luecken
    # abschaltbar (z. B. fuer einen Bestand ohne Quiz-Daten)
    assert "Personen (Quiz)" not in "\n".join(bp.pruefen(str(tmp_path), personen=None)[0])


def test_personen_lesen_wirft_bei_kaputter_datei_nicht(tmp_path):
    """Fehlende und kaputte Dateien ergeben ehrliche Zahlen, keinen Wurf."""
    e = bp.personen_lesen(str(tmp_path))
    assert e["fehlt"] is True and e["kennungen"] == 0 and e["personen"] == 0
    assert e["fehlende"] == [bp.STANDARD_PERSONEN]
    ordner = tmp_path / "personen_gruppen"
    ordner.mkdir()
    (ordner / "personen_bestaetigt.json").write_text("{kein json", encoding="utf-8")
    kaputt = bp.personen_lesen(str(tmp_path))
    assert kaputt["fehlt"] is False and kaputt["kaputt"] is True
    assert "\n".join(bp.pruefen(str(tmp_path))[0]).count("nicht lesbar (kein JSON)") == 1
    assert "personen_bestaetigt.json nicht lesbar" in bp.pruefen(str(tmp_path))[1]
    # Nur der Namensteil fehlt: die uebrigen Dateien werden trotzdem gezaehlt.
    (ordner / "personen_bestaetigt.json").write_text(json.dumps({"bestaetigt": {
        "Person_1001": "X", "Person_1001b": "X", "Person_1001c": None}}), encoding="utf-8")
    (tmp_path / "kontakte.json").write_text(json.dumps({"kontakte": "keine Liste"}),
                                            encoding="utf-8")
    e3 = bp.personen_lesen(str(tmp_path))
    assert e3["kennungen"] == 3 and e3["personen"] == 1 and e3["ohne_namen"] == 1
    assert e3["kontakte"] == 0                      # kaputte Liste = 0, kein Wurf
    assert e3["fehlt"] is False                     # die Namen sind ja da


# ── Fotos-Uebersicht fuer die App (N11/N13a) im Nachweis ─────────────────────
# `fotos_uebersicht.json` (Zahlen der App) und `fotos_dateien.json` (Datei-
# Kennungen je Event) leitet das PC-Werkzeug aus `sortierplan.json` ab; gelesen
# werden sie von `services/foto_uebersicht.py` / `services/foto_bilder.py` (App
# und Chat-Werkzeug). Gezaehlt wurden sie bisher NIRGENDS — dieselbe Luecke wie
# bei OSM, Bildindex, Anlaessen, Ortsnamen, Erzaehl-Quellen, Beziehungen und
# Personen.

def _app_dateien(tmp_path, uebersicht_events=2, dateien_events=2, pro_event=3):
    """Die zwei abgeleiteten App-Dateien nachgebaut (Fantasienamen).

    Absichtlich Fantasieworte: der Nachweis darf NIE einen Event-Namen, einen
    Kategorien-Namen, ein Thema oder einen Dateinamen zeigen.
    """
    (tmp_path / "fotos_uebersicht.json").write_text(json.dumps({
        "version": 1, "art": "foto_uebersicht", "stand": "2026-09-27T22:40:09+02:00",
        "zahlen": {"zeilen": 10, "anlaesse": 4, "zuege": dateien_events * pro_event,
                   "events": uebersicht_events},
        "jahre": [2014, 2015], "themen": ["THEMA_DARF_NICHT_ERSCHEINEN"],
        "kategorien": ["KAT_DARF_NICHT_ERSCHEINEN"],
        "events": [{"jahr": 2014, "kategorie": "KAT_DARF_NICHT_ERSCHEINEN",
                    "name": "EVENT_DARF_NICHT_ERSCHEINEN", "dateien": pro_event,
                    "quelle": "neu"}] * uebersicht_events,
    }), encoding="utf-8")
    (tmp_path / "fotos_dateien.json").write_text(json.dumps({
        "art": "foto_dateien", "version": 1, "stand": "2026-09-28T09:44:53+02:00",
        "plan_stand": "2026-09-27T13:49:46",
        "zahlen": {"events": dateien_events, "dateien": dateien_events * pro_event,
                   "ohne_kennung": 0},
        "events": [{"jahr": 2014, "kategorie": "DATEI_KAT_DARF_NICHT_ERSCHEINEN",
                    "event": "DATEI_EVENT_DARF_NICHT_ERSCHEINEN", "anzahl": pro_event,
                    "dateien": [{"datei_id": 111, "name": "DATEINAME_DARF_NICHT_ERSCHEINEN.jpg"},
                                {"datei_id": 222, "name": "b.jpg"},
                                {"datei_id": 333, "name": "c.jpg"}][:pro_event]}]
                   * dateien_events,
    }), encoding="utf-8")


def test_nachweis_zaehlt_app_uebersicht(tmp_path):
    """Die App-Dateien standen in KEINEM Nachweis — jetzt werden sie gezaehlt."""
    _app_dateien(tmp_path)
    text = "\n".join(bp.pruefen(str(tmp_path))[0])
    assert ("Fotos-Uebersicht (App): fotos_uebersicht.json: 2 Events, 2 Jahre, 1 Kategorien, "
            "1 Themen") in text
    assert "  zahlen: 10 zeilen, 4 anlaesse, 6 zuege; Stand 2026-09-27T22:40:09+02:00" in text
    assert ("Datei-Kennungen (App): fotos_dateien.json: 2 Events, 6 Datei-Kennungen, "
            "Summe anzahl 6") in text
    assert ("  zahlen: 2 events, 6 dateien, 0 ohne_kennung; Stand 2026-09-28T09:44:53+02:00; "
            "Plan-Stand 2026-09-27T13:49:46") in text
    assert "  Abgleich: Events 2 / 2; Dateien 6 / 6" in text


def test_nachweis_zeigt_keine_event_namen_und_meldet_abweichung(tmp_path):
    """Nur Zahlen — kein Event-/Kategorien-/Thema-/Dateiname. Abweichung = Luecke."""
    _app_dateien(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    for verboten in ("EVENT_DARF_NICHT_ERSCHEINEN", "KAT_DARF_NICHT_ERSCHEINEN",
                     "THEMA_DARF_NICHT_ERSCHEINEN", "DATEI_EVENT_DARF_NICHT_ERSCHEINEN",
                     "DATEI_KAT_DARF_NICHT_ERSCHEINEN", "DATEINAME_DARF_NICHT_ERSCHEINEN"):
        assert verboten not in text
    # Zwei Event-Zeilen, aber zahlen.events behauptet 99: nicht reproduzierbar.
    _app_dateien(tmp_path, uebersicht_events=2)
    daten = json.loads((tmp_path / "fotos_uebersicht.json").read_text(encoding="utf-8"))
    daten["zahlen"]["events"] = 99
    (tmp_path / "fotos_uebersicht.json").write_text(json.dumps(daten), encoding="utf-8")
    zeilen2, luecken2 = bp.pruefen(str(tmp_path))
    assert "    Abweichung: 2 Event-Zeilen, zahlen.events nennt 99" in "\n".join(zeilen2)
    assert ("fotos_uebersicht.json: 2 Event-Zeilen, zahlen.events 99 (nicht reproduzierbar)"
            in luecken2)
    # Und zwei verschiedene Event-Zahlen der beiden Dateien sind ein Befund.
    _app_dateien(tmp_path, uebersicht_events=2, dateien_events=3)
    _, luecken3 = bp.pruefen(str(tmp_path))
    assert ("App-Uebersicht (2 Events) und Datei-Kennungen (3) passen nicht zusammen"
            in luecken3)


def test_nachweis_meldet_fehlende_app_dateien_ehrlich(tmp_path):
    """Fehlen die App-Dateien, steht das als Luecke — nicht als stiller Nullwert."""
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Fotos-Uebersicht (App): fotos_uebersicht.json fehlt" in text
    assert "fotos_uebersicht.json fehlt (App-Uebersicht nicht abgeleitet)" in luecken
    assert "Datei-Kennungen (App): fotos_dateien.json fehlt" in text
    assert "fotos_dateien.json fehlt (Vorschau ohne Datei-Kennungen)" in luecken
    # abschaltbar (z. B. fuer einen Bestand ohne abgeleitete App-Dateien)
    ohne = "\n".join(bp.pruefen(str(tmp_path), app_uebersicht=None, app_dateien=None)[0])
    assert "Fotos-Uebersicht (App)" not in ohne
    assert "Datei-Kennungen (App)" not in ohne


def test_app_leser_werfen_bei_kaputter_datei_nicht(tmp_path):
    """Fehlende und kaputte Dateien ergeben ehrliche Zahlen, keinen Wurf."""
    e = bp.app_uebersicht_lesen(os.path.join(str(tmp_path), bp.STANDARD_APP_UEBERSICHT))
    assert e["fehlt"] is True and e["events"] == 0 and e["zahlen"] == {}
    d = bp.app_dateien_lesen(os.path.join(str(tmp_path), bp.STANDARD_APP_DATEIEN))
    assert d["fehlt"] is True and d["events"] == 0 and d["datei_eintraege"] == 0
    (tmp_path / "fotos_uebersicht.json").write_text("{kein json", encoding="utf-8")
    (tmp_path / "fotos_dateien.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    kaputt_ue = bp.app_uebersicht_lesen(os.path.join(str(tmp_path), "fotos_uebersicht.json"))
    kaputt_da = bp.app_dateien_lesen(os.path.join(str(tmp_path), "fotos_dateien.json"))
    assert kaputt_ue["fehlt"] is False and kaputt_ue["kaputt"] is True
    assert kaputt_da["fehlt"] is False and kaputt_da["kaputt"] is True
    assert "\n".join(bp.pruefen(str(tmp_path))[0]).count("nicht lesbar (kein JSON)") == 2


# ── Doppelte (pCloud, Pruefsumme) im Nachweis ───────────────────────────────
# `duplikate.json` (`tools/pcloud/pcloud_duplikate.py`) vergleicht die zwei
# pCloud-Baeume ueber die Pruefsumme — die Entscheidungsgrundlage „was ist
# doppelt, was wuerde eine Freigabe bringen?". Sie stand in KEINEM Nachweis
# (dieselbe Luecke wie OSM, Bildindex, Anlaesse, Ortsnamen, Erzaehl-Quellen,
# Beziehungen, Personen und die App-Uebersicht). Faellt sie weg oder halbiert
# sie sich, faellt die Grundlage weg, ohne dass es auffiele.

def _duplikate(tmp_path, abgebrochen=False, abweichung=False):
    """Eine kleine ``duplikate.json`` nachgebaut — mit Fantasienamen.

    Absichtlich Fantasieworte: der Nachweis darf NIE einen Dateinamen, einen Pfad
    oder eine Pruefsumme zeigen. Die Zahlen sind in sich stimmig (2 Gruppen,
    3 betroffene Dateien, 2 Loesch-Kandidaten); ``abweichung`` bricht genau das
    (die Zusammenfassung nennt dann 9 Gruppen, die Liste hat 2).
    """
    datei = {
        "stand": "2026-09-27T22:15:30+02:00", "trocken": True,
        "werkzeug": "tools/pcloud/pcloud_duplikate.py", "tiefe_grenze": 8,
        "baeume": {
            "upload": {"gelesen": True, "name": "BAUM_DARF_NICHT_ERSCHEINEN",
                       "dateien": 100, "ordner_gelesen": 3, "tiefe_erreicht": 2,
                       "abgebrochen": abgebrochen, "offen_gelassen": 4 if abgebrochen else 0,
                       "ohne_hash": 1 if abgebrochen else 0, "ohne_groesse": 0,
                       "ohne_kennung": 0, "kaputte_eintraege": 0},
            "sammlung": {"gelesen": True, "name": "BAUM_DARF_NICHT_ERSCHEINEN",
                         "dateien": 50, "ordner_gelesen": 2, "tiefe_erreicht": 3,
                         "abgebrochen": False, "offen_gelassen": 0, "ohne_hash": 0,
                         "ohne_groesse": 0, "ohne_kennung": 0, "kaputte_eintraege": 0},
        },
        "gruppen": [
            {"size": 9000000, "hash": 12345, "hash_text": "HASH_DARF_NICHT_ERSCHEINEN",
             "anzahl": 2, "art": "ueber_baeume", "baeume": ["upload", "sammlung"],
             "mitglieder": [{"fileid": 1, "name": "DATEINAME_DARF_NICHT_ERSCHEINEN.jpg",
                             "pfad": "/PFAD_DARF_NICHT_ERSCHEINEN"},
                            {"fileid": 2, "name": "DATEINAME_DARF_NICHT_ERSCHEINEN.jpg",
                             "pfad": "/PFAD_DARF_NICHT_ERSCHEINEN"}],
             "loesch_kandidaten": [{"fileid": 1}]},
            {"size": 5000000, "hash": 54321, "hash_text": "HASH_DARF_NICHT_ERSCHEINEN",
             "anzahl": 1, "art": "innerhalb_upload", "baeume": ["upload"],
             "mitglieder": [{"fileid": 3, "name": "DATEINAME_DARF_NICHT_ERSCHEINEN.jpg",
                             "pfad": "/PFAD_DARF_NICHT_ERSCHEINEN"}],
             "loesch_kandidaten": [{"fileid": 3}]},
        ],
        "loesch_kandidaten": {"dateien": 2, "mb": 12.5, "liste": [{"fileid": 1}, {"fileid": 3}]},
        "zusammenfassung": {
            "gescannte_dateien": 150, "vergleichbare_dateien": 150,
            "duplikatgruppen": 2, "betroffene_dateien": 3,
            "mb_alle_kopien": 45.5, "mb_freigabe_kandidaten": 12.5,
            "ueber_baeume": {"gruppen": 1, "dateien": 2, "mb_alle_kopien": 9.0,
                             "mb_freigabe_kandidaten": 4.5},
            "innerhalb": {"upload": {"gruppen": 1, "dateien": 1, "mb_alle_kopien": 5.0,
                                     "mb_freigabe_kandidaten": 5.0},
                          "sammlung": {"gruppen": 0, "dateien": 0, "mb_alle_kopien": 0.0,
                                       "mb_freigabe_kandidaten": 0.0}},
            "loesch_kandidaten": {"dateien": 2, "mb": 12.5},
        },
    }
    if abweichung:
        datei["zusammenfassung"]["duplikatgruppen"] = 9
    (tmp_path / "duplikate.json").write_text(json.dumps(datei), encoding="utf-8")


def test_nachweis_zaehlt_doppelte(tmp_path):
    """Die Duplikat-Pruefung stand in KEINEM Nachweis — jetzt wird sie gezaehlt."""
    _duplikate(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert ("Doppelte (pCloud): duplikate.json: 2 Gruppen, 3 betroffene Dateien, 3 Mitglieder "
            "(innerhalb_upload 1, ueber_baeume 1)") in text
    assert "  Baum sammlung: 50 Dateien in 2 Ordnern gelesen, Tiefe 3" in text
    assert "  Baum upload: 100 Dateien in 3 Ordnern gelesen, Tiefe 2" in text
    assert ("  Zusammenfassung: 150 gescannte_dateien, 150 vergleichbare_dateien, "
            "2 duplikatgruppen, 3 betroffene_dateien") in text
    assert "  Groesse: 45,5 MB in allen Kopien, 12,5 MB Loesch-Kandidaten (2 Dateien)" in text
    assert ("  Ueber Baeume: 1 Gruppen, 2 Dateien; innerhalb je Baum (Gruppen/Dateien): "
            "sammlung 0/0, upload 1/1") in text
    assert ("  Abgleich: Gruppen 2 / 2, Dateien 3 / 3, Kandidaten 2 / 2; "
            "Stand 2026-09-27T22:15:30+02:00; Trockenlauf (es wurde nichts geloescht)") in text
    # Eine stimmige Datei ist kein Befund.
    assert not [l for l in luecken if "duplikate.json" in l]


def test_nachweis_zeigt_keine_dateinamen_und_meldet_abweichung(tmp_path):
    """Nur Zahlen — kein Dateiname, kein Pfad, keine Pruefsumme. Abweichung = Luecke."""
    _duplikate(tmp_path)
    zeilen, _ = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    for verboten in ("DATEINAME_DARF_NICHT_ERSCHEINEN", "PFAD_DARF_NICHT_ERSCHEINEN",
                     "HASH_DARF_NICHT_ERSCHEINEN", "BAUM_DARF_NICHT_ERSCHEINEN"):
        assert verboten not in text
    # Zusammenfassung nennt 9 Gruppen, die Liste hat 2: nicht reproduzierbar.
    _duplikate(tmp_path, abweichung=True)
    _, luecken = bp.pruefen(str(tmp_path))
    assert ("duplikate.json: 2 Gruppen in der Liste, Zusammenfassung nennt 9 "
            "(nicht reproduzierbar)") in luecken
    # Ein abgebrochener Baum und Dateien ohne Pruefsumme sind ehrliche Luecken.
    _duplikate(tmp_path, abgebrochen=True)
    zeilen2, luecken2 = bp.pruefen(str(tmp_path))
    assert ("  Baum upload: 100 Dateien in 3 Ordnern gelesen, Tiefe 2; nicht zu Ende gelesen "
            "(offen 4); 1 ohne Pruefsumme") in "\n".join(zeilen2)
    assert ("duplikate.json: Baum upload nicht zu Ende gelesen (offen 4) - Doppeltenzahl "
            "unvollstaendig") in luecken2
    assert ("duplikate.json: Baum upload 1 Dateien ohne Pruefsumme, Groesse oder Kennung "
            "(nicht vergleichbar)") in luecken2


def test_nachweis_meldet_fehlende_doppelte_ehrlich(tmp_path):
    """Fehlt die Duplikat-Datei, steht das als Luecke — nicht als stiller Nullwert."""
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    assert "Doppelte (pCloud): duplikate.json fehlt" in "\n".join(zeilen)
    assert "duplikate.json fehlt (Doppelte nicht geprueft)" in luecken
    # abschaltbar (z. B. fuer einen Bestand, der nie doppelt geprueft wurde)
    ohne = "\n".join(bp.pruefen(str(tmp_path), duplikate=None)[0])
    assert "Doppelte (pCloud)" not in ohne


def test_duplikate_lesen_wirft_bei_kaputter_datei_nicht(tmp_path):
    """Fehlende und kaputte Dateien ergeben ehrliche Zahlen, keinen Wurf."""
    e = bp.duplikate_lesen(os.path.join(str(tmp_path), bp.STANDARD_DUPLIKATE))
    assert e["fehlt"] is True and e["gruppen"] == 0 and e["baeume"] == {}
    (tmp_path / "duplikate.json").write_text("{kein json", encoding="utf-8")
    kaputt = bp.duplikate_lesen(os.path.join(str(tmp_path), "duplikate.json"))
    assert kaputt["fehlt"] is False and kaputt["kaputt"] is True
    (tmp_path / "duplikate.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    liste = bp.duplikate_lesen(os.path.join(str(tmp_path), "duplikate.json"))
    assert liste["fehlt"] is False and liste["kaputt"] is True
    zeilen, luecken = bp.pruefen(str(tmp_path))
    assert "Doppelte (pCloud): duplikate.json nicht lesbar (kein JSON)" in "\n".join(zeilen)
    assert "duplikate.json nicht lesbar" in luecken


# ── Eigene Erzaehl-Stufen (Schicht "mensch": Geschichten + eigene Titel) ─────

def _erzaehl_mensch(tmp_path, ohne_anlass=False, kaputt=False, ohne_id=False,
                    toter_verweis=False, titel_ohne_kennung=False):
    """Anlass-Bestand + die zwei Dateien, die Sebastian selbst am Geraet fuellt.

    Absichtlich Fantasieworte: der Nachweis darf NIE einen Geschichtentext und
    NIE einen eigenen Titel zeigen. ``ohne_anlass`` laesst beide Dateien auf
    einen Anlass zeigen, den es im Anlass-Bestand nicht gibt; ``toter_verweis``
    bricht die Fassungskette (``ersetzt`` auf eine unbekannte Kennung).
    """
    _jsonl(tmp_path / "ordner_ereignisse.jsonl", [
        {"kennung": "O-100", "datum": "2020-07-01", "datei_kennungen": [1, 2]},
        {"kennung": "O-200", "datum": "2021-08-02", "datei_kennungen": [3]},
    ])
    fremd = "O-FREMD" if ohne_anlass else "O-200"
    geschichten = [
        {"id": "g1", "schicht": "mensch", "ereignis_kennung": "O-100",
         "text": "TEXT_DARF_NICHT_ERSCHEINEN", "quelle": "sprache", "ersetzt": None},
        {"id": "g2", "schicht": "mensch", "ereignis_kennung": "O-100", "datei_kennung": 2,
         "text": "TEXT_DARF_NICHT_ERSCHEINEN", "quelle": "tippen", "ersetzt": "g1"},
        {"id": "g3", "schicht": "mensch", "ereignis_kennung": fremd,
         "text": "TEXT_DARF_NICHT_ERSCHEINEN", "quelle": "import"},
    ]
    if toter_verweis:
        geschichten.append({"id": "g4", "schicht": "mensch", "ereignis_kennung": "O-100",
                            "text": "TEXT_DARF_NICHT_ERSCHEINEN", "quelle": "tippen",
                            "ersetzt": "g-weg"})
    if ohne_id:
        geschichten.append({"schicht": "mensch", "ereignis_kennung": "O-200",
                            "text": "TEXT_DARF_NICHT_ERSCHEINEN"})
    rohdaten = "\n".join(json.dumps(z) for z in geschichten) + "\n"
    (tmp_path / "geschichten.jsonl").write_text(
        rohdaten + ("{kein json\n" if kaputt else ""), encoding="utf-8")
    titel = [
        {"kennung": "O-100", "name": "TITEL_DARF_NICHT_ERSCHEINEN"},
        {"kennung": "O-100", "name": ""},                  # leer = zurueckgesetzt (neueste Zeile)
        {"kennung": "O-200", "name": "TITEL_DARF_NICHT_ERSCHEINEN"},
    ]
    if titel_ohne_kennung:
        titel.append({"name": "TITEL_DARF_NICHT_ERSCHEINEN"})  # ohne Kennung: Name geht verloren
    if ohne_anlass:
        titel.append({"kennung": "O-FREMD", "name": "TITEL_DARF_NICHT_ERSCHEINEN"})
    _jsonl(tmp_path / "anlass_umbenennung.jsonl", titel)


def test_nachweis_zaehlt_erzaehl_mensch(tmp_path):
    """Die eigenen Erzaehl-Stufen standen in KEINEM Nachweis — jetzt werden sie gezaehlt."""
    _erzaehl_mensch(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Eigene Geschichten: geschichten.jsonl: 3 Geschichten, 2 Anlaesse, 1 zu einem Bild" in text
    assert "  Quellen: import 1, sprache 1, tippen 1; 1 abgeloeste Fassungen" in text
    assert ("Eigene Titel: anlass_umbenennung.jsonl: 2 Anlaesse umbenannt (1 mit eigenem Namen, "
            "1 zurueckgesetzt), 1 mit mehreren Zeilen (Fassungen)") in text
    # Eine stimmige Datei ist kein Befund.
    assert not [l for l in luecken
                if "geschichten.jsonl" in l or "anlass_umbenennung.jsonl" in l]


def test_nachweis_zeigt_keine_texte_und_meldet_verwaiste_kennungen(tmp_path):
    """Nur Zahlen — kein Text, kein Titel. Ein Text ohne Anlass ist eine Luecke."""
    _erzaehl_mensch(tmp_path)
    zeilen, _ = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    for verboten in ("TEXT_DARF_NICHT_ERSCHEINEN", "TITEL_DARF_NICHT_ERSCHEINEN"):
        assert verboten not in text
    # Beide Dateien zeigen auf einen Anlass, den es nicht mehr gibt.
    _erzaehl_mensch(tmp_path, ohne_anlass=True)
    _, luecken = bp.pruefen(str(tmp_path))
    assert ("geschichten.jsonl: 1 Geschichten zu einem Anlass, den es nicht mehr gibt "
            "(Text zeigt ins Leere)") in luecken
    assert ("anlass_umbenennung.jsonl: 1 eigene Titel zu einem Anlass, den es nicht mehr gibt "
            "(Name zeigt ins Leere)") in luecken
    # Gebrochene Fassungskette, Zeile ohne Kennung und ein Titel ohne Kennung.
    _erzaehl_mensch(tmp_path, toter_verweis=True, ohne_id=True, kaputt=True,
                    titel_ohne_kennung=True)
    _, luecken2 = bp.pruefen(str(tmp_path))
    assert ("geschichten.jsonl: 1 kaputte Zeilen") in luecken2
    assert ("geschichten.jsonl: 1 Zeilen ohne Kennung (der Dienst verwirft sie still - "
            "die Geschichte fehlt)") in luecken2
    assert ("geschichten.jsonl: 1 ersetzt-Verweise auf eine nicht vorhandene Kennung "
            "(Fassungskette gebrochen)") in luecken2
    assert ("anlass_umbenennung.jsonl: 1 Zeilen ohne brauchbare Kennung "
            "(der eigene Name geht verloren)") in luecken2
    # Eine leere Geschichte zaehlt als eigener Fall.
    _erzaehl_mensch(tmp_path)
    _jsonl(tmp_path / "geschichten.jsonl", [{"id": "g1", "ereignis_kennung": "O-100", "text": " "}])
    _, luecken3 = bp.pruefen(str(tmp_path))
    assert "geschichten.jsonl: 1 leere Geschichten" in luecken3


def test_nachweis_meldet_fehlende_erzaehl_mensch_ehrlich(tmp_path):
    """Am PC noch nicht angelegt heisst 'noch nicht angelegt' — nicht 'Luecke'."""
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert "Eigene Geschichten: geschichten.jsonl noch nicht angelegt" in text
    assert "Eigene Titel: anlass_umbenennung.jsonl noch nicht angelegt" in text
    assert not [l for l in luecken
                if "geschichten.jsonl" in l or "anlass_umbenennung.jsonl" in l]
    ohne = "\n".join(bp.pruefen(str(tmp_path), geschichten=None, titel=None)[0])
    assert "Eigene Geschichten" not in ohne and "Eigene Titel" not in ohne


def test_erzaehl_mensch_leser_werfen_bei_kaputter_datei_nicht(tmp_path):
    """Fehlende und kaputte Dateien ergeben ehrliche Zahlen, keinen Wurf."""
    leer = bp.geschichten_lesen(os.path.join(str(tmp_path), bp.STANDARD_GESCHICHTEN))
    assert leer["fehlt"] is True and leer["eintraege"] == 0
    leer_titel = bp.eigene_titel_lesen(os.path.join(str(tmp_path), bp.STANDARD_TITEL))
    assert leer_titel["fehlt"] is True and leer_titel["kennungen"] == set()
    # Fremde Formen (Liste statt Zeile, kaputtes JSON) zaehlen als kaputt, nie ein Wurf.
    (tmp_path / "geschichten.jsonl").write_text(
        '[1, 2, 3]\n{kein json\n{"id": "g1", "ereignis_kennung": "O-100", "text": "x"}\n',
        encoding="utf-8")
    e = bp.geschichten_lesen(os.path.join(str(tmp_path), "geschichten.jsonl"))
    assert e["fehlt"] is False and e["kaputt_zeilen"] == 2 and e["eintraege"] == 1
    (tmp_path / "anlass_umbenennung.jsonl").write_text('[{"kennung": "O-100"}]\n', encoding="utf-8")
    t = bp.eigene_titel_lesen(os.path.join(str(tmp_path), "anlass_umbenennung.jsonl"))
    assert t["fehlt"] is False and t["kaputt_zeilen"] == 1 and t["kennungen"] == set()


# ── Uebergabe (Handy): Ketten-Schritt 9 ─────────────────────────────────────

def _sha(pfad):
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _uebergabe_manifest(tmp_path, eintraege):
    (tmp_path / bp.STANDARD_UEBERGABE_MANIFEST).write_text(
        "\n".join(json.dumps(z) for z in eintraege) + "\n", encoding="utf-8")


def test_nachweis_zaehlt_die_uebergabe_stufe(tmp_path):
    """Die Uebergabe (Kettenschritt 9) stand in KEINEM Nachweis — jetzt wird sie gezaehlt."""
    _bestand(tmp_path)
    (tmp_path / "orte.jsonl").write_text("eine zeile\n", encoding="utf-8")
    (tmp_path / "bild_index.db").write_bytes(b"frisch")
    _uebergabe_manifest(tmp_path, [
        {"name": "orte.jsonl", "quelle": "C:/irgendwo/orte.jsonl",
         "groesse": (tmp_path / "orte.jsonl").stat().st_size,
         "pruefsumme": _sha(tmp_path / "orte.jsonl")},
        # Zwei Buchungen fuer dieselbe Datei: die JUENGSTE gilt (hier stimmt sie).
        {"name": "bild_index.db", "quelle": "C:/irgendwo/bild_index.db",
         "groesse": 1, "pruefsumme": "veraltet"},
        {"name": "bild_index.db", "quelle": "C:/irgendwo/bild_index.db",
         "groesse": (tmp_path / "bild_index.db").stat().st_size,
         "pruefsumme": _sha(tmp_path / "bild_index.db")},
    ])
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert ("Uebergabe (Handy): uebergabe_manifest.jsonl: 3 Buchungen, 2 verschiedene Dateien "
            "(gleich 2, geaendert 0, am PC fehlt 0)") in text
    # Zwei stimmige Dateien sind kein Befund.
    assert not [l for l in luecken if "uebergabe_manifest" in l]
    # Nur die eigenen Ergebnis-Dateinamen — kein Pfad, kein Inhalt.
    assert "C:/irgendwo" not in text and str(tmp_path) not in text


def test_nachweis_uebergabe_meldet_geaendert_und_fehlend_als_luecke(tmp_path):
    """Eine seit der Uebergabe geaenderte Datei ist der Fehlerfall aus Journal 13."""
    _bestand(tmp_path)
    (tmp_path / "orte.jsonl").write_text("alt\n", encoding="utf-8")
    alte_groesse = (tmp_path / "orte.jsonl").stat().st_size
    alte_summe = _sha(tmp_path / "orte.jsonl")
    (tmp_path / "gleich.jsonl").write_text("gleich\n", encoding="utf-8")
    (tmp_path / "orte.jsonl").write_text("NEU und laenger\n", encoding="utf-8")   # andere Groesse
    _uebergabe_manifest(tmp_path, [
        {"name": "orte.jsonl", "groesse": alte_groesse, "pruefsumme": alte_summe},
        {"name": "weg.jsonl", "groesse": 5, "pruefsumme": "ab" * 32},             # lokal nicht da
        # Gleiche Groesse, andere Pruefsumme: nur der Hash merkt es.
        {"name": "gleich.jsonl",
         "groesse": (tmp_path / "gleich.jsonl").stat().st_size, "pruefsumme": "f" * 64},
    ])
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert ("Uebergabe (Handy): uebergabe_manifest.jsonl: 3 Buchungen, 3 verschiedene Dateien "
            "(gleich 0, geaendert 2, am PC fehlt 1)") in text
    assert ("  Seit der letzten Uebergabe geaendert (2) - das Geraet holt die alte Fassung: "
            "gleich.jsonl, orte.jsonl") in text
    assert "  Am PC nicht mehr vorhanden (1): weg.jsonl" in text
    assert ("uebergabe_manifest.jsonl: 2 Datei(en) seit der letzten Uebergabe geaendert - das "
            "Geraet holt beim naechsten Start die alte Fassung") in luecken
    assert ("uebergabe_manifest.jsonl: 1 uebertragene Datei(en) am PC nicht mehr vorhanden "
            "(Uebergabe nicht nachvollziehbar)") in luecken


def test_nachweis_meldet_fehlende_uebergabe_ehrlich(tmp_path):
    """Ohne Manifest heisst es 'noch nicht angelegt' — nicht 'Luecke'."""
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path))
    text = "\n".join(zeilen)
    assert ("Uebergabe (Handy): uebergabe_manifest.jsonl noch nicht angelegt - es wurde noch "
            "nichts kabellos uebergeben (uebergabe_hochladen.py)") in text
    assert not [l for l in luecken if "uebergabe_manifest" in l]
    ohne = "\n".join(bp.pruefen(str(tmp_path), uebergabe=None)[0])
    assert "Uebergabe (Handy)" not in ohne


def test_uebergabe_stand_leser_wirft_nie_und_juengste_buchung_gilt(tmp_path):
    """Fehlende und kaputte Dateien ergeben ehrliche Zahlen, keinen Wurf."""
    leer = bp.uebergabe_stand_lesen(str(tmp_path))
    assert leer["fehlt"] is True
    (tmp_path / "a.jsonl").write_text("kurz\n", encoding="utf-8")
    groesse = (tmp_path / "a.jsonl").stat().st_size
    alle = ([1, 2],                                              # fremde Form -> kaputt
            "{kein json",                                        # kaputt
            {"name": "", "groesse": 1},                          # ohne Namen -> kaputt
            {"name": "a.jsonl", "groesse": 999, "pruefsumme": "falsch"},   # aeltere Buchung
            {"name": "a.jsonl", "groesse": groesse, "pruefsumme": _sha(tmp_path / "a.jsonl")})
    (tmp_path / "uebergabe_manifest.jsonl").write_text(
        "\n".join(json.dumps(z) for z in alle) + "\n", encoding="utf-8")
    e = bp.uebergabe_stand_lesen(str(tmp_path))
    assert e["fehlt"] is False and e["kaputt"] == 3 and e["buchungen"] == 2
    assert e["gleich"] == ["a.jsonl"] and e["geaendert"] == []   # die juengste Buchung gilt
    assert e["fehlt_lokal"] == [] and e["ohne_pruefsumme"] == []


def _mini_archiv(tmp_path, *, index_nachrichten=None, chunks_mit_vektor=None,
                 waisen=0, fts=None, meta_nachrichten=None, memory_nachrichten=None,
                 vektor_richtig=False, roh_text=None):
    """Ein winziges Chat-Archiv nachbauen: Rohdaten, Index und Textschicht."""
    archiv = tmp_path / "archiv"
    (archiv / "normalized").mkdir(parents=True)
    (archiv / "db").mkdir(parents=True)
    roh = roh_text if roh_text is not None else [
        json.dumps({"source": "whatsapp", "text": "Fantasiewort im Chat"}),
        json.dumps({"source": "whatsapp", "text": "noch eine Nachricht"}),
        json.dumps({"source": "chatgpt", "text": "und noch eine"}),
    ]
    (archiv / "normalized" / "messages.jsonl").write_text("\n".join(roh) + "\n",
                                                          encoding="utf-8")
    n = 3 if index_nachrichten is None else index_nachrichten
    c = 3
    mit = c if chunks_mit_vektor is None else chunks_mit_vektor
    verb = sqlite3.connect(str(archiv / "db" / "archiv_index.db"))
    verb.executescript(
        "CREATE TABLE meta (schluessel TEXT PRIMARY KEY, wert TEXT);"
        "CREATE TABLE gespraeche (conversation_id TEXT PRIMARY KEY, source TEXT);"
        "CREATE TABLE nachrichten (id INTEGER PRIMARY KEY, source TEXT, timestamp TEXT);"
        "CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, hat_vektor INTEGER DEFAULT 1);"
        "CREATE TABLE vektoren (chunk_id INTEGER PRIMARY KEY, dimension INTEGER, modell TEXT);"
        "CREATE TABLE chunks_fts_docsize (id INTEGER PRIMARY KEY);")
    for i in range(1, n + 1):
        verb.execute("INSERT INTO nachrichten (id, source, timestamp) VALUES (?,?,?)",
                     (i, "whatsapp" if i < 3 else "chatgpt",
                      "2026-01-0%dT10:00:00+00:00" % (i % 9 + 1)))
    verb.execute("INSERT INTO gespraeche (conversation_id, source) VALUES (?,?)",
                 ("g1", "whatsapp"))
    for i in range(1, c + 1):
        verb.execute("INSERT INTO chunks (id, source, hat_vektor) VALUES (?,?,?)",
                     (i, "whatsapp" if i < 3 else "chatgpt", 1 if i <= mit else 0))
        if i <= mit:
            verb.execute("INSERT INTO vektoren (chunk_id, dimension, modell) VALUES (?,?,?)",
                         (i, 8, "test-embed"))
    for i in range(waisen):
        verb.execute("INSERT INTO vektoren (chunk_id, dimension, modell) VALUES (?,?,?)",
                     (900 + i, 8, "test-embed"))
    for i in range(1, (c if fts is None else fts) + 1):
        verb.execute("INSERT INTO chunks_fts_docsize (id) VALUES (?)", (i,))
    for k, v in (("nachrichten", str(n if meta_nachrichten is None else meta_nachrichten)),
                 ("chunks", str(c)), ("gespraeche", "1"), ("modell", "test-embed"),
                 ("dimension", "8"), ("gebaut_am", "2026-01-01T10:00:00+00:00"),
                 ("tokens_gezaehlt", "1000"), ("kosten_usd", "0.000001")):
        verb.execute("INSERT INTO meta (schluessel, wert) VALUES (?,?)", (k, v))
    verb.commit()
    verb.close()
    verb = sqlite3.connect(str(archiv / "db" / "memory.db"))
    verb.executescript(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY, source TEXT, text TEXT);"
        "CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, hat_vektor INTEGER DEFAULT 1);"
        "CREATE TABLE index_meta (schluessel TEXT PRIMARY KEY, wert TEXT);")
    for i in range(1, (3 if memory_nachrichten is None else memory_nachrichten) + 1):
        verb.execute("INSERT INTO messages (id, source, text) VALUES (?,?,?)",
                     (i, "whatsapp", "x"))
    for i in range(1, 4):
        verb.execute("INSERT INTO chunks (id, source, hat_vektor) VALUES (?,?,?)",
                     (i, "whatsapp", 1))
    verb.execute("INSERT INTO index_meta (schluessel, wert) VALUES (?,?)",
                 ("modell", "mistral-embed"))
    verb.commit()
    verb.close()
    name = "memory.vektoren.f32" if vektor_richtig else "memory.vektoren [conflicted].f32"
    (archiv / "db" / name).write_bytes(b"\x00" * 16)
    return archiv


def test_nachweis_zaehlt_das_chat_archiv(tmp_path):
    """Das Chat-/WhatsApp-Archiv stand in KEINEM Nachweis — jetzt wird es gezaehlt."""
    _bestand(tmp_path)
    archiv = _mini_archiv(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path), archiv=str(archiv))
    text = "\n".join(zeilen)
    assert "Archiv (Chat/WhatsApp): messages.jsonl: 3 Zeilen - 2 Quellen" in text
    assert "  Quellen: whatsapp 2, chatgpt 1" in text
    assert ("archiv_index.db: 3 Nachrichten, 1 Gespraeche, 3 Chunks, 3 mit Vektor, "
            "3 Vektoren") in text
    assert "Volltextindex: 3 von 3 Chunks indexiert" in text
    assert "Zeitstempel: 0 ohne" in text and "vor 1990: 0" in text
    assert "Rueckfallweg memory.db: 3 Nachrichten, 3 Chunks, davon 3 mit Vektor" in text
    # Nur Zahlen: kein Nachrichtentext, kein Pfad.
    assert "Fantasiewort" not in text and str(tmp_path) not in text
    # Ein stimmiges Archiv ist kein Befund.
    assert not [l for l in luecken if "archiv_index.db" in l or "memory.db" in l]


def test_nachweis_archiv_meldet_abweichungen_als_luecke(tmp_path):
    """Jede stille Abweichung der Archiv-Stufe wird eine Luecke."""
    _bestand(tmp_path)
    archiv = _mini_archiv(tmp_path, index_nachrichten=5, chunks_mit_vektor=1,
                          waisen=2, fts=2, meta_nachrichten=9, memory_nachrichten=4)
    zeilen, luecken = bp.pruefen(str(tmp_path), archiv=str(archiv))
    text = "\n".join(zeilen)
    assert "2 Vektoren ohne Chunk" in text
    assert ("archiv_index.db: 5 Nachrichten gegen 3 Zeilen in messages.jsonl "
            "-> nicht reproduzierbar") in luecken
    assert "archiv_index.db: 2 Chunks ohne Vektor (Bedeutungssuche unvollstaendig)" in luecken
    assert ("archiv_index.db: Vektoren (3) und Chunks mit Vektor (1) passen nicht zusammen "
            "-> nicht reproduzierbar") in luecken
    assert ("archiv_index.db: 1 Chunks nicht im Volltextindex "
            "(Volltextsuche unvollstaendig)") in luecken
    assert ("archiv_index.db: Selbstauskunft weicht von der Zaehlung ab (nachrichten) "
            "-> nicht reproduzierbar") in luecken
    assert ("memory.db: 4 Nachrichten gegen 3 Zeilen in messages.jsonl "
            "-> nicht reproduzierbar") in luecken


def test_nachweis_archiv_fehlend_und_abschaltbar(tmp_path):
    """Fehlender Ordner/Index ist ehrlich eine Luecke; abschaltbar mit archiv=None."""
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path), archiv=str(tmp_path / "gibtsnicht"))
    assert ("Archiv (Chat/WhatsApp): Archivordner nicht gefunden - das Chat-Archiv ist "
            "nicht pruefbar") in zeilen
    assert "Chat-Archiv nicht gefunden (Archiv-Antworten ohne Fundstellen)" in luecken
    ohne = "\n".join(bp.pruefen(str(tmp_path), archiv=None)[0])
    assert "Archiv (Chat/WhatsApp)" not in ohne
    # Ordner da, aber der volle Index fehlt: der Chat sucht nur im alten Weg.
    archiv = _mini_archiv(tmp_path, vektor_richtig=True)
    os.remove(str(archiv / "db" / "archiv_index.db"))
    zeilen3, luecken2 = bp.pruefen(str(tmp_path), archiv=str(archiv))
    assert "archiv_index.db fehlt (Chat-Suche ohne vollen Bestand)" in luecken2
    assert "Vektordatei des Rueckfallwegs (memory.vektoren.f32): vorhanden" in \
        "\n".join(zeilen3)


def test_archiv_leser_werfen_nie(tmp_path):
    """Kaputte Rohdaten, keine brauchbare SQLite-Datei: ehrliche Zahlen, kein Wurf."""
    assert bp.archiv_jsonl_zaehlen(str(tmp_path / "weg.jsonl"))["fehlt"] is True
    assert bp.archiv_index_lesen(str(tmp_path / "weg.db"))["fehlt"] is True
    assert bp.archiv_memory_lesen(str(tmp_path / "weg.db"))["fehlt"] is True
    kaputt = tmp_path / "roh.jsonl"
    kaputt.write_text("\n".join(["Fantasiewort", "[1, 2]",
                                 json.dumps({"text": "ohne Quelle"}),
                                 json.dumps({"source": "whatsapp", "text": "gut"})]) + "\n",
                      encoding="utf-8")
    z = bp.archiv_jsonl_zaehlen(str(kaputt))
    assert z["zeilen"] == 4 and z["kaputt"] == 2 and z["ohne_quelle"] == 1
    assert z["quellen"] == {"whatsapp": 1}
    keine_db = tmp_path / "kein.db"
    keine_db.write_bytes(b"das ist keine SQLite-Datei")
    assert bp.archiv_index_lesen(str(keine_db)).get("nicht_lesbar") is True
    assert bp.archiv_memory_lesen(str(keine_db)).get("nicht_lesbar") is True
    # Leere, aber gueltige DB: keine Tabellen -> ehrlich "nicht lesbar" (keine Nullwerte).
    leer = tmp_path / "leer.db"
    sqlite3.connect(str(leer)).close()
    assert bp.archiv_index_lesen(str(leer)).get("nicht_lesbar") is True
    assert bp.archiv_vektordatei_stand(str(tmp_path))["da"] is False
    archiv = _mini_archiv(tmp_path)
    assert bp.archiv_vektordatei_stand(str(archiv / "db"))["andere"] == 1
    assert bp.archiv_vektordatei_stand(str(tmp_path / "gibtsnicht"))["ordner_fehlt"] is True


# ── 12. Uebergabe-LISTEN: was geht ueberhaupt ans Geraet ─────────────────────

def _mini_projekt(tmp_path, *,
                  script_zeilen=("        --dateien foto_a.json foto_b.json \\",
                                 "        --dateien foto_a.json foto_b.json || true"),
                  app_dateien=(("foto_a.json", "foto_b.json", "geschichten.jsonl"),),
                  script_name="termux/start-vorbereiten.sh"):
    """Ein Mini-Projekt: Startskript mit --dateien-Liste(n) und backend/app."""
    projekt = tmp_path / "projekt"
    if script_zeilen:
        weg = projekt / script_name
        weg.parent.mkdir(parents=True, exist_ok=True)
        weg.write_text("#!/bin/bash\n" + "\n".join(script_zeilen) + "\n", encoding="utf-8")
    for nummer, namen in enumerate(app_dateien):
        ziel = projekt / "backend" / "app" / "services"
        ziel.mkdir(parents=True, exist_ok=True)
        zeilen = [f'DATEI_{i} = "{n}"' for i, n in enumerate(namen)]
        (ziel / f"dienst_{nummer}.py").write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return projekt


def test_uebergabe_listen_zaehlt_namen_und_stellen(tmp_path):
    """Zwei Aufrufstellen derselben Liste werden gelesen und verglichen."""
    projekt = _mini_projekt(tmp_path)
    stand = bp.uebergabe_listen_lesen(str(projekt / "termux" / "start-vorbereiten.sh"))
    assert stand["fehlt"] is False
    assert stand["namen"] == {"foto_a.json", "foto_b.json"}
    assert len(stand["stellen"]) == 2
    assert [z for z, _ in stand["stellen"]] == [2, 3]

    dl = bp.uebergabe_deckung_pruefen(str(projekt), listen=("termux/start-vorbereiten.sh",))
    skript = dl["skripte"][0]
    assert skript["pflicht"] is True and skript["fehlt"] is False
    assert skript["ungleich"] is False and len(skript["namen"]) == 2
    # Beide gelesenen Dateien stehen auf der Liste, die Geraetedatei ist begruendet frei.
    assert dl["ohne_liste"] == set()
    assert dl["geraeteseitig"] == {"geschichten.jsonl"}
    assert dl["ohne_leser"] == set()

    # Eine stimmige Liste ist kein Befund.
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path), projekt=str(projekt),
                                uebergabe_listen=("termux/start-vorbereiten.sh",))
    text = "\n".join(zeilen)
    assert ("Uebergabe-Listen (Deckung): termux/start-vorbereiten.sh: 2 Namen, "
            "2 Stellen (gleich)") in text
    assert "  Dienst liest 3 Datendateinamen; auf einer Liste 2, geraeteseitig 1, ohne Liste 0" in text
    assert not [l for l in luecken if "Uebergabe" in l or "keiner Uebergabe-Liste" in l]


def test_uebergabe_listen_ungleich_und_ohne_liste_sind_luecken(tmp_path):
    """Auseinanderlaufende Stellen und eine ungelistete Datei sind Luecken."""
    projekt = _mini_projekt(
        tmp_path,
        script_zeilen=("        --dateien foto_a.json \\",
                       "        --dateien foto_a.json foto_b.json || true",
                       "        --dateien nur_geliefert.json || true"),
        app_dateien=(("foto_a.json", "foto_b.json", "unbekannt.json"),))
    _bestand(tmp_path)
    zeilen, luecken = bp.pruefen(str(tmp_path), projekt=str(projekt),
                                uebergabe_listen=("termux/start-vorbereiten.sh",))
    text = "\n".join(zeilen)
    assert "3 Stellen (ungleich)" in text
    assert "ohne Liste 1" in text
    # Unbekannt.json liest der Dienst, sie steht auf keiner Liste -> Luecke.
    assert ("unbekannt.json: der Dienst liest sie, sie steht aber auf keiner "
            "Uebergabe-Liste (kommt nie ans Geraet)") in luecken
    assert ("termux/start-vorbereiten.sh: die 3 Aufrufstellen der Uebergabe-Liste "
            "stimmen nicht ueberein") in luecken
    # Geliefert, aber kein Dienst liest sie: eine Zeile, KEINE Luecke.
    assert "Uebergeben, aber von keinem Dienst gelesen (1): nur_geliefert.json" in text
    assert not [l for l in luecken if "nur_geliefert" in l]


def test_uebergabe_listen_fehlend_und_abschaltbar(tmp_path):
    """Fehlende Pflicht-Liste ist eine Luecke; ohne Schalter wird nichts geprueft."""
    _bestand(tmp_path)
    projekt = _mini_projekt(tmp_path, script_zeilen=(), app_dateien=())
    zeilen, luecken = bp.pruefen(str(tmp_path), projekt=str(projekt),
                                uebergabe_listen=bp.STANDARD_UEBERGABE_LISTEN)
    text = "\n".join(zeilen)
    # Die Pflichtliste (der gemeinsame Startweg) fehlt am PC -> Luecke.
    assert ("termux/start-vorbereiten.sh fehlt (die Uebergabe-Liste ist nicht "
            "pruefbar)") in luecken
    # Das alte Skript ist keine Pflicht: es steht als Zeile, nicht als Luecke.
    assert "start-termux.sh: nicht gefunden" in text
    assert not [l for l in luecken if "start-termux.sh" in l or "keine --dateien" in l]
    ohne = "\n".join(bp.pruefen(str(tmp_path), projekt=str(projekt))[0])
    assert "Uebergabe-Listen" not in ohne


def test_uebergabe_listen_leser_werfen_nie_und_nur_namen(tmp_path):
    """Beide Leser sind tolerant; im Bericht stehen nur Namen, kein Pfad."""
    assert bp.uebergabe_listen_lesen(str(tmp_path / "weg.sh"))["fehlt"] is True
    assert bp.dienst_dateinamen(str(tmp_path / "weg")) == {}
    # Platzhalter und Endungs-Reste zaehlen nicht mit.
    projekt = _mini_projekt(
        tmp_path,
        script_zeilen=('        --dateien "$DATEIEN" && echo ".csv" || true',),
        app_dateien=(("Fantasie.json",),))
    # Gueltiges Python mit Platzhalter, Endungs-Rest, Pfad und Leerzeichen.
    (projekt / "backend" / "app" / "roh.py").write_text(
        'A = "$VAR"\nB = ".csv"\nC = "backend/app/x.json"\nD = "mit leer.json"\n',
        encoding="utf-8")
    stand = bp.uebergabe_listen_lesen(str(projekt / "termux" / "start-vorbereiten.sh"))
    assert stand["stellen"] == [(2, [])] and stand["namen"] == set()
    dienst = bp.dienst_dateinamen(str(projekt / "backend" / "app"))
    assert set(dienst) == {"Fantasie.json"}
    assert list(dienst.values())[0].endswith(":1")
    # __pycache__ und kaputte .py-Dateien stoeren nicht.
    ziel = projekt / "backend" / "app" / "__pycache__"
    ziel.mkdir(parents=True, exist_ok=True)
    (ziel / "alt.py").write_text('X = "aus_pycache.json"\n', encoding="utf-8")
    (projekt / "backend" / "app" / "kaputt.py").write_text("def (:\n", encoding="utf-8")
    assert "aus_pycache.json" not in bp.dienst_dateinamen(str(projekt / "backend" / "app"))

    _bestand(tmp_path)
    zeilen, _ = bp.pruefen(str(tmp_path), projekt=str(projekt),
                          uebergabe_listen=("termux/start-vorbereiten.sh",))
    text = "\n".join(zeilen)
    assert "Uebergabe-Listen (Deckung)" in text
    # Im Bericht stehen nur Zahlen und Dateinamen — kein Pfad, keine .py-Datei.
    block = "\n".join(z for z in zeilen if "Uebergabe-Listen" in z
                      or z.startswith(("  Dienst liest", "  Auf keiner Liste", "  Uebergeben")))
    assert str(tmp_path) not in block and "backend" not in block and ".py" not in block
