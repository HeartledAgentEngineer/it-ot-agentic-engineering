"""Pruefungen fuer ``tools/foto_sortierung/gesicht_referenz_wege_messen.py``.

Aufruf::

    cd backend && .venv/Scripts/python.exe -m pytest tests/test_gesicht_referenz_wege_messen.py -q

Zwei Sorten Pruefungen:
* **Gegen den echten Code** — die tragenden Stellen (Geraet rechnet selbst, der
  Gesichter-Weg bettet ein, der Gruppen-Weg nicht) werden an den echten Dateien
  gemessen, nicht an Attrappen. Damit bricht der Test, wenn sich der Code
  aendert, und nicht erst der Bericht.
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
QUELLE = PROJEKT / "tools" / "foto_sortierung" / "gesicht_referenz_wege_messen.py"


def _laden(pfad: Path, name: str):
    spez = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spez)
    sys.modules[name] = modul
    spez.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def mess():
    assert QUELLE.is_file(), f"Werkzeug fehlt: {QUELLE}"
    return _laden(QUELLE, "gesicht_referenz_wege_messen")


# ── gegen den echten Code ──────────────────────────────────────────────────

def test_vektor_rechner_ist_belegt(mess):
    """Das Geraet rechnet die Einbettung selbst — mit Datei:Zeile."""
    belege = mess.vektor_rechner()
    assert belege["service_da"] and belege["infer_da"]
    for feld in ("skript", "aufruf", "ping", "embed_bbox", "embed_crop_aufruf",
                 "op_embed", "op_embed_crop", "verteiler"):
        stelle = belege[feld]
        assert stelle is not None, f"Code-Stelle fehlt: {feld}"
        assert stelle[1] > 0 and stelle[0].endswith(".py")
    text = "\n".join(mess.vektor_rechner_bericht(belege))
    assert "Ja — die Einbettung rechnet das Geraet selbst" in text
    assert "face_service.py:" in text and "face_infer.py:" in text


def test_gesichter_weg_erzeugt_eine_referenz(mess):
    """Der Editor speichert ueber den Gesichter-Weg — der bettet den Rahmen ein."""
    stellen = mess.speicherwege()
    text = "\n".join(mess.speicherwege_bericht(stellen))
    assert "POST /api/gesichter/quiz/antwort" in text
    assert "gesicht_quiz.py:667" in text                      # beantworte_runde
    # Der Hinweistext der App ist eine echte Code-Stelle, keine Erfindung.
    # Seit Schritt A2 (16.10.2026) nennt der Hinweis zuerst den Grund und dann
    # den Weg zur Person; der Anker wurde am 16.10. nachgezogen.
    assert "dann speichert 💾 den Rahmen." in (PROJEKT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "dann speichert 💾 den Rahmen." in QUELLE.read_text(encoding="utf-8")


def test_gruppen_weg_traegt_keinen_vektor(mess):
    """Gegenprobe: der Namensweg hat im echten Code kein embedding/vektor."""
    belege = mess.gruppen_weg()
    assert belege["da"]
    assert belege["vektor_vorkommen"] == 0
    text = "\n".join(mess.gruppen_weg_bericht(belege))
    assert "0 Vorkommen von embedding/vektor" in text
    assert "POST /api/gruppen/antwort" in text


# ── an erfundenen Mini-Dateien ─────────────────────────────────────────────

def _schreibe(pfad: Path, inhalt) -> Path:
    pfad.write_text(json.dumps(inhalt), encoding="utf-8")
    return pfad


def test_zaehlt_benennungs_dateien_ohne_vektor(mess, tmp_path):
    _schreibe(tmp_path / mess.BESTAETIGT, {"bestaetigt": {"G-1": "A", "G-2": "B"}})
    _schreibe(tmp_path / mess.VORGABEN, {"gleich": [[1, 2]], "verschieden": [[3, 4]],
                                         "ausgeschlossen": [{"kennung": "x"}]})
    text = "\n".join(mess.dateien_bericht(tmp_path))
    assert "bestaetigt: 2" in text and "gleich: 1" in text and "verschieden: 1" in text
    assert "ausgeschlossen: 1" in text
    assert "0 Vektor-Schluessel" in text or "Vektor-Schluessel: keine (0)" in text


def test_gegenprobe_ein_vektor_schluessel_wird_gefunden(mess, tmp_path):
    """Damit die Nullaussage etwas bedeutet: ein echter Vektor wird gemeldet."""
    _schreibe(tmp_path / mess.BESTAETIGT, {"bestaetigt": {"G-1": {"embedding": [0.1, 0.2]}}})
    _schreibe(tmp_path / mess.VORGABEN, {"gleich": [], "verschieden": [], "ausgeschlossen": []})
    text = "\n".join(mess.dateien_bericht(tmp_path))
    assert "embedding" in text
    assert "Vektoren vorhanden" in text


def test_fehlende_datei_wird_ehrlich_gemeldet(mess, tmp_path):
    text = "\n".join(mess.dateien_bericht(tmp_path))
    assert "fehlt am PC" in text
    assert "NICHT zaehlbar am PC" in text          # Katalog fehlt hier ebenfalls
    zahlen = mess.datei_zaehlen(tmp_path / "gibtsnicht.json")
    assert zahlen["fehlt"] is True and zahlen["eintraege"] == 0


def test_kaputte_datei_wird_gemeldet_statt_geworfen(mess, tmp_path):
    (tmp_path / mess.BESTAETIGT).write_text("{kein json", encoding="utf-8")
    zahlen = mess.datei_zaehlen(tmp_path / mess.BESTAETIGT)
    assert zahlen["kaputt"] is True and zahlen["fehlt"] is False
    text = "\n".join(mess.dateien_bericht(tmp_path))
    assert "nicht lesbar" in text


def test_leerer_katalog_ist_die_ehrliche_grenze(mess, tmp_path):
    (tmp_path / mess.KATALOG).write_text('{"personen": []}', encoding="utf-8")
    text = "\n".join(mess.dateien_bericht(tmp_path))
    assert "leere Huelle" in text
    assert "NICHT zaehlbar am PC" not in text      # der Katalog liegt vor, nur leer


def test_keine_personennamen_im_bericht(mess, tmp_path):
    _schreibe(tmp_path / mess.BESTAETIGT, {"bestaetigt": {"G-1": "ErfundenePersonXyz"}})
    _schreibe(tmp_path / mess.VORGABEN, {"gleich": [["ErfundenePersonXyz"]], "verschieden": [],
                                         "ausgeschlossen": []})
    (tmp_path / mess.KATALOG).write_text('{"personen": [{"name": "ErfundenePersonXyz"}]}',
                                         encoding="utf-8")
    text = "\n".join(mess.dateien_bericht(tmp_path))
    assert "ErfundenePersonXyz" not in text


def test_bericht_hat_alle_vier_abschnitte(mess, tmp_path):
    zeilen = mess.bericht(tmp_path)
    text = "\n".join(zeilen)
    for ueberschrift in ("Kann das Geraet Gesichtsvektoren selbst rechnen?",
                         "Erzeugt „Benennen/Speichern im Detailbild“ eine Referenz?",
                         "Derselbe Nachweis fuer den Namensweg",
                         "Dateien des Benennens"):
        assert ueberschrift in text


def test_werkzeug_schreibt_nichts(mess):
    """Nur-Lese-Zusage im Quelltext: keine Schreib-Oeffnung, kein Netzzugriff."""
    quelle = QUELLE.read_text(encoding="utf-8")
    for verboten in ("open(pfad, \"w\"", "open(pfad, 'w'", '"w", encoding', "'w', encoding",
                     "requests.", "urllib", "subprocess"):
        assert verboten not in quelle, f"Schreib-/Netz- oder Prozessaufruf gefunden: {verboten}"
    assert "os.replace" not in quelle


def test_kommandozeile_ist_gruen(mess, tmp_path):
    assert mess.main(["--daten-dir", str(tmp_path)]) == 0
