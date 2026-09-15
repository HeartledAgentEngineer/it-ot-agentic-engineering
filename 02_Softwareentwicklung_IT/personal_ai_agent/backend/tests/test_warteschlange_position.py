"""Tests: sichtbare Warteschlange der Inbox-Auftraege (Coding-Chat).

Fund 2026-09-15 (Sebastian): „ich schreibe, es reagiert nicht / haengt".
Ursache: Der Inbox-Daemon arbeitet die Auftraege streng NACHEINANDER ab; ein
zweiter Auftrag wartet also, bis der erste fertig ist. Das Frontend zeigte nur
„🔁 uebernommen … bearbeitet" — ohne Zahl davor war nicht erkennbar, ob etwas
haengt oder ob nur gewartet wird.

`_warteschlange_davor()` zaehlt die noch unbeantworteten Auftraege VOR dem
eigenen; `_warteschlange_text()` macht daraus eine ehrliche Chat-Meldung.
"""
import json
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

from app.services.hermes_local import (  # noqa: E402
    _warteschlange_davor,
    _warteschlange_text,
)


def _dateien(tmp_path, auftraege, antworten=()):
    a = tmp_path / "auftraege.jsonl"
    b = tmp_path / "antworten.jsonl"
    a.write_text(
        "".join(json.dumps({"auftrag_id": x, "text": "t"}) + "\n" for x in auftraege),
        encoding="utf-8",
    )
    b.write_text(
        "".join(json.dumps({"auftrag_id": x, "text": "a"}) + "\n" for x in antworten),
        encoding="utf-8",
    )
    return str(a), str(b)


def test_erster_auftrag_hat_niemanden_davor(tmp_path):
    a, b = _dateien(tmp_path, ["aaa"])
    assert _warteschlange_davor(a, b, "aaa") == 0


def test_zweiter_auftrag_wartet_auf_den_ersten(tmp_path):
    a, b = _dateien(tmp_path, ["aaa", "bbb"])
    assert _warteschlange_davor(a, b, "bbb") == 1


def test_spaeter_kommender_wartet_auf_zwei(tmp_path):
    a, b = _dateien(tmp_path, ["aaa", "bbb", "ccc"])
    assert _warteschlange_davor(a, b, "ccc") == 2


def test_beantwortete_auftraege_zaehlen_nicht(tmp_path):
    """Der erste ist fertig, also ist der zweite jetzt dran."""
    a, b = _dateien(tmp_path, ["aaa", "bbb"], antworten=["aaa"])
    assert _warteschlange_davor(a, b, "bbb") == 0


def test_auftraege_nach_uns_zaehlen_nicht(tmp_path):
    """Nur was VOR uns steht, verzoegert uns."""
    a, b = _dateien(tmp_path, ["aaa", "bbb", "ccc"], antworten=["aaa"])
    assert _warteschlange_davor(a, b, "bbb") == 0
    assert _warteschlange_davor(a, b, "ccc") == 1


def test_unbekannte_id_und_fehlende_dateien_sind_harmlos(tmp_path):
    a, b = _dateien(tmp_path, ["aaa"])
    assert _warteschlange_davor(a, b, "gibtsnicht") == 0
    assert _warteschlange_davor(str(tmp_path / "leer.jsonl"), b, "aaa") == 0
    assert _warteschlange_davor("", "", "aaa") == 0


def test_kaputte_zeilen_brechen_die_zaehlung_nicht(tmp_path):
    a = tmp_path / "auftraege.jsonl"
    b = tmp_path / "antworten.jsonl"
    a.write_text(
        "kein json\n" + json.dumps({"auftrag_id": "aaa"}) + "\n"
        + json.dumps({"auftrag_id": "bbb"}) + "\n",
        encoding="utf-8",
    )
    b.write_text("", encoding="utf-8")
    assert _warteschlange_davor(str(a), str(b), "bbb") == 1


def test_texte_sind_ehrlich_und_deutsch():
    """Die Meldung sagt, dass gewartet wird — und dass es kein Haenger ist."""
    text_wartend = _warteschlange_text(3)
    assert "3" in text_wartend
    assert "nacheinander" in text_wartend
    assert "kein Haenger" in text_wartend
    assert _warteschlange_text(1).count("1 Auftrag davor") == 1
    jetzt = _warteschlange_text(0)
    assert "Jetzt dran" in jetzt