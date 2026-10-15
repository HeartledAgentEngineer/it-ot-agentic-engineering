"""Tests für die Lage der Kaskaden-Matrix und die Besetzung."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_schalter import rollen
from master_schalter.signale import Fenster, Kontingent

JETZT = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
SPAETER = JETZT + timedelta(hours=2)
VORBEI = JETZT - timedelta(minutes=5)


def _k(master, fuenf, woche, fenster_reset=SPAETER):
    return Kontingent(master, (Fenster("5h", fuenf, fenster_reset), Fenster("Woche", woche, fenster_reset)),
                      stand=JETZT)


def _abgelaufen(master, woche=10.0):
    return Kontingent(master, (Fenster("5h", 0.0, VORBEI, zurueckgesetzt=True), Fenster("Woche", woche, SPAETER)),
                      stand=JETZT)


FREI = ("Claude", 20.0, 30.0)
VOLL = ("Claude", 98.0, 30.0)


def test_lage_1_beide_frei():
    assert rollen.lage(_k("Claude", 20, 30), _k("Codex", 5, 10), 97) == "1"


def test_lage_2a_claude_im_limit():
    assert rollen.lage(_k("Claude", 98, 30), _k("Codex", 5, 10), 97) == "2A"


def test_lage_2b_codex_im_limit():
    assert rollen.lage(_k("Claude", 20, 30), _k("Codex", 5, 99), 97) == "2B"


def test_lage_3_beide_im_limit():
    assert rollen.lage(_k("Claude", 97, 10), _k("Codex", 5, 100), 97) == "3"


def test_grenze_genau_schwelle_ist_im_limit_knapp_darunter_frei():
    assert rollen.lage(_k("Claude", 96.9, 30), _k("Codex", 5, 10), 97) == "1"
    assert rollen.lage(_k("Claude", 97.0, 30), _k("Codex", 5, 10), 97) == "2A"
    assert rollen.lage(_k("Claude", 20, 30), _k("Codex", 5, 10), 90) == "1"
    assert rollen.lage(_k("Claude", 90, 30), _k("Codex", 5, 10), 90) == "2A"


def test_wochenfenster_allein_reicht_fuer_limit():
    assert rollen.lage(_k("Claude", 10, 97), _k("Codex", 5, 10), 97) == "2A"


def test_fehlende_daten_sind_unbekannt():
    fehlt = Kontingent("Codex", fehler="keine Daten")
    assert rollen.lage(_k("Claude", 20, 30), fehlt, 97) is None
    assert rollen.lage(fehlt, fehlt, 97) is None


def test_fehlender_prozentwert_ist_unbekannt_nie_frei():
    assert rollen.lage(_k("Claude", None, 30), _k("Codex", 5, 10), 97) is None
    assert rollen.lage(_k("Claude", 20, 30), Kontingent("Codex", (Fenster("5h", 5, SPAETER),)), 97) is None


def test_fehlende_resetzeiten_sind_unbekannt_und_werden_begruendet():
    claude = Kontingent("Claude", (Fenster("5h", 20, None), Fenster("Woche", 20, None)), stand=JETZT)
    codex = Kontingent("Codex", (Fenster("5h", 20, None), Fenster("Woche", 20, None)), stand=JETZT)

    assert rollen.lage(claude, codex, 97) is None
    assert rollen.lage_grund(claude, codex, 97) == (
        "Claude 5h ohne gültige Rücksetzzeit; Claude Woche ohne gültige Rücksetzzeit; "
        "Codex 5h ohne gültige Rücksetzzeit; Codex Woche ohne gültige Rücksetzzeit"
    )


def test_gueltiges_limitfenster_zaehlt_trotz_fehlendem_reset_im_anderen():
    claude = Kontingent("Claude", (Fenster("5h", 98, SPAETER), Fenster("Woche", 20, None)), stand=JETZT)

    assert rollen.lage(claude, _k("Codex", 5, 10), 97) == "2A"


def test_abgelaufenes_fenster_ist_unbekannt_nie_lage_1():
    assert rollen.lage(_k("Claude", 20, 30), _abgelaufen("Codex"), 97) is None


def test_limit_plus_unbekannt_ist_keine_lage():
    assert rollen.lage(_k("Claude", 99, 30), _abgelaufen("Codex"), 97) is None
    assert rollen.lage(_abgelaufen("Claude"), _k("Codex", 5, 99), 97) is None


def test_abgelaufen_aber_anderes_fenster_im_limit_bleibt_limit():
    claude = Kontingent("Claude", (Fenster("5h", 0.0, VORBEI, zurueckgesetzt=True), Fenster("Woche", 98.0, SPAETER)))
    assert rollen.lage(claude, _k("Codex", 5, 10), 97) == "2A"


def test_grund_nennt_abo_und_fenster_nach_reset():
    grund = rollen.lage_grund(_k("Claude", 20, 30), _abgelaufen("Codex"), 97)
    assert grund == "Codex 5h nach Reset noch nicht neu gemessen"


def test_grund_bei_fehlenden_daten_und_mehreren_abos():
    grund = rollen.lage_grund(Kontingent("Claude", fehler="keine Daten"), Kontingent("Codex", fehler="Datei unlesbar"), 97)
    assert grund == "Claude keine Daten; Codex Datei unlesbar"


def test_grund_bei_fehlendem_wert():
    assert rollen.lage_grund(_k("Claude", None, 30), _k("Codex", 5, 10), 97) == "Claude 5h nicht gemessen"


def test_grund_leer_wenn_lage_bekannt():
    assert rollen.lage_grund(_k("Claude", 20, 30), _k("Codex", 5, 10), 97) == ""


def test_besetzung_unbekannte_lage_ist_none():
    assert rollen.besetzung(None) is None
    assert rollen.besetzung("9") is None


def test_besetzung_hat_drei_rollen_fuer_alle_lagen():
    for lage in ("1", "2A", "2B", "3"):
        b = rollen.besetzung(lage)
        assert b.thinker and b.reviewer and b.worker


def _agents_md() -> Path | None:
    for ordner in Path(__file__).resolve().parents:
        kandidat = ordner / "AGENTS.md"
        if kandidat.is_file():
            return kandidat
    return None


def test_besetzung_stimmt_mit_agents_md_ueberein():
    """Maßgeblich ist die Tabelle in AGENTS.md; die Konstante übernimmt die Zellen wörtlich."""
    datei = _agents_md()
    if datei is None:
        pytest.skip("AGENTS.md nicht gefunden (Projekt außerhalb des Workspaces)")
    text = datei.read_text(encoding="utf-8")
    abschnitt = text.split("## Rollen und Datenschutz im Agenten-Workflow", 1)[1]
    zeilen = [z for z in abschnitt.splitlines() if z.startswith("|")]
    gefunden = {}
    for zeile in zeilen:
        zellen = [c.strip() for c in zeile.strip().strip("|").split("|")]
        if len(zellen) == 4 and zellen[0].split(" ", 1)[0] in ("1", "2A", "2B", "3"):
            gefunden[zellen[0].split(" ", 1)[0]] = zellen
    assert set(gefunden) == {"1", "2A", "2B", "3"}
    for lage, zellen in gefunden.items():
        b = rollen.besetzung(lage)
        assert (b.name, b.thinker, b.reviewer, b.worker) == tuple(zellen[0].split(" ", 1)[1:2] + zellen[1:]), lage
