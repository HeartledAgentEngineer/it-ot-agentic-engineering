"""Tests für Multi-Plattform Limits & Verbräuche (Gemini/Argon, ChatGPT, Claude, OpenRouter)."""
import tkinter as tk
import pytest
from master_schalter import signale
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


def test_alle_limits_lesen_enthaelt_alle_vier_anbieter():
    limits = signale.alle_limits_lesen()
    anbieter = [l.anbieter for l in limits]
    assert "Claude" in anbieter
    assert "Codex" in anbieter
    assert "Gemini" in anbieter
    assert "OpenRouter" in anbieter

    gemini = next(l for l in limits if l.anbieter == "Gemini")
    assert "Argon-Limit" in gemini.details
    assert "Gemini 2.5 Pro" in gemini.details
    assert "Gemini 3.8 Flash" in gemini.details


def test_limits_dialog_laesst_sich_oeffnen(wurzel):
    f = Fenster(wurzel, starten=False)
    assert hasattr(f, "limits_knopf")
    # Dialog aufrufen
    f.limits_dialog_oeffnen()
    # Der modale Dialog wurde als Toplevel erzeugt:
    toplevels = [w for w in wurzel.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(toplevels) >= 1
    dlg = toplevels[-1]
    assert "Limits & Verbräuche" in dlg.title()
    dlg.destroy()
