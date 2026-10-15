"""Tests für Tooltip, Menü- und Hinweistexte sowie die Einstellungen."""
import json
from datetime import datetime, timezone

import pytest

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


# --- v0.2: Master, Lage, Schwelle --------------------------------------------

from master_schalter.zustand import Zustand  # noqa: E402


def test_tooltip_beginnt_mit_master_und_lage():
    text = anzeige.tooltip([_k("Claude", 62, 80), _k("Codex", 1.0, 32.0)], kopf=anzeige.tooltip_kopf("claude", "1"))
    assert text == "M Claude L1 | Claude 5h 62% · Wo 80% | Codex 5h 1% · Wo 32%"
    assert len(text) <= 127


def test_tooltip_kopf_ohne_master_und_lage():
    assert anzeige.tooltip_kopf(None, None) == "M – L?"
    assert anzeige.tooltip_kopf("codex", "2B") == "M Codex L2B"


def test_tooltip_mit_kopf_bleibt_hoechstens_127_zeichen():
    lang = Kontingent("Claude", fehler="x" * 300)
    text = anzeige.tooltip([lang, lang], kopf=anzeige.tooltip_kopf("claude", "3"))
    assert len(text) <= 127 and text.startswith("M Claude L3 | ")


def test_master_menuezeile():
    z = Zustand("claude", datetime(2026, 10, 14, 19, 50, tzinfo=UTC).isoformat(), None)
    assert anzeige.master_menuezeile(z, zone=UTC) == "Master: Claude (seit 14.10. 19:50)"
    assert anzeige.master_menuezeile(Zustand(None, None, None)) == "Master: nicht gesetzt"
    assert anzeige.master_menuezeile(Zustand("codex", "kaputt", None)) == "Master: Codex"


def test_lage_zeilen_bekannt_nennt_besetzung():
    zeilen = anzeige.lage_zeilen("2A", "")
    assert zeilen[0].startswith("Lage 2A")
    text = "\n".join(zeilen)
    assert "Thinker" in text and "GPT-6 Sol" in text and "DeepSeek V4.1 Flash" in text and "Worker" in text


def test_lage_zeilen_unbekannt_nennt_grund():
    assert anzeige.lage_zeilen(None, "Codex 5h nach Reset noch nicht neu gemessen") == [
        "Lage ? – Codex 5h nach Reset noch nicht neu gemessen"]


def test_master_status_zeile():
    assert anzeige.master_status_zeile(Zustand("claude", None, None), "1", "") == "Master: Claude · Lage 1"
    assert anzeige.master_status_zeile(Zustand(None, None, None), None, "Claude keine Daten") == \
        "Master: nicht gesetzt · Lage ? – Claude keine Daten"


def test_schwelle_setzen_roundtrip_und_andere_felder_bleiben(tmp_path):
    datei = tmp_path / "einstellungen.json"
    datei.write_text(json.dumps({"schwelle": 97, "claude_takt_min": 5, "x": [1, 2]}), encoding="utf-8")
    anzeige.schwelle_setzen(90, datei)
    assert anzeige.schwelle(datei) == 90
    roh = json.loads(datei.read_text(encoding="utf-8"))
    assert roh == {"schwelle": 90, "claude_takt_min": 5, "x": [1, 2]}


def test_schwelle_setzen_ohne_datei_legt_sie_an(tmp_path):
    datei = tmp_path / "neu" / "einstellungen.json"
    anzeige.schwelle_setzen(80, datei)
    assert anzeige.schwelle(datei) == 80
    assert [p.name for p in datei.parent.iterdir()] == ["einstellungen.json"]


def test_schwelle_setzen_lehnt_ungueltig_ab(tmp_path):
    datei = tmp_path / "einstellungen.json"
    anzeige.schwelle_setzen(95, datei)
    for schlecht in (0, 101, -5, "90", 90.5, True, None):
        with pytest.raises(ValueError):
            anzeige.schwelle_setzen(schlecht, datei)
    assert anzeige.schwelle(datei) == 95


def test_schwelle_setzen_ueber_kaputte_datei(tmp_path):
    datei = tmp_path / "einstellungen.json"
    datei.write_text("{kaputt", encoding="utf-8")
    anzeige.schwelle_setzen(90, datei)
    assert anzeige.schwelle(datei) == 90


def test_schwellen_auswahl_wie_im_plan():
    assert anzeige.SCHWELLEN == (80, 90, 95, 97, 100)


def test_wechsel_hinweis_texte(tmp_path):
    from master_schalter.wechsel import Ergebnis
    paket = tmp_path / "2026-10-14_215007_masterwechsel-claude-codex.md"
    text = anzeige.wechsel_hinweis(Ergebnis("gewechselt", "codex", paket, ""))
    assert text == f"Master jetzt Codex – Übergabe: {paket.name}. Im Codex-Chat lesen lassen."
    assert anzeige.wechsel_hinweis(Ergebnis("gleich", "codex", None, "")) == "Master ist schon Codex."
    assert anzeige.wechsel_hinweis(Ergebnis("fehler", "codex", None, "Sperre belegt")) == \
        "Wechsel fehlgeschlagen: Sperre belegt"
    assert len(anzeige.wechsel_hinweis(Ergebnis("fehler", "codex", None, "x" * 500))) <= 255


def test_claude_takt_min_standard_und_auswahl(tmp_path):
    datei = tmp_path / "einstellungen.json"
    assert anzeige.claude_takt_min(datei) == 1

    anzeige.claude_takt_setzen(15, datei)

    assert anzeige.claude_takt_min(datei) == 15
    assert json.loads(datei.read_text(encoding="utf-8")) == {"claude_takt_min": 15}


@pytest.mark.parametrize("wert", [0, 61, True, 1.5, "5"])
def test_claude_takt_min_ungueltige_werte_standardisieren_und_setzen_verwerfen(tmp_path, wert):
    datei = tmp_path / "einstellungen.json"
    datei.write_text(json.dumps({"claude_takt_min": wert}), encoding="utf-8")

    assert anzeige.claude_takt_min(datei) == 1
    with pytest.raises(ValueError):
        anzeige.claude_takt_setzen(wert, datei)
