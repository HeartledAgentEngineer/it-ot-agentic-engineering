"""Tests der Arbeitsweise je Thema (`protokoll` | `vibe`): Datei, CLI `vibe`, Vorrang vor der Workerwahl, Anzeige.

Alles synthetisch: Datenordner und Repo liegen unter `tmp_path` (Fixture `umgebung` aus `conftest.py`); kein Netz,
keine echten Dateien.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from master_schalter import alle, arbeitsweise, automatik, cli, kurz, modi, signale, zustand
from master_schalter import uebersicht_modell as um

THEMA = "engineering"
MARKE = "claude 2026-10-28T00:00:00+00:00 modus engineering"


def _datei():
    return arbeitsweise.datei()


def _bytes(pfad):
    return pfad.read_bytes() if pfad.exists() else None


def _vibe_an(capsys=None):
    """Thema auf Ausführer Claude und Vibe an stellen (wie ein Anwender es täte)."""
    assert cli.main(["worker-setzen", THEMA, "claude"]) == 0
    assert cli.main(["vibe", THEMA, "an"]) == 0
    if capsys is not None:
        capsys.readouterr()


# --- Datei und CLI `vibe` ----------------------------------------------------------------------------------------

def test_vibe_an_aus_und_idempotent(umgebung, capsys):
    assert cli.main(["worker-setzen", THEMA, "claude"]) == 0
    capsys.readouterr()

    assert cli.main(["vibe", THEMA, "an"]) == 0
    aus = capsys.readouterr().out
    assert "Arbeitsweise Vibe" in aus and "unverändert" not in aus
    assert arbeitsweise.VIBE_REGEL in aus                              # die Ausgabe nennt die Regel
    assert json.loads(_datei().read_text(encoding="utf-8")) == {"version": 1, "themen": {THEMA: "vibe"}}
    vorher = _bytes(_datei())

    assert cli.main(["vibe", THEMA, "an"]) == 0                        # idempotent
    assert "unverändert" in capsys.readouterr().out
    assert _bytes(_datei()) == vorher

    assert cli.main(["vibe", THEMA, "aus"]) == 0
    assert "Protokoll" in capsys.readouterr().out
    assert json.loads(_datei().read_text(encoding="utf-8")) == {"version": 1, "themen": {}}
    assert arbeitsweise.arbeitsweise(THEMA) == arbeitsweise.PROTOKOLL
    nachher = _bytes(_datei())

    assert cli.main(["vibe", THEMA, "aus"]) == 0                        # idempotent
    assert "unverändert" in capsys.readouterr().out
    assert _bytes(_datei()) == nachher


def test_vibe_aus_ohne_datei_legt_keine_an(umgebung, capsys):
    assert cli.main(["vibe", THEMA, "aus"]) == 0
    assert not _datei().exists()


def test_vibe_unbekanntes_thema_ist_fehler_und_datei_bleibt(umgebung, capsys):
    _vibe_an(capsys)
    vorher = _bytes(_datei())
    for zustand_ in ("an", "aus"):
        assert cli.main(["vibe", "gibtsnicht", zustand_]) == 1
        assert "Thema unbekannt" in capsys.readouterr().err
    assert cli.main(["vibe", "Ungültig!", "an"]) == 1                    # unzulässiger Themenname
    assert _bytes(_datei()) == vorher


def test_vibe_nimmt_auch_ein_thema_nur_mit_profil(umgebung, capsys):
    modi._speichern(modi.datei(), "nurprofil", modi.Profil("kontingent", "claude", None))
    assert cli.main(["vibe", "nurprofil", "an"]) == 0
    assert arbeitsweise.arbeitsweise("nurprofil") == arbeitsweise.VIBE


def test_vibe_zustand_nur_an_oder_aus(umgebung, capsys):
    assert cli.main(["vibe", THEMA, "vielleicht"]) == 2
    assert not _datei().exists()


@pytest.mark.parametrize("inhalt", [
    "{kaputt",
    "[]",
    '{"version": 2, "themen": {}}',
    '{"version": 1, "themen": {"engineering": "wild"}}',
    '{"version": 1, "themen": {"engineering": "vibe"}, "extra": 1}',
    '{"version": 1, "themen": {"Ungültig!": "vibe"}}',
    '{"version": 1, "themen": []}',
])
def test_kaputte_datei_zeigt_fragezeichen_und_stuerzt_nicht_ab(umgebung, capsys, inhalt):
    modi.worker_setzen(THEMA, "claude")
    _datei().write_text(inhalt, encoding="utf-8")
    vorher = _bytes(_datei())

    with pytest.raises(arbeitsweise.ArbeitsweiseFehler):
        arbeitsweise.lesen()
    assert arbeitsweise.anzeige_wert(THEMA) == arbeitsweise.UNBEKANNT == "?"
    text = "\n".join(kurz.sammeln())                                     # kein Absturz
    assert f"  {THEMA}: " in text and "· Arbeitsweise ?" in text and "Arbeitsweise-Datei ungültig" in text
    assert cli.main(["profil", THEMA, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["arbeitsweise"] == "?"
    assert cli.main(["profil", THEMA]) == 0
    assert "Arbeitsweise: ?" in capsys.readouterr().out
    assert cli.main(["vibe", THEMA, "an"]) == 1                          # Setzen: Fehler, Datei bleibt
    assert cli.main(["vibe", THEMA, "aus"]) == 1
    assert "Arbeitsweise nicht geändert" in capsys.readouterr().err
    assert _bytes(_datei()) == vorher


def test_schreiben_ist_atomar_und_sortiert(umgebung):
    modi.worker_setzen(THEMA, "claude")
    modi._speichern(modi.datei(), "zzz", modi.Profil("kontingent", "claude", None))
    assert modi.vibe_setzen("zzz", True) is True
    assert modi.vibe_setzen(THEMA, True) is True
    assert list(json.loads(_datei().read_text(encoding="utf-8"))["themen"]) == [THEMA, "zzz"]
    assert [p.name for p in _datei().parent.iterdir() if p.name.endswith(".tmp")] == []   # kein Rest einer Zwischendatei


# --- `profil` ----------------------------------------------------------------------------------------------------

def test_profil_json_alte_felder_bytegleich_und_neue_felder(umgebung, capsys):
    assert cli.main(["worker-setzen", THEMA, "hermes"]) == 0
    capsys.readouterr()
    alt = json.dumps({"thema": THEMA, "master": "kontingent", "worker": "hermes", "modell": modi.HERMES_MODELL,
                      "modell_standard": False, "geschuetzt": False}, ensure_ascii=False)

    assert cli.main(["profil", THEMA, "--json"]) == 0
    ausgabe = capsys.readouterr().out.strip()

    assert ausgabe.startswith(alt[:-1])                                 # die bisherigen Felder unverändert vorneweg
    daten = json.loads(ausgabe)
    assert daten["arbeitsweise"] == "protokoll" and "vibe_regel" not in daten


def test_profil_json_bei_vibe_nennt_die_regel(umgebung, capsys):
    _vibe_an(capsys)
    assert cli.main(["profil", THEMA, "--json"]) == 0
    daten = json.loads(capsys.readouterr().out)
    assert daten["arbeitsweise"] == "vibe" and daten["vibe_regel"] == arbeitsweise.VIBE_REGEL
    assert daten["worker"] == "claude" and daten["modell_standard"] is True
    assert "Sonnet oder Haiku" in daten["vibe_regel"] and "keine Codex-/Hermes-Gegenprüfung" in daten["vibe_regel"]


def test_profil_text_zeigt_arbeitsweise_und_regel(umgebung, capsys):
    assert cli.main(["profil", THEMA]) == 0
    assert "Arbeitsweise: Protokoll" in capsys.readouterr().out
    _vibe_an(capsys)
    assert cli.main(["profil", THEMA]) == 0
    aus = capsys.readouterr().out
    assert "Arbeitsweise: Vibe" in aus and f"Vibe-Regel: {arbeitsweise.VIBE_REGEL}" in aus


# --- Anzeige in `status` ---------------------------------------------------------------------------------------------

def test_themenzeile_zeigt_vibe_nur_bei_vibe(umgebung, capsys):
    ohne = [z for z in kurz.sammeln() if z.startswith(f"  {THEMA}:")][0]
    assert "VIBE" not in ohne and "Arbeitsweise" not in ohne
    _vibe_an(capsys)
    mit = [z for z in kurz.sammeln() if z.startswith(f"  {THEMA}:")][0]
    assert mit == ohne.replace("Ausführer Workflow", "Ausführer Claude") + " · VIBE"


@pytest.mark.parametrize("weise, ende", [("protokoll", "· Auto an"), ("vibe", "· Auto an · VIBE"),
                                          ("?", "· Auto an · Arbeitsweise ?")])
def test_themenzeile_der_reinen_funktion(weise, ende):
    jetzt = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
    thema = kurz.Thema("t1", modi.Profil("kontingent", "claude", None), "claude", True, "claude", weise)
    zeilen = kurz.zeilen([signale.Kontingent("Claude", fehler="x"), signale.Kontingent("Codex", fehler="x")], [thema], [],
                         schwelle=95, automatik_global=True, jetzt=jetzt, zone=timezone.utc)
    assert next(z for z in zeilen if z.startswith("  t1:")).endswith(ende)


def test_zeilen_pure_funktion_kennt_die_drei_werte():
    assert kurz.arbeitsweise_zusatz("protokoll") == ""
    assert kurz.arbeitsweise_zusatz("vibe") == " · VIBE"
    assert kurz.arbeitsweise_zusatz("?") == " · Arbeitsweise ?"


# --- Vorrang Vibe vor der Workerwahl (R1-1, R2-1) ----------------------------------------------------------------------

@pytest.mark.parametrize("worker", ["codex", "hermes", "workflow"])
def test_vibe_an_bei_anderem_ausfuehrer_ist_fehler(umgebung, capsys, worker):
    assert cli.main(["worker-setzen", THEMA, worker]) == 0
    capsys.readouterr()
    assert cli.main(["vibe", THEMA, "an"]) == 1
    assert "Vibe braucht Ausführer Claude" in capsys.readouterr().err
    assert not _datei().exists()


def test_worker_setzen_bei_vibe_lehnt_anderen_ausfuehrer_ab(umgebung, capsys):
    _vibe_an(capsys)
    profil_vorher, vibe_vorher = _bytes(modi.datei()), _bytes(_datei())
    for worker in ("codex", "hermes", "workflow"):
        assert cli.main(["worker-setzen", THEMA, worker]) == 1
        assert "erst `masterwechsel vibe engineering aus`" in capsys.readouterr().err
        assert _bytes(modi.datei()) == profil_vorher and _bytes(_datei()) == vibe_vorher
    assert cli.main(["worker-setzen", THEMA, "claude"]) == 0              # Claude bleibt erlaubt
    assert _bytes(modi.datei()) == profil_vorher


def test_nach_vibe_aus_ist_die_workerwahl_wieder_frei(umgebung, capsys):
    _vibe_an(capsys)
    assert cli.main(["vibe", THEMA, "aus"]) == 0
    assert cli.main(["worker-setzen", THEMA, "codex"]) == 0
    assert modi.profil(THEMA).worker == "codex"


def test_modus_mit_legacy_profil_umgeht_den_schutz_nicht(umgebung, capsys):
    """`modus THEMA hermes-codex|kontingent` setzt ein Legacy-Profil mit Ausführer codex/workflow."""
    umgebung.marke_setzen(MARKE)
    _vibe_an(capsys)
    profil_vorher, vibe_vorher, marke_vorher = _bytes(modi.datei()), _bytes(_datei()), _bytes(umgebung.master_datei())
    for modus in ("hermes-codex", "kontingent"):
        assert cli.main(["modus", THEMA, modus]) == 1
        assert "Vibe" in capsys.readouterr().err
        assert _bytes(modi.datei()) == profil_vorher and _bytes(_datei()) == vibe_vorher
        assert _bytes(umgebung.master_datei()) == marke_vorher             # keine Zwischenmarke geschrieben


def test_zentrale_pruefung_vor_der_ersten_besitzmarke(umgebung, capsys):
    """Auch ein Aufrufer, der ein Zielprofil mit anderem Ausführer baut (master-setzen/alle würden es nie tun)."""
    umgebung.marke_setzen(MARKE)
    _vibe_an(capsys)
    profil_vorher, marke_vorher = _bytes(modi.datei()), _bytes(umgebung.master_datei())
    with zustand.thema_sperre(THEMA, blockierend=True, frist=1.0) as frei:
        assert frei
        with pytest.raises(modi.ModusFehler, match="Vibe"):
            modi._umschalten_gesperrt(THEMA, modi.Profil("codex", "codex", None), None, repo=umgebung.repo)
    assert _bytes(modi.datei()) == profil_vorher and _bytes(umgebung.master_datei()) == marke_vorher
    with pytest.raises(modi.ModusFehler, match="Vibe"):
        modi._speichern(modi.datei(), THEMA, modi.Profil("claude", "codex", None))
    assert _bytes(modi.datei()) == profil_vorher


def test_master_setzen_und_alle_bleiben_bei_vibe_moeglich(umgebung, capsys):
    umgebung.marke_setzen(MARKE)
    _vibe_an(capsys)
    assert cli.main(["master-setzen", THEMA, "codex"]) == 0
    assert modi.profil(THEMA) == modi.Profil("codex", "claude", None)        # Ausführer Claude bleibt
    bericht = alle.auf_kontingent(repo=umgebung.repo)
    assert bericht.offen == 0 and modi.profil(THEMA).worker == "claude"
    assert arbeitsweise.arbeitsweise(THEMA) == arbeitsweise.VIBE


def test_vibe_prueft_unter_der_themensperre(umgebung, capsys):
    modi.worker_setzen(THEMA, "claude")
    with zustand.thema_sperre(THEMA, blockierend=True, frist=1.0) as frei:
        assert frei
        assert cli.main(["vibe", THEMA, "an"]) == 1
        assert "Übergabe läuft" in capsys.readouterr().err
    assert not _datei().exists()


def test_kaputte_arbeitsweise_datei_sperrt_profilschreiben_fail_closed(umgebung, capsys):
    _datei().write_text("{kaputt", encoding="utf-8")
    profil_vorher = _bytes(modi.datei())
    assert cli.main(["worker-setzen", THEMA, "codex"]) == 1
    assert "nicht prüfbar" in capsys.readouterr().err
    assert _bytes(modi.datei()) == profil_vorher
    assert cli.main(["worker-setzen", THEMA, "claude"]) == 0               # Ausführer Claude braucht die Datei nicht


# --- Nur von Hand --------------------------------------------------------------------------------------------------------

def test_automatik_und_sammelbefehle_aendern_die_datei_nie(umgebung, monkeypatch, capsys):
    umgebung.marke_setzen(MARKE)
    _vibe_an(capsys)
    vorher = _bytes(_datei())

    def nie(*_a, **_k):
        raise AssertionError("kein Automatikpfad darf die Arbeitsweise schreiben")

    monkeypatch.setattr(arbeitsweise, "setzen", nie)
    monkeypatch.setattr(arbeitsweise, "_atomar_schreiben", nie)
    automatik.lauf(trocken=True)
    assert alle.auf_kontingent(repo=umgebung.repo).offen == 0
    assert alle.zurueck(repo=umgebung.repo).offen == 0
    assert cli.main(["automatik-pruefen", "--trocken"]) == 0
    assert _bytes(_datei()) == vorher


def test_nur_modi_und_oberflaeche_rufen_setzen():
    """Statische Zusage: außer `modi.vibe_setzen` ruft kein Modul `arbeitsweise.setzen` auf."""
    from pathlib import Path
    quelle = Path(arbeitsweise.__file__).parent
    aufrufer = sorted(p.name for p in quelle.glob("*.py")
                      if p.name != "arbeitsweise.py" and "arbeitsweise.setzen(" in p.read_text(encoding="utf-8"))
    assert aufrufer == ["modi.py"]


# --- Übersichtsfenster-Modell ------------------------------------------------------------------------------------------------

@pytest.fixture
def snap(umgebung, monkeypatch):
    from master_schalter import signale
    monkeypatch.setattr(signale, "alle_lesen", lambda jetzt=None: [signale.Kontingent("Claude", fehler="keine Daten"),
                                                                    signale.Kontingent("Codex", fehler="keine Daten")])
    return lambda: um.aufnehmen(datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc))


def test_aufnahme_traegt_arbeitsweise_und_ausfuehrer(umgebung, snap, capsys):
    zeile = snap().themen[0]
    assert (zeile.thema, zeile.arbeitsweise, zeile.worker_wert) == (THEMA, "protokoll", "workflow")
    _vibe_an(capsys)
    zeile = snap().themen[0]
    assert (zeile.arbeitsweise, zeile.worker_wert) == ("vibe", "claude")


def test_aktion_vibe_fragt_mit_regel_und_schreibt_nur_bei_ausfuehren(umgebung, snap, capsys):
    modi.worker_setzen(THEMA, "claude")
    aktion = um.arbeitsweise_aktion(snap(), THEMA, "vibe")
    assert arbeitsweise.VIBE_REGEL in aktion.frage and "keine Sitzung" in aktion.frage
    assert not _datei().exists()                                            # Rückfrage allein ändert nichts
    ergebnis = aktion.ausfuehren()
    assert ergebnis.ok and "Vibe gespeichert" in ergebnis.text
    assert arbeitsweise.arbeitsweise(THEMA) == "vibe"
    zurueck = um.arbeitsweise_aktion(snap(), THEMA, "protokoll")
    assert "Protokoll" in zurueck.frage
    assert zurueck.ausfuehren().ok and arbeitsweise.arbeitsweise(THEMA) == "protokoll"


def test_aktion_lehnt_ab_bei_falschem_ausfuehrer_gleichem_wert_unbekanntem_thema_und_nur_anzeige(umgebung, snap, capsys):
    with pytest.raises(um.AktionAbgelehnt, match="Vibe braucht Ausführer Claude"):
        um.arbeitsweise_aktion(snap(), THEMA, "vibe")
    with pytest.raises(um.AktionAbgelehnt, match="schon Protokoll"):
        um.arbeitsweise_aktion(snap(), THEMA, "protokoll")
    with pytest.raises(um.AktionAbgelehnt, match="nicht bekannt"):
        um.arbeitsweise_aktion(snap(), "gibtsnicht", "vibe")
    with pytest.raises(um.AktionAbgelehnt, match="Unbekannte Arbeitsweise"):
        um.arbeitsweise_aktion(snap(), THEMA, "wild")
    with pytest.raises(um.AktionAbgelehnt, match="nur Anzeige"):
        um.arbeitsweise_aktion(replace(snap(), schreiben=False), THEMA, "vibe")
    _datei().write_text("{kaputt", encoding="utf-8")
    with pytest.raises(um.AktionAbgelehnt, match="Arbeitsweise unbekannt"):
        um.arbeitsweise_aktion(snap(), THEMA, "vibe")


def test_aktion_meldet_fehler_aus_modi_statt_abzustuerzen(umgebung, snap, capsys):
    modi.worker_setzen(THEMA, "claude")
    aktion = um.arbeitsweise_aktion(snap(), THEMA, "vibe")
    modi.worker_setzen(THEMA, "codex")                                       # zwischen Rückfrage und Ausführen geändert
    ergebnis = aktion.ausfuehren()
    assert not ergebnis.ok and "nicht geändert" in ergebnis.text and "Vibe braucht Ausführer Claude" in ergebnis.text
    assert not _datei().exists()
