"""Tests der Auswahllisten der Übersicht (Stufe 4, Teil I): Prüfer, Ausführer, Modell, Auto – bildschirmfrei.

Alles synthetisch: Datenordner und Repo liegen unter `tmp_path`; Kataloge und Kontingente sind Attrappen.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from master_schalter import anzeige, arbeitsweise, besitz, cli, modelle, modi, paare, pruefer_wahl, signale
from master_schalter import uebersicht_modell as um
from master_schalter.signale import Fenster, Kontingent

UTC = timezone.utc
JETZT = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
THREAD = "00000000-0000-4000-8000-0000000000f1"
THEMA = "thema-a"


def _k(name, fuenf, woche):
    return Kontingent(name, (Fenster("5h", fuenf, JETZT + timedelta(hours=2)),
                             Fenster("Woche", woche, JETZT + timedelta(days=3))), JETZT - timedelta(minutes=5))


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    daten = tmp_path / "daten"
    daten.mkdir()
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(daten))
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    monkeypatch.setattr(signale, "alle_lesen", lambda jetzt=None: [_k("Claude", 10, 20), _k("Codex", 1, 2)])
    paare.setzen(THEMA, THREAD, paare.laufend_bilden(THEMA), aktiv=True)
    besitz.schreiben(besitz.pfad(repo, paare.laufend_bilden(THEMA)), "claude 2026-10-28T00:00:00+00:00 modus x")
    return tmp_path


def _katalog(provider, *ids, fehler=None, veraltet=False):
    return modelle.Katalog(provider, tuple(modelle.Modell(i, f"Name {i}") for i in ids), JETZT, fehler, veraltet)


@pytest.fixture
def kataloge(monkeypatch):
    """Gültige Kataloge für claude und codex (auch für `modi._katalog_pruefen`, das `modelle.lesen` nutzt)."""
    stand = {"claude": _katalog("claude", "claude-a", "claude-b"), "codex": _katalog("codex", "gpt-6-luna", "gpt-6-sol")}
    monkeypatch.setattr(modelle, "lesen", lambda provider, **kw: stand[provider])
    return stand


def _snap():
    return um.aufnehmen(JETZT, UTC)


def _zeile(snap=None, thema=THEMA):
    return next(t for t in (snap or _snap()).themen if t.thema == thema)


# --- Aufnahme ---------------------------------------------------------------------------------------------------

def test_aufnahme_liefert_die_neuen_felder(umgebung, kataloge):
    snap = _snap()
    zeile = _zeile(snap)
    assert (zeile.pruefer_wert, zeile.pruefer_warnung, zeile.paar_aktiv, zeile.modell_wert, zeile.pk_master) == (
        "automatisch", False, True, None, "claude")
    assert zeile.auto_zustand == anzeige.AUTO_WARTET                      # Paar aktiv, aber Hauptschalter aus
    assert [(k.anbieter, k.geprueft, k.modelle) for k in snap.kataloge] == [
        ("claude", True, (("claude-a", "Name claude-a"), ("claude-b", "Name claude-b"))),
        ("codex", True, (("gpt-6-luna", "Name gpt-6-luna"), ("gpt-6-sol", "Name gpt-6-sol")))]


def test_aufnahme_katalog_veraltet_fehlerhaft_oder_defekt_ist_nicht_geprueft(umgebung, monkeypatch):
    def lesen(provider, **kw):
        if provider == "claude":
            return _katalog("claude", "x", veraltet=True)
        return _katalog("codex", "y", fehler=modelle.ANTWORT_UNGUELTIG)

    monkeypatch.setattr(modelle, "lesen", lesen)
    assert [(k.anbieter, k.geprueft, k.modelle) for k in _snap().kataloge] == [("claude", False, ()), ("codex", False, ())]
    monkeypatch.setattr(modelle, "lesen", lambda provider, **kw: (_ for _ in ()).throw(modelle.KatalogFehler("kaputt")))
    assert all(not k.geprueft for k in _snap().kataloge)


def test_aufnahme_ohne_cache_datei_ist_nicht_geprueft(umgebung):
    assert all(not k.geprueft for k in _snap().kataloge)


# --- Auto: wirksamer Zustand (R1-2) --------------------------------------------------------------------------------

@pytest.mark.parametrize("schalter, paar, master, erwartet, text", [
    (True, True, "kontingent", "wirksam", "Auto an (wirksam)"),
    (False, True, "kontingent", "wartet", "Freigabe an – wirkt nicht: Hauptschalter aus"),
    (True, True, "claude", "wartet", "Freigabe an – wirkt nicht: fester Master Claude"),
    (True, False, "kontingent", "aus", "Freigabe aus"),
])
def test_auto_spalte_zeigt_den_wirksamen_zustand(umgebung, schalter, paar, master, erwartet, text):
    anzeige.automatik_setzen(schalter)
    paare.aktiv_setzen(THEMA, paar)
    modi.master_setzen(THEMA, master, repo=umgebung / "repo")
    zeile = _zeile()
    assert zeile.auto_zustand == erwartet and zeile.auto == text


def test_thema_ohne_paar_hat_keinen_auto_schalter(umgebung):
    modi.thema_anlegen("ohne-paar", "kontingent")
    zeile = _zeile(thema="ohne-paar")
    assert (zeile.paar_aktiv, zeile.auto_zustand, zeile.auto) == (None, anzeige.AUTO_OHNE_PAAR, "ohne Codex-Paar")
    with pytest.raises(um.AktionAbgelehnt, match="ohne Codex-Paar"):
        um.auto_aktion(_snap(), "ohne-paar", True)


def test_auto_aktion_schaltet_nur_die_paarfreigabe_und_nie_den_hauptschalter(umgebung, monkeypatch):
    monkeypatch.setattr(anzeige, "automatik_setzen", lambda *a, **k: pytest.fail("Hauptschalter berührt"))
    snap = _snap()
    assert snap.automatik is False and _zeile(snap).paar_aktiv is True
    aus = um.auto_aktion(snap, THEMA, False)
    assert "ausschalten" in aus.frage and "Hauptschalter bleibt unverändert" in aus.frage
    assert paare.lesen()[0].aktiv is True                                      # Bauen ändert nichts (Rückfrage „Nein“)
    ergebnis = aus.ausfuehren()
    assert ergebnis.ok and "Freigabe aus" in ergebnis.text and paare.lesen()[0].aktiv is False
    an = um.auto_aktion(_snap(), THEMA, True)
    assert "wirkt erst" in an.frage and "Hauptschalter bleibt unverändert" in an.frage
    ergebnis = an.ausfuehren()
    assert ergebnis.ok and "wirkt nicht: Hauptschalter aus" in ergebnis.text and paare.lesen()[0].aktiv is True
    assert anzeige.automatik_an() is False                                     # Hauptschalter unverändert


def test_auto_aktion_lehnt_gleichen_wert_und_nur_anzeige_ab(umgebung):
    with pytest.raises(um.AktionAbgelehnt, match="schon An"):
        um.auto_aktion(_snap(), THEMA, True)
    (umgebung / "repo" / ".git").rmdir()
    with pytest.raises(um.AktionAbgelehnt, match="nur Anzeige"):
        um.auto_aktion(_snap(), THEMA, False)


def test_auto_fehler_wird_ergebnis(umgebung, monkeypatch):
    aktion = um.auto_aktion(_snap(), THEMA, False)
    monkeypatch.setattr(paare, "aktiv_setzen", lambda *a: (_ for _ in ()).throw(paare.PaarFehler("weg\nzweite Zeile")))
    ergebnis = aktion.ausfuehren()
    assert not ergebnis.ok and ergebnis.text == f"{THEMA}: nicht geändert – weg zweite Zeile"


# --- Prüfer -----------------------------------------------------------------------------------------------------

def test_pruefer_aktion_fragt_und_schreibt_erst_beim_ausfuehren(umgebung):
    aktion = um.pruefer_aktion(_snap(), THEMA, "hermes")
    assert "Hermes" in aktion.frage and "--sensibel" in aktion.frage and "Familie" in aktion.frage
    assert not pruefer_wahl.datei().exists()                                   # „Nein“ ⇒ nichts geändert
    ergebnis = aktion.ausfuehren()
    assert ergebnis.ok and pruefer_wahl.wahl(THEMA) == "hermes"
    zeile = _zeile()
    assert zeile.pruefer_wert == "hermes" and zeile.pruefer == "Hermes · DeepSeek V4.1 Flash (gewählt)"
    assert not zeile.pruefer_warnung
    um.pruefer_aktion(_snap(), THEMA, "automatisch").ausfuehren()
    assert pruefer_wahl.wahl(THEMA) == "automatisch"


def test_pruefer_gleiche_familie_warnt_in_zeile_und_frage(umgebung):
    besitz.schreiben(besitz.pfad(umgebung / "repo", paare.laufend_bilden(THEMA)), "codex 2026-10-28T00:00:00+00:00 modus x")
    aktion = um.pruefer_aktion(_snap(), THEMA, "codex")
    assert "Achtung: gleiche Familie wie der Master" in aktion.frage and "AGENTS.md" in aktion.frage
    aktion.ausfuehren()
    zeile = _zeile()
    assert zeile.pruefer_warnung and "gleiche Familie wie Master" in zeile.pruefer


def test_pruefer_aktion_ablehnungen(umgebung):
    snap = _snap()
    with pytest.raises(um.AktionAbgelehnt, match="schon Automatisch"):
        um.pruefer_aktion(snap, THEMA, "automatisch")
    with pytest.raises(um.AktionAbgelehnt, match="Unbekannter Prüfer"):
        um.pruefer_aktion(snap, THEMA, "gpt")
    with pytest.raises(um.AktionAbgelehnt, match="nicht bekannt"):
        um.pruefer_aktion(snap, "gibtsnicht", "codex")
    pruefer_wahl.datei().write_text("{kaputt", encoding="utf-8")
    kaputt = _snap()
    assert _zeile(kaputt).pruefer_wert == "?"
    with pytest.raises(um.AktionAbgelehnt, match="pruefer.json ungültig"):
        um.pruefer_aktion(kaputt, THEMA, "codex")
    assert pruefer_wahl.datei().read_text(encoding="utf-8") == "{kaputt"


# --- Ausführer ---------------------------------------------------------------------------------------------------

def test_ausfuehrer_aktion_ruft_worker_setzen_mit_dem_repo_der_aufnahme(umgebung, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(modi, "worker_setzen", lambda *a, **k: aufrufe.append((a, k)) or modi.Profil("kontingent", "codex"))
    snap = _snap()
    aktion = um.ausfuehrer_aktion(snap, THEMA, "codex")
    assert aufrufe == []
    assert "Workflow auf Codex" in aktion.frage and "zurückgesetzt" in aktion.frage
    ergebnis = aktion.ausfuehren()
    assert aufrufe == [((THEMA, "codex"), {"repo": snap.repo})]
    assert ergebnis.ok and ergebnis.text == anzeige.ausfuehrer_meldung(THEMA, "codex", None)


@pytest.mark.parametrize("ziel, satz", [
    ("hermes", "feste Kennung DeepSeek V4.1 Flash"),
    ("workflow", "kein festes Modell"),
    ("claude", "„Standard“ des Werkzeugs zurückgesetzt"),
])
def test_ausfuehrer_frage_nennt_die_ruecksetzung_je_ziel(umgebung, ziel, satz):
    if ziel == "workflow":
        modi.worker_setzen(THEMA, "codex", repo=umgebung / "repo")
    assert satz in um.ausfuehrer_aktion(_snap(), THEMA, ziel).frage


def test_echter_ausfuehrerwechsel_setzt_das_modell_zurueck(umgebung, kataloge):
    repo = umgebung / "repo"
    modi.worker_setzen(THEMA, "codex", repo=repo)
    modi.modell_setzen(THEMA, "gpt-6-luna", repo=repo)
    assert _zeile().modell_wert == "gpt-6-luna" and "bisher: gpt-6-luna" in um.ausfuehrer_aktion(_snap(), THEMA, "claude").frage
    assert um.ausfuehrer_aktion(_snap(), THEMA, "claude").ausfuehren().ok
    assert modi.profil(THEMA) == modi.Profil("kontingent", "claude", None)
    ergebnis = um.ausfuehrer_aktion(_snap(), THEMA, "hermes").ausfuehren()
    assert ergebnis.ok and modi.profil(THEMA).modell == modi.HERMES_MODELL
    assert "DeepSeek V4.1 Flash" in ergebnis.text or "Hermes" in ergebnis.text


def test_ausfuehrer_bei_vibe_ist_eine_modi_fehlermeldung(umgebung):
    repo = umgebung / "repo"
    modi.worker_setzen(THEMA, "claude", repo=repo)
    modi.vibe_setzen(THEMA, True)
    aktion = um.ausfuehrer_aktion(_snap(), THEMA, "codex")                     # wird nicht vorab abgelehnt …
    ergebnis = aktion.ausfuehren()                                             # … sondern von `modi` mit Grund
    assert not ergebnis.ok and "nicht geändert" in ergebnis.text and "Vibe" in ergebnis.text
    assert modi.profil(THEMA).worker == "claude" and arbeitsweise.arbeitsweise(THEMA) == "vibe"


def test_ausfuehrer_ablehnungen(umgebung):
    snap = _snap()
    with pytest.raises(um.AktionAbgelehnt, match="schon Workflow"):
        um.ausfuehrer_aktion(snap, THEMA, "workflow")
    with pytest.raises(um.AktionAbgelehnt, match="Unbekannter Ausführer"):
        um.ausfuehrer_aktion(snap, THEMA, "gpt")
    with pytest.raises(um.AktionAbgelehnt, match="nicht bekannt"):
        um.ausfuehrer_aktion(snap, "gibtsnicht", "claude")
    (umgebung / "repo" / ".git").rmdir()
    with pytest.raises(um.AktionAbgelehnt, match="nur Anzeige"):
        um.ausfuehrer_aktion(_snap(), THEMA, "claude")


# --- Modellliste (R1-1) ---------------------------------------------------------------------------------------------------

def _roh(worker, modell=None):
    return um.ThemaZeile(THEMA, "m", "claude", "p", "a", "x", "kontingent", worker_wert=worker, modell_wert=modell)


GUT = (um.KatalogAnsicht("claude", True, (("claude-a", "Claude A"), ("claude-b", "Claude B"))),
       um.KatalogAnsicht("codex", True, (("gpt-6-luna", "GPT Luna"),)))
SCHLECHT = (um.KatalogAnsicht("claude", False), um.KatalogAnsicht("codex", False))


@pytest.mark.parametrize("worker, erwartet", [
    ("claude", [("Standard", None), ("Claude A", "claude-a"), ("Claude B", "claude-b")]),
    ("codex", [("Standard", None), ("GPT Luna", "gpt-6-luna")]),
])
def test_modellliste_mit_geprueftem_katalog_ist_standard_plus_katalog(worker, erwartet):
    liste = um.modell_liste(_roh(worker), GUT)
    assert list(liste.eintraege) == erwartet and not liste.gesperrt and liste.hinweis == "" and liste.aktuell == "Standard"


def test_modellliste_zeigt_das_gespeicherte_modell():
    assert um.modell_liste(_roh("claude", "claude-b"), GUT).aktuell == "Claude B"


@pytest.mark.parametrize("katalog", [SCHLECHT, ()], ids=["veraltet-oder-fehlerhaft", "fehlt"])
def test_modellliste_ohne_geprueften_katalog_nur_standard_und_gespeichertes(katalog):
    liste = um.modell_liste(_roh("claude"), katalog)
    assert list(liste.eintraege) == [("Standard", None)] and liste.hinweis == "Modellkatalog nicht geprüft"
    liste = um.modell_liste(_roh("codex", "gpt-6-luna"), katalog)
    assert list(liste.eintraege) == [("Standard", None), ("gpt-6-luna", "gpt-6-luna")]
    assert liste.aktuell == "gpt-6-luna" and liste.hinweis == "Modellkatalog nicht geprüft" and not liste.gesperrt


def test_modellliste_bleibt_sichtbar_wenn_das_gespeicherte_modell_nicht_im_katalog_steht():
    liste = um.modell_liste(_roh("claude", "alt-modell"), GUT)
    assert ("alt-modell", "alt-modell") in liste.eintraege and liste.aktuell == "alt-modell"


def test_modellliste_hermes_ist_gesperrt_ohne_standard():
    liste = um.modell_liste(_roh("hermes", modi.HERMES_MODELL), GUT)
    assert liste.gesperrt and list(liste.eintraege) == [("DeepSeek V4.1 Flash", modi.HERMES_MODELL)]
    assert liste.aktuell == "DeepSeek V4.1 Flash" and all(text != "Standard" for text, _ in liste.eintraege)


def test_modellliste_workflow_ist_gesperrt_ohne_festes_modell():
    liste = um.modell_liste(_roh("workflow"), GUT)
    assert liste.gesperrt and liste.eintraege == () and liste.aktuell == "— (nach Matrix aufgelöst)"


# --- Modell setzen ---------------------------------------------------------------------------------------------------------

def test_modell_aktion_ruft_modell_setzen_mit_dem_repo_der_aufnahme(umgebung, kataloge, monkeypatch):
    modi.worker_setzen(THEMA, "claude", repo=umgebung / "repo")
    aufrufe = []
    monkeypatch.setattr(modi, "modell_setzen", lambda *a, **k: aufrufe.append((a, k)) or modi.Profil("kontingent", "claude", "claude-a"))
    snap = _snap()
    aktion = um.modell_aktion(snap, THEMA, "claude-a")
    assert aufrufe == [] and "Standard auf Name claude-a" in aktion.frage
    ergebnis = aktion.ausfuehren()
    assert aufrufe == [((THEMA, "claude-a"), {"repo": snap.repo})]
    assert ergebnis.ok and ergebnis.text == anzeige.ausfuehrer_meldung(THEMA, "claude", "claude-a")


def test_echtes_modell_setzen_und_zurueck_auf_standard(umgebung, kataloge):
    modi.worker_setzen(THEMA, "codex", repo=umgebung / "repo")
    assert um.modell_aktion(_snap(), THEMA, "gpt-6-sol").ausfuehren().ok
    assert modi.profil(THEMA) == modi.Profil("kontingent", "codex", "gpt-6-sol")
    assert um.modell_aktion(_snap(), THEMA, None).ausfuehren().ok
    assert modi.profil(THEMA).modell is None


def test_modell_aktion_ablehnungen(umgebung, kataloge):
    with pytest.raises(um.AktionAbgelehnt, match="kein wählbares Modell"):           # Workflow
        um.modell_aktion(_snap(), THEMA, None)
    modi.worker_setzen(THEMA, "hermes", repo=umgebung / "repo")
    with pytest.raises(um.AktionAbgelehnt, match="Ausführer Hermes hat kein wählbares Modell"):
        um.modell_aktion(_snap(), THEMA, modi.HERMES_MODELL)
    modi.worker_setzen(THEMA, "claude", repo=umgebung / "repo")
    with pytest.raises(um.AktionAbgelehnt, match="nicht im geprüften Katalog"):
        um.modell_aktion(_snap(), THEMA, "erfunden")
    with pytest.raises(um.AktionAbgelehnt, match="schon Standard"):
        um.modell_aktion(_snap(), THEMA, None)


def test_modell_aktion_bei_ungeprueftem_katalog_bietet_keine_feste_wahl(umgebung, monkeypatch):
    monkeypatch.setattr(modelle, "lesen", lambda provider, **kw: _katalog(provider, "claude-a", veraltet=True))
    modi.worker_setzen(THEMA, "claude", repo=umgebung / "repo")
    snap = _snap()
    assert [text for text, _ in um.modell_liste(_zeile(snap), snap.kataloge).eintraege] == ["Standard"]
    with pytest.raises(um.AktionAbgelehnt, match="nicht im geprüften Katalog"):
        um.modell_aktion(snap, THEMA, "claude-a")


def test_modell_fehler_aus_modi_wird_ergebnis(umgebung, kataloge, monkeypatch):
    modi.worker_setzen(THEMA, "claude", repo=umgebung / "repo")
    aktion = um.modell_aktion(_snap(), THEMA, "claude-a")
    monkeypatch.setattr(modi, "modell_setzen", lambda *a, **k: (_ for _ in ()).throw(modi.ModusFehler("Katalog veraltet")))
    ergebnis = aktion.ausfuehren()
    assert not ergebnis.ok and ergebnis.text == f"{THEMA}: nicht geändert – Katalog veraltet"


# --- Zusammenspiel mit der CLI (gleiche Datei, gleiche Wirkung) --------------------------------------------------------------------

def test_cli_und_fenster_teilen_dieselbe_pruefer_datei(umgebung, capsys):
    assert cli.main(["pruefer-setzen", THEMA, "codex"]) == 0
    assert _zeile().pruefer_wert == "codex"
