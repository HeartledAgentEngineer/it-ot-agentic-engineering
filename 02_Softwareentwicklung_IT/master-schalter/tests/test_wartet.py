"""Tests für „Wartet worauf“ (`wartet.py`, `masterwechsel warte`, Anzeige in `kurz`)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import cli, kurz, wartet
from master_schalter.signale import Fenster, Kontingent

JETZT = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    return tmp_path / "daten"


def test_setzen_und_lesen(daten):
    wartet.setzen("master-schalter", "Freigabe Vibe-Modus", jetzt=JETZT)
    [m] = wartet.alle_lesen()
    assert (m.thema, m.text, m.zeit) == ("master-schalter", "Freigabe Vibe-Modus", JETZT)
    assert (daten / "wartet" / "master-schalter.json").is_file()


def test_text_wird_eine_zeile_und_begrenzt():
    assert wartet.text_bereinigen("  Codex-Prüfung\nR2\t läuft\x07 ") == "Codex-Prüfung R2 läuft"
    lang = wartet.text_bereinigen("x" * 300)
    assert len(lang) == wartet.MAX_ZEICHEN and lang.endswith("…")


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_leerer_text_ist_fehler(daten, text):
    with pytest.raises(wartet.WartetFehler):
        wartet.setzen("master-schalter", text)
    assert wartet.alle_lesen() == []


@pytest.mark.parametrize("thema", ["../x", "Groß", "a/b", ""])
def test_unzulaessiges_thema(daten, thema):
    with pytest.raises(wartet.WartetFehler):
        wartet.setzen(thema, "Text")


def test_loeschen_ist_idempotent(daten):
    wartet.setzen("t1", "Text")
    assert wartet.loeschen("t1") is True
    assert wartet.loeschen("t1") is False
    assert wartet.alle_lesen() == []


def test_kaputte_und_zu_grosse_dateien_werden_uebersprungen(daten):
    wartet.setzen("gut", "Text", jetzt=JETZT)
    (daten / "wartet" / "kaputt.json").write_text("{kein json", encoding="utf-8")
    (daten / "wartet" / "gross.json").write_text('{"text": "' + "x" * 2000 + '", "zeit": "2026-10-28T00:00:00+00:00"}',
                                                  encoding="utf-8")
    (daten / "wartet" / "ohnezeit.json").write_text('{"text": "x"}', encoding="utf-8")
    assert [m.thema for m in wartet.alle_lesen()] == ["gut"]
    assert (daten / "wartet" / "kaputt.json").is_file()      # nichts wird aufgeräumt oder geraten


def test_alle_lesen_ohne_ordner_ist_leer(daten):
    assert wartet.alle_lesen() == [] and not (daten / "wartet").exists()


def test_cli_warte_setzen_und_fertig(daten, capsys):
    assert cli.main(["warte", "master-schalter", "Freigabe", "Vibe-Modus"]) == 0
    assert "wartet auf „Freigabe Vibe-Modus“" in capsys.readouterr().out
    assert cli.main(["warte", "master-schalter", "--fertig"]) == 0
    assert "entfernt" in capsys.readouterr().out
    assert cli.main(["warte", "master-schalter", "--fertig"]) == 0
    assert "keine Wartemeldung" in capsys.readouterr().out


def test_cli_warte_fehler_ohne_nebenwirkung(daten, capsys):
    assert cli.main(["warte", "master-schalter"]) == 1
    assert "Text ist leer" in capsys.readouterr().err
    assert cli.main(["warte", "../x", "Text"]) == 1
    assert cli.main(["warte", "master-schalter", "Text", "--fertig"]) == 1
    assert "nimmt keinen Text" in capsys.readouterr().err
    assert wartet.alle_lesen() == []


def _k(name):
    return Kontingent(name, (Fenster("5h", 10.0, JETZT + timedelta(hours=2)),
                             Fenster("Woche", 20.0, JETZT + timedelta(days=3))), JETZT - timedelta(minutes=5))


def test_kurz_zeigt_meldungen_aelteste_zuerst_und_veraltet():
    neu = wartet.Meldung("b", "Codex-Prüfung R2", JETZT - timedelta(minutes=5))
    alt = wartet.Meldung("a", "Freigabe Vibe-Modus", JETZT - timedelta(hours=30))
    text = kurz.zeilen([_k("Claude"), _k("Codex")], [], [], schwelle=95, automatik_global=True, jetzt=JETZT,
                       zone=timezone.utc, wartet_auf=(neu, alt))
    warte = [z for z in text if z.startswith("Wartet worauf:")]
    assert warte == ["Wartet worauf: a: Freigabe Vibe-Modus (seit 27.10. 06:00) (veraltet?)",
                     "Wartet worauf: b: Codex-Prüfung R2 (seit 11:55)"]


def test_kurz_ohne_meldung():
    text = kurz.zeilen([_k("Claude"), _k("Codex")], [], [], schwelle=95, automatik_global=True, jetzt=JETZT,
                       zone=timezone.utc)
    assert text[-1] == kurz.WARTET == "Wartet worauf: nichts gemeldet"


def test_sammeln_liest_wartemeldungen(daten, monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    wartet.setzen("master-schalter", "Freigabe Vibe-Modus")
    assert any(z.startswith("Wartet worauf: master-schalter: Freigabe Vibe-Modus") for z in kurz.sammeln())
