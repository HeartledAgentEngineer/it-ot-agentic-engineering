"""Tests des Übersichtsfensters: Einzelinstanz, Start und die dünne Tk-Schicht.

Wie bei `test_fenster.py` öffnet kein Test ein sichtbares Fenster: Wurzel und Toplevel werden sofort mit `withdraw()`
verborgen, es läuft nie eine Ereignisschleife, Aktionen und Rückfrage sind Attrappen. Ohne Anzeige werden die
Tk-Tests übersprungen.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

tk = pytest.importorskip("tkinter")

from master_schalter import uebersicht, zustand  # noqa: E402
from master_schalter import uebersicht_modell as um  # noqa: E402

JETZT = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))


# --- Einzelinstanz und Start -------------------------------------------------------------------------

def test_zweiter_start_beendet_sich_still_ohne_fenster(monkeypatch, capsys):
    def nie(*_a, **_k):
        raise AssertionError("zweite Instanz darf kein Fenster öffnen")

    monkeypatch.setattr(uebersicht.tk, "Tk", nie)
    monkeypatch.setattr(uebersicht, "Fenster", nie)

    with zustand.instanz_sperre(uebersicht.INSTANZ) as frei:
        assert frei
        assert uebersicht.main() == 0

    assert "läuft bereits" in capsys.readouterr().err


def test_sperre_der_uebersicht_stoert_das_wechselfenster_nicht():
    assert uebersicht.INSTANZ == "uebersicht"
    with zustand.instanz_sperre(uebersicht.INSTANZ) as erste:
        with zustand.instanz_sperre("fenster") as zweite:
            assert erste and zweite


def test_start_baut_fenster_laeuft_und_gibt_die_sperre_frei(monkeypatch):
    abfolge = []

    class Wurzel:
        def mainloop(self):
            abfolge.append("mainloop")

    wurzel = Wurzel()
    monkeypatch.setattr(uebersicht.tk, "Tk", lambda: abfolge.append("Tk") or wurzel)
    monkeypatch.setattr(uebersicht, "Fenster", lambda root: abfolge.append(("Fenster", root)))

    assert uebersicht.main() == 0

    assert abfolge == ["Tk", ("Fenster", wurzel), "mainloop"]
    with zustand.instanz_sperre(uebersicht.INSTANZ) as frei:
        assert frei is True


def test_start_ohne_anzeige_meldet_nur_die_fehlerklasse(monkeypatch, capsys):
    def keine_anzeige():
        raise tk.TclError("C:/Users/sebas/geheim: no display")

    monkeypatch.setattr(uebersicht.tk, "Tk", keine_anzeige)

    assert uebersicht.main() == 1

    fehler = capsys.readouterr().err
    assert "TclError" in fehler and "geheim" not in fehler


# --- Tk-Schicht -------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _tk_wurzel():
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


@pytest.fixture
def wurzel(_tk_wurzel):
    fenster_obj = tk.Toplevel(_tk_wurzel)
    fenster_obj.withdraw()
    yield fenster_obj
    fenster_obj.destroy()


def _balken(abo, fuenf, woche, **kw):
    farbe = {"Claude": "#d97757", "Codex": "#10a37f"}[abo]
    return um.Abo(abo, (um.Balken(abo, "5h", fuenf, f"{fuenf} % verbraucht", farbe, "Reset in 2 h 0 min (11:00)", True),
                        um.Balken(abo, "Woche", woche, f"{woche} % verbraucht", "#eab308", "", True)),
                  "gemessen 08:55", kw.get("fehler"), kw.get("messfehler"))


def _thema(name="thema-a", master="kontingent", arbeitsweise="protokoll", worker="workflow"):
    return um.ThemaZeile(name, "nach Kontingent", "claude", "Codex", "Workflow", "Auto an", master, arbeitsweise, worker)


def _snap(*, schreiben=True, messfehler=None, hinweise=()):
    return um.Uebersicht(
        zeit="09:00", lage="1", lage_text="Lage 1", automatik=False, schwelle=97,
        abos=(_balken("Claude", 62, 85, messfehler=messfehler), _balken("Codex", 1, 32)),
        themen=(_thema(), _thema("thema-b", "claude", "vibe", "claude")),
        wartet=("Wartet worauf: thema-a: auf Freigabe (seit 08:00)",), sitzungen=("Sitzung Claude eins-sit · ruht · 08:50",),
        hinweise=tuple(hinweise), repo=None, schreiben=schreiben,
        schreib_hinweis="" if schreiben else um.NUR_ANZEIGE)


class Aktionen:
    """Attrappen für den Bestätigungsdialog und die Übergabe."""

    def __init__(self, antwort=True):
        self.antwort, self.fragen, self.uebergaben = antwort, [], 0

    def frage(self, titel, text):
        self.fragen.append(text)
        return self.antwort

    def uebergabe(self):
        self.uebergaben += 1
        return um.Ergebnis(True, "Wechselfenster wird geöffnet.")


def _fenster(wurzel, snap=None, aktionen=None):
    aktionen = aktionen or Aktionen()
    snap = snap or _snap()
    f = uebersicht.Fenster(wurzel, laden=lambda: snap, frage=aktionen.frage, uebergabe=aktionen.uebergabe,
                           starten=False)
    f.snapshot_anwenden(snap)
    return f, aktionen


def _warten(f):
    art, inhalt = f._queue.get(timeout=5)
    f._queue.put((art, inhalt))
    f._abfragen()


def _themen_wahl(f, name):
    f.themen_baum.selection_set(name)
    f._auswahl_geaendert()


def test_schicht_zeigt_kopf_balken_themen_und_listen(wurzel):
    f, _ = _fenster(wurzel, _snap(messfehler="Claude-Messung scheitert seit 07:12 (letzter Versuch 07:42): X",
                                  hinweise=("Gemerkt: …",)))

    assert f.kopf_var.get() == "Master-Schalter · 09:00 · Lage 1"
    assert f.automatik_var.get() == "Automatik: aus"
    assert str(f.automatik_knopf["text"]).startswith("Automatik einschalten")
    claude_5h = f._balken[0]
    assert float(claude_5h[1]["value"]) == 62 and claude_5h[2].get() == "62 % verbraucht"
    assert claude_5h[3].get() == "Reset in 2 h 0 min (11:00)"
    assert float(f._balken[3][1]["value"]) == 32
    assert f._abo_info[0][0].get() == "gemessen 08:55"
    assert f._abo_info[0][1].get() == "Claude-Messung scheitert seit 07:12 (letzter Versuch 07:42): X"
    assert f._abo_info[1][1].get() == ""
    assert f.themen_baum.get_children() == ("thema-a", "thema-b")
    assert tuple(f.themen_baum.item("thema-a", "values")) == (
        "thema-a", "nach Kontingent", "claude", "Codex", "Workflow", "Protokoll", "Auto an")
    assert tuple(f.themen_baum.item("thema-b", "values"))[5] == "Vibe"
    assert [f.unten_liste.get(i) for i in range(f.unten_liste.size())] == [
        "Wartet worauf: thema-a: auf Freigabe (seit 08:00)", "Sitzung Claude eins-sit · ruht · 08:50"]
    assert f.hinweis_var.get() == "Gemerkt: …"


def test_balkenfarben_haengen_am_stil(wurzel):
    f, _ = _fenster(wurzel)
    assert f._balken[0][1]["style"] == "Fd97757.Horizontal.TProgressbar"
    assert f._balken[1][1]["style"] == "Feab308.Horizontal.TProgressbar"


def test_master_auswahl_folgt_dem_gewaehlten_thema(wurzel):
    f, _ = _fenster(wurzel)
    assert f.master_var.get() == "" and str(f.master_box["state"]) == "disabled"
    _themen_wahl(f, "thema-b")
    assert f.master_var.get() == "Claude Code" and str(f.master_box["state"]) == "readonly"
    assert tuple(f.master_box["values"]) == ("Nach Kontingent", "Claude Code", "Codex", "Hermes", "Antigravity")


def test_nur_anzeige_sperrt_schreibknoepfe_und_zeigt_den_hinweis(wurzel):
    f, _ = _fenster(wurzel, _snap(schreiben=False))
    _themen_wahl(f, "thema-a")
    assert f.sperre_var.get() == um.NUR_ANZEIGE == "Hauptarbeitsbaum nicht gefunden – nur Anzeige"
    assert str(f.kontingent_knopf["state"]) == "disabled" and str(f.zurueck_knopf["state"]) == "disabled"
    assert str(f.master_box["state"]) == "disabled"
    assert str(f.uebergabe_knopf["state"]) == "normal" and str(f.aktualisieren_knopf["state"]) == "normal"


def test_master_wechsel_fragt_und_bei_nein_wird_nichts_gestartet(wurzel, monkeypatch):
    aufrufe = []
    f, aktionen = _fenster(wurzel, aktionen=Aktionen(antwort=False))
    monkeypatch.setattr(um, "master_aktion", lambda snap, thema, wert: um.Aktion(
        "Master setzen", f"Frage {thema} {wert}", lambda: aufrufe.append("lauf") or um.Ergebnis(True, "x")))
    _themen_wahl(f, "thema-a")
    f.master_box.current(2)                                        # Codex
    f.master_klick()

    assert aktionen.fragen == ["Frage thema-a codex"]
    assert aufrufe == [] and f._beschaeftigt is False
    assert f.status_var.get().startswith("Nicht geändert")
    assert f.master_var.get() == "Nach Kontingent"                  # springt zurück


def test_master_wechsel_bei_ja_laeuft_im_hintergrund_und_meldet(wurzel, monkeypatch):
    aufrufe = []
    f, aktionen = _fenster(wurzel)
    monkeypatch.setattr(um, "master_aktion", lambda snap, thema, wert: um.Aktion(
        "Master setzen", "Frage", lambda: aufrufe.append((thema, wert)) or um.Ergebnis(True, "thema-a: Master Codex gespeichert")))
    _themen_wahl(f, "thema-a")
    f.master_box.current(2)
    f.master_klick()
    assert f._beschaeftigt is True
    _warten(f)

    assert aufrufe == [("thema-a", "codex")] and f._beschaeftigt is False
    assert f.status_var.get() == "thema-a: Master Codex gespeichert"


def test_abgelehnte_aktion_zeigt_status_ohne_rueckfrage(wurzel):
    f, aktionen = _fenster(wurzel, _snap(schreiben=False))
    f.alle_klick("kontingent")
    assert aktionen.fragen == []
    assert f.status_var.get() == "Fehler: " + um.NUR_ANZEIGE


@pytest.mark.parametrize("richtung, knopf", [("kontingent", "kontingent_knopf"), ("zurueck", "zurueck_knopf")])
def test_sammelknopf_nein_aendert_nichts_ja_zeigt_bericht(wurzel, monkeypatch, richtung, knopf):
    gebaut = []
    for antwort in (False, True):
        f, aktionen = _fenster(wurzel, aktionen=Aktionen(antwort))
        monkeypatch.setattr(um, "alle_aktion", lambda snap, r: gebaut.append(r) or um.Aktion(
            "Sammel", "Wirklich?", lambda: um.Ergebnis(True, "fertig", "a: ok\nb: ok")))
        getattr(f, knopf).invoke()
        assert aktionen.fragen == ["Wirklich?"]
        if not antwort:
            assert f._beschaeftigt is False and f.bericht_feld.get("1.0", "end").strip() == ""
            continue
        _warten(f)
        assert f.bericht_feld.get("1.0", "end").strip() == "a: ok\nb: ok"
        assert f.status_var.get() == "fertig"
    assert gebaut == [richtung, richtung]


def test_automatik_knopf_fragt_und_schaltet_bei_ja(wurzel, monkeypatch):
    aufrufe = []
    f, aktionen = _fenster(wurzel)
    monkeypatch.setattr(um, "automatik_aktion", lambda snap: um.Aktion(
        "Automatik", "Einschalten?", lambda: aufrufe.append("an") or um.Ergebnis(True, "Automatik an.")))
    f.automatik_knopf.invoke()
    _warten(f)
    assert aktionen.fragen == ["Einschalten?"] and aufrufe == ["an"] and f.status_var.get() == "Automatik an."

    f2, nein = _fenster(wurzel, aktionen=Aktionen(antwort=False))
    f2.automatik_knopf.invoke()
    assert nein.fragen and aufrufe == ["an"]


def test_uebergabe_knopf_oeffnet_wechselfenster_ohne_rueckfrage(wurzel):
    f, aktionen = _fenster(wurzel)
    f.uebergabe_knopf.invoke()
    _warten(f)
    assert aktionen.uebergaben == 1 and aktionen.fragen == []
    assert f.status_var.get() == "Wechselfenster wird geöffnet."


def test_aktualisieren_liest_im_hintergrund_neu(wurzel):
    f, _ = _fenster(wurzel)
    f.aktualisieren_knopf.invoke()
    assert f._laedt is True
    _warten(f)
    assert f._laedt is False


def test_lesefehler_im_hintergrund_wird_zur_hinweiszeile(wurzel):
    def kaputt():
        raise OSError("C:/geheim")

    f = uebersicht.Fenster(wurzel, laden=kaputt, starten=False)
    f.laden_anstossen()
    _warten(f)
    assert f.hinweis_var.get() == "Aktualisierung fehlgeschlagen (OSError)"
    assert "geheim" not in f.hinweis_var.get()
    assert str(f.kontingent_knopf["state"]) == "disabled"


def test_laden_laeuft_nicht_doppelt(wurzel):
    aufrufe = []
    f = uebersicht.Fenster(wurzel, laden=lambda: aufrufe.append(1) or _snap(), starten=False)
    f.laden_anstossen()
    f.laden_anstossen()
    _warten(f)
    assert aufrufe == [1]


def test_beschaeftigt_sperrt_knoepfe_und_zweite_aktion(wurzel):
    f, aktionen = _fenster(wurzel)
    f._beschaeftigt = True
    f._knoepfe_aktualisieren()
    assert str(f.kontingent_knopf["state"]) == "disabled" and str(f.automatik_knopf["state"]) == "disabled"
    f.automatik_klick()
    assert aktionen.fragen == [] and "warten" in f.status_var.get()


def test_lesefehler_loescht_alte_balken_und_sperrt_die_automatik(wurzel):
    f, aktionen = _fenster(wurzel)
    assert float(f._balken[0][1]["value"]) == 62
    f.snapshot_anwenden(um.leer("Aktualisierung fehlgeschlagen (OSError)"))

    assert all(float(leiste["value"]) == 0 and text.get() == "unbekannt" and reset.get() == ""
               for _, leiste, text, reset in f._balken)
    assert all(info.get() == "" and "Aktualisierung fehlgeschlagen" in fehler.get() for info, fehler in f._abo_info)
    assert f.automatik_var.get() == "Automatik: unbekannt"
    assert str(f.automatik_knopf["state"]) == "disabled"
    f.automatik_klick()
    assert aktionen.fragen == [] and "unbekannt" in f.status_var.get()

    f.snapshot_anwenden(_snap())                                    # nächste gute Aufnahme stellt alles wieder her
    assert float(f._balken[0][1]["value"]) == 62 and str(f.automatik_knopf["state"]) == "normal"


def test_arbeitsweise_auswahl_folgt_dem_gewaehlten_thema(wurzel):
    f, _ = _fenster(wurzel)
    assert f.arbeitsweise_var.get() == "" and str(f.arbeitsweise_box["state"]) == "disabled"
    _themen_wahl(f, "thema-b")
    assert f.arbeitsweise_var.get() == "Vibe" and str(f.arbeitsweise_box["state"]) == "readonly"
    assert tuple(f.arbeitsweise_box["values"]) == ("Protokoll", "Vibe")
    _themen_wahl(f, "thema-a")
    assert f.arbeitsweise_var.get() == "Protokoll"


def test_arbeitsweise_nur_anzeige_sperrt_den_umschalter(wurzel):
    f, _ = _fenster(wurzel, _snap(schreiben=False))
    _themen_wahl(f, "thema-b")
    assert str(f.arbeitsweise_box["state"]) == "disabled"


def test_arbeitsweise_wechsel_fragt_und_bei_nein_wird_nichts_gestartet(wurzel, monkeypatch):
    aufrufe = []
    f, aktionen = _fenster(wurzel, aktionen=Aktionen(antwort=False))
    monkeypatch.setattr(um, "arbeitsweise_aktion", lambda snap, thema, wert: um.Aktion(
        "Arbeitsweise setzen", f"Frage {thema} {wert}", lambda: aufrufe.append("lauf") or um.Ergebnis(True, "x")))
    _themen_wahl(f, "thema-a")
    f.arbeitsweise_box.current(1)                                   # Vibe
    f.arbeitsweise_klick()

    assert aktionen.fragen == ["Frage thema-a vibe"]
    assert aufrufe == [] and f._beschaeftigt is False
    assert f.status_var.get().startswith("Nicht geändert")
    assert f.arbeitsweise_var.get() == "Protokoll"                   # springt zurück


def test_arbeitsweise_wechsel_bei_ja_laeuft_im_hintergrund_und_meldet(wurzel, monkeypatch):
    aufrufe = []
    f, aktionen = _fenster(wurzel)
    monkeypatch.setattr(um, "arbeitsweise_aktion", lambda snap, thema, wert: um.Aktion(
        "Arbeitsweise setzen", "Frage", lambda: aufrufe.append((thema, wert)) or um.Ergebnis(True, "thema-a: Arbeitsweise Vibe gespeichert")))
    _themen_wahl(f, "thema-a")
    f.arbeitsweise_box.current(1)
    f.arbeitsweise_klick()
    assert f._beschaeftigt is True
    _warten(f)

    assert aufrufe == [("thema-a", "vibe")] and f._beschaeftigt is False
    assert f.status_var.get() == "thema-a: Arbeitsweise Vibe gespeichert"


def test_arbeitsweise_abgelehnt_zeigt_status_ohne_rueckfrage(wurzel):
    f, aktionen = _fenster(wurzel)                                   # thema-a: Ausführer Workflow
    _themen_wahl(f, "thema-a")
    f.arbeitsweise_box.current(1)
    f.arbeitsweise_klick()
    assert aktionen.fragen == []
    assert f.status_var.get().startswith("Fehler: Vibe braucht Ausführer Claude")
    assert f.arbeitsweise_var.get() == "Protokoll"
