"""Pruefungen fuer ``anlass_namen.py`` (N-0929 Schritt 4).

Alles OHNE Netz, ohne Bild und mit erfundenen Daten (Orte/Handordner frei
erfunden, Kennungen sind Zaehler).

Aufruf:
    cd backend && .venv/Scripts/python -m pytest tests/test_anlass_namen.py -q
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WERKZEUG = REPO / "tools" / "foto_sortierung" / "anlass_namen.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    assert spez is not None and spez.loader is not None
    modul = importlib.util.module_from_spec(spez)
    spez.loader.exec_module(modul)
    return modul


an = _laden(WERKZEUG, "anlass_namen")
D = "–"          # Halbgeviertstrich

STAND = "2026-09-29T12:00:00Z"


def _schreibe(pfad: Path, zeilen) -> Path:
    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
        for z in zeilen:
            f.write((z if isinstance(z, str) else json.dumps(z)) + "\n")
    return pfad


def ereignis(nr, bilder, thema="Urlaub", datum="2022-06-10", jahr=2022):
    return {"kennung": f"E-a{nr}", "anlass_id": f"a{nr}", "datei_kennungen": list(bilder),
            "datum": datum, "jahr": jahr, "thema": thema}


def ort(bild, ort_="Beispielstadt", region="Beispielregion", land="Italien", code="IT",
        aufnahme="2022-06-12T10:00:00"):
    return {"bild_id": str(bild), "ort": ort_, "region": region, "land": land,
            "land_code": code, "aufnahme": aufnahme}


def lauf(tmp_path, ereignisse, orte=None, hand=None):
    e = _schreibe(tmp_path / "ereignisse.jsonl", ereignisse)
    o = _schreibe(tmp_path / "orte.jsonl", orte) if orte is not None else tmp_path / "fehlt_orte.jsonl"
    h = _schreibe(tmp_path / "hand.jsonl", hand) if hand is not None else tmp_path / "fehlt_hand.jsonl"
    zeilen, zahlen = an.namen_ableiten(str(e), str(o), str(h), stand=STAND)
    return {z["kennung"]: z for z in zeilen}, zahlen


# ── Regeln ───────────────────────────────────────────────────────────────

def test_regel_ort_mit_zeitraum_und_thema(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [1, 2, 3])],
                [ort(1, "Musterburg"), ort(2, "Musterburg"), ort(3, "Nachbardorf")])
    e = z["E-a1"]
    assert e["regel"] == "ort"
    assert e["vorschlag"] == f"Musterburg, Juni 2022 {D} Urlaub"
    assert e["ort_anteil"] == pytest.approx(0.667, abs=0.001)
    assert e["version"] == 1 and e["erzeugt"] == STAND


def test_regel_region_bei_drei_orten(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [1, 2, 3, 4])],
                [ort(1, "Alpha", region="Toskana"), ort(2, "Beta", region="Toskana"),
                 ort(3, "Gamma", region="Toskana"), ort(4, "Gamma", region="Toskana")])
    e = z["E-a1"]
    assert e["regel"] == "region"
    assert e["vorschlag"].startswith("Toskana, Juni 2022")
    assert e["ort_anteil"] == 1.0


def test_zwei_orte_bleiben_ort(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [1, 2, 3])],
                [ort(1, "Alpha", region="Toskana"), ort(2, "Beta", region="Toskana"),
                 ort(3, "Beta", region="Toskana")])
    assert z["E-a1"]["regel"] == "ort"
    assert z["E-a1"]["vorschlag"].startswith("Beta,")


def test_regel_land_bei_drei_orten_ueber_regionen(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [1, 2, 3])],
                [ort(1, "Alpha", region="R1"), ort(2, "Beta", region="R2"),
                 ort(3, "Gamma", region="R3")])
    e = z["E-a1"]
    assert e["regel"] == "land"
    assert e["vorschlag"].startswith("Italien, Juni 2022")


def test_regel_handordner_und_prioritaet_vor_ort(tmp_path):
    hand = [{"bild_id": str(i), "handordner": "Konzerte_Party/2016"} for i in (1, 2)]
    z, _ = lauf(tmp_path, [ereignis(1, [1, 2, 3], thema="Konzert")],
                [ort(1, "Musterburg"), ort(2, "Musterburg"), ort(3, "Musterburg")], hand)
    e = z["E-a1"]
    assert e["regel"] == "handordner"
    assert e["vorschlag"] == f"Konzerte Party, 2016 {D} Konzert"
    assert "Musterburg" not in e["vorschlag"]
    assert e["ort_anteil"] == pytest.approx(0.667, abs=0.001)


def test_handordner_ohne_mehrheit_faellt_auf_ort(tmp_path):
    hand = [{"bild_id": "1", "handordner": "Urlaub_X"}]      # 1 von 3: keine Mehrheit
    z, _ = lauf(tmp_path, [ereignis(1, [1, 2, 3])],
                [ort(1, "Musterburg"), ort(2, "Musterburg"), ort(3, "Musterburg")], hand)
    assert z["E-a1"]["regel"] == "ort"


def test_handordner_ohne_jahr_nutzt_errechneten_zeitraum(tmp_path):
    hand = [{"bild_id": "1", "handordner": "Freunde\\Grillabend"}]
    z, _ = lauf(tmp_path, [ereignis(1, [1], thema="Sonstiges")],
                [ort(1, "Musterburg")], hand)
    assert z["E-a1"]["vorschlag"] == "Grillabend, Juni 2022"


def test_regel_nur_zeit_ist_ehrlicher_rueckfall(tmp_path):
    z, zahlen = lauf(tmp_path, [ereignis(1, [1, 2], datum="2019-03-05", jahr=2019)], [])
    e = z["E-a1"]
    assert e["regel"] == "nur_zeit"
    assert e["vorschlag"] == f"März 2019 {D} Urlaub"
    assert e["ort_anteil"] == 0.0
    assert e["reise"] is False and e["heimat_verdacht"] is False
    assert zahlen["ohne_ort"] == 1


def test_ohne_alle_angaben(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [], thema="Sonstiges", datum="", jahr=None)])
    assert z["E-a1"]["regel"] == "nur_zeit"
    assert z["E-a1"]["vorschlag"] == "Anlass ohne Angaben"


def test_fehlende_orte_datei_ist_kein_fehler(tmp_path):
    z, zahlen = lauf(tmp_path, [ereignis(1, [1])])
    assert zahlen["orte_vorhanden"] is False
    assert z["E-a1"]["vorschlag"] == f"Juni 2022 {D} Urlaub"


def test_sonstiges_entfaellt_auch_in_anderer_schreibweise(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [1], thema="sonstiges"), ereignis(2, [2], thema="")],
                [ort(1, "Musterburg"), ort(2, "Musterburg")])
    assert z["E-a1"]["vorschlag"] == "Musterburg, Juni 2022"
    assert z["E-a2"]["vorschlag"] == "Musterburg, Juni 2022"


# ── Zeitraum ─────────────────────────────────────────────────────────────

def test_zeitraum_formate():
    f = an.zeitraum_text
    assert f([(2022, 6), (2022, 6)]) == "Juni 2022"
    assert f([(2014, 7), (2014, 8)]) == f"Juli{D}August 2014"
    assert f([(2013, 12), (2014, 1)]) == f"Dezember 2013{D}Januar 2014"
    assert f([]) == ""
    assert f([], 2020) == "2020"


def test_zeitraum_aus_aufnahmedaten_ueber_monatsgrenze(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [1, 2])],
                [ort(1, aufnahme="2014-07-30T09:00:00"), ort(2, aufnahme="2014-08-02T09:00:00")])
    assert f", Juli{D}August 2014" in z["E-a1"]["vorschlag"]


def test_zeitraum_ueber_jahresgrenze(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [1, 2])],
                [ort(1, aufnahme="2013-12-30T09:00:00"), ort(2, aufnahme="2014-01-02T09:00:00")])
    assert f"Dezember 2013{D}Januar 2014" in z["E-a1"]["vorschlag"]


def test_unlesbare_aufnahme_faellt_auf_datum_zurueck(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [1], datum="2021-11-05")],
                [ort(1, aufnahme="kaputt")])
    assert "November 2021" in z["E-a1"]["vorschlag"]


# ── Heimat / Reise ───────────────────────────────────────────────────────

def test_heimat_erkennung_und_reise(tmp_path):
    ereignisse = [ereignis(1, [1, 2, 3]), ereignis(2, [4, 5]), ereignis(3, [6])]
    orte = [ort(i, "Heimatstadt", "H", "Deutschland", "DE") for i in (1, 2, 3, 4)] + \
           [ort(5, "Heimatstadt", "H", "Deutschland", "DE"),
            ort(6, "Fernort", "F", "Daenemark", "DK")]
    z, zahlen = lauf(tmp_path, ereignisse, orte)
    assert z["E-a1"]["heimat_verdacht"] is True and z["E-a1"]["reise"] is False
    assert z["E-a2"]["heimat_verdacht"] is True and z["E-a2"]["reise"] is False
    assert z["E-a3"]["heimat_verdacht"] is False and z["E-a3"]["reise"] is True
    assert zahlen["reisen"] == 1 and zahlen["heimat"] == 2


def test_gleicher_ortsname_in_anderem_land_ist_nicht_heimat(tmp_path):
    ereignisse = [ereignis(1, [1, 2]), ereignis(2, [3])]
    orte = [ort(1, "Neustadt", "A", "Deutschland", "DE"), ort(2, "Neustadt", "A", "Deutschland", "DE"),
            ort(3, "Neustadt", "B", "Oesterreich", "AT")]
    z, _ = lauf(tmp_path, ereignisse, orte)
    assert z["E-a2"]["heimat_verdacht"] is False and z["E-a2"]["reise"] is True


# ── Ableitung: nichts veraendern, atomar, Trockenlauf ────────────────────

def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _dateien(tmp_path):
    e = _schreibe(tmp_path / "ereignisse.jsonl",
                  [ereignis(1, [1, 2]), ereignis(2, [3], thema="Sonstiges")])
    o = _schreibe(tmp_path / "orte.jsonl", [ort(1, "Musterburg"), ort(2, "Musterburg"), ort(3, "Fernort")])
    return e, o


def test_ereignisse_bleiben_byte_gleich_und_trockenlauf_schreibt_nichts(tmp_path):
    e, o = _dateien(tmp_path)
    vorher = _sha(e)
    ziel = tmp_path / "aus" / "namen.jsonl"
    argv = ["--ereignisse", str(e), "--orte", str(o), "--ausgabe", str(ziel), "--stand", STAND]
    assert an.haupt(argv) == 0                    # Trockenlauf ist Standard
    assert not ziel.exists()
    assert an.haupt(argv + ["--trocken"]) == 0
    assert not ziel.exists()
    assert an.haupt(argv + ["--schreiben"]) == 0
    assert ziel.exists()
    assert _sha(e) == vorher
    assert sorted(p.name for p in ziel.parent.iterdir()) == ["namen.jsonl"]   # keine temp-Reste


def test_schreiben_komplett_neu_und_idempotent(tmp_path):
    e, o = _dateien(tmp_path)
    ziel = tmp_path / "namen.jsonl"
    ziel.write_text("ALTER INHALT\n", encoding="utf-8")
    argv = ["--ereignisse", str(e), "--orte", str(o), "--ausgabe", str(ziel),
            "--stand", STAND, "--schreiben"]
    an.haupt(argv)
    erste = ziel.read_bytes()
    assert b"ALTER" not in erste
    zeilen = [json.loads(z) for z in erste.decode("utf-8").splitlines()]
    assert [z["kennung"] for z in zeilen] == ["E-a1", "E-a2"]
    assert set(zeilen[0]) == {"kennung", "vorschlag", "regel", "ort_anteil",
                              "heimat_verdacht", "reise", "version", "erzeugt"}
    an.haupt(argv)
    assert ziel.read_bytes() == erste
    assert erste.isascii()                        # ensure_ascii, Umlaute/Strich escaped


def test_konsole_zeigt_nur_zaehler_keine_namen(tmp_path, capsys):
    e, o = _dateien(tmp_path)
    an.haupt(["--ereignisse", str(e), "--orte", str(o),
              "--ausgabe", str(tmp_path / "n.jsonl"), "--schreiben"])
    aus = capsys.readouterr().out
    assert "Musterburg" not in aus and "Fernort" not in aus and "Urlaub" not in aus
    assert "Reisen:" in aus and "ohne Ort:" in aus and "Regel ort:" in aus


# ── Schutz und Fehler ────────────────────────────────────────────────────

def test_repo_pfad_als_ausgabe_ist_exit_2(tmp_path):
    e, o = _dateien(tmp_path)
    with pytest.raises(SystemExit) as exc:
        an.haupt(["--ereignisse", str(e), "--orte", str(o),
                  "--ausgabe", str(REPO / "anlass_namen_test.jsonl"), "--schreiben"])
    assert exc.value.code == 2
    assert not (REPO / "anlass_namen_test.jsonl").exists()


def test_ausgabe_gleich_eingabe_ist_exit_2(tmp_path):
    e, o = _dateien(tmp_path)
    vorher = _sha(e)
    with pytest.raises(SystemExit) as exc:
        an.haupt(["--ereignisse", str(e), "--orte", str(o), "--ausgabe", str(e), "--schreiben"])
    assert exc.value.code == 2
    assert _sha(e) == vorher


def test_fehlende_ereignisdatei_ist_exit_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        an.haupt(["--ereignisse", str(tmp_path / "gibt_es_nicht.jsonl"),
                  "--ausgabe", str(tmp_path / "n.jsonl")])
    assert exc.value.code == 2


def test_kaputte_zeilen_werden_gezaehlt(tmp_path):
    e = _schreibe(tmp_path / "e.jsonl", [ereignis(1, [1]), "{kaputt", "[1,2]",
                                          {"thema": "ohne Kennung"}])
    o = _schreibe(tmp_path / "o.jsonl", [ort(1, "Musterburg"), "nicht json", {"ort": "ohne bild"}])
    h = _schreibe(tmp_path / "h.jsonl", ["{{", {"bild_id": "1"}, {"bild_id": "1", "handordner": "X_Y"}])
    zeilen, zahlen = an.namen_ableiten(str(e), str(o), str(h), stand=STAND)
    assert len(zeilen) == 1
    assert zahlen["kaputt_ereignisse"] == 3
    assert zahlen["kaputt_orte"] == 2
    assert zahlen["kaputt_handordner"] == 2
    assert zeilen[0]["regel"] == "handordner"


def test_doppelte_datei_kennungen_und_zahlen_als_kennung(tmp_path):
    z, _ = lauf(tmp_path, [ereignis(1, [1, 1, 2.0, True, None])],
                [ort(1, "Musterburg"), ort(2, "Musterburg")])
    assert z["E-a1"]["ort_anteil"] == 1.0


def test_handordner_zerlegen():
    assert an.handordner_zerlegen("Konzerte_Party/2016") == ("Konzerte Party", 2016)
    assert an.handordner_zerlegen("2016") == (None, 2016)
    assert an.handordner_zerlegen("A/B_C/") == ("B C", None)
    assert an.handordner_zerlegen("") == (None, None)
