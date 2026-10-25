"""Tests für das Wechselfenster: Einzelinstanz, Start und die dünne Tk-Schicht.

Die Tk-Tests öffnen kein sichtbares Fenster: Wurzel und Toplevel werden sofort mit `withdraw()` verborgen, es läuft nie
eine Ereignisschleife, Aktionen sind Attrappen, und die Zwischenablage wird durch eine Attrappe ersetzt (die
echte des Benutzers bleibt unberührt). Ohne Anzeige werden sie übersprungen.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

tk = pytest.importorskip("tkinter")

from master_schalter import chat_register, cli, fenster, zustand  # noqa: E402
from master_schalter import fenster_modell as fm  # noqa: E402

JETZT = datetime(2026, 10, 25, 12, 0, 0, tzinfo=timezone.utc)
THEMA = "engineering"


@pytest.fixture(autouse=True)
def _daten(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))


# --- Einzelinstanz und Start ------------------------------------------------------------------

def test_instanz_sperre_haelt_genau_eine_instanz():
    with zustand.instanz_sperre("fenster") as erste:
        assert erste is True
        with zustand.instanz_sperre("fenster") as zweite:
            assert zweite is False
        with zustand.instanz_sperre("anderes") as fremd:
            assert fremd is True                                  # andere Namen stören sich nicht
    with zustand.instanz_sperre("fenster") as wieder:
        assert wieder is True                                     # nach dem Ende ist sie frei


def test_zweiter_start_beendet_sich_still_ohne_fenster(monkeypatch, capsys):
    def nie(*_a, **_k):
        raise AssertionError("zweite Instanz darf kein Fenster öffnen")

    monkeypatch.setattr(fenster.tk, "Tk", nie)
    monkeypatch.setattr(fenster, "Fenster", nie)

    with zustand.instanz_sperre(fenster.INSTANZ) as frei:
        assert frei
        assert fenster.main() == 0

    assert "läuft bereits" in capsys.readouterr().err


def test_start_baut_fenster_laeuft_und_gibt_die_sperre_frei(monkeypatch):
    abfolge = []

    class Wurzel:
        def mainloop(self):
            abfolge.append("mainloop")

    wurzel = Wurzel()
    monkeypatch.setattr(fenster.tk, "Tk", lambda: abfolge.append("Tk") or wurzel)
    monkeypatch.setattr(fenster, "Fenster", lambda root: abfolge.append(("Fenster", root)))

    assert fenster.main() == 0

    assert abfolge == ["Tk", ("Fenster", wurzel), "mainloop"]
    with zustand.instanz_sperre(fenster.INSTANZ) as frei:
        assert frei is True


def test_start_ohne_anzeige_meldet_nur_die_fehlerklasse(monkeypatch, capsys):
    def keine_anzeige():
        raise tk.TclError("C:/Users/sebas/geheim: no display")

    monkeypatch.setattr(fenster.tk, "Tk", keine_anzeige)

    assert fenster.main() == 1

    fehler = capsys.readouterr().err
    assert "TclError" in fehler and "geheim" not in fehler
    with zustand.instanz_sperre(fenster.INSTANZ) as frei:
        assert frei is True


def test_cli_fenster_ruft_main_des_fensters(monkeypatch):
    monkeypatch.setattr(fenster, "main", lambda: 7)
    assert cli.main(["fenster"]) == 7


# --- Tk-Schicht -----------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _tk_wurzel():
    """Eine einzige, verborgene Tk-Wurzel für das ganze Modul (weniger Starts, nie ein sichtbares Fenster).

    Der Tcl-Start schlägt auf dieser Maschine gelegentlich mit „couldn't read file …“ fehl (Dateizugriff
    scheitert kurz); deshalb ein paar Versuche, sonst werden die Tk-Tests übersprungen.
    """
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
    """Je Test ein frisches, verborgenes Toplevel (es wird nie angezeigt, es läuft nie eine Ereignisschleife)."""
    fenster_obj = tk.Toplevel(_tk_wurzel)
    fenster_obj.withdraw()
    yield fenster_obj
    fenster_obj.destroy()


def _chat(kennung, titel, werkzeug="claude", minuten=0):
    return chat_register.Chat(werkzeug, kennung, titel, "", JETZT - timedelta(minutes=minuten), "claude-desktop")


def _vorgang_zeile(ident, phase="abgabe_angefragt", kopie=None, **extra):
    return fm.VorgangZeile(ident, THEMA, "Claude → Hermes", phase, "Hinweistext", extra.get("offen", True),
                           extra.get("kann_abbrechen", True), kopie)


def _snapshot(chats=(), vorgaenge=(), protokoll=("12:00  engineering: Wechsel angelegt",), hinweise=()):
    thema = fm.ThemaZeile(THEMA, "Claude", "claude", "ja · vor 5 min", True)
    return fm.Momentaufnahme(JETZT, (thema,), tuple(chats), tuple(vorgaenge), tuple(protokoll), tuple(hinweise))


class Aktionen:
    """Attrappen für die drei Aktionen und den Bestätigungsdialog."""

    def __init__(self, antwort=True):
        self.antwort, self.fragen, self.uebergeben, self.weiter, self.abbrechen = antwort, [], [], [], []

    def frage(self, titel, text):
        self.fragen.append(text)
        return self.antwort

    def tun_uebergeben(self, auswahl):
        self.uebergeben.append(auswahl)
        return fm.Ergebnis(True, "Wechsel engineering: wartet auf Abgabe")

    def tun_weiter(self, ident):
        self.weiter.append(ident)
        return fm.Ergebnis(True, "weiter")

    def tun_abbrechen(self, ident):
        self.abbrechen.append(ident)
        return fm.Ergebnis(False, "Abbrechen nicht mehr möglich (Phase rolle_gesetzt)")


def _fenster(wurzel, aktionen=None, snap=None):
    aktionen = aktionen or Aktionen()
    f = fenster.Fenster(wurzel, laden=lambda: snap or _snapshot(), frage=aktionen.frage,
                        uebergeben=aktionen.tun_uebergeben, weiter=aktionen.tun_weiter,
                        abbrechen=aktionen.tun_abbrechen, starten=False)
    if snap is not None:
        f.snapshot_anwenden(snap)
    return f, aktionen


def _warten(f):
    """Ergebnis des Hintergrund-Threads abholen (statt der Ereignisschleife)."""
    art, inhalt = f._queue.get(timeout=5)
    f._queue.put((art, inhalt))
    f._abfragen()


def test_schicht_zeigt_themen_vorgaenge_protokoll_und_hinweise(wurzel):
    snap = _snapshot(vorgaenge=[_vorgang_zeile("v-1")], hinweise=("Chatquelle hermes: gesperrt",))
    f, _ = _fenster(wurzel, snap=snap)

    assert f.themen_baum.get_children() == (THEMA,)
    assert tuple(f.themen_baum.item(THEMA, "values")) == (THEMA, "Claude", "ja · vor 5 min", "an")
    assert f.vorgang_baum.get_children() == ("v-1",)
    assert f.vorgang_baum.item("v-1", "values")[2:] == ("abgabe_angefragt", "Hinweistext")
    assert f.protokoll_liste.get(0) == "12:00  engineering: Wechsel angelegt"
    assert f.hinweis_var.get() == "Chatquelle hermes: gesperrt"
    assert tuple(f.thema_box["values"]) == (THEMA,)


def test_vorbelegung_nur_mit_vorschlag_sonst_bewusst_leer(wurzel):
    chats = [fm.ChatInfo(_chat("k-alt", "Alter Chat", minuten=30), THEMA, "Ordner", "ruht"),
             fm.ChatInfo(_chat("k-neu", "Neuer Hermes", "hermes"), None, "unbekannt", "unbekannt")]
    f, _ = _fenster(wurzel, snap=_snapshot(chats=chats))

    f.thema_var.set(THEMA)
    f.ziel_var.set("Hermes")
    f._thema_oder_ziel_gewaehlt()

    assert f.von_box.current() == 0 and f._eintrag("von").kennung == "k-alt"       # Vorschlag für das Thema
    assert f.nach_box.current() == -1 and f._eintrag("nach") is None               # kein Vorschlag: nichts gewählt
    assert [e.text for e in f._optionen["nach"]][-1] == fm.NEU_CHAT_LEER
    auswahl = f.auswahl_lesen()
    assert (auswahl.thema, auswahl.ziel, auswahl.von_master) == (THEMA, "hermes", "claude")
    assert fm.auswahl_pruefen(auswahl) is not None                                  # Nach-Chat fehlt noch


def test_bewusste_wahl_ueberlebt_die_aktualisierung_und_titel_aenderungen(wurzel):
    chats = [fm.ChatInfo(_chat("k-alt", "Alter Chat"), THEMA, "Ordner", "ruht"),
             fm.ChatInfo(_chat("k-zwei", "Zweiter", minuten=5), None, "unbekannt", "unbekannt")]
    f, _ = _fenster(wurzel, snap=_snapshot(chats=chats))
    f.thema_var.set(THEMA)
    f.ziel_var.set("Hermes")
    f._thema_oder_ziel_gewaehlt()

    f.von_box.current(1)                                   # bewusst den zweiten Chat wählen
    f._chat_gewaehlt("von")
    neu = [fm.ChatInfo(_chat("k-alt", "Alter Chat"), THEMA, "Ordner", "arbeitet"),
           fm.ChatInfo(_chat("k-zwei", "Zweiter (umbenannt)", minuten=1), None, "unbekannt", "ruht")]
    f.snapshot_anwenden(_snapshot(chats=neu))

    assert f._eintrag("von").kennung == "k-zwei"           # Auswahl bleibt, obwohl Reihenfolge und Text wechseln
    assert "umbenannt" in f.von_var.get()


def test_leereintrag_ist_eine_ausdrueckliche_wahl(wurzel):
    f, _ = _fenster(wurzel, snap=_snapshot())
    f.thema_var.set(THEMA)
    f.ziel_var.set("Codex")
    f._thema_oder_ziel_gewaehlt()
    f.nach_box.current(len(f._optionen["nach"]) - 1)
    f._chat_gewaehlt("nach")
    assert f._eintrag("nach").leer and f._eintrag("nach").text == fm.NEU_CHAT_LEER


def test_uebergeben_fragt_nach_nein_ist_der_abbruch(wurzel):
    f, aktionen = _fenster(wurzel, Aktionen(antwort=False), snap=_snapshot())
    f.thema_var.set(THEMA)
    f.ziel_var.set("Codex")
    f._thema_oder_ziel_gewaehlt()
    for art in ("von", "nach"):
        (f.von_box if art == "von" else f.nach_box).current(len(f._optionen[art]) - 1)
        f._chat_gewaehlt(art)

    f.uebergeben_klick()

    assert len(aktionen.fragen) == 1 and aktionen.uebergeben == []
    assert "Thema engineering: Claude → Codex" in aktionen.fragen[0] and "\n" not in aktionen.fragen[0].split("\n\n")[0]
    assert f.status_var.get() == "Nicht übergeben – nichts geändert."


def test_uebergeben_unvollstaendig_fragt_gar_nicht_erst(wurzel):
    f, aktionen = _fenster(wurzel, snap=_snapshot())
    f.uebergeben_klick()
    assert aktionen.fragen == [] and aktionen.uebergeben == []
    assert f.status_var.get().startswith("Fehler: Bitte ein Thema wählen")


def test_uebergeben_ja_laeuft_im_hintergrund_und_zeigt_das_ergebnis(wurzel):
    f, aktionen = _fenster(wurzel, snap=_snapshot())
    f.thema_var.set(THEMA)
    f.ziel_var.set("Hermes")
    f._thema_oder_ziel_gewaehlt()
    for art in ("von", "nach"):
        (f.von_box if art == "von" else f.nach_box).current(len(f._optionen[art]) - 1)
        f._chat_gewaehlt(art)

    f.uebergeben_klick()
    assert f._beschaeftigt is True and str(f.uebergeben_knopf["state"]) == "disabled"      # kein Doppelklick
    _warten(f)

    assert len(aktionen.uebergeben) == 1 and aktionen.uebergeben[0].ziel == "hermes"
    assert f.status_var.get() == "Wechsel engineering: wartet auf Abgabe"
    assert f._beschaeftigt is False and str(f.uebergeben_knopf["state"]) == "normal"


def test_knoepfe_je_nach_ausgewaehltem_vorgang(wurzel):
    snap = _snapshot(vorgaenge=[_vorgang_zeile("v-1", kopie="Text für Hermes"),
                                _vorgang_zeile("v-2", phase="im_postfach", kann_abbrechen=False),
                                _vorgang_zeile("v-3", phase="bestaetigt", offen=False, kann_abbrechen=False)])
    f, _ = _fenster(wurzel, snap=snap)

    def zustaende():
        return [str(k["state"]) for k in (f.weiter_knopf, f.abbrechen_knopf, f.kopieren_knopf)]

    assert zustaende() == ["disabled"] * 3                    # nichts gewählt
    f.vorgang_baum.selection_set("v-1")
    f._knoepfe_aktualisieren()
    assert zustaende() == ["normal", "normal", "normal"]
    assert f.kopierfeld.get("1.0", "end").strip() == "Text für Hermes"
    f.vorgang_baum.selection_set("v-2")
    f._knoepfe_aktualisieren()
    assert zustaende() == ["normal", "disabled", "disabled"]
    assert f.kopierfeld.get("1.0", "end").strip() == ""
    f.vorgang_baum.selection_set("v-3")
    f._knoepfe_aktualisieren()
    assert zustaende() == ["disabled"] * 3


def test_jetzt_weiter_und_abbrechen_gehen_an_die_aktionen(wurzel):
    f, aktionen = _fenster(wurzel, snap=_snapshot(vorgaenge=[_vorgang_zeile("v-1")]))
    f.vorgang_baum.selection_set("v-1")

    f.weiter_klick()
    _warten(f)
    assert aktionen.weiter == ["v-1"] and f.status_var.get() == "weiter"

    f.abbrechen_klick()
    assert len(aktionen.fragen) == 1 and "wirklich abbrechen" in aktionen.fragen[0]
    _warten(f)
    assert aktionen.abbrechen == ["v-1"]
    assert f.status_var.get() == "Fehler: Abbrechen nicht mehr möglich (Phase rolle_gesetzt)"


def test_abbrechen_mit_nein_aendert_nichts(wurzel):
    f, aktionen = _fenster(wurzel, Aktionen(antwort=False), snap=_snapshot(vorgaenge=[_vorgang_zeile("v-1")]))
    f.vorgang_baum.selection_set("v-1")
    f.abbrechen_klick()
    assert aktionen.abbrechen == [] and f.status_var.get() == "Nicht abgebrochen."


def test_text_kopieren_nutzt_nur_die_zwischenablage_der_attrappe(wurzel):
    f, _ = _fenster(wurzel, snap=_snapshot(vorgaenge=[_vorgang_zeile("v-1", kopie="Text für Hermes")]))
    f.vorgang_baum.selection_set("v-1")

    class Ablage:
        def __init__(self):
            self.inhalt = []

        def clipboard_clear(self):
            self.inhalt.clear()

        def clipboard_append(self, text):
            self.inhalt.append(text)

        def update(self):
            pass

    ablage = Ablage()
    f.root = ablage
    f.kopieren_klick()

    assert ablage.inhalt == ["Text für Hermes"] and "Zwischenablage" in f.status_var.get()


def test_hintergrundlesen_uebergibt_die_aufnahme_per_warteschlange(wurzel):
    f, _ = _fenster(wurzel, snap=None)
    gelesen_in = []
    snap = _snapshot(vorgaenge=[_vorgang_zeile("v-1")])
    f._laden = lambda: gelesen_in.append(threading.current_thread()) or snap

    f.laden_anstossen()
    f.laden_anstossen()                                       # läuft schon: keine zweite Aufnahme
    _warten(f)

    assert len(gelesen_in) == 1 and gelesen_in[0] is not threading.main_thread()
    assert f.vorgang_baum.get_children() == ("v-1",)
    assert f._laedt is False


def test_lesefehler_im_hintergrund_zeigt_nur_die_klasse(wurzel):
    f, _ = _fenster(wurzel, snap=None)

    def kaputt():
        raise OSError("C:/Users/sebas/geheim")

    f._laden = kaputt
    f.laden_anstossen()
    _warten(f)

    assert f.hinweis_var.get() == "Aktualisierung fehlgeschlagen (OSError)"


def test_unveraenderte_tabellen_werden_nicht_neu_geschrieben(wurzel):
    snap = _snapshot(vorgaenge=[_vorgang_zeile("v-1")])
    f, _ = _fenster(wurzel, snap=snap)
    f.vorgang_baum.selection_set("v-1")
    f.snapshot_anwenden(snap)
    assert f.vorgang_baum.selection() == ("v-1",)             # Auswahl bleibt bei jedem Takt erhalten
    f.snapshot_anwenden(_snapshot(vorgaenge=[]))
    assert f.vorgang_baum.get_children() == () and f.vorgang_baum.selection() == ()
