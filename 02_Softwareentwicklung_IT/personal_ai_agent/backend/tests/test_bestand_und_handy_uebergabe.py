"""Tests: Bestandspruefung (nur Zahlen) und Gruppen-Uebergabe per Kabel (01.10.2026).

Offline, erfundene Dateien in tmp_path, nachgebautes adb.

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_bestand_und_handy_uebergabe.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os

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
