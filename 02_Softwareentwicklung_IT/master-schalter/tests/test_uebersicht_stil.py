"""Tests des dunklen Aussehens: Stile existieren, Farben sind gültig, Schriftwahl – keine Pixelprüfung."""
from __future__ import annotations

import re
import time

import pytest

tk = pytest.importorskip("tkinter")
from tkinter import ttk  # noqa: E402

from master_schalter import uebersicht_stil as st  # noqa: E402

FARBEN = [name for name in dir(st) if name.isupper() and isinstance(getattr(st, name), str)
          and getattr(st, name).startswith("#")]


@pytest.fixture(scope="module")
def wurzel():
    letzter = None
    for _ in range(4):
        try:
            root = tk.Tk()
            break
        except tk.TclError as fehler:
            letzter = fehler
            time.sleep(0.5)
    else:
        pytest.skip(f"keine Anzeige für Tk: {str(letzter)[:80]}")
    root.withdraw()
    yield root
    root.destroy()


def test_alle_farben_sind_sechsstellige_hexwerte():
    assert len(FARBEN) >= 12
    for name in FARBEN:
        assert re.fullmatch(r"#[0-9a-f]{6}", getattr(st, name)), name


def test_schrift_waehlen_nimmt_die_erste_vorhandene_sonst_den_tk_standard():
    assert st.schrift_waehlen(["Arial", "segoe ui", "Segoe UI Variable"]) == "Segoe UI Variable"
    assert st.schrift_waehlen(["Arial", "Segoe UI"]) == "Segoe UI"
    assert st.schrift_waehlen(["Arial"]) == st.SCHRIFT_ERSATZ
    assert st.schrift_waehlen([]) == st.SCHRIFT_ERSATZ


def test_balken_stil_name_haengt_an_der_farbe():
    assert st.balken_stil_name("#d97757") == "Fd97757.Horizontal.TProgressbar"


def test_anwenden_legt_alle_stile_mit_den_farben_an(wurzel):
    stil, familie = st.anwenden(wurzel)
    assert familie
    assert stil.theme_use() == "clam"
    for name, grund in st.STILE.items():
        assert stil.lookup(name, "background") == grund, name
    assert stil.lookup(st.KNOPF_AKZENT, "foreground") == st.AUF_AKZENT
    assert stil.lookup(st.KARTE_FEHLER, "foreground") == st.FEHLER
    assert stil.lookup(st.KARTE_WARNUNG, "foreground") == st.WARNUNG
    assert stil.lookup(st.TABELLE, "fieldbackground") == st.FLAECHE
    assert stil.lookup(st.KOMBI, "fieldbackground") == st.FLAECHE2
    assert int(stil.lookup(st.TABELLE, "rowheight")) == st.ZEILENHOEHE


def test_tabelle_ist_ohne_gitterrahmen_und_auswahl_in_akzentfarbe(wurzel):
    stil, _ = st.anwenden(wurzel)
    assert "border" not in str(stil.layout(st.TABELLE))
    auswahl = dict(stil.map(st.TABELLE, "background"))
    assert auswahl["selected"] == st.AKZENT_CLAUDE


def test_balken_stil_ist_schmal_und_flach(wurzel):
    stil, _ = st.anwenden(wurzel)
    name = st.balken_stil(stil, st.AKZENT_CODEX)
    assert name == st.balken_stil_name(st.AKZENT_CODEX)
    assert stil.lookup(name, "background") == st.AKZENT_CODEX
    assert stil.lookup(name, "troughcolor") == st.FLAECHE2
    assert int(stil.lookup(name, "thickness")) == st.BALKEN_DICKE
    assert int(stil.lookup(name, "borderwidth")) == 0
    assert isinstance(stil, ttk.Style)
