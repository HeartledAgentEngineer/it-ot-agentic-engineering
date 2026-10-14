"""Tests für Tooltip, Menü- und Hinweistexte sowie die Einstellungen."""
import json
from datetime import datetime, timezone

from master_schalter import anzeige
from master_schalter.signale import Fenster, Kontingent

UTC = timezone.utc
STAND = datetime(2026, 10, 14, 16, 5, tzinfo=UTC)
RESET = datetime(2026, 10, 14, 18, 40, tzinfo=UTC)


def _k(master, fuenf, woche, **kw):
    return Kontingent(master, (Fenster("5h", fuenf, RESET), Fenster("Woche", woche, RESET)), stand=STAND, **kw)


def test_tooltip_zeigt_beide_master_kurz():
    text = anzeige.tooltip([_k("Claude", 79, 58.4), _k("Codex", 1.0, 32.0)])
    assert text == "Claude 5h 79% · Wo 58% | Codex 5h 1% · Wo 32%"


def test_tooltip_hoechstens_127_zeichen():
    lang = Kontingent("Claude", fehler="x" * 300)
    assert len(anzeige.tooltip([lang, lang])) <= 127


def test_tooltip_ohne_daten_und_fehlende_werte():
    text = anzeige.tooltip([Kontingent("Claude", fehler="keine Daten"), _k("Codex", None, 3)])
    assert text == "Claude: keine Daten | Codex 5h – · Wo 3%"


def test_details_mit_reset_und_stand():
    zeilen = anzeige.details([_k("Claude", 79, 58)], zone=UTC)
    assert zeilen == [
        "Claude",
        "  5h: 79 % · Reset 14.10. 18:40",
        "  Woche: 58 % · Reset 14.10. 18:40",
        "  Stand: 14.10. 16:05",
    ]


def test_details_zurueckgesetzt_und_fehler():
    k = Kontingent("Codex", (Fenster("5h", 0.0, RESET, zurueckgesetzt=True),), stand=STAND)
    zeilen = anzeige.details([k, Kontingent("Claude", fehler="keine Daten")], zone=UTC)
    assert "  5h: zurückgesetzt (seit 14.10. 18:40)" in zeilen
    assert zeilen[-2:] == ["Claude", "  keine Daten"]


def test_hinweis_fuer_benachrichtigung_kurz():
    text = anzeige.hinweis([_k("Claude", 79, 58), _k("Codex", 1, 32)], zone=UTC)
    assert text.splitlines()[0] == "Claude: 5h 79 % · Woche 58 % (Stand 14.10. 16:05)"
    assert len(text) <= 255


def test_stufe():
    assert anzeige.stufe(None, 97) == "unbekannt"
    assert anzeige.stufe(50, 97) == "ok"
    assert anzeige.stufe(85, 97) == "warn"
    assert anzeige.stufe(97, 97) == "voll"


def test_schwelle_standard_und_datei(tmp_path):
    datei = tmp_path / "einstellungen.json"
    assert anzeige.schwelle(datei) == 97
    datei.write_text(json.dumps({"schwelle": 90}), encoding="utf-8")
    assert anzeige.schwelle(datei) == 90
    for schlecht in ('{"schwelle": 0}', '{"schwelle": 101}', '{"schwelle": "hoch"}', "{kaputt", "[]"):
        datei.write_text(schlecht, encoding="utf-8")
        assert anzeige.schwelle(datei) == 97
