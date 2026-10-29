"""Tests des Übersichtsfensters: Einzelinstanz, Start und die dünne Tk-Schicht.

Wie bei `test_fenster.py` öffnet kein Test ein sichtbares Fenster: Wurzel und Toplevel werden sofort mit `withdraw()`
verborgen, es läuft nie eine Ereignisschleife, Aktionen und Rückfrage sind Attrappen. Ohne Anzeige werden die
Tk-Tests übersprungen.
"""
from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

tk = pytest.importorskip("tkinter")

from master_schalter import uebersicht, zustand  # noqa: E402
from master_schalter import uebersicht_modell as um
from master_schalter import uebersicht_stil as st  # noqa: E402

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
    snap = um.Uebersicht(
        zeit="09:00", lage="1", lage_text="Lage 1", automatik=False, schwelle=97,
        abos=(_balken("Claude", 62, 85, messfehler=messfehler), _balken("Codex", 1, 32)),
        themen=(_thema(), _thema("thema-b", "claude", "vibe", "claude")),
        wartet=("Wartet worauf: thema-a: auf Freigabe (seit 08:00)",), sitzungen=("Sitzung Claude eins-sit · ruht · 08:50",),
        hinweise=tuple(hinweise), repo=None, schreiben=schreiben,
        schreib_hinweis="" if schreiben else um.NUR_ANZEIGE)
    object.__setattr__(snap, "wechsel_themen", ())
    object.__setattr__(snap, "wechsel_pruefbar", True)
    return snap


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
    return f.themen_tabelle.zeilen[name]


def test_schicht_zeigt_kopf_balken_themen_und_listen(wurzel):
    f, _ = _fenster(wurzel, _snap(messfehler="Claude-Messung scheitert seit 07:12 (letzter Versuch 07:42): X",
                                  hinweise=("Gemerkt: …",)))

    assert f.zeit_var.get() == "09:00" and f.lage_var.get() == "Lage 1" and f.lage_grund_var.get() == ""
    assert f.automatik_var.get() == "Automatik: aus"
    assert str(f.automatik_knopf["text"]).startswith("Automatik einschalten")
    claude_5h = f._balken[0]
    assert float(claude_5h[1]["value"]) == 62 and claude_5h[2].get() == "62 % verbraucht"
    assert claude_5h[3].get() == "Reset in 2 h 0 min (11:00)"
    assert float(f._balken[3][1]["value"]) == 32
    assert f._abo_info[0][0].get() == "gemessen 08:55"
    assert f._abo_info[0][1].get() == "Claude-Messung scheitert seit 07:12 (letzter Versuch 07:42): X"
    assert f._abo_info[1][1].get() == ""
    assert set(f.themen_tabelle.zeilen) == {"thema-a", "thema-b"}
    assert f.themen_tabelle.zeilen["thema-a"].felder["master"].get() == "Nach Kontingent"
    assert f.themen_tabelle.zeilen["thema-b"].felder["arbeitsweise"].get() == "Vibe"
    assert [f.unten_liste.get(i) for i in range(f.unten_liste.size())] == [
        "Wartet worauf: thema-a: auf Freigabe (seit 08:00)", "Sitzung Claude eins-sit · ruht · 08:50"]
    assert f.hinweis_var.get() == "Gemerkt: …"


def test_balkenfarben_haengen_am_stil(wurzel):
    f, _ = _fenster(wurzel)
    assert f._balken[0][1]["style"] == "Fd97757.Horizontal.TProgressbar"
    assert f._balken[1][1]["style"] == "Feab308.Horizontal.TProgressbar"


def test_master_auswahl_folgt_dem_gewaehlten_thema(wurzel):
    f, _ = _fenster(wurzel)
    box = _themen_wahl(f, "thema-b").felder["master"]
    assert box.get() == "Claude Code" and str(box["state"]) == "readonly"
    assert tuple(box["values"]) == ("Nach Kontingent", "Claude Code", "Codex", "Hermes", "Antigravity")


def test_nur_anzeige_sperrt_schreibknoepfe_und_zeigt_den_hinweis(wurzel):
    f, _ = _fenster(wurzel, _snap(schreiben=False))
    _themen_wahl(f, "thema-a")
    assert f.sperre_var.get() == um.NUR_ANZEIGE == "Hauptarbeitsbaum nicht gefunden – nur Anzeige"
    assert str(f.kontingent_knopf["state"]) == "disabled" and str(f.zurueck_knopf["state"]) == "disabled"
    assert all(str(box["state"]) == "disabled" for box in f.themen_tabelle.zeilen["thema-a"].felder.values())
    assert str(f.uebergabe_knopf["state"]) == "normal" and str(f.aktualisieren_knopf["state"]) == "normal"


def test_master_auswahl_erstellt_nur_lokalen_entwurf(wurzel, monkeypatch):
    aufrufe = []
    f, aktionen = _fenster(wurzel, aktionen=Aktionen(antwort=False))
    monkeypatch.setattr(um, "master_aktion", lambda snap, thema, wert: um.Aktion(
        "Master setzen", f"Frage {thema} {wert}", lambda: aufrufe.append("lauf") or um.Ergebnis(True, "x")))
    _themen_wahl(f, "thema-a")
    box = _themen_wahl(f, "thema-a").felder["master"]
    box.current(2)
    box.event_generate("<<ComboboxSelected>>")
    wurzel.update_idletasks()
    assert aktionen.fragen == [] and aufrufe == [] and f._beschaeftigt is False
    assert [(a.thema, a.feld, a.neu) for a in f._entwuerfe.aenderungen()] == [("thema-a", "master", "codex")]


def test_masterauswahl_ruft_keine_hintergrundaktion_auf(wurzel, monkeypatch):
    aufrufe = []
    f, aktionen = _fenster(wurzel)
    monkeypatch.setattr(um, "master_aktion", lambda snap, thema, wert: um.Aktion(
        "Master setzen", "Frage", lambda: aufrufe.append((thema, wert)) or um.Ergebnis(True, "thema-a: Master Codex gespeichert")))
    _themen_wahl(f, "thema-a")
    box = _themen_wahl(f, "thema-a").felder["master"]
    box.current(2)
    box.event_generate("<<ComboboxSelected>>")
    wurzel.update_idletasks()
    assert aufrufe == [] and f._beschaeftigt is False
    assert f._entwuerfe.zeile("thema-a").master_wert == "codex"


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


def test_aktualisieren_knopf_sitzt_klein_in_der_kopfzeile_neben_dem_hauptschalter(wurzel):
    f, _ = _fenster(wurzel)
    kopf = f.automatik_knopf.master
    assert f.aktualisieren_knopf.master is kopf
    assert str(f.aktualisieren_knopf["text"]) == "↻ Aktualisieren"
    assert str(f.aktualisieren_knopf["style"]) == st.KNOPF_KLEIN
    info, auto = f.aktualisieren_knopf.grid_info(), f.automatik_knopf.grid_info()
    assert info["row"] == auto["row"] == 0 and int(info["column"]) > int(auto["column"])      # oben rechts, nach dem Hauptschalter
    unten = {str(w) for w in f.uebergabe_knopf.master.winfo_children()}
    assert str(f.aktualisieren_knopf) not in unten                                            # nicht mehr in der Knopfreihe


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
    row = _themen_wahl(f, "thema-b")
    box = row.felder["arbeitsweise"]
    assert box.get() == "Vibe" and str(box["state"]) == "readonly"
    assert tuple(box["values"]) == ("Protokoll", "Vibe")


def test_arbeitsweise_nur_anzeige_sperrt_den_umschalter(wurzel):
    f, _ = _fenster(wurzel, _snap(schreiben=False))
    assert str(_themen_wahl(f, "thema-b").felder["arbeitsweise"]["state"]) == "disabled"


def test_arbeitsweise_auswahl_bleibt_lokal_und_startet_keine_aktion(wurzel, monkeypatch):
    aufrufe = []
    f, aktionen = _fenster(wurzel, aktionen=Aktionen(antwort=False))
    monkeypatch.setattr(um, "arbeitsweise_aktion", lambda snap, thema, wert: um.Aktion(
        "Arbeitsweise setzen", f"Frage {thema} {wert}", lambda: aufrufe.append("lauf") or um.Ergebnis(True, "x")))
    _themen_wahl(f, "thema-a")
    box = _themen_wahl(f, "thema-a").felder["arbeitsweise"]
    box.current(1)
    box.event_generate("<<ComboboxSelected>>")
    wurzel.update_idletasks()
    assert aktionen.fragen == [] and aufrufe == [] and f._beschaeftigt is False
    assert f._entwuerfe.zeile("thema-a").arbeitsweise == "vibe"


def test_arbeitsweise_auswahl_bestaetigt_nicht_unmittelbar(wurzel, monkeypatch):
    aufrufe = []
    f, aktionen = _fenster(wurzel)
    monkeypatch.setattr(um, "arbeitsweise_aktion", lambda snap, thema, wert: um.Aktion(
        "Arbeitsweise setzen", "Frage", lambda: aufrufe.append((thema, wert)) or um.Ergebnis(True, "thema-a: Arbeitsweise Vibe gespeichert")))
    _themen_wahl(f, "thema-a")
    box = _themen_wahl(f, "thema-a").felder["arbeitsweise"]
    box.current(1)
    box.event_generate("<<ComboboxSelected>>")
    wurzel.update_idletasks()
    assert aufrufe == [] and f._beschaeftigt is False
    assert f._entwuerfe.zeile("thema-a").arbeitsweise == "vibe"


def test_arbeitsweise_abgelehnt_zeigt_status_ohne_rueckfrage(wurzel):
    f, aktionen = _fenster(wurzel)                                   # thema-a: Ausführer Workflow
    row = _themen_wahl(f, "thema-a")
    assert row.felder["ausfuehrer"].get() == "Workflow"
    assert row.felder["arbeitsweise"].get() == "Protokoll"


# --- Auswahllisten Prüfer, Ausführer, Modell, Auto (Stufe 4) ------------------------------------------------

def _thema_voll(name="thema-a", **kw):
    felder = dict(thema=name, master="nach Kontingent", besitz="claude", pruefer="Codex · App-Standard",
                  ausfuehrer="Claude · Sonnet 5.5", auto="Auto an (wirksam)", master_wert="kontingent",
                  worker_wert="claude", auto_zustand="wirksam", paar_aktiv=True)
    felder.update(kw)
    return um.ThemaZeile(**felder)


def _snap_mit(*themen, kataloge=(), automatik=True):
    return replace(_snap(), themen=tuple(themen), kataloge=tuple(kataloge), automatik=automatik)


def test_listen_zeigen_gespeicherte_werte_des_gewaehlten_themas(wurzel):
    snap = _snap_mit(_thema_voll(pruefer_wert="hermes", modell_wert=None),
                     kataloge=(um.KatalogAnsicht("claude", True, (("claude-x", "Claude X"),)),))
    f, _ = _fenster(wurzel, snap)
    row = _themen_wahl(f, "thema-a")
    assert row.felder["pruefer"].get() == "Hermes" and str(row.felder["pruefer"]["state"]) == "readonly"
    assert tuple(row.felder["pruefer"]["values"]) == ("Automatisch", "Codex", "Hermes")
    assert row.felder["ausfuehrer"].get() == "Claude" and tuple(row.felder["ausfuehrer"]["values"]) == (
        "Workflow", "Claude", "Codex", "Hermes", "Antigravity")
    assert um.STANDARD_MODELL in tuple(row.felder["modell"]["values"])
    assert row.felder["auto"].get() == "An" and tuple(row.felder["auto"]["values"]) == ("An", "Aus")


def test_modell_ist_bei_workflow_und_hermes_gesperrt_und_ohne_katalog_mit_hinweis(wurzel):
    snap = _snap_mit(_thema_voll("a", worker_wert="workflow"), _thema_voll("b", worker_wert="hermes"),
                     _thema_voll("c", worker_wert="codex"))
    f, _ = _fenster(wurzel, snap)
    assert str(_themen_wahl(f, "a").felder["modell"]["state"]) == "disabled"
    assert str(_themen_wahl(f, "b").felder["modell"]["state"]) == "disabled"
    c = _themen_wahl(f, "c").felder["modell"]
    assert str(c["state"]) == "readonly" and tuple(c["values"]) == (um.STANDARD_MODELL,)


def test_auto_liste_ist_ohne_paar_gesperrt_und_zeigt_den_wirksamen_zustand(wurzel):
    snap = _snap_mit(_thema_voll("mit"), _thema_voll("ohne", paar_aktiv=None, auto="kein Codex-Paar",
                                                      auto_zustand="ohne"),
                     _thema_voll("wartet", auto="Freigabe an, wirkt nicht", auto_zustand="wartet", master_wert="claude"))
    f, _ = _fenster(wurzel, snap)
    assert str(_themen_wahl(f, "ohne").felder["auto"]["state"]) == "disabled"
    mit = _themen_wahl(f, "mit")
    assert "● Auto an (wirksam)" in mit.details.cget("text")
    wartet = _themen_wahl(f, "wartet")
    assert "Freigabe an, wirkt nicht" in wartet.details.cget("text")


def test_pruefer_familienhinweis_erscheint_nur_bei_gleicher_familie(wurzel):
    snap = _snap_mit(_thema_voll("a", pruefer_warnung=True), _thema_voll("b"))
    f, _ = _fenster(wurzel, snap)
    assert "Achtung: gleiche Prüferfamilie" in _themen_wahl(f, "a").details.cget("text")
    assert "gleiche Prüferfamilie" not in _themen_wahl(f, "b").details.cget("text")


def test_listen_gesperrt_bei_nur_anzeige(wurzel):
    snap = replace(_snap_mit(_thema_voll()), schreiben=False, schreib_hinweis=um.NUR_ANZEIGE)
    f, _ = _fenster(wurzel, snap)
    for box in _themen_wahl(f, "thema-a").felder.values():
        assert str(box["state"]) == "disabled"


@pytest.mark.parametrize("box, klick, aktion, index, erwartet", [
    ("pruefer_box", "pruefer_klick", "pruefer_aktion", 2, "hermes"),
    ("ausfuehrer_box", "ausfuehrer_klick", "ausfuehrer_aktion", 2, "codex"),
    ("auto_box", "auto_klick", "auto_aktion", 1, False),
])
def test_listenwahl_bleibt_lokaler_entwurf_ohne_mutator(wurzel, monkeypatch, box, klick, aktion, index, erwartet):
    aufrufe = []
    monkeypatch.setattr(um, aktion, lambda snap, thema, wert: um.Aktion(
        "X", f"Frage {thema} {wert}", lambda: aufrufe.append((thema, wert)) or um.Ergebnis(True, "gespeichert")))
    f, aktionen = _fenster(wurzel, _snap_mit(_thema_voll(pruefer_wert="automatisch")), Aktionen(True))
    cell = _themen_wahl(f, "thema-a").felder[box.removesuffix("_box")]
    cell.current(index)
    cell.event_generate("<<ComboboxSelected>>")
    wurzel.update_idletasks()
    assert aktionen.fragen == [] and aufrufe == [] and f._beschaeftigt is False
    assert f._entwuerfe.aenderungen()[0].neu == erwartet


def test_modellwahl_vormerkt_katalogkennung_ohne_mutator(wurzel, monkeypatch):
    gesehen = []
    monkeypatch.setattr(um, "modell_aktion", lambda snap, thema, modell: gesehen.append((thema, modell)) or um.Aktion(
        "M", "Frage", lambda: um.Ergebnis(True, "ok")))
    snap = _snap_mit(_thema_voll(), kataloge=(um.KatalogAnsicht("claude", True, (("claude-x", "Claude X"),)),))
    f, _ = _fenster(wurzel, snap)
    cell = _themen_wahl(f, "thema-a").felder["modell"]
    cell.current(1)
    cell.event_generate("<<ComboboxSelected>>")
    wurzel.update_idletasks()
    assert gesehen == []
    assert f._entwuerfe.zeile("thema-a").modell_wert == "claude-x"


def test_unzulaessiger_modellentwurf_wird_abgelehnt_und_erhaelt_anderen_entwurf(wurzel):
    snap = _snap_mit(
        _thema_voll(modell_wert="claude-x"),
        kataloge=(um.KatalogAnsicht("claude", True, (("claude-x", "Claude X"),)),),
    )
    f, _ = _fenster(wurzel, snap)
    f._themenwert_aendern("thema-a", "master", "hermes")
    f._themenwert_aendern("thema-a", "modell", "nicht-im-katalog")

    assert f._entwuerfe.zeile("thema-a").master_wert == "hermes"
    assert f._entwuerfe.zeile("thema-a").modell_wert == "claude-x"
    assert f._snap.themen[0].modell_wert == "claude-x"
    assert "Modell muss im aktuell geprüften Claude-Katalog stehen" in f.status_var.get()
