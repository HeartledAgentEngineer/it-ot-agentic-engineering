"""Pruefungen fuer ``tools/foto_sortierung/gesicht_lernt_mit_wege_messen.py``.

Aufruf::

    cd backend && .venv/Scripts/python.exe -m pytest tests/test_gesicht_lernt_mit_wege_messen.py -q

Zwei Sorten Pruefungen:
* **Gegen den echten Code** — die tragenden Stellen (die Korrektur wird als
  Referenz eingebettet; der Mittelpunkt entsteht nur im PC-Lauf aus den festen
  Zuordnungen; das Geraet rechnet keinen Mittelpunkt nach) werden an den echten
  Dateien gemessen. Damit bricht der Test, wenn sich der Code aendert, und nicht
  erst der Bericht.
* **An erfundenen Mini-Dateien** — Zaehlung, fehlende/kaputte Dateien, ehrliche
  Grenze, keine Namen im Bericht.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
PROJEKT = BACKEND.parent
QUELLE = PROJEKT / "tools" / "foto_sortierung" / "gesicht_lernt_mit_wege_messen.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spez)
    sys.modules[name] = modul
    spez.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def mess():
    assert QUELLE.is_file(), f"Werkzeug fehlt: {QUELLE}"
    return _laden(QUELLE, "gesicht_lernt_mit_wege_messen")


# ── gegen den echten Code ──────────────────────────────────────────────────

def test_referenz_weg_ist_belegt(mess):
    """Der Gesichter-Weg bettet die Korrektur ein und speichert sie als Referenz."""
    belege = mess.referenz_weg()
    assert belege["da"]
    for feld in ("antwort_dienst", "bbox_fallback", "neue_referenz", "schwelle",
                 "speichern", "katalog_datei", "person_speichern", "atomar"):
        stelle = belege[feld]
        assert stelle is not None, f"Code-Stelle fehlt: {feld}"
        assert stelle[1] > 0 and stelle[0].endswith(".py")
    text = "\n".join(mess.referenz_weg_bericht(belege))
    assert "gesicht_quiz.py:" in text and "gesichter_service.py:" in text
    assert "REFERENZVEKTOR" in text
    assert "Achtung" not in text


def test_gruppen_weg_ist_belegt(mess):
    """Die feste Zuordnung ist der einzige Weg zum Mittelpunkt — belegt am echten Code."""
    belege = mess.gruppen_weg()
    assert belege["da"]
    for feld in ("zuordnen", "schreibt_zugeordnet", "schreibt_vorgaben", "aufloesen",
                 "liest_fest", "vorbilder", "fixiert", "startgruppen", "gruppieren_v2"):
        assert belege[feld] is not None, f"Code-Stelle fehlt: {feld}"
    text = "\n".join(mess.gruppen_weg_bericht(belege))
    assert "gruppen_quiz.py:" in text and "personen_gruppieren.py:" in text
    assert "Vorbild-Gruppen starten mit ihrem Mittelpunkt" in text
    assert "Achtung" not in text


def test_luecke_ist_gemessen(mess):
    """Zwei Nullen mit Bedeutung — und der Suchbegriff greift wirklich."""
    belege = mess.luecke()
    assert belege["da"]
    assert belege["pc_liest_katalog"] == 0, "der PC-Gruppenlauf liest den Geraete-Katalog"
    assert sum(belege["geraet_mittelpunkt"].values()) == 0
    # Der Suchbegriff ist nicht einfach unauffindbar: im PC-Werkzeug findet er etwas.
    assert belege["pc_mittelpunkt"] > 0
    text = "\n".join(mess.luecke_bericht(belege))
    assert "GENAU 0x" in text
    assert "0 Mittelpunkt-Stellen im Geraete-Code" in text
    assert "Gegenprobe" in text and "Achtung" not in text


def test_gegenprobe_ein_treffer_kippt_das_urteil(mess, tmp_path):
    """Damit die Nullaussage etwas bedeutet: ein echter Treffer wird gemeldet."""
    gesicht = tmp_path / "gesicht_quiz.py"
    gruppen = tmp_path / "gruppen_quiz.py"
    werkzeug = tmp_path / "personen_gruppieren.py"
    gesicht.write_text("# ohne Treffer\n", encoding="utf-8")
    gruppen.write_text("def zuordnen():\n    mittelpunkt = 1\n", encoding="utf-8")
    werkzeug.write_text("# liest gesichter_katalog\n", encoding="utf-8")
    belege = mess.luecke(gruppieren=werkzeug, gruppen=gruppen, gesicht=gesicht)
    assert sum(belege["geraet_mittelpunkt"].values()) == 1
    assert belege["pc_liest_katalog"] == 1
    text = "\n".join(mess.luecke_bericht(belege))
    assert "Achtung" in text and "GENAU 0x" not in text


# ── an erfundenen Mini-Dateien ─────────────────────────────────────────────

def _schreibe(pfad: Path, inhalt) -> Path:
    pfad.write_text(json.dumps(inhalt), encoding="utf-8")
    return pfad


def test_zaehlt_die_vier_vorgabe_regeln(mess, tmp_path):
    _schreibe(tmp_path / mess.VORGABEN, {
        "zugeordnet": [{"bild_id": "1", "index": 0, "name": "A"},
                       {"bild_id": "2", "index": 1, "name": "B"}],
        "ausgeschlossen": [{"kennung": "x"}],
        "gleich": [[1, 2]],
        "verschieden": [[3, 4], [5, 6]],
    })
    _schreibe(tmp_path / mess.BESTAETIGT, {"bestaetigt": {"G-1": "A", "G-2": "B"}})
    text = "\n".join(mess.bestand_bericht(tmp_path))
    assert "zugeordnet: 2" in text and "ausgeschlossen: 1" in text
    assert "gleich: 1" in text and "verschieden: 2" in text
    assert "Summe 6" in text
    assert "feste Einzelzuordnungen (zugeordnet): 0" not in text


def test_ohne_feste_zuordnung_steht_das_ausdruecklich_da(mess, tmp_path):
    _schreibe(tmp_path / mess.VORGABEN, {"ausgeschlossen": [{"kennung": "x"}]})
    text = "\n".join(mess.bestand_bericht(tmp_path))
    assert "zugeordnet: 0" in text
    assert "feste Einzelzuordnungen (zugeordnet): 0" in text


def test_gruppendateien_werden_gezaehlt(mess, tmp_path):
    ordner = tmp_path / mess.GRUPPEN_ORDNER
    ordner.mkdir()
    (ordner / mess.ZUORDNUNG).write_text('{"kennung": "P_1"}\n{"kennung": "P_2"}\n',
                                         encoding="utf-8")
    _schreibe(ordner / mess.KENNUNGEN, {"stand": "x", "kennungen": [1, 2, 3]})
    text = "\n".join(mess.bestand_bericht(tmp_path))
    assert "gesicht_zuordnung.jsonl: 2 Zeilen" in text
    assert "kennungen.json: 3 Kennungen" in text


def test_fehlende_datei_wird_ehrlich_gemeldet(mess, tmp_path):
    text = "\n".join(mess.bestand_bericht(tmp_path))
    assert "NICHT messbar" in text and "NICHT zaehlbar" in text
    assert "gesichter_katalog.json liegt am PC nicht vor" in text
    zahlen = mess.json_zaehlen(tmp_path / "gibtsnicht.json")
    assert zahlen["fehlt"] is True and zahlen["listen"] == {}
    assert mess.jsonl_zeilen(tmp_path / "gibtsnicht.jsonl")["fehlt"] is True


def test_kaputte_datei_wird_gemeldet_statt_geworfen(mess, tmp_path):
    (tmp_path / mess.VORGABEN).write_text("{kein json", encoding="utf-8")
    zahlen = mess.json_zaehlen(tmp_path / mess.VORGABEN)
    assert zahlen["kaputt"] is True and zahlen["fehlt"] is False
    text = "\n".join(mess.bestand_bericht(tmp_path))
    assert "nicht lesbar" in text


def test_leerer_katalog_ist_die_ehrliche_grenze(mess, tmp_path):
    (tmp_path / mess.KATALOG).write_text('{"personen": []}', encoding="utf-8")
    text = "\n".join(mess.bestand_bericht(tmp_path))
    assert "leere Huelle" in text
    assert "liegt am PC nicht vor" not in text


def test_keine_personennamen_im_bericht(mess, tmp_path):
    _schreibe(tmp_path / mess.VORGABEN, {
        "zugeordnet": [{"bild_id": "1", "index": 0, "name": "ErfundenePersonXyz"}],
        "ausgeschlossen": [], "gleich": [], "verschieden": [],
    })
    _schreibe(tmp_path / mess.BESTAETIGT, {"bestaetigt": {"G-1": "ErfundenePersonXyz"}})
    (tmp_path / mess.KATALOG).write_text('{"personen": [{"name": "ErfundenePersonXyz"}]}',
                                         encoding="utf-8")
    assert "ErfundenePersonXyz" not in "\n".join(mess.bestand_bericht(tmp_path))
    assert "ErfundenePersonXyz" not in "\n".join(mess.bericht(tmp_path))


def test_bericht_hat_alle_vier_abschnitte(mess, tmp_path):
    text = "\n".join(mess.bericht(tmp_path))
    for ueberschrift in ("1. Referenzvektor (Geraet, Gesichter-Weg)",
                         "2. Gruppenmittelpunkt (PC, naechster Gruppenlauf)",
                         "3. Die Luecke dazwischen",
                         "4. Zahlen am echten Bestand"):
        assert ueberschrift in text
    assert "POST /api/gruppen/zuordnen" in text


def test_werkzeug_schreibt_nichts(mess):
    """Nur-Lese-Zusage im Quelltext: keine Schreib-Oeffnung, kein Netz, kein Prozess."""
    quelle = QUELLE.read_text(encoding="utf-8")
    for verboten in ('open(pfad, "w"', "open(pfad, 'w'", '"w", encoding', "'w', encoding",
                     "requests.", "urllib", "subprocess", "shutil"):
        assert verboten not in quelle, f"Schreib-/Netz- oder Prozessaufruf gefunden: {verboten}"
    # Ein echtes Schreiben waere "os.replace(" ohne Suchmuster-Kennzeichnung.
    assert "os.replace(" not in quelle
    assert "os\\.replace\\(" in quelle        # nur als Suchmuster fuer die Messung


def test_kommandozeile_ist_gruen(mess, tmp_path):
    assert mess.main(["--daten-dir", str(tmp_path)]) == 0
