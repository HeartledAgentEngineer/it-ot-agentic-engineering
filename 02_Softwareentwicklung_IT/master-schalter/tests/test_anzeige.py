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
    assert anzeige.tooltip_kopf("hermes", "3") == "M Hermes L3"


def test_tooltip_mit_kopf_bleibt_hoechstens_127_zeichen():
    lang = Kontingent("Claude", fehler="x" * 300)
    text = anzeige.tooltip([lang, lang], kopf=anzeige.tooltip_kopf("claude", "3"))
    assert len(text) <= 127 and text.startswith("M Claude L3 | ")


def test_master_menuezeile():
    z = Zustand("claude", datetime(2026, 10, 14, 19, 50, tzinfo=UTC).isoformat(), None)
    assert anzeige.master_menuezeile(z, zone=UTC) == "Master: Claude (seit 14.10. 19:50)"
    assert anzeige.master_menuezeile(Zustand(None, None, None)) == "Master: nicht gesetzt"
    assert anzeige.master_menuezeile(Zustand("codex", "kaputt", None)) == "Master: Codex"
    assert anzeige.master_menuezeile(Zustand("hermes", datetime(2026, 10, 15, 12, 25, tzinfo=UTC).isoformat(), None), zone=UTC) == "Master: Hermes (seit 15.10. 12:25)"


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
    assert anzeige.master_status_zeile(Zustand("hermes", None, None), "3", "") == "Master: Hermes · Lage 3"


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
    assert text == f"Standard-Master jetzt Codex. Technisches Übergabepaket: {paket.name}. Geschützte Hermes-Themen bleiben unverändert."
    assert anzeige.wechsel_hinweis(Ergebnis("gleich", "codex", None, "")) == "Standard-Master ist schon Codex."
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


def test_details_ohne_resetzeit_laesst_reset_text_weg():
    k = Kontingent("Claude", (Fenster("5h", 0.0, None), Fenster("Woche", 40.0, RESET)), stand=STAND)
    zeilen = anzeige.details([k], zone=UTC)
    fuenf = next(z for z in zeilen if z.strip().startswith("5h:"))
    woche = next(z for z in zeilen if z.strip().startswith("Woche:"))
    assert "Reset" not in fuenf
    assert "Reset" in woche


# --- Rollen je Thema, Menüeinträge und Katalogstände (v0.4.0) ------------------

from master_schalter import modi  # noqa: E402
from master_schalter.anzeige import Katalogstand, Rollenstand  # noqa: E402


def _stand(master="kontingent", worker="workflow", modell=None, kataloge=()):
    return Rollenstand(master, worker, modell, tuple(kataloge))


def _katalog(provider="codex", *eintraege, fehler=None, veraltet=False):
    return Katalogstand(provider, tuple((kennung, name) for kennung, name in eintraege),
                        None, fehler, veraltet)


def test_rollenauswahl_entspricht_den_planlabels():
    assert anzeige.MASTER_AUSWAHL == (("Nach Kontingent", "kontingent"), ("Claude Code", "claude"),
                                      ("Codex", "codex"), ("Hermes", "hermes"))
    assert anzeige.WORKER_AUSWAHL == (("Nach Workflow", "workflow"), ("Claude Code", "claude"),
                                      ("Codex", "codex"), ("Hermes", "hermes"))
    assert anzeige.MODELLE_AKTUALISIEREN == "Modelle aktualisieren"
    assert anzeige.STANDARD_MODELL == "Standard des Werkzeugs"


@pytest.mark.parametrize("master", ["kontingent", "claude", "codex", "hermes"])
def test_master_eintraege_haken_genau_eine_wahl(master):
    eintraege = anzeige.master_eintraege(_stand(master=master))

    assert [e.text for e in eintraege] == ["Nach Kontingent", "Claude Code", "Codex", "Hermes"]
    assert all(e.aktiv and not e.hinweis for e in eintraege)
    assert [e.wert for e in eintraege if e.haken] == [master]


@pytest.mark.parametrize("worker", ["workflow", "claude", "codex", "hermes"])
def test_worker_eintraege_haken_genau_eine_wahl_und_zeigen_die_vorgabe(worker):
    eintraege = anzeige.worker_eintraege(_stand(worker=worker))
    wahl = [e for e in eintraege if e.aktiv]

    assert [e.text for e in wahl] == ["Nach Workflow", "Claude Code", "Codex", "Hermes"]
    assert [e.wert for e in wahl if e.haken] == [worker]
    hinweise = [e.text for e in eintraege if e.hinweis]
    assert any("Ausführervorgabe" in text for text in hinweise)     # ausdrücklich Vorgabe, keine Sitzung
    assert any("OpenRouter" in text and "kostenpflichtig" in text for text in hinweise)  # Provider immer sichtbar


def test_modell_eintraege_workflow_nur_deaktivierter_hinweis():
    eintraege = anzeige.modell_eintraege(_stand(worker="workflow"))

    assert len(eintraege) == 1
    assert eintraege[0].hinweis and not eintraege[0].aktiv and "Workflow" in eintraege[0].text


def test_modell_eintraege_hermes_genau_die_feste_kennung():
    eintraege = anzeige.modell_eintraege(_stand(worker="hermes", modell=modi.HERMES_MODELL))
    wahl = [e for e in eintraege if e.aktiv]

    assert [e.text for e in wahl] == ["DeepSeek V4.1 Flash"]
    assert wahl[0].wert == modi.HERMES_MODELL and wahl[0].haken
    assert any("OpenRouter" in e.text and "kostenpflichtig" in e.text for e in eintraege if e.hinweis)


def test_modell_eintraege_dynamische_namen_und_gesetztes_haken():
    eintraege = anzeige.modell_eintraege(_stand(
        worker="codex", modell="gpt-6-luna",
        kataloge=[_katalog("codex", ("gpt-6-luna", "GPT-6 Luna"), ("gpt-6-sol", "GPT-6 Sol"))]))

    assert [e.text for e in eintraege if e.aktiv] == ["GPT-6 Luna", "GPT-6 Sol"]
    assert [e.wert for e in eintraege if e.haken] == ["gpt-6-luna"]
    assert not any(e.text == anzeige.STANDARD_MODELL for e in eintraege)   # gespeichertes Modell steht


def test_modell_eintraege_standard_ist_bewusst_waehlbar():
    eintraege = anzeige.modell_eintraege(_stand(
        worker="claude", modell=None, kataloge=[_katalog("claude", ("opus", "Opus"))]))
    standard = next(e for e in eintraege if e.text == anzeige.STANDARD_MODELL)

    assert standard.aktiv and standard.wert is None and standard.haken
    assert [e.wert for e in eintraege if e.aktiv] == ["opus", None]


def test_modell_eintraege_veralteter_katalog_sperrt_die_neuauswahl():
    eintraege = anzeige.modell_eintraege(_stand(
        worker="codex", modell="gpt-6-luna",
        kataloge=[_katalog("codex", ("gpt-6-luna", "GPT-6 Luna"), veraltet=True)]))

    assert any("veraltet" in e.text for e in eintraege if e.hinweis)
    assert not any(e.aktiv for e in eintraege if e.wert is not None)


def test_modell_eintraege_katalogfehler_wird_genannt():
    eintraege = anzeige.modell_eintraege(_stand(
        worker="codex", kataloge=[_katalog("codex", ("gpt-6-luna", "GPT-6 Luna"),
                                           fehler="Zeitüberschreitung")]))

    assert any("Zeitüberschreitung" in e.text for e in eintraege if e.hinweis)
    assert not any(e.aktiv for e in eintraege if e.wert is not None)


def test_modell_eintraege_fehlender_katalog_nennt_modelle_aktualisieren():
    eintraege = anzeige.modell_eintraege(_stand(worker="codex"))

    assert any(anzeige.MODELLE_AKTUALISIEREN in e.text for e in eintraege if e.hinweis)
    assert not any(e.aktiv and e.wert is not None for e in eintraege)


def test_modell_eintraege_gespeichertes_nicht_bestaetigtes_modell_nach_refresh():
    eintraege = anzeige.modell_eintraege(_stand(
        worker="codex", modell="gpt-6-alt",
        kataloge=[_katalog("codex", ("gpt-6-luna", "GPT-6 Luna"))]))
    alt = next(e for e in eintraege if "gespeichert" in e.text)

    assert alt.text == "gpt-6-alt (gespeichert, nicht bestätigt)"
    assert not alt.aktiv and alt.haken                       # sichtbar, zur Neuauswahl deaktiviert
    assert [e.wert for e in eintraege if e.aktiv] == ["gpt-6-luna"]   # nie still ersetzt


def test_rollen_zeilen_meldungen_und_schutzhinweis():
    zeilen = anzeige.rollen_zeilen("engineering",
                                   _stand(master="claude", worker="codex", modell="gpt-6-luna"), True)

    assert zeilen[0] == "engineering: Master Claude Code · Ausführer Codex · Ausführermodell gpt-6-luna"
    assert "ChatGPT-Abo" in zeilen[1]
    assert "keine Sitzung gestartet" in zeilen[2] and "lassen dieses Thema aus" in zeilen[2]


def test_rollen_zeilen_ohne_schutz_nennen_den_kontingentweg():
    zeilen = anzeige.rollen_zeilen("engineering", _stand(), False)
    assert "Kontingentweg offen" in zeilen[2]


def test_rollen_meldungen_sind_codegenau():
    assert anzeige.master_meldung("engineering", "hermes") == \
        "engineering: Master Hermes gespeichert – keine Sitzung gestartet."
    assert anzeige.ausfuehrer_meldung("engineering", "claude", None) == \
        "engineering: Ausführer Claude Code gespeichert – Ausführermodell Standard des Werkzeugs · keine Sitzung gestartet."
    assert anzeige.modell_meldung("engineering", modi.HERMES_MODELL) == \
        "engineering: Ausführermodell DeepSeek V4.1 Flash gespeichert – keine Sitzung gestartet."


def test_katalog_zeilen_nennen_nur_fehler_und_veraltetes():
    assert anzeige.katalog_zeilen([_katalog("codex", ("a", "A"))]) == []
    assert anzeige.katalog_zeilen([_katalog("codex", fehler="Zeitüberschreitung")]) == \
        ["Modellkatalog Codex: Zeitüberschreitung"]
    assert anzeige.katalog_zeilen(
        [_katalog("claude", ("opus", "Opus"), veraltet=True)]) == \
        ["Modellkatalog Claude Code: veraltet oder leer – " + anzeige.MODELLE_AKTUALISIEREN]


def test_katalog_ausgabe_fuer_die_cli():
    stand = Katalogstand("codex", (("gpt-6-luna", "GPT-6 Luna"),),
                         "2026-10-16T12:00:00+00:00", None, False)
    zeilen = anzeige.katalog_ausgabe(stand)

    assert zeilen[0] == "Codex: Codex-Modelle aus dem ChatGPT-Abo"
    assert any("Stand: 2026-10-16T12:00:00+00:00" in zeile for zeile in zeilen)
    assert any(zeile.strip() == "GPT-6 Luna  gpt-6-luna" for zeile in zeilen)

    leer = anzeige.katalog_ausgabe(Katalogstand("claude"))
    assert any("keine Modelle ermittelt" in zeile for zeile in leer)
