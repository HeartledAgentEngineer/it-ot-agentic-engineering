from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from dataclasses import replace

import pytest

from master_schalter import uebersicht_modell as um
from master_schalter.uebersicht_tabelle import FELDER
from master_schalter.uebersicht import Fenster


@pytest.fixture(scope="module")
def _tk_wurzel():
    try:
        root = tk.Tk()
    except tk.TclError as fehler:
        pytest.skip(f"keine Tk-Anzeige verfügbar: {str(fehler)[:100]}")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def wurzel(_tk_wurzel):
    top = tk.Toplevel(_tk_wurzel)
    top.withdraw()
    yield top
    top.destroy()


def _zeile(thema: str, *, worker: str = "claude", paar: bool | None = True) -> um.ThemaZeile:
    return um.ThemaZeile(
        thema=thema,
        master="Kontingent",
        besitz="Codex · 10:00",
        pruefer="Automatisch",
        ausfuehrer="Claude",
        auto="Freigabe aus",
        master_wert="kontingent",
        worker_wert=worker,
        pruefer_wert="automatisch",
        paar_aktiv=paar,
        modell_wert=None,
        auto_zustand="aus",
    )


def _snap(*zeilen: um.ThemaZeile, wechsel: tuple[str, ...] = (), pruefbar: bool = True) -> um.Uebersicht:
    snap = um.Uebersicht(
        zeit="10:00", lage=None, lage_text="Lage ?", automatik=False, schwelle=80,
        abos=(), themen=zeilen, wartet=(), sitzungen=(), hinweise=(), repo=None,
        schreiben=True, schreib_hinweis="",
        kataloge=(
            um.KatalogAnsicht("claude", True, (("claude-a", "Claude A"),)),
            um.KatalogAnsicht("codex", True, (("gpt-6-luna", "GPT Luna"),)),
        ),
    )
    object.__setattr__(snap, "wechsel_themen", wechsel)
    object.__setattr__(snap, "wechsel_pruefbar", pruefbar)
    return snap


def test_jede_themenzeile_hat_sechs_fachlich_gebundene_dropdowns(wurzel) -> None:
    root = wurzel
    rueckfragen: list[str] = []
    try:
        fenster = Fenster(root, frage=lambda *_: rueckfragen.append("frage") or True, starten=False)
        tabelle = fenster.themen_tabelle
        fenster.snapshot_anwenden(_snap(_zeile("alpha"), _zeile("beta")))
        root.update_idletasks()

        assert set(tabelle.zeilen) == {"alpha", "beta"}
        for thema in ("alpha", "beta"):
            assert set(tabelle.zeilen[thema].felder) == set(FELDER)
            assert all(isinstance(w, ttk.Combobox) for w in tabelle.zeilen[thema].felder.values())

        # Jede Auswahl bleibt an Kennung und fachlicher Werteliste ihrer Zeile gebunden.
        for feld in FELDER:
            box = tabelle.zeilen["beta"].felder[feld]
            box.current(2 if feld == "ausfuehrer" else 1)
            box.event_generate("<<ComboboxSelected>>")
            root.update()
        assert [(a.feld, a.neu) for a in fenster._entwuerfe.aenderungen()] == list(zip(
            FELDER, (um.MASTER_WERTE[1], um.PRUEFER_WERTE[1], um.AUSFUEHRER_WERTE[2],
                     "gpt-6-luna", um.ARBEITSWEISE_WERTE[1], um.AUTO_WERTE[1])))
        assert not rueckfragen
        assert all(a.thema == "beta" for a in fenster._entwuerfe.aenderungen())
        assert len(fenster._entwuerfe.aenderungen()) == 6

        schreibgeschuetzt = _snap(_zeile("beta"))
        object.__setattr__(schreibgeschuetzt, "schreiben", False)
        tabelle.aktualisieren(schreibgeschuetzt, entwuerfe=fenster._entwuerfe)
        zustaende = {f: str(tabelle.zeilen["beta"].felder[f].cget("state")) for f in FELDER}
        assert all(state == "disabled" for state in zustaende.values()), zustaende

        assert "Entwurf für beta" in fenster.status_var.get()

        # Ein unveränderter Snapshot erhält dieselben Zeilenwidgets und Entwürfe.
        widgets = {feld: fenster.themen_tabelle.zeilen["beta"].felder[feld] for feld in FELDER}
        fenster.themen_tabelle.aktualisieren(fenster._snap, entwuerfe=fenster._entwuerfe)
        assert all(fenster.themen_tabelle.zeilen["beta"].felder[f] is w for f, w in widgets.items())
        assert len(fenster._entwuerfe.aenderungen()) == 6

        # Modell und Auto folgen der Aufnahme: Hermes/Workflow sind feste Anzeige,
        # eine fehlende Paarfreigabe sperrt Auto.
        hermes = replace(_zeile("hermes", worker="hermes"), modell_wert=um.modi.HERMES_MODELL)
        workflow = _zeile("workflow", worker="workflow", paar=None)
        neuer_snap = _snap(hermes, workflow)
        fenster._entwuerfe.aktualisieren(neuer_snap)
        fenster.themen_tabelle.aktualisieren(neuer_snap, entwuerfe=fenster._entwuerfe)
        hr = fenster.themen_tabelle.zeilen["hermes"]
        wr = fenster.themen_tabelle.zeilen["workflow"]
        assert str(hr.felder["modell"].cget("state")) == "disabled"
        assert tuple(hr.felder["modell"].cget("values")) == ("DeepSeek V4.1 Flash",)
        assert str(wr.felder["modell"].cget("state")) == "disabled"
        assert str(wr.felder["auto"].cget("state")) == "disabled"
    finally:
        pass


def test_pruefen_zeigt_vorschau_zuruecksetzen_verwirft_nur_lokalen_entwurf(wurzel) -> None:
    root = wurzel
    try:
        fenster = Fenster(root, starten=False)
        fenster.snapshot_anwenden(_snap(_zeile("projekt-a"), _zeile("projekt-b")))
        fenster._themenwert_aendern("projekt-a", "master", "hermes")
        assert fenster.entwurf_anzahl_var.get() == "1 offene Änderung"
        assert str(fenster.entwurf_uebernehmen_knopf.cget("state")) == "disabled"

        gesehen: list[str] = []

        def prueftext_lesen() -> None:
            dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
            textfelder: list[tk.Text] = []

            def suchen(widget: tk.Misc) -> None:
                if isinstance(widget, tk.Text):
                    textfelder.append(widget)
                for kind in widget.winfo_children():
                    suchen(kind)

            suchen(dialog)
            gesehen.append(textfelder[0].get("1.0", "end"))
            dialog.destroy()

        root.after(50, prueftext_lesen)
        fenster.entwurf_pruefen()
        assert "projekt-a · master" in gesehen[0] and "'kontingent' → 'hermes'" in gesehen[0]
        assert fenster.entwurf_anzahl_var.get() == "1 offene Änderung"

        fenster.entwurf_zuruecksetzen()
        assert fenster._entwuerfe.aenderungen() == ()
        assert fenster.entwurf_anzahl_var.get() == "Keine offenen Entwürfe"
        assert fenster._snap.themen[0].master_wert == "kontingent"
    finally:
        pass


def test_laufender_wechsel_sperrt_nur_die_betroffene_themenzeile(wurzel) -> None:
    fenster = Fenster(wurzel, starten=False)
    fenster.snapshot_anwenden(_snap(_zeile("alpha"), _zeile("beta"), wechsel=("alpha",)))
    a = fenster.themen_tabelle.zeilen["alpha"]
    b = fenster.themen_tabelle.zeilen["beta"]

    assert all(str(a.felder[f].cget("state")) == "disabled" for f in FELDER)
    assert all(str(b.felder[f].cget("state")) == "readonly" for f in FELDER)
    assert "Wechsel läuft" in a.details.cget("text")


def test_unbekannter_wechselstatus_sperrt_edits_zeigt_entwurf_und_erlaubt_reset(wurzel) -> None:
    fenster = Fenster(wurzel, starten=False)
    fenster.snapshot_anwenden(_snap(_zeile("alpha"), _zeile("beta")))
    fenster._themenwert_aendern("beta", "master", "hermes")
    assert fenster.entwurf_anzahl_var.get() == "1 offene Änderung"

    unbekannt = _snap(_zeile("alpha"), _zeile("beta"), pruefbar=False)
    fenster.snapshot_anwenden(unbekannt)
    beta = fenster.themen_tabelle.zeilen["beta"]
    assert all(str(beta.felder[f].cget("state")) == "disabled" for f in FELDER)
    assert beta.felder["master"].get() == "Hermes"
    assert "Wechselstatus nicht prüfbar" in beta.details.cget("text")
    assert fenster.entwurf_anzahl_var.get() == "1 offene Änderung"

    fenster.entwurf_zuruecksetzen()
    assert fenster.entwurf_anzahl_var.get() == "Keine offenen Entwürfe"
    assert fenster._snap.themen[1].master_wert == "kontingent"
