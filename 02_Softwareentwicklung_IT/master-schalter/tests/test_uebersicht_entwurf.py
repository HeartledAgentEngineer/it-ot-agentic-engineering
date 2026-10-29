from __future__ import annotations

from dataclasses import replace

import pytest

from master_schalter import arbeitsweise, modi
from master_schalter import uebersicht_modell as um
from master_schalter.uebersicht_entwurf import EntwurfsVerwaltung, EntwurfFehler


def _zeile(thema: str, *, worker: str = "claude", modell: str | None = "claude-a",
           master: str = "kontingent", arbeitsart: str = arbeitsweise.PROTOKOLL,
           paar: bool | None = True) -> um.ThemaZeile:
    return um.ThemaZeile(thema, "Aufgelöst", "Besitz Claude", "Prüfer", "Ausführer", "Auto aus",
                         master, arbeitsart, worker, paar_aktiv=paar, modell_wert=modell)


def _snap(*zeilen: um.ThemaZeile, wechsel: tuple[str, ...] = (), pruefbar: bool = True,
          schreiben: bool = True, kataloge: tuple[um.KatalogAnsicht, ...] | None = None) -> um.Uebersicht:
    snap = um.Uebersicht("10:00", None, "Lage ?", False, 80, (), zeilen, (), (), (), None,
                         schreiben, "" if schreiben else um.NUR_ANZEIGE,
                         kataloge if kataloge is not None else (
                             um.KatalogAnsicht("claude", True, (("claude-a", "Claude A"), ("claude-b", "Claude B"))),
                             um.KatalogAnsicht("codex", True, (("gpt-6-luna", "GPT Luna"),))))
    object.__setattr__(snap, "wechsel_themen", wechsel)
    object.__setattr__(snap, "wechsel_pruefbar", pruefbar)
    return snap


def test_entwuerfe_bleiben_an_thema_und_feld_gebunden() -> None:
    verwaltung = EntwurfsVerwaltung(_snap(_zeile("alpha"), _zeile("beta")))
    verwaltung.waehlen("beta", "master", "hermes")
    verwaltung.waehlen("beta", "pruefer", "codex")

    assert verwaltung.zeile("alpha").master_wert == "kontingent"
    assert verwaltung.zeile("beta").master_wert == "hermes"
    assert verwaltung.zeile("beta").pruefer_wert == "codex"
    assert [(a.thema, a.feld, a.alt, a.neu) for a in verwaltung.aenderungen()] == [
        ("beta", "master", "kontingent", "hermes"), ("beta", "pruefer", "automatisch", "codex")]


def test_ausfuehrerwechsel_setzt_modell_zurueck_und_zeigt_beide_aenderungen() -> None:
    verwaltung = EntwurfsVerwaltung(_snap(_zeile("alpha")))
    verwaltung.waehlen("alpha", "ausfuehrer", "codex")

    assert verwaltung.zeile("alpha").worker_wert == "codex"
    assert verwaltung.zeile("alpha").modell_wert is None
    assert [(a.feld, a.alt, a.neu) for a in verwaltung.aenderungen()] == [
        ("ausfuehrer", "claude", "codex"), ("modell", "claude-a", None)]


def test_neues_modell_muss_im_geprueften_katalog_des_entwurfsanbieters_liegen() -> None:
    verwaltung = EntwurfsVerwaltung(_snap(_zeile("alpha")))
    verwaltung.waehlen("alpha", "ausfuehrer", "codex")
    with pytest.raises(EntwurfFehler, match="geprüften Codex-Katalog"):
        verwaltung.waehlen("alpha", "modell", "claude-b")
    verwaltung.waehlen("alpha", "modell", "gpt-6-luna")
    assert verwaltung.zeile("alpha").modell_wert == "gpt-6-luna"


def test_bisheriges_modell_ausserhalb_katalog_bleibt_istwert_aber_nicht_neue_wahl() -> None:
    snap = _snap(_zeile("alpha", modell="alt-modell"))
    verwaltung = EntwurfsVerwaltung(snap)
    assert verwaltung.zeile("alpha").modell_wert == "alt-modell"
    with pytest.raises(EntwurfFehler, match="geprüften Claude-Katalog"):
        verwaltung.waehlen("alpha", "modell", "alt-modell")


def test_snapshot_refresh_erhaelt_entwurf_und_markiert_geaenderte_basis_als_konflikt() -> None:
    verwaltung = EntwurfsVerwaltung(_snap(_zeile("alpha")))
    verwaltung.waehlen("alpha", "master", "hermes")
    verwaltung.aktualisieren(_snap(_zeile("alpha", master="codex")))

    aenderung, = verwaltung.aenderungen()
    assert aenderung.neu == "hermes" and aenderung.konflikt
    assert verwaltung.zeile("alpha").master_wert == "hermes"


def test_externer_ausfuehrerwechsel_konfliktiert_modellentwurf_auch_bei_gleicher_modellkennung() -> None:
    kataloge = (
        um.KatalogAnsicht("claude", True, (("shared", "Shared"), ("shared-next", "Shared Next"))),
        um.KatalogAnsicht("codex", True, (("shared", "Shared"), ("shared-next", "Shared Next"))),
    )
    verwaltung = EntwurfsVerwaltung(_snap(_zeile("alpha", modell="shared"), kataloge=kataloge))
    verwaltung.waehlen("alpha", "modell", "shared-next")
    verwaltung.aktualisieren(_snap(_zeile("alpha", worker="codex", modell="shared"), kataloge=kataloge))

    modell, = verwaltung.aenderungen()
    assert modell.feld == "modell" and modell.konflikt
    assert "Ausführer" in modell.hinweis
    verwaltung.waehlen("alpha", "modell", "shared-next")
    modell, = verwaltung.aenderungen()
    assert not modell.konflikt and modell.hinweis == ""


def test_entfernter_themenentwurf_bleibt_als_nicht_uebernehmbarer_konflikt_sichtbar() -> None:
    verwaltung = EntwurfsVerwaltung(_snap(_zeile("alpha"), _zeile("beta")))
    verwaltung.waehlen("beta", "master", "hermes")
    verwaltung.aktualisieren(_snap(_zeile("alpha")))

    aenderung, = verwaltung.aenderungen()
    assert aenderung.thema == "beta" and aenderung.konflikt
    assert "entfernt" in aenderung.hinweis.lower()


def test_zuruecksetzen_verwirft_einzelnes_thema_oder_alle_entwuerfe() -> None:
    verwaltung = EntwurfsVerwaltung(_snap(_zeile("alpha"), _zeile("beta")))
    verwaltung.waehlen("alpha", "master", "hermes")
    verwaltung.waehlen("beta", "master", "codex")
    verwaltung.zuruecksetzen("alpha")
    assert [a.thema for a in verwaltung.aenderungen()] == ["beta"]
    verwaltung.zuruecksetzen()
    assert verwaltung.aenderungen() == ()


@pytest.mark.parametrize("snap, thema, meldung", [
    (_snap(_zeile("alpha"), pruefbar=False), "alpha", "Wechselstatus nicht prüfbar"),
    (_snap(_zeile("alpha"), wechsel=("alpha",)), "alpha", "Wechsel läuft"),
    (_snap(_zeile("alpha"), schreiben=False), "alpha", "nur Anzeige"),
])
def test_gesperrter_aufnahmezustand_verhindert_neue_entwuerfe(snap, thema, meldung) -> None:
    verwaltung = EntwurfsVerwaltung(snap)
    with pytest.raises(EntwurfFehler, match=meldung):
        verwaltung.waehlen(thema, "master", "hermes")


def test_vibe_wird_gegen_den_vollstaendigen_entwurf_geprueft() -> None:
    verwaltung = EntwurfsVerwaltung(_snap(_zeile("alpha")))
    verwaltung.waehlen("alpha", "ausfuehrer", "codex")
    verwaltung.waehlen("alpha", "arbeitsweise", "vibe")
    eintraege = verwaltung.aenderungen()
    assert {a.feld for a in eintraege} == {"ausfuehrer", "modell", "arbeitsweise"}
    assert all("Vibe" in a.hinweis and "Claude" in a.hinweis
               for a in eintraege if a.feld in ("ausfuehrer", "arbeitsweise"))


def test_ungepruefter_katalog_blockiert_pruefung_aber_zeigt_entwurfshinweis() -> None:
    kataloge = (um.KatalogAnsicht("claude", False), um.KatalogAnsicht("codex", False))
    verwaltung = EntwurfsVerwaltung(_snap(_zeile("alpha"), kataloge=kataloge))
    verwaltung.waehlen("alpha", "ausfuehrer", "codex")
    with pytest.raises(EntwurfFehler, match="geprüften Codex-Katalog"):
        verwaltung.waehlen("alpha", "modell", "gpt-6-luna")
