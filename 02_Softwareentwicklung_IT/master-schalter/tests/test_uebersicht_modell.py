"""Tests des bildschirmfreien Übersichtsmodells: Zeilen, Balkenwerte, Repo-Ort, Messfehler, Aktionen.

Alles synthetisch: Datenordner und Repo liegen unter `tmp_path`, Kontingente sind Attrappen, kein Prozess wird gestartet.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_schalter import alle, anzeige, besitz, modi, paare, signale, symbol
from master_schalter import uebersicht_modell as um
from master_schalter.signale import Fenster, Kontingent

UTC = timezone.utc
JETZT = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
THREAD = "00000000-0000-4000-8000-0000000000e1"
THEMA = "thema-a"


def _k(name, fuenf, woche, **kw):
    return Kontingent(name, (Fenster("5h", fuenf, JETZT + timedelta(hours=2)),
                             Fenster("Woche", woche, JETZT + timedelta(days=3))), JETZT - timedelta(minutes=5), **kw)


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    daten = tmp_path / "daten"
    daten.mkdir()
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    monkeypatch.setattr(signale, "alle_lesen", lambda jetzt=None: [_k("Claude", 62, 80), _k("Codex", 1, 32)])
    paare.setzen(THEMA, THREAD, paare.laufend_bilden(THEMA), aktiv=True)
    return tmp_path


def _worktree(tmp_path, monkeypatch, *, commondir_ok=True):
    """Haupt- und Worktree-Attrappe; das Modell wird aus dem Worktree gestartet."""
    haupt = tmp_path / "haupt"
    (haupt / ".git" / "worktrees" / "w").mkdir(parents=True)
    if commondir_ok:
        (haupt / ".git" / "worktrees" / "w" / "commondir").write_text("../..", encoding="utf-8")
    baum = tmp_path / "baum"
    baum.mkdir()
    (baum / ".git").write_text(f"gitdir: {haupt / '.git' / 'worktrees' / 'w'}", encoding="utf-8")
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(baum))
    return haupt, baum


# --- Anzeige ---------------------------------------------------------------------------------------------

def test_balkenwerte_sind_0_bis_100_mit_text_und_statusfarbe(umgebung, monkeypatch):
    monkeypatch.setattr(signale, "alle_lesen", lambda jetzt=None: [_k("Claude", 130, -5), _k("Codex", 85, 20)])
    snap = um.aufnehmen(JETZT, UTC)
    claude, codex = snap.abos
    assert [b.prozent for b in claude.balken] == [100, 0]
    assert [b.text for b in claude.balken] == ["100 % verbraucht", "0 % verbraucht"]
    assert claude.balken[0].farbe == "#dc2626"                                 # rot ab Schwelle (97)
    assert codex.balken[0].farbe == "#eab308"                                  # gelb ab 80 %
    assert codex.balken[1].farbe == "#10a37f"                                  # Grundfarbe Codex
    assert claude.balken[1].farbe == "#d97757"                                 # Grundfarbe Claude
    assert codex.balken[0].reset == "Reset in 2 h 0 min (11:00)"
    assert claude.gemessen == "gemessen 08:55"
    assert all(0 <= b.prozent <= 100 for a in snap.abos for b in a.balken)


def test_farbe_folgt_der_symbollogik(umgebung):
    snap = um.aufnehmen(JETZT, UTC)
    erwartet = "#{:02x}{:02x}{:02x}".format(*symbol.farbe(62, symbol.CLAUDE, anzeige.schwelle()))
    assert snap.abos[0].balken[0].farbe == erwartet


def test_unbekanntes_kontingent_zeigt_grund_und_keinen_balken(umgebung, monkeypatch):
    monkeypatch.setattr(signale, "alle_lesen",
                        lambda jetzt=None: [Kontingent("Claude", fehler="keine Daten"), _k("Codex", 1, 2)])
    snap = um.aufnehmen(JETZT, UTC)
    claude = snap.abos[0]
    assert claude.fehler == "keine Daten" and all(not b.bekannt and b.prozent == 0 for b in claude.balken)
    assert um.abo_meldungen(claude) == ["Claude: keine Messdaten (keine Daten)"]


def test_zurueckgesetztes_fenster_ist_neu_nicht_gemessen(umgebung, monkeypatch):
    k = Kontingent("Claude", (Fenster("5h", 0.0, JETZT - timedelta(minutes=1), True), Fenster("Woche", 5, JETZT + timedelta(days=1))), JETZT)
    monkeypatch.setattr(signale, "alle_lesen", lambda jetzt=None: [k, _k("Codex", 1, 2)])
    b = um.aufnehmen(JETZT, UTC).abos[0].balken[0]
    assert (b.prozent, b.text, b.bekannt) == (0, "neu, nicht gemessen", True)


def test_kopf_lage_automatik_und_themenzeilen(umgebung):
    anzeige.automatik_setzen(True)
    besitz.schreiben(besitz.pfad(umgebung / "repo", paare.laufend_bilden(THEMA)).parent / "thema-a.master", "claude")
    snap = um.aufnehmen(JETZT, UTC)
    assert snap.zeit == "09:00" and snap.lage == "1" and snap.lage_text == "Lage 1" and snap.automatik is True
    zeile = snap.themen[0]
    assert (zeile.thema, zeile.master, zeile.besitz, zeile.pruefer, zeile.auto) == (
        THEMA, "nach Kontingent", "claude", "Codex", "Auto an")
    assert zeile.master_wert == "kontingent"
    assert snap.schreiben and snap.schreib_hinweis == ""


def test_messfehler_steht_beim_abo(umgebung):
    signale.messfehler_setzen("claude", "netz", "Claude-Kontingent konnte nicht gelesen werden",
                              jetzt=datetime(2026, 10, 28, 8, 12, tzinfo=UTC))
    snap = um.aufnehmen(JETZT, UTC)
    assert snap.abos[0].messfehler == ("Claude-Messung scheitert seit 08:12 (letzter Versuch 08:12): "
                                       "Claude-Kontingent konnte nicht gelesen werden")
    assert snap.abos[1].messfehler is None


def test_kaputte_messfehlerdatei_und_unlesbarer_datenordner_stuerzen_nicht_ab(umgebung):
    (umgebung / "daten" / "messfehler.json").write_text("{kaputt", encoding="utf-8")
    assert um.aufnehmen(JETZT, UTC).abos[0].messfehler is None


def test_wartet_und_sitzungen_kommen_aus_den_kurz_bausteinen(umgebung):
    from master_schalter import status, wartet
    status.schreiben("claude", "eins-sitzung", status.RUHT, "Stop")
    wartet.setzen(THEMA, "auf Freigabe")
    snap = um.aufnehmen(datetime.now(UTC), UTC)
    assert any(s.startswith("Sitzung Claude eins-sit") for s in snap.sitzungen)
    assert any(f"{THEMA}: auf Freigabe" in z for z in snap.wartet)
    assert str(umgebung) not in "\n".join(snap.sitzungen + snap.wartet + snap.hinweise)


def test_aufnehmen_liest_nur(umgebung):
    vorher = sorted((p, p.stat().st_mtime_ns) for p in umgebung.rglob("*") if p.is_file())
    um.aufnehmen(JETZT, UTC)
    assert sorted((p, p.stat().st_mtime_ns) for p in umgebung.rglob("*") if p.is_file()) == vorher


def test_leer_sperrt_alles(umgebung):
    snap = um.leer("Aktualisierung fehlgeschlagen (OSError)", JETZT, UTC)
    assert snap.hinweise == ("Aktualisierung fehlgeschlagen (OSError)",) and not snap.schreiben
    with pytest.raises(um.AktionAbgelehnt):
        um.alle_aktion(snap, "kontingent")


# --- Repo-Ort ------------------------------------------------------------------------------------------------

def test_aus_dem_worktree_trifft_anzeige_und_schreiben_den_hauptbaum(umgebung, monkeypatch):
    haupt, baum = _worktree(umgebung, monkeypatch)
    besitz.schreiben(besitz.pfad(haupt, paare.laufend_bilden(THEMA)), "codex 2026-10-28T00:00:00+00:00 modus x")

    snap = um.aufnehmen(JETZT, UTC)

    assert snap.repo == haupt.resolve() or snap.repo == haupt
    assert snap.schreiben is True
    assert snap.themen[0].besitz == "codex"                                    # gelesen im Hauptbaum

    aufrufe = []
    monkeypatch.setattr(modi, "master_setzen", lambda *a, **k: aufrufe.append((a, k)))
    ergebnis = um.master_aktion(snap, THEMA, "claude").ausfuehren()
    assert ergebnis.ok and aufrufe == [((THEMA, "claude"), {"repo": snap.repo})]


def test_echtes_schreiben_aus_dem_worktree_landet_im_hauptbaum(umgebung, monkeypatch):
    haupt, baum = _worktree(umgebung, monkeypatch)
    snap = um.aufnehmen(JETZT, UTC)
    ergebnis = um.master_aktion(snap, THEMA, "codex").ausfuehren()
    assert ergebnis.ok, ergebnis.text
    assert modi.profil(THEMA).master == "codex"
    assert not besitz.pfad(baum, paare.laufend_bilden(THEMA)).exists()         # nichts in der Arbeitskopie


def test_gescheiterte_commondir_aufloesung_sperrt_alle_schreibaktionen(umgebung, monkeypatch):
    haupt, baum = _worktree(umgebung, monkeypatch, commondir_ok=False)

    def nie(*_a, **_k):
        raise AssertionError("es darf nichts geschrieben werden")

    monkeypatch.setattr(modi, "master_setzen", nie)
    monkeypatch.setattr(alle, "auf_kontingent", nie)
    monkeypatch.setattr(alle, "zurueck", nie)

    snap = um.aufnehmen(JETZT, UTC)

    assert snap.repo == baum and snap.schreiben is False and snap.schreib_hinweis == um.NUR_ANZEIGE
    for bau in (lambda: um.master_aktion(snap, THEMA, "claude"), lambda: um.alle_aktion(snap, "kontingent"),
                lambda: um.alle_aktion(snap, "zurueck")):
        with pytest.raises(um.AktionAbgelehnt, match="Hauptarbeitsbaum nicht gefunden"):
            bau()
    assert not besitz.pfad(haupt, paare.laufend_bilden(THEMA)).exists()
    assert not besitz.pfad(baum, paare.laufend_bilden(THEMA)).exists()


def test_repo_nicht_bestimmbar_sperrt_schreiben(umgebung, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(umgebung / "gibt-es-nicht"))
    snap = um.aufnehmen(JETZT, UTC)
    assert snap.repo is None and not snap.schreiben and snap.schreib_hinweis == um.NUR_ANZEIGE
    assert "Repo nicht gefunden" in " ".join(snap.hinweise)
    with pytest.raises(um.AktionAbgelehnt):
        um.master_aktion(snap, THEMA, "claude")


def test_git_wird_unmittelbar_vor_dem_schreiben_noch_einmal_geprueft(umgebung, monkeypatch):
    snap = um.aufnehmen(JETZT, UTC)
    aktion = um.master_aktion(snap, THEMA, "claude")
    (umgebung / "repo" / ".git").rmdir()
    monkeypatch.setattr(modi, "master_setzen", lambda *a, **k: pytest.fail("geschrieben"))
    ergebnis = aktion.ausfuehren()
    assert not ergebnis.ok and ergebnis.text == um.NUR_ANZEIGE


# --- Aktionen ----------------------------------------------------------------------------------------------------

def test_master_aktion_hat_rueckfrage_und_ruft_setter_nur_beim_ausfuehren(umgebung, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(modi, "master_setzen", lambda *a, **k: aufrufe.append((a, k)))
    snap = um.aufnehmen(JETZT, UTC)

    aktion = um.master_aktion(snap, THEMA, "hermes")

    assert aufrufe == []                                                       # Bauen ändert nichts (Rückfrage „Nein“)
    assert THEMA in aktion.frage and "Nach Kontingent" in aktion.frage and "Hermes" in aktion.frage
    ergebnis = aktion.ausfuehren()
    assert aufrufe == [((THEMA, "hermes"), {"repo": snap.repo})]
    assert ergebnis.ok and ergebnis.text == anzeige.master_meldung(THEMA, "hermes")


@pytest.mark.parametrize("thema, wert, meldung", [
    ("gibt-es-nicht", "claude", "nicht bekannt"), (THEMA, "gott", "Unbekannte Masterrolle"),
    (THEMA, "kontingent", "schon"),
])
def test_master_aktion_lehnt_unsinn_ab(umgebung, thema, wert, meldung):
    with pytest.raises(um.AktionAbgelehnt, match=meldung):
        um.master_aktion(um.aufnehmen(JETZT, UTC), thema, wert)


def test_master_fehler_wird_zum_ergebnis_ohne_absturz(umgebung, monkeypatch):
    def kaputt(*_a, **_k):
        raise modi.ModusFehler("gesperrt\nzweite Zeile")

    monkeypatch.setattr(modi, "master_setzen", kaputt)
    ergebnis = um.master_aktion(um.aufnehmen(JETZT, UTC), THEMA, "claude").ausfuehren()
    assert not ergebnis.ok and ergebnis.text == f"{THEMA}: nicht geändert – gesperrt zweite Zeile"


@pytest.mark.parametrize("richtung, name", [("kontingent", "auf_kontingent"), ("zurueck", "zurueck")])
def test_sammelaktionen_rufen_die_richtige_funktion_mit_dem_repo_der_aufnahme(umgebung, monkeypatch, richtung, name):
    aufrufe = []
    monkeypatch.setattr(alle, name, lambda **k: aufrufe.append(k) or alle.Bericht(["a: ok", "b: ok"], 0))
    snap = um.aufnehmen(JETZT, UTC)

    aktion = um.alle_aktion(snap, richtung)
    assert aufrufe == [] and aktion.frage
    ergebnis = aktion.ausfuehren()

    assert aufrufe == [{"repo": snap.repo}]
    assert ergebnis.ok and ergebnis.bericht == "a: ok\nb: ok"


def test_sammelaktion_offene_themen_und_fehler(umgebung, monkeypatch):
    monkeypatch.setattr(alle, "auf_kontingent", lambda **k: alle.Bericht(["a: offen: x"], 1))
    snap = um.aufnehmen(JETZT, UTC)
    ergebnis = um.alle_aktion(snap, "kontingent").ausfuehren()
    assert not ergebnis.ok and "1 offen" in ergebnis.text

    def kaputt(**_k):
        raise alle.MerkFehler("Merkdatei ist kein gültiges JSON")

    monkeypatch.setattr(alle, "zurueck", kaputt)
    ergebnis = um.alle_aktion(snap, "zurueck").ausfuehren()
    assert not ergebnis.ok and "nichts geändert" in ergebnis.text
    with pytest.raises(um.AktionAbgelehnt):
        um.alle_aktion(snap, "quer")


def test_echtes_alle_nach_kontingent_und_zurueck_im_repo_der_aufnahme(umgebung):
    modi.master_setzen(THEMA, "claude", repo=umgebung / "repo")
    snap = um.aufnehmen(JETZT, UTC)
    assert um.alle_aktion(snap, "kontingent").ausfuehren().ok
    assert modi.profil(THEMA).master == "kontingent"
    assert um.alle_aktion(um.aufnehmen(JETZT, UTC), "zurueck").ausfuehren().ok
    assert modi.profil(THEMA).master == "claude"


def test_automatik_aktion_schaltet_um_und_fragt_vorher(umgebung):
    snap = um.aufnehmen(JETZT, UTC)
    assert snap.automatik is False
    an = um.automatik_aktion(snap)
    assert "einschalten" in an.frage and anzeige.automatik_an() is False       # bis zur Rückfrage unverändert
    assert an.ausfuehren().text == "Automatik an." and anzeige.automatik_an() is True
    aus = um.automatik_aktion(um.aufnehmen(JETZT, UTC))
    assert "ausschalten" in aus.frage
    assert aus.ausfuehren().text == "Automatik aus." and anzeige.automatik_an() is False


def test_automatik_schreibfehler_wird_ergebnis(umgebung, monkeypatch):
    monkeypatch.setattr(anzeige, "automatik_setzen", lambda an: (_ for _ in ()).throw(OSError("gesperrt")))
    ergebnis = um.automatik_aktion(um.aufnehmen(JETZT, UTC)).ausfuehren()
    assert not ergebnis.ok and "nicht geändert" in ergebnis.text


# --- Fenster starten -----------------------------------------------------------------------------------------------

def test_modul_befehl_bevorzugt_pythonw(tmp_path, monkeypatch):
    (tmp_path / "python.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(um.sys, "executable", str(tmp_path / "python.exe"))
    assert um.modul_befehl("fenster") == [str(tmp_path / "python.exe"), "-m", "master_schalter.fenster"]
    (tmp_path / "pythonw.exe").write_text("", encoding="utf-8")
    assert um.modul_befehl("uebersicht") == [str(tmp_path / "pythonw.exe"), "-m", "master_schalter.uebersicht"]


def test_uebergabe_starten_oeffnet_fenster_py_als_eigenen_prozess(monkeypatch):
    aufrufe = []
    monkeypatch.setattr(um.subprocess, "Popen", lambda befehl, **kw: aufrufe.append((befehl, kw)))
    ergebnis = um.uebergabe_starten()
    assert ergebnis.ok and len(aufrufe) == 1
    befehl, kw = aufrufe[0]
    assert befehl[-2:] == ["-m", "master_schalter.fenster"]
    assert kw["stdin"] is kw["stdout"] is kw["stderr"] is subprocess.DEVNULL
    assert kw["env"]["PYTHONPATH"].split(um.os.pathsep)[0] == str(Path(um.__file__).resolve().parent.parent)


def test_uebergabe_starten_fehler_nennt_nur_die_klasse(monkeypatch):
    monkeypatch.setattr(um.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError("C:/geheim/python.exe")))
    ergebnis = um.uebergabe_starten()
    assert not ergebnis.ok and "OSError" in ergebnis.text and "geheim" not in ergebnis.text


# --- R1-Befunde 2 und 3 ---------------------------------------------------------------------------------------

def test_leer_kennt_den_automatikzustand_nicht_und_bietet_kein_umschalten(umgebung):
    snap = um.leer("Aktualisierung fehlgeschlagen (OSError)", JETZT, UTC)
    assert snap.automatik is None and snap.abos == ()
    with pytest.raises(um.AktionAbgelehnt, match="unbekannt"):
        um.automatik_aktion(snap)


@pytest.mark.parametrize("wert", [96.6, 79.6])
def test_balkenfarbe_kommt_aus_dem_ungerundeten_wert_wie_beim_symbol(umgebung, monkeypatch, wert):
    monkeypatch.setattr(signale, "alle_lesen", lambda jetzt=None: [_k("Claude", wert, 1), _k("Codex", 1, 2)])
    balken = um.aufnehmen(JETZT, UTC).abos[0].balken[0]
    erwartet = "#{:02x}{:02x}{:02x}".format(*symbol.farbe(wert, symbol.CLAUDE, anzeige.schwelle()))
    assert balken.prozent == round(wert) and balken.farbe == erwartet
    assert balken.farbe != "#{:02x}{:02x}{:02x}".format(*symbol.farbe(round(wert), symbol.CLAUDE, anzeige.schwelle()))
