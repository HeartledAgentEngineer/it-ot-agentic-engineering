"""Tests der Prüferwahl je Thema (`pruefer.json`), der CLI `pruefer-setzen`, der Anzeige und des wirksamen Auto-Zustands.

Alles synthetisch: Datenordner und Repo liegen unter `tmp_path` (Fixture `umgebung` aus `conftest.py`).
"""
from __future__ import annotations

import itertools
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_schalter import alle, anzeige, automatik, cli, kurz, modi, paare, pruefer_wahl, signale

THEMA = "engineering"
SRC = Path(pruefer_wahl.__file__).resolve().parent


def _datei():
    return pruefer_wahl.datei()


def _bytes():
    return _datei().read_bytes() if _datei().exists() else None


# --- Datei und Modul -------------------------------------------------------------------------------------------

def test_standard_ist_automatisch_ohne_datei(umgebung):
    assert pruefer_wahl.wahl(THEMA) == "automatisch" and pruefer_wahl.lesen() == {}
    assert pruefer_wahl.anzeige_wert(THEMA) == "automatisch" and not _datei().exists()


def test_setzen_automatisch_idempotent(umgebung):
    assert pruefer_wahl.setzen(THEMA, "codex") is True
    assert json.loads(_datei().read_text(encoding="utf-8")) == {"version": 1, "themen": {THEMA: "codex"}}
    vorher = _bytes()
    assert pruefer_wahl.setzen(THEMA, "codex") is False and _bytes() == vorher        # idempotent
    assert pruefer_wahl.setzen(THEMA, "hermes") is True and pruefer_wahl.wahl(THEMA) == "hermes"
    assert pruefer_wahl.setzen(THEMA, "automatisch") is True
    assert json.loads(_datei().read_text(encoding="utf-8")) == {"version": 1, "themen": {}}
    nachher = _bytes()
    assert pruefer_wahl.setzen(THEMA, "automatisch") is False and _bytes() == nachher
    assert pruefer_wahl.wahl(THEMA) == "automatisch"


def test_automatisch_ohne_datei_legt_keine_an(umgebung):
    assert pruefer_wahl.setzen(THEMA, "automatisch") is False and not _datei().exists()


def test_unbekanntes_thema_und_unbekannter_wert_aendern_nichts(umgebung):
    pruefer_wahl.setzen(THEMA, "hermes")
    vorher = _bytes()
    with pytest.raises(pruefer_wahl.PrueferWahlFehler, match="Thema unbekannt"):
        pruefer_wahl.setzen("gibtsnicht", "codex")
    with pytest.raises(pruefer_wahl.PrueferWahlFehler):
        pruefer_wahl.setzen("Ungültig!", "codex")
    with pytest.raises(pruefer_wahl.PrueferWahlFehler, match="Unbekannter Prüfer"):
        pruefer_wahl.setzen(THEMA, "gpt")
    assert _bytes() == vorher


def test_thema_nur_mit_profil_ist_erlaubt(umgebung):
    modi.thema_anlegen("ohne-paar")
    assert pruefer_wahl.setzen("ohne-paar", "codex") is True


@pytest.mark.parametrize("inhalt", [
    "{kaputt", "[]", '{"version": 2, "themen": {}}', '{"version": 1}', '{"version": 1, "themen": []}',
    '{"version": 1, "themen": {"engineering": "gpt"}}', '{"version": 1, "themen": {"engineering": "automatisch"}}',
    '{"version": 1, "themen": {"Ungültig!": "codex"}}', '{"version": 1, "themen": {}, "extra": 1}',
])
def test_kaputte_datei_zeigt_fragezeichen_und_wird_nie_ueberschrieben(umgebung, inhalt):
    _datei().write_text(inhalt, encoding="utf-8")
    with pytest.raises(pruefer_wahl.PrueferWahlFehler):
        pruefer_wahl.lesen()
    assert pruefer_wahl.anzeige_wert(THEMA) == "?"
    with pytest.raises(pruefer_wahl.PrueferWahlFehler):
        pruefer_wahl.setzen(THEMA, "codex")
    assert _datei().read_text(encoding="utf-8") == inhalt


def test_nicht_utf8_datei_ist_fehler(umgebung):
    _datei().write_bytes(b"\xff\xfe\x00")
    assert pruefer_wahl.anzeige_wert(THEMA) == "?"


# --- CLI ----------------------------------------------------------------------------------------------------------

def test_cli_setzt_und_nennt_die_regeln(umgebung, capsys):
    assert cli.main(["pruefer-setzen", THEMA, "codex"]) == 0
    aus = capsys.readouterr().out
    assert "Prüfer Codex" in aus and "--sensibel" in aus and "unverändert" not in aus
    assert cli.main(["pruefer-setzen", THEMA, "codex"]) == 0
    assert "unverändert" in capsys.readouterr().out
    assert cli.main(["pruefer-setzen", THEMA, "automatisch"]) == 0
    assert "automatisch" in capsys.readouterr().out and pruefer_wahl.wahl(THEMA) == "automatisch"


def test_cli_fehler_haben_exit_1_und_aendern_nichts(umgebung, capsys):
    pruefer_wahl.setzen(THEMA, "hermes")
    vorher = _bytes()
    for argv in (["pruefer-setzen", "gibtsnicht", "codex"], ["pruefer-setzen", THEMA, "gpt"]):
        assert cli.main(argv) == 1
        assert "Prüfer nicht geändert" in capsys.readouterr().err
    assert _bytes() == vorher


def test_profil_und_master_setzen_nennen_die_wahl(umgebung, capsys):
    umgebung.marke_setzen("claude 2026-10-28T00:00:00+00:00 modus engineering")
    pruefer_wahl.setzen(THEMA, "hermes")
    assert cli.main(["profil", THEMA]) == 0
    aus = capsys.readouterr().out
    assert "Jetzt: Prüfer Hermes (Wahl für dieses Thema" in aus and "Sobald" not in aus and "Nach Kontingent: Prüfer" not in aus
    _datei().write_text("{kaputt", encoding="utf-8")
    assert cli.main(["profil", THEMA]) == 0
    assert "pruefer.json ungültig" in capsys.readouterr().out


# --- Anzeige im Master-Status -----------------------------------------------------------------------------------------

def _zeile(thema=THEMA):
    return next(z for z in kurz.sammeln() if z.startswith(f"  {thema}:"))


def test_status_zeigt_gewaehlten_pruefer_und_familienhinweis(umgebung):
    umgebung.marke_setzen("codex 2026-10-28T00:00:00+00:00 modus engineering")
    assert "Prüfer Hermes · DeepSeek V4.1 Flash ·" in _zeile()                          # Regel: Master Codex ⇒ Hermes
    pruefer_wahl.setzen(THEMA, "codex")
    zeile = _zeile()
    assert "Prüfer Codex · App-Standard (gewählt) – gleiche Familie wie Master" in zeile


def test_status_kaputte_datei_zeigt_fragezeichen_und_hinweis(umgebung):
    _datei().write_text("{kaputt", encoding="utf-8")
    zeilen = kurz.sammeln()
    assert any("Prüfer ? (Besitz unklar" in z or "Prüfer ? (pruefer.json ungültig" in z
               for z in zeilen if z.startswith(f"  {THEMA}:"))
    assert any(z.startswith("Hinweis: Prüfer-Datei ungültig") for z in zeilen)


# --- Automatik schreibt pruefer.json nie ---------------------------------------------------------------------------------

def test_kein_automatikpfad_ruft_den_setter(umgebung):
    erlaubt = {"pruefer_wahl.py", "cli.py", "uebersicht_modell.py"}
    for quelle in SRC.glob("*.py"):
        if quelle.name in erlaubt:
            continue
        assert "pruefer_wahl.setzen" not in quelle.read_text(encoding="utf-8"), quelle.name


def test_sammelaktionen_und_umschalten_beruehren_die_datei_nicht(umgebung):
    pruefer_wahl.setzen(THEMA, "codex")
    vorher = _bytes()
    alle.auf_kontingent(repo=umgebung.repo)
    alle.zurueck(repo=umgebung.repo)
    modi.master_setzen(THEMA, "claude", repo=umgebung.repo)
    modi.master_setzen(THEMA, "kontingent", repo=umgebung.repo)
    anzeige.automatik_setzen(True)
    paare.aktiv_setzen(THEMA, False)
    assert _bytes() == vorher


# --- wirksamer Auto-Zustand (Plan I, R1-2) ----------------------------------------------------------------------------------

@pytest.mark.parametrize("schalter, paar, master, zustand, text", [
    (True, True, "kontingent", "wirksam", "Auto an (wirksam)"),
    (False, True, "kontingent", "wartet", "Freigabe an – wirkt nicht: Hauptschalter aus"),
    (True, True, "hermes", "wartet", "Freigabe an – wirkt nicht: fester Master Hermes"),
    (True, True, "claude", "wartet", "Freigabe an – wirkt nicht: fester Master Claude"),
    (False, True, "codex", "wartet", "Freigabe an – wirkt nicht: Hauptschalter aus, fester Master Codex"),
    (True, False, "kontingent", "aus", "Freigabe aus"),
    (False, False, "hermes", "aus", "Freigabe aus"),
    (True, None, "kontingent", "ohne", "ohne Codex-Paar"),
    (None, True, "kontingent", "?", "Freigabe an – Hauptschalter unbekannt (?)"),
])
def test_auto_zustand_folgt_der_bedingung(schalter, paar, master, zustand, text):
    assert anzeige.auto_zustand(schalter, paar, master) == (zustand, text)


def _faelligkeit(an, aktiv, master):
    """Ergibt `automatik.faellige` für dieses Paar einen Auftrag? (Claude im Limit, Codex frei – alles andere passt)"""
    jetzt = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    ende = jetzt + timedelta(hours=3)
    claude = signale.Kontingent("Claude", (signale.Fenster("5h", 97, ende), signale.Fenster("Woche", 50, ende)), stand=jetzt)
    codex = signale.Kontingent("Codex", (signale.Fenster("5h", 5, ende), signale.Fenster("Woche", 5, ende)), stand=jetzt)
    paar = paare.Paar("engineering", "00000000-0000-4000-8000-0000000000a1",
                      ".hermes/uebergabe/laufend/engineering.md", aktiv)
    return bool(automatik.faellige([paar], automatik.Messung(claude, codex), 90, an, [], jetzt,
                                   modus_mapping={"engineering": modi.Profil(master)}))


@pytest.mark.parametrize("an, aktiv, master", list(itertools.product((True, False), (True, False),
                                                                    modi.MASTER_WERTE)))
def test_anzeige_und_automatik_nutzen_dieselbe_bedingung(an, aktiv, master):
    wirksam = anzeige.auto_zustand(an, aktiv, master)[0] == anzeige.AUTO_WIRKSAM
    assert wirksam == _faelligkeit(an, aktiv, master) == (an and anzeige.auto_paar_zaehlt(aktiv, master))
