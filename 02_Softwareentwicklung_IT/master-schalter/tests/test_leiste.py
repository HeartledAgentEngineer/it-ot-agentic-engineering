"""Tests für die Taskleisten-Oberfläche – ohne Fenster: Menüeinträge prüfen, Klicks per Attrappe auslösen."""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pystray = pytest.importorskip("pystray")

from master_schalter import anzeige, leiste, modi, modelle, paare, signale, vorgaenge, wechsel, zustand  # noqa: E402

JETZT = datetime.now(timezone.utc)
SPAETER = JETZT + timedelta(hours=2)


def _kontingent(master, fuenf, woche):
    return signale.Kontingent(master, (signale.Fenster("5h", fuenf, SPAETER), signale.Fenster("Woche", woche, SPAETER)),
                              stand=JETZT)


class _Icon:
    """Attrappe statt echtem Symbol: sammelt Titel, Bild und Benachrichtigungen."""

    def __init__(self):
        self.title = ""
        self.icon = None
        self.meldungen = []
        self.menue_neu = 0

    def notify(self, text, titel=None):
        self.meldungen.append((titel, text))

    def update_menu(self):
        self.menue_neu += 1

    def stop(self):
        pass


@pytest.fixture
def lst(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path / "daten"))
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    monkeypatch.setattr(signale, "alle_lesen",
                        lambda jetzt=None: [_kontingent("Claude", 62, 80), _kontingent("Codex", 1, 32)])
    monkeypatch.setattr(leiste.pystray, "Icon", lambda *args, **kwargs: _Icon())
    l = leiste.Leiste()
    return l


def _texte(items):
    return [i.text for i in items]


def _eintrag(items, text):
    return next(i for i in items if i.text == text)


def _einstellungen(lst):
    """Die Einträge des Untermenüs „Einstellungen ▸“ (Plan E9)."""
    return list(_eintrag(list(lst._menue()), "Einstellungen ▸").submenu.items)


def test_menue_beginnt_mit_master_und_lage(lst):
    zustand.aendern(lambda z: z.__class__("claude", JETZT.isoformat(), None))
    lst.aktualisieren()
    items = [i for i in lst._menue() if i.visible]
    texte = _texte(items)
    assert texte[0].startswith("Master: Claude (seit ")
    assert texte[1].startswith("Lage 1")
    assert any("Thinker" in t for t in texte[1:5])
    assert not items[0].enabled


def test_menue_enthaelt_untermenues(lst):
    """E9: oben nur Übergabe starten, Aktualisieren, Einstellungen und Beenden; die Einstellpunkte liegen darunter."""
    lst.aktualisieren()
    texte = _texte(lst._menue())
    assert "Übergabe starten …" in texte and "Einstellungen ▸" in texte
    assert "Aktualisieren" in texte and "Beenden" in texte
    for umgehaengt in ("Master wechseln", "Wechsel-Schwelle", "Arbeitsmodus je Thema", "Modelle aktualisieren",
                       "Chats übergeben"):
        assert umgehaengt not in texte
    unter = _texte(_einstellungen(lst))
    assert "Wechsel-Schwelle" in unter and "Arbeitsmodus je Thema" in unter and "Modelle aktualisieren" in unter
    assert "Automatik je Thema" in unter and "Standard-Master (übrige Themen)" in unter


def test_modusmenue_zeigt_master_ausfuehrer_und_modellgruppen(lst):
    thema = "personal-ai-agent"
    paare.setzen(thema, "00000000-0000-4000-8000-000000000001",
                 paare.laufend_bilden(thema), aktiv=True)
    modi.setzen(thema, modi.HERMES_CODEX)
    lst.aktualisieren()
    items = list(lst._menue())

    assert any(i.text.startswith("Feste Themenrollen") and thema in i.text for i in items)
    themen = _eintrag(_einstellungen(lst), "Arbeitsmodus je Thema").submenu.items
    gruppen = _eintrag(list(themen), thema).submenu.items
    assert _texte(gruppen) == ["Master", "Ausführer", "Ausführermodell"]
    master = _eintrag(list(gruppen), "Master").submenu.items
    assert _texte(master) == ["Nach Kontingent", "Claude Code", "Codex", "Hermes"]
    assert all(i.radio for i in master)
    assert [i.checked for i in master] == [False, False, False, True]      # Hermes aus dem gespeicherten Profil


def test_modus_radio_haken_nutzt_nur_den_snapshot(lst, monkeypatch):
    thema = "engineering"
    paare.setzen(thema, "00000000-0000-4000-8000-000000000001",
                 paare.laufend_bilden(thema), aktiv=True)
    lst.aktualisieren()

    def kaputt(*_args, **_kwargs):
        raise AssertionError("Dateizugriff")

    monkeypatch.setattr(modi, "snapshot", kaputt)
    monkeypatch.setattr(modi, "lesen", kaputt)
    monkeypatch.setattr(leiste.modelle, "lesen", kaputt)

    gruppen = _eintrag(list(_eintrag(_einstellungen(lst), "Arbeitsmodus je Thema").submenu.items),
                       thema).submenu.items
    master = _eintrag(list(gruppen), "Master").submenu.items
    assert [i.checked for i in master] == [True, False, False, False]      # kontingent aus dem Snapshot
    ausfuehrer = [i for i in _eintrag(list(gruppen), "Ausführer").submenu.items if i.enabled]
    assert [i.checked for i in ausfuehrer] == [True, False, False, False]


def test_modusaktion_meldet_belegte_sperre_ohne_warten(lst, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def belegt(*_args, **_kwargs):
        yield False

    class Sofort:
        def __init__(self, *, target, daemon, args=()):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(leiste.zustand, "thema_sperre", belegt)
    monkeypatch.setattr(leiste.threading, "Thread", Sofort)
    lst._master_aktion("engineering", "hermes")()

    assert lst.icon.meldungen[-1][1] == "Übergabe läuft – Modus gleich erneut wählen"


def test_modus_snapshot_fehler_zeigt_status_und_deaktiviert_optionen(lst, monkeypatch):
    def kaputt(*_args, **_kwargs):
        raise modi.ModusFehler("synthetischer Lesefehler")

    monkeypatch.setattr(modi, "snapshot", kaputt)
    lst.aktualisieren()
    items = list(lst._menue())

    assert any(i.text == "Arbeitsmodus: nicht verfügbar: synthetischer Lesefehler" for i in items)
    submenu = _eintrag(_einstellungen(lst), "Arbeitsmodus je Thema").submenu.items
    assert len(submenu) == 1
    assert submenu[0].text == "Modusdaten nicht lesbar"
    assert submenu[0].enabled is False


def test_modus_klick_schreibfehler_beendet_leiste_nicht(lst, monkeypatch):
    def kaputt(*_args, **_kwargs):
        raise OSError("synthetischer Schreibfehler")

    monkeypatch.setattr(modi, "master_setzen", kaputt)
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    lst._master_aktion("engineering", "hermes")()

    assert lst.icon.meldungen[-1][1] == "Modus nicht geändert: synthetischer Schreibfehler"


def test_master_wechseln_optionsfelder_aktiver_angehakt(lst):
    zustand.aendern(lambda z: z.__class__("codex", JETZT.isoformat(), None))
    lst.aktualisieren()
    sub = _eintrag(_einstellungen(lst), "Standard-Master (übrige Themen)").submenu.items
    assert _texte(sub) == ["Claude", "Codex", "Hermes"]
    assert all(i.radio for i in sub)
    assert [i.checked for i in sub] == [False, True, False]


def test_klick_auf_master_wechselt_aktualisiert_und_meldet(lst, tmp_path, monkeypatch):
    aufrufe = []
    paket = tmp_path / "2026-10-14_215007_masterwechsel-claude-codex.md"

    def attrappe(nach, hinweis=None, **kw):
        aufrufe.append(nach)
        zustand.aendern(lambda z: z.__class__(nach, JETZT.isoformat(), str(paket)))
        return wechsel.Ergebnis("gewechselt", nach, paket, "")

    monkeypatch.setattr(wechsel, "wechseln", attrappe)
    monkeypatch.setattr(leiste.rueckgabe, "rueckgabe", lambda **k: [])
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    lst._dialog = lambda titel, text: True
    lst.aktualisieren()
    sub = _eintrag(_einstellungen(lst), "Standard-Master (übrige Themen)").submenu.items
    _eintrag(sub, "Codex")(lst.icon)   # MenuItem.__call__ führt die Aktion aus

    assert aufrufe == ["codex"]
    assert lst.icon.title.startswith("M Codex L")
    assert lst.icon.meldungen[-1][1] == f"Standard-Master jetzt Codex. Technisches Übergabepaket: {paket.name}. Geschützte Hermes-Themen bleiben unverändert."


def test_klick_auf_hermes_wechselt(lst, tmp_path, monkeypatch):
    aufrufe = []
    paket = tmp_path / "2026-10-15_142540_masterwechsel-codex-hermes.md"

    def attrappe(nach, hinweis=None, **kw):
        aufrufe.append(nach)
        zustand.aendern(lambda z: z.__class__(nach, JETZT.isoformat(), str(paket)))
        return wechsel.Ergebnis("gewechselt", nach, paket, "")

    monkeypatch.setattr(wechsel, "wechseln", attrappe)
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    lst._dialog = lambda titel, text: True
    lst.aktualisieren()
    sub = _eintrag(_einstellungen(lst), "Standard-Master (übrige Themen)").submenu.items
    _eintrag(sub, "Hermes")(lst.icon)

    assert aufrufe == ["hermes"]
    assert lst.icon.title.startswith("M Hermes L")
    assert lst.icon.meldungen[-1][1] == f"Standard-Master jetzt Hermes. Technisches Übergabepaket: {paket.name}. Geschützte Hermes-Themen bleiben unverändert."


def test_fehlschlag_beim_wechsel_zeigt_meldung_und_stuerzt_nicht(lst, monkeypatch):
    def kaputt(nach, hinweis=None, **kw):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(wechsel, "wechseln", kaputt)
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    lst._dialog = lambda titel, text: True
    lst.aktualisieren()
    sub = _eintrag(_einstellungen(lst), "Standard-Master (übrige Themen)").submenu.items
    _eintrag(sub, "Claude")(lst.icon)
    assert lst.icon.meldungen[-1][1].startswith("Wechsel fehlgeschlagen")


def test_tooltip_beginnt_mit_master_und_hat_hoechstens_127_zeichen(lst):
    zustand.aendern(lambda z: z.__class__("claude", JETZT.isoformat(), None))
    lst.aktualisieren()
    assert lst.icon.title.startswith("M Claude L1 | Claude 5h 62%")
    assert len(lst.icon.title) <= 127


def test_symbol_bekommt_aktiven_master(lst, monkeypatch):
    gesehen = {}
    from master_schalter import symbol
    original = symbol.bild

    def spion(claude, codex, schwelle, master=None):
        gesehen["master"] = master
        return original(claude, codex, schwelle, master)

    monkeypatch.setattr(symbol, "bild", spion)
    zustand.aendern(lambda z: z.__class__("codex", JETZT.isoformat(), None))
    lst.aktualisieren()
    assert gesehen["master"] == "codex"


def test_schwelle_untermenue_fuenf_optionen_aktive_angehakt(lst):
    lst.aktualisieren()
    sub = _eintrag(_einstellungen(lst), "Wechsel-Schwelle").submenu.items
    assert _texte(sub) == ["80 %", "90 %", "95 %", "97 %", "100 %"]
    assert all(i.radio for i in sub)
    assert [i.checked for i in sub] == [False, False, False, True, False]


def test_klick_auf_schwelle_schreibt_datei_und_zeichnet_neu(lst):
    lst.aktualisieren()
    sub = _eintrag(_einstellungen(lst), "Wechsel-Schwelle").submenu.items
    _eintrag(sub, "90 %")(lst.icon)
    assert anzeige.schwelle() == 90
    sub = _eintrag(_einstellungen(lst), "Wechsel-Schwelle").submenu.items
    assert [i.checked for i in sub] == [False, True, False, False, False]
    assert lst.icon.menue_neu >= 2


def test_messfehler_zeigt_sichere_menuezeile_und_429_backoff(lst, monkeypatch):
    def begrenzt():
        raise leiste.claude_messen.MessFehler("Claude-Kontingent konnte nicht gelesen werden", 429)

    monkeypatch.setattr(leiste.claude_messen, "messen", begrenzt)
    lst._messung_ausfuehren()

    assert lst._messung_intervall == 300
    assert any("Claude-Messung:" in item.text and "konnte nicht gelesen werden" in item.text
               for item in lst._menue())


def test_messfehler_zeigt_keine_unerwarteten_exceptiondetails(lst, monkeypatch):
    geheim = "synthetischer-geheim-token"
    monkeypatch.setattr(leiste.claude_messen, "messen", lambda: (_ for _ in ()).throw(RuntimeError(geheim)))

    lst._messung_ausfuehren()

    assert "Claude-Messung konnte nicht gelesen werden" in lst._messung_fehler
    assert geheim not in lst._messung_fehler


def test_erfolg_beendet_429_backoff_und_nutzt_einstellung(lst, monkeypatch, tmp_path):
    datei = tmp_path / "einstellungen.json"
    anzeige.claude_takt_setzen(12, datei)
    monkeypatch.setattr(anzeige, "einstellungen_datei", lambda: datei)
    lst._429_aktiv = True
    lst._messung_intervall = 300
    monkeypatch.setattr(leiste.claude_messen, "messen", lambda: True)

    lst._messung_ausfuehren()

    assert lst._messung_fehler is None
    assert lst._429_aktiv is False
    assert lst._messung_intervall == 12 * 60


def test_parallelmessung_wird_uebersprungen(lst, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(leiste.claude_messen, "messen", lambda: aufrufe.append(True))
    assert lst._messung_sperre.acquire(blocking=False)
    try:
        lst._messung_ausfuehren()
    finally:
        lst._messung_sperre.release()

    assert aufrufe == []


def test_start_fordert_sofortige_hintergrundmessung_an(lst, monkeypatch):
    threads = []

    class ThreadAttrappe:
        def __init__(self, **kw):
            self.kw = kw
            threads.append(self)

        def start(self):
            self.gestartet = True

    monkeypatch.setattr(leiste.threading, "Thread", ThreadAttrappe)
    lst._start(lst.icon)

    assert lst._messung_angefordert.is_set()
    assert threads[0].kw["daemon"] is True
    assert threads[0].gestartet is True


def test_menue_aktualisieren_fordert_messung_an(lst):
    eintrag = _eintrag(list(lst._menue()), "Aktualisieren")
    eintrag(lst.icon)

    assert lst._messung_angefordert.is_set()


def test_menue_anzeige_bleibt_auch_bei_langem_claude_takt_minutlich(lst, monkeypatch):
    class StopAttrappe:
        anzahl = 0

        def is_set(self):
            self.anzahl += 1
            return self.anzahl > 2

    class AnfrageAttrappe:
        def wait(self, sekunden):
            assert sekunden == leiste.TAKT_SEKUNDEN
            return False

        def clear(self):
            pass

    aktualisierungen = []
    messungen = []
    monkeypatch.setattr(leiste.time, "monotonic", lambda: 100)
    monkeypatch.setattr(lst, "aktualisieren", lambda: aktualisierungen.append(True))
    monkeypatch.setattr(lst, "_messung_ausfuehren", lambda: messungen.append(True))
    lst._stopp = StopAttrappe()
    lst._messung_angefordert = AnfrageAttrappe()
    lst._messung_intervall = 15 * 60

    lst._takt()

    assert aktualisierungen == [True]
    assert messungen == []


def test_429_pause_wird_durch_manuelles_aktualisieren_nicht_umgangen(lst, monkeypatch):
    zeit = [0]

    class StopAttrappe:
        anzahl = 0

        def is_set(self):
            self.anzahl += 1
            return self.anzahl > 10

    class AnfrageAttrappe:
        anzahl = 0

        def wait(self, sekunden):
            assert sekunden == leiste.TAKT_SEKUNDEN
            self.anzahl += 1
            zeit[0] += 60
            return self.anzahl <= 4

        def clear(self):
            pass

    aktualisierungen = []
    messzeiten = []
    monkeypatch.setattr(leiste.time, "monotonic", lambda: zeit[0])
    monkeypatch.setattr(lst, "aktualisieren", lambda: aktualisierungen.append(zeit[0]))
    monkeypatch.setattr(lst, "_messung_ausfuehren", lambda: messzeiten.append(zeit[0]))
    monkeypatch.setattr(lst, "_bestaetigung_anfordern", lambda: None)   # eigener Faden – kein Rennen um die Zählung
    lst._stopp = StopAttrappe()
    lst._messung_angefordert = AnfrageAttrappe()
    lst._messung_intervall = 300
    lst._429_aktiv = True

    lst._takt()

    assert aktualisierungen == [60, 120, 180, 240, 300, 300]
    assert messzeiten == [300]


# --- Automatik (v0.3.0) -------------------------------------------------------

THREAD = "01a12557-3bb3-7171-a021-53e6ac879534"


def test_menue_ohne_automatik_haken_und_jetzt_pruefen(lst):
    """v0.3.2: der Automatik-Haken entfällt; „Jetzt prüfen" ging in „Aktualisieren" auf."""
    lst.aktualisieren()
    texte = _texte(lst._menue())
    assert "Automatik Claude → Codex" not in texte
    assert "Jetzt prüfen" not in texte
    assert "Automatik je Thema" in _texte(_einstellungen(lst))
    assert "Aktualisieren" in texte


class _Sofort:
    """Attrappe statt echtem Faden: führt das Ziel beim Start sofort aus."""

    def __init__(self, target=None, args=(), daemon=None):
        self._ziel = target
        self._args = args

    def start(self):
        self._ziel(*self._args)

    def is_alive(self):
        return False


_ECHTER_THREAD = leiste.threading.Thread


class _ThreadSammler:
    """Startet echte Fäden und hält sie für begrenztes Aufräumen fest."""

    threads = []

    def __init__(self, *, target, args=(), daemon=None):
        self._thread = _ECHTER_THREAD(target=target, args=args, daemon=daemon)
        self.threads.append(self)

    def start(self):
        self._thread.start()

    def join(self, timeout=2):
        self._thread.join(timeout)

    def is_alive(self):
        return self._thread.is_alive()

    @classmethod
    def aufraeumen(cls):
        for thread in cls.threads:
            thread.join(2)
        assert all(not thread.is_alive() for thread in cls.threads)
        cls.threads.clear()


def test_menueaktion_kehren_zurueck_waehrend_dialog_wartet(lst, monkeypatch):
    _ThreadSammler.threads.clear()
    monkeypatch.setattr(leiste.threading, "Thread", _ThreadSammler)
    dialog_betreten = leiste.threading.Event()
    dialog_freigeben = leiste.threading.Event()
    rueckkehr = leiste.threading.Event()

    def dialog(*_args):
        dialog_betreten.set()
        dialog_freigeben.wait(2)
        return False

    lst._dialog = dialog
    aktion = lst._wechsel_aktion("codex")
    aufrufer = _ECHTER_THREAD(target=lambda: (aktion(), rueckkehr.set()), daemon=True)
    aufrufer.start()
    try:
        assert rueckkehr.wait(2)
        assert dialog_betreten.wait(2)
        assert len(_ThreadSammler.threads) == 1
    finally:
        dialog_freigeben.set()
        aufrufer.join(2)
        _ThreadSammler.aufraeumen()
    assert not aufrufer.is_alive()


def test_belegte_sperre_unterdrueckt_gleichzeitige_und_direkte_aufrufe(lst, monkeypatch):
    _ThreadSammler.threads.clear()
    monkeypatch.setattr(leiste.threading, "Thread", _ThreadSammler)
    dialog_betreten = leiste.threading.Event()
    dialog_freigeben = leiste.threading.Event()
    dialogaufrufe = []

    def dialog(*_args):
        dialogaufrufe.append(True)
        dialog_betreten.set()
        dialog_freigeben.wait(2)
        return False

    lst._dialog = dialog
    aktion = lst._wechsel_aktion("codex")
    aktion()
    try:
        assert dialog_betreten.wait(2)
        aktion()
        lst._wechseln("hermes")
        assert dialogaufrufe == [True]
        assert len(_ThreadSammler.threads) == 1
    finally:
        dialog_freigeben.set()
        _ThreadSammler.aufraeumen()


def test_reentrante_menue_und_direktaufrufe_werden_uebersprungen(lst, monkeypatch):
    _ThreadSammler.threads.clear()
    monkeypatch.setattr(leiste.threading, "Thread", _ThreadSammler)
    dialogaufrufe = []
    aktion = lst._wechsel_aktion("codex")

    def dialog(*_args):
        dialogaufrufe.append(True)
        if len(dialogaufrufe) == 1:
            aktion()
            lst._wechseln("hermes")
        return False

    lst._dialog = dialog
    try:
        aktion()
        _ThreadSammler.aufraeumen()
        assert dialogaufrufe == [True]
        assert len(_ThreadSammler.threads) == 0
    finally:
        _ThreadSammler.aufraeumen()


def test_nein_und_dialogfehler_geben_sperre_fuer_neuen_versuch_frei(lst, monkeypatch):
    wechselaufrufe = []
    monkeypatch.setattr(leiste.wechsel, "wechseln", lambda *a, **k: wechselaufrufe.append(a))
    lst._dialog = lambda *_args: False
    lst._wechseln("codex")
    assert wechselaufrufe == []
    assert lst.icon.meldungen == []

    def dialogfehler(*_args):
        raise RuntimeError("Dialogfehler")

    lst._dialog = dialogfehler
    lst._wechseln("codex")
    assert "Bestätigung fehlgeschlagen" in lst.icon.meldungen[-1][1]

    lst._dialog = lambda *_args: False
    lst._wechseln("codex")
    assert wechselaufrufe == []
    assert len(lst.icon.meldungen) == 1


def test_ja_wechselt_genau_einmal_und_startet_codex_rueckgabe(lst, monkeypatch):
    class E:
        art, master, paket, meldung = "gewechselt", "codex", None, ""

    wechselaufrufe = []
    rueckgaben = []
    monkeypatch.setattr(leiste.wechsel, "wechseln", lambda *a, **k: wechselaufrufe.append(a) or E())
    monkeypatch.setattr(leiste.rueckgabe, "rueckgabe", lambda **k: rueckgaben.append(True) or [])
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    lst._dialog = lambda *_args: True

    lst._wechseln("codex")

    assert wechselaufrufe == [("codex",)]
    assert rueckgaben == [True]
    assert len(lst.icon.meldungen) == 1


@pytest.mark.parametrize("fehlerphase", ["konstruktion", "start"])
def test_threadfehler_meldet_sich_gibt_sperre_frei_und_erlaubt_neuen_versuch(
        lst, monkeypatch, fehlerphase):
    class ThreadFehler:
        def __init__(self, **_kwargs):
            if fehlerphase == "konstruktion":
                raise RuntimeError("Threadfehler")

        def start(self):
            raise RuntimeError("Threadfehler")

    monkeypatch.setattr(leiste.threading, "Thread", ThreadFehler)
    lst._dialog = lambda *_args: False
    aktion = lst._wechsel_aktion("codex")
    aktion()
    assert "Threadfehler" in lst.icon.meldungen[-1][1]

    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    dialogaufrufe = []
    lst._dialog = lambda *_args: dialogaufrufe.append(True) or False
    aktion()
    assert dialogaufrufe == [True]


def test_notifyfehler_verhindert_sperrfreigabe_nicht(lst, monkeypatch):
    dialogaufrufe = []
    lst._dialog = lambda *_args: dialogaufrufe.append(True) or (_ for _ in ()).throw(
        RuntimeError("Dialogfehler"))
    monkeypatch.setattr(lst.icon, "notify", lambda *_args: (_ for _ in ()).throw(RuntimeError("Notifyfehler")))

    lst._wechseln("codex")
    lst._wechseln("codex")

    assert dialogaufrufe == [True, True]


def test_dialog_flags_und_ergebnis_werden_fail_closed_ausgewertet(lst, monkeypatch):
    from types import SimpleNamespace
    from master_schalter import dialog

    ergebnisse = []
    monkeypatch.setattr(dialog.ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(
        MessageBoxW=lambda *args: ergebnisse.pop(0))), raising=False)
    ergebnisse.extend([dialog.IDYES, 7, 0])

    assert dialog.frage("Titel", "Text") is True
    assert dialog.frage("Titel", "Text") is False
    assert dialog.frage("Titel", "Text") is False




def test_wechsel_fragt_und_bricht_bei_nein_ab(lst, monkeypatch):
    gerufen = []
    monkeypatch.setattr(leiste.wechsel, "wechseln", lambda *a, **k: gerufen.append(a))
    lst._dialog = lambda titel, text: False
    lst._wechseln("codex")
    assert gerufen == [] and lst.icon.meldungen == []


def test_wechsel_ja_wechselt_und_stoesst_die_rueckgabe_an(lst, monkeypatch):
    class E:
        art, master, paket, meldung = "gewechselt", "codex", None, ""

    monkeypatch.setattr(leiste.wechsel, "wechseln", lambda *a, **k: E())
    gerufen = []
    monkeypatch.setattr(leiste.rueckgabe, "rueckgabe", lambda **k: gerufen.append(True) or [])
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    lst._dialog = lambda titel, text: True
    lst._wechseln("codex")
    assert gerufen == [True]
    assert len(lst.icon.meldungen) == 1


def test_wechsel_bei_gleich_keine_rueckgabe(lst, monkeypatch):
    class E:
        art, master, paket, meldung = "gleich", "codex", None, ""

    monkeypatch.setattr(leiste.wechsel, "wechseln", lambda *a, **k: E())
    gerufen = []
    monkeypatch.setattr(leiste.rueckgabe, "rueckgabe", lambda **k: gerufen.append(True) or [])
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    lst._dialog = lambda titel, text: True
    lst._wechseln("codex")
    assert gerufen == []


def test_wechsel_text_nennt_die_themen(lst):
    paare.setzen("engineering", THREAD, ".hermes/uebergabe/laufend/engineering.md", aktiv=True)
    lst.aktualisieren()
    text = lst._wechsel_text("codex")
    assert "engineering" in text and "Nachricht" in text and "echtes ACK" in text
    assert "Kopfzeile" in text        # Kopfzeilen-Zustand je Thema (hier: fehlt)
    assert "bereits Standard-Master" in text and "kein neues Übergabepaket" in text
    assert "--erneut" not in text      # keine erneute Übergabe bei bereits aktivem Codex


def test_kopfzeilen_zustand_liest_bereit_nein_und_head(lst, monkeypatch):
    import os
    repo = Path(os.environ["MASTER_SCHALTER_REPO"])
    datei = repo / ".hermes" / "uebergabe" / "laufend" / "engineering.md"
    datei.parent.mkdir(parents=True, exist_ok=True)
    paar = paare.Paar("engineering", THREAD, ".hermes/uebergabe/laufend/engineering.md", True)
    monkeypatch.setattr(leiste.automatik, "kopf_hash",
                        lambda repo, git=None: "abcdef1234567890")
    datei.write_text(
        f"Übergabebereit: ja · {datetime.now(timezone.utc).isoformat()} · abcdef1\n",
        encoding="utf-8")
    assert lst._kopfzeilen_zustand(paar) == "bereit"
    datei.write_text(
        f"Übergabebereit: ja · {datetime.now(timezone.utc).isoformat()} · 9999999999\n",
        encoding="utf-8")
    assert lst._kopfzeilen_zustand(paar) == "Stand veraltet – wird beim Senden gezogen"
    datei.write_text("Übergabebereit: nein · 2026-10-16T04:00:00+00:00 · abcdef1\n",
                     encoding="utf-8")
    assert lst._kopfzeilen_zustand(paar) == "steht auf nein"


def test_messfehler_werden_mit_zeitstempel_protokolliert(lst, monkeypatch, capsys):
    def kaputt(**kw):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(leiste.claude_messen, "messen", kaputt)
    lst._messung_ausfuehren()
    fehler = capsys.readouterr().err
    assert "Claude-Messung konnte nicht gelesen werden" in fehler
    assert re.search(r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\]", fehler)


def test_aktualisieren_hakt_uebergaben_ab(lst, monkeypatch):
    gerufen = []
    monkeypatch.setattr(leiste.automatik, "bestaetigungen_pruefen",
                        lambda **k: gerufen.append(True) or [])
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    lst._aktualisieren_aktion()
    assert gerufen == [True]


def test_chat_untermenue_zeigt_je_paar_status_und_haken(lst):
    paare.setzen("engineering", THREAD, ".hermes/uebergabe/laufend/engineering.md", aktiv=True)
    lst.aktualisieren()
    sub = _eintrag(_einstellungen(lst), "Automatik je Thema").submenu.items
    assert _texte(sub) == ["engineering: bereit"]
    assert sub[0].checked is True


def test_chat_untermenue_ohne_paare(lst):
    sub = _eintrag(_einstellungen(lst), "Automatik je Thema").submenu.items
    assert _texte(sub) == ["keine Paare angelegt"]
    assert not sub[0].enabled


def test_paar_haken_schaltet_das_paar_um(lst):
    paare.setzen("engineering", THREAD, ".hermes/uebergabe/laufend/engineering.md", aktiv=False)
    lst.aktualisieren()
    sub = _eintrag(_einstellungen(lst), "Automatik je Thema").submenu.items
    sub[0](lst.icon)
    assert paare.lesen()[0].aktiv is True


def test_chat_untermenue_zeigt_bestaetigten_status(lst):
    d = leiste.vorgaenge.Vorgang("engineering@1", "engineering", "l", "bestaetigt", JETZT.isoformat())
    leiste.vorgaenge.aendern(lambda alt: [*alt, d])
    paare.setzen("engineering", THREAD, ".hermes/uebergabe/laufend/engineering.md", aktiv=True)
    lst.aktualisieren()
    sub = _eintrag(_einstellungen(lst), "Automatik je Thema").submenu.items
    assert _texte(sub) == ["engineering: bestätigt"]


def test_automatik_anfordern_ist_bei_aus_still(lst, monkeypatch):
    threads = []
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: threads.append(kw))

    lst._automatik_anfordern()

    assert threads == []


def test_automatik_anfordern_startet_bei_an_einen_faden(lst, monkeypatch):
    anzeige.automatik_setzen(True)
    threads = []

    class ThreadAttrappe:
        def __init__(self, **kw):
            threads.append(kw)

        def start(self):
            self.gestartet = True

    monkeypatch.setattr(leiste.threading, "Thread", ThreadAttrappe)

    lst._automatik_anfordern()

    assert threads and threads[0]["daemon"] is True


def test_automatik_ausfuehren_legt_staende_ab(lst, monkeypatch):
    monkeypatch.setattr(leiste.automatik, "lauf",
                        lambda **kw: [leiste.automatik.Stand("engineering", "bereit (trocken)")])
    monkeypatch.setattr(leiste.automatik, "bestaetigungen_pruefen", lambda *a, **kw: [])

    lst._automatik_ausfuehren()

    assert lst._automatik_staende_zeilen() == ["engineering: bereit (trocken)"]
    assert "engineering: bereit (trocken)" in _texte(lst._menue())


def test_automatik_ausfuehren_zeigt_fehler_statt_abzustuerzen(lst, monkeypatch):
    def kaputt(**kw):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(leiste.automatik, "lauf", kaputt)

    lst._automatik_ausfuehren()

    assert lst._automatik_staende_zeilen() == ["Automatikprüfung fehlgeschlagen"]


def test_takt_prueft_die_automatik_nach_erfolgreicher_messung(lst, monkeypatch):
    class StopAttrappe:
        def __init__(self):
            self.n = 0

        def is_set(self):
            self.n += 1
            return self.n > 2

    class AnfrageAttrappe:
        def wait(self, sekunden):
            return False

        def clear(self):
            pass

    angefragt = []
    anzeige.automatik_setzen(True)
    monkeypatch.setattr(lst, "aktualisieren", lambda: None)
    monkeypatch.setattr(lst, "_messung_ausfuehren", lambda: None)
    monkeypatch.setattr(lst, "_automatik_anfordern", lambda: angefragt.append(True))
    lst._stopp = StopAttrappe()
    lst._messung_angefordert = AnfrageAttrappe()
    lst._messung_fehler = None
    lst._429_aktiv = False
    lst._messung_intervall = -1   # Intervall gilt sofort als abgelaufen

    lst._takt()

    assert angefragt and all(angefragt)


def test_takt_hakt_uebergaben_ab_wenn_automatik_aus(lst, monkeypatch):
    """v0.3.2: ohne Automatik läuft nach der Messung nur die Bestätigungsprüfung."""
    class StopAttrappe:
        def __init__(self):
            self.n = 0

        def is_set(self):
            self.n += 1
            return self.n > 2

    class AnfrageAttrappe:
        def wait(self, sekunden):
            return False

        def clear(self):
            pass

    abgehakt = []
    anzeige.automatik_setzen(False)
    monkeypatch.setattr(lst, "aktualisieren", lambda: None)
    monkeypatch.setattr(lst, "_messung_ausfuehren", lambda: None)
    monkeypatch.setattr(lst, "_bestaetigung_anfordern", lambda: abgehakt.append(True))
    lst._stopp = StopAttrappe()
    lst._messung_angefordert = AnfrageAttrappe()
    lst._messung_fehler = None
    lst._429_aktiv = False
    lst._messung_intervall = -1

    lst._takt()

    assert abgehakt and all(abgehakt)


# --- Rollenprofile und Modellkataloge (v0.4.0) --------------------------------

class _ThreadAttrappe:
    """Fängt Fadenwünsche ab, ohne sie auszuführen – der Klick bleibt beweisbar im Klickfaden."""

    def __init__(self, **kw):
        kw["gestartet"] = False
        self.kw = kw

    def start(self):
        self.kw["gestartet"] = True


def _katalog_schreiben(provider, *eintraege, fehler=None, veraltet=False):
    """Synthetischer Metadatencache – keine Prozesse, kein Netz."""
    pfad = modelle.datei()
    pfad.parent.mkdir(parents=True, exist_ok=True)
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        roh = {"version": 1, "anbieter": {}}
    zeit = (datetime.now(timezone.utc) - timedelta(hours=25) if veraltet
            else datetime.now(timezone.utc)).isoformat()
    roh["anbieter"][provider] = {"zeit": zeit, "fehler": fehler,
                                 "modelle": [{"id": kennung, "name": name} for kennung, name in eintraege]}
    pfad.write_text(json.dumps(roh, ensure_ascii=False), encoding="utf-8")


def _thema_vorbereiten(lst, *, master="kontingent", worker="workflow", modell=None, thema="engineering"):
    paare.setzen(thema, THREAD, paare.laufend_bilden(thema), aktiv=True)
    modi._speichern(modi.datei(), thema, modi.Profil(master, worker, modell))
    lst.aktualisieren()


def _gruppen(lst, thema):
    return _eintrag(list(_eintrag(_einstellungen(lst), "Arbeitsmodus je Thema").submenu.items),
                    thema).submenu.items


def _gruppe(lst, thema, name):
    return _eintrag(list(_gruppen(lst, thema)), name).submenu.items


@pytest.mark.parametrize("master", modi.MASTER_WERTE)
def test_mastergruppe_hakt_genau_die_gewaehlte_rolle(lst, master):
    _thema_vorbereiten(lst, master=master)
    master_items = _gruppe(lst, "engineering", "Master")

    assert [i.checked for i in master_items] == [wert == master for _, wert in anzeige.MASTER_AUSWAHL]


@pytest.mark.parametrize("worker", modi.WORKER_WERTE)
def test_ausfuehrergruppe_hakt_genau_die_gewaehlte_vorgabe(lst, worker):
    modell = modi.HERMES_MODELL if worker == "hermes" else None
    _thema_vorbereiten(lst, master="kontingent", worker=worker, modell=modell)
    ausfuehrer = [i for i in _gruppe(lst, "engineering", "Ausführer") if i.enabled]

    assert _texte(ausfuehrer) == ["Nach Workflow", "Claude Code", "Codex", "Hermes"]
    assert [i.checked for i in ausfuehrer] == [wert == worker for _, wert in anzeige.WORKER_AUSWAHL]


def test_ausfuehrergruppe_nennt_vorgabe_und_providerherkunft(lst):
    _thema_vorbereiten(lst)
    ausfuehrer = _gruppe(lst, "engineering", "Ausführer")
    hinweise = [i.text for i in ausfuehrer if not i.enabled]

    assert any("Ausführervorgabe" in text and "keine Sitzung" in text for text in hinweise)
    assert any("ChatGPT-Abo" in text and "OpenRouter" in text for text in hinweise)


def test_modellgruppe_workflow_zeigt_nur_den_deaktivierten_hinweis(lst):
    _thema_vorbereiten(lst, worker="workflow")
    modell_items = _gruppe(lst, "engineering", "Ausführermodell")

    assert len(modell_items) == 1
    assert modell_items[0].enabled is False and "Workflow" in modell_items[0].text


def test_modellgruppe_hermes_genau_deepseek_mit_kostenhinweis(lst):
    _thema_vorbereiten(lst, master="hermes", worker="hermes", modell=modi.HERMES_MODELL)
    modell_items = _gruppe(lst, "engineering", "Ausführermodell")
    wahl = [i for i in modell_items if i.enabled]

    assert _texte(wahl) == ["DeepSeek V4.1 Flash"]
    assert wahl[0].checked is True
    assert any("kostenpflichtig" in i.text for i in modell_items if not i.enabled)


def test_modellgruppe_dynamische_namen_und_gesetztes_haken(lst):
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"), ("gpt-6-sol", "GPT-6 Sol"))
    _thema_vorbereiten(lst, master="hermes", worker="codex", modell="gpt-6-luna")
    modell_items = _gruppe(lst, "engineering", "Ausführermodell")
    wahl = [i for i in modell_items if i.enabled]

    assert _texte(wahl) == ["GPT-6 Luna", "GPT-6 Sol"]
    assert [i.checked for i in wahl] == [True, False]
    assert any("ChatGPT-Abo" in i.text for i in modell_items if not i.enabled)


def test_modellgruppe_fehlender_katalog_blockiert_nichts(lst):
    _thema_vorbereiten(lst, worker="codex", modell=None)
    modell_items = _gruppe(lst, "engineering", "Ausführermodell")

    assert any("Modelle aktualisieren" in i.text for i in modell_items if not i.enabled)
    standard = next(i for i in modell_items if i.text == anzeige.STANDARD_MODELL)
    assert standard.enabled and standard.checked        # Defaultwahl bleibt bewusst verfügbar
    assert any("Modellkatalog Codex:" in i.text for i in _einstellungen(lst))


def test_modellgruppe_veralteter_katalog_nennt_hinweis_und_sperrt_neuauswahl(lst):
    _katalog_schreiben("codex", ("gpt-6-alt", "GPT-6 Alt"), veraltet=True)
    _thema_vorbereiten(lst, master="hermes", worker="codex", modell="gpt-6-alt")
    modell_items = _gruppe(lst, "engineering", "Ausführermodell")

    assert any("veraltet" in i.text for i in modell_items if not i.enabled)
    alt = next(i for i in modell_items if i.text == "GPT-6 Alt")
    assert alt.enabled is False and alt.checked is True      # gespeicherte Auswahl bleibt sichtbar
    assert not any(i.enabled and i.text != anzeige.STANDARD_MODELL for i in modell_items)


def test_modellgruppe_fehlerkatalog_wird_benannt(lst):
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"), fehler="Zeitüberschreitung")
    _thema_vorbereiten(lst, master="hermes", worker="codex", modell="gpt-6-luna")
    modell_items = _gruppe(lst, "engineering", "Ausführermodell")

    assert any("Zeitüberschreitung" in i.text for i in modell_items if not i.enabled)
    assert not any(i.enabled and i.text == "GPT-6 Luna" for i in modell_items)
    assert any("Modellkatalog Codex: Zeitüberschreitung" == i.text for i in _einstellungen(lst))


def test_modellgruppe_alte_auswahl_nach_refresh_nicht_bestaetigt(lst):
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"), ("gpt-6-sol", "GPT-6 Sol"))
    _thema_vorbereiten(lst, master="hermes", worker="codex", modell="gpt-6-alt")
    modell_items = _gruppe(lst, "engineering", "Ausführermodell")

    alt = next(i for i in modell_items if "gespeichert" in i.text)
    assert alt.text == "gpt-6-alt (gespeichert, nicht bestätigt)"
    assert alt.enabled is False and alt.checked is True      # nie still ersetzt
    assert _texte([i for i in modell_items if i.enabled]) == ["GPT-6 Luna", "GPT-6 Sol"]


def test_masterklick_speichert_im_hintergrund_und_meldet(lst, monkeypatch):
    _thema_vorbereiten(lst)
    master_items = _gruppe(lst, "engineering", "Master")
    threads = []
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: threads.append(kw) or _ThreadAttrappe(**kw))

    _eintrag(list(master_items), "Hermes")(lst.icon)

    assert threads and threads[0]["daemon"] is True          # nur der Faden wurde angefordert
    assert modi.profil("engineering").master == "kontingent"  # im Klickfaden ist nichts passiert

    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    _eintrag(list(master_items), "Hermes")(lst.icon)

    assert modi.profil("engineering").master == "hermes"
    assert lst.icon.meldungen[-1][1] == "engineering: Master Hermes gespeichert – keine Sitzung gestartet."


def test_workerwechsel_per_menue_setzt_das_modell_auf_standard(lst, monkeypatch):
    _katalog_schreiben("claude", ("opus", "Opus"))
    _thema_vorbereiten(lst, master="hermes", worker="codex", modell="gpt-6-luna")
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)

    _eintrag(list(_gruppe(lst, "engineering", "Ausführer")), "Claude Code")(lst.icon)

    profil = modi.profil("engineering")
    assert (profil.master, profil.worker, profil.modell) == ("hermes", "claude", None)
    assert lst.icon.meldungen[-1][1] == ("engineering: Ausführer Claude Code gespeichert – "
                                         "Ausführermodell Standard des Werkzeugs · keine Sitzung gestartet.")


def test_modellklick_speichert_das_gewaehlte_modell(lst, monkeypatch):
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"), ("gpt-6-sol", "GPT-6 Sol"))
    _thema_vorbereiten(lst, master="hermes", worker="codex", modell="gpt-6-luna")
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)

    _eintrag(list(_gruppe(lst, "engineering", "Ausführermodell")), "GPT-6 Sol")(lst.icon)

    assert modi.profil("engineering").modell == "gpt-6-sol"
    assert lst.icon.meldungen[-1][1] == "engineering: Ausführermodell gpt-6-sol gespeichert – keine Sitzung gestartet."


def test_modelle_aktualisieren_menuepunkt_ist_hintergrund_und_single_flight(lst, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(leiste.modelle, "alle_aktualisieren", lambda: aufrufe.append(True) or {})
    threads = []
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: threads.append(kw) or _ThreadAttrappe(**kw))

    _eintrag(_einstellungen(lst), anzeige.MODELLE_AKTUALISIEREN)(lst.icon)

    assert threads and aufrufe == []                          # nichts im Menüfaden abgefragt

    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    assert lst._modelle_sperre.acquire(blocking=False)
    try:
        lst._modelle_aktualisieren()                          # belegt → übersprungen
    finally:
        lst._modelle_sperre.release()
    assert aufrufe == []
    lst._modelle_aktualisieren()                              # frei → genau ein Abgleich
    assert aufrufe == [True]


def test_start_fordert_frischen_katalogabgleich_nur_bei_veraltetem_stand(lst, monkeypatch):
    threads = []
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: threads.append(kw) or _ThreadAttrappe(**kw))
    _katalog_schreiben("claude", ("opus", "Opus"))
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"))

    lst._start(lst.icon)
    assert len(threads) == 2                                  # frisch: Messtakt und Takt des Wechselassistenten

    threads.clear()
    lst._kataloge = None
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"), veraltet=True)
    lst._start(lst.icon)
    assert len(threads) == 3 and all(kw["daemon"] is True for kw in threads)   # beide Takte + Katalogabgleich


def test_modellabgleich_wird_gedrosselt_nicht_doppelt_angefordert(lst, monkeypatch):
    threads = []
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: threads.append(kw) or _ThreadAttrappe(**kw))
    _katalog_schreiben("claude", ("opus", "Opus"), veraltet=True)
    lst.aktualisieren()

    lst._modellabgleich_pruefen()
    lst._modellabgleich_pruefen()
    lst._modelle_anfordern()                                  # Drossel greift auch hier

    assert len(threads) == 1


def test_takt_fordert_bei_veraltetem_katalog_einen_hintergrundabgleich(lst, monkeypatch):
    class StopAttrappe:
        def __init__(self):
            self.n = 0

        def is_set(self):
            self.n += 1
            return self.n > 2

    class AnfrageAttrappe:
        def wait(self, sekunden):
            return False

        def clear(self):
            pass

    _katalog_schreiben("claude", ("opus", "Opus"), veraltet=True)
    _katalog_schreiben("codex", ("gpt-6-luna", "GPT-6 Luna"))
    lst.aktualisieren()
    threads = []
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: threads.append(kw) or _ThreadAttrappe(**kw))
    monkeypatch.setattr(lst, "aktualisieren", lambda: None)
    monkeypatch.setattr(lst, "_messung_ausfuehren", lambda: None)
    lst._stopp = StopAttrappe()
    lst._messung_angefordert = AnfrageAttrappe()
    lst._messung_fehler = None
    lst._429_aktiv = False
    lst._messung_intervall = 10 ** 9

    lst._takt()

    assert len(threads) == 1 and threads[0]["daemon"] is True


# --- Wechselassistent in der Leiste (v0.5.0, P7a) ------------------------------------------

from master_schalter import assistent_vorgaenge as av  # noqa: E402


def _wechsel_vorgang(ident="w-1", phase="abgabe_angefragt", thema="engineering", ziel="hermes", von="claude",
                     zeit=None, **felder):
    return av.Vorgang(ident, thema, ziel, von, phase, (zeit or datetime.now(timezone.utc)).isoformat(),
                      {"master": "kontingent", "worker": "workflow", "modell": None}, "", **felder)


def _vorgaenge_ablegen(*liste):
    av.aendern(lambda alt: [*alt, *liste])


def _sichtbar(lst):
    return [i.text for i in lst._menue() if i.text != "Details"]


def test_menue_oben_ist_nach_e9_aufgebaut(lst):
    lst.aktualisieren()
    texte = _sichtbar(lst)
    reihenfolge = ["Übergabe starten …", "Aktualisieren", "Einstellungen ▸", "Beenden"]
    stellen = [texte.index(t) for t in reihenfolge]
    assert stellen == sorted(stellen)
    assert texte[-1] == "Beenden" and texte[-2] == "Einstellungen ▸" and texte[-3] == "Aktualisieren"
    assert texte.index("Übergabe starten …") > max(i for i, t in enumerate(texte) if t.startswith("Claude"))


def test_einstellungen_enthalten_die_umgehaengten_punkte_in_der_vorgegebenen_reihenfolge(lst):
    lst.aktualisieren()
    texte = _texte(_einstellungen(lst))
    ordnung = ["Wechsel-Schwelle", anzeige.MODELLE_AKTUALISIEREN, "Automatik je Thema", "Arbeitsmodus je Thema",
               "Standard-Master (übrige Themen)"]
    stellen = [texte.index(t) for t in ordnung]
    assert stellen == sorted(stellen) and texte[0] == "Wechsel-Schwelle"
    assert texte[-1] == "Standard-Master (übrige Themen)"
    katalog = [t for t in texte if t.startswith("Modellkatalog")]
    assert katalog and all(stellen[0] < texte.index(t) < stellen[1] for t in katalog)   # Katalogzeilen vor „Modelle aktualisieren“


def test_umgehaengte_punkte_behalten_ihre_funktion(lst, monkeypatch):
    """„Automatik je Thema“ schaltet wie früher „Chats übergeben“, „Standard-Master“ wie „Master wechseln“."""
    paare.setzen("engineering", THREAD, ".hermes/uebergabe/laufend/engineering.md", aktiv=False)
    lst.aktualisieren()
    _eintrag(_einstellungen(lst), "Automatik je Thema").submenu.items[0](lst.icon)
    assert paare.lesen()[0].aktiv is True

    aufrufe = []
    monkeypatch.setattr(wechsel, "wechseln", lambda nach, hinweis=None, **kw: aufrufe.append(nach) or
                        wechsel.Ergebnis("gleich", nach, None, ""))
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    lst._dialog = lambda titel, text: True
    _eintrag(_eintrag(_einstellungen(lst), "Standard-Master (übrige Themen)").submenu.items, "Hermes")(lst.icon)
    assert aufrufe == ["hermes"]


def test_offene_wechsel_erscheinen_als_deaktivierte_zeilen(lst):
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "abgabe_angefragt"), _wechsel_vorgang("w-2", "im_postfach", ziel="claude"),
                       _wechsel_vorgang("w-3", "bestaetigt"), _wechsel_vorgang("w-4", "verworfen"))
    lst.aktualisieren()

    zeilen = [i for i in lst._menue() if i.text.startswith("Wechsel ")]

    assert [i.text for i in zeilen] == ["Wechsel engineering: wartet auf Abgabe",
                                        "Wechsel engineering: liegt im Postfach"]
    assert not any(i.enabled for i in zeilen)


def test_ohne_offene_wechsel_keine_wechselzeilen(lst):
    _vorgaenge_ablegen(_wechsel_vorgang("w-3", "bestaetigt"))
    lst.aktualisieren()
    assert not [i for i in lst._menue() if i.text.startswith("Wechsel ")]


def test_menue_baut_die_wechselzeilen_nur_aus_der_momentaufnahme(lst, monkeypatch):
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "abgabe_angefragt"))
    lst.aktualisieren()

    def kaputt(*_a, **_k):
        raise AssertionError("Dateizugriff im Menüfaden")

    monkeypatch.setattr(av, "lesen", kaputt)
    assert [i.text for i in lst._menue() if i.text.startswith("Wechsel ")] == ["Wechsel engineering: wartet auf Abgabe"]


# --- Fenster öffnen --------------------------------------------------------------------------

def test_fenster_befehl_bevorzugt_pythonw_neben_dem_interpreter(tmp_path, monkeypatch):
    (tmp_path / "python.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(leiste.sys, "executable", str(tmp_path / "python.exe"))
    assert leiste.fenster_befehl() == [str(tmp_path / "python.exe"), "-m", "master_schalter.fenster"]
    (tmp_path / "pythonw.exe").write_text("", encoding="utf-8")
    assert leiste.fenster_befehl() == [str(tmp_path / "pythonw.exe"), "-m", "master_schalter.fenster"]


def test_uebergabe_starten_oeffnet_das_fenster_in_eigenem_faden_und_eigenem_prozess(lst, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(leiste.subprocess, "Popen", lambda befehl, **kw: aufrufe.append((befehl, kw)))
    threads = []
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: threads.append(kw) or _ThreadAttrappe(**kw))

    _eintrag(list(lst._menue()), "Übergabe starten …")(lst.icon)

    assert aufrufe == [] and threads and threads[0]["daemon"] is True        # im Klickfaden startet nichts

    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)
    _eintrag(list(lst._menue()), "Übergabe starten …")(lst.icon)

    assert len(aufrufe) == 1
    befehl, kw = aufrufe[0]
    assert befehl == leiste.fenster_befehl() and befehl[-2:] == ["-m", "master_schalter.fenster"]
    assert kw["stdin"] is kw["stdout"] is kw["stderr"] is leiste.subprocess.DEVNULL
    paket = str(Path(leiste.__file__).resolve().parent.parent)
    assert kw["env"]["PYTHONPATH"].split(leiste.os.pathsep)[0] == paket


def test_fensterstart_fehler_beendet_die_leiste_nicht(lst, monkeypatch, capsys):
    def kaputt(*_a, **_k):
        raise OSError("C:/Users/sebas/geheimer Pfad/python.exe fehlt")

    monkeypatch.setattr(leiste.subprocess, "Popen", kaputt)
    monkeypatch.setattr(leiste.threading, "Thread", _Sofort)

    _eintrag(list(lst._menue()), "Übergabe starten …")(lst.icon)

    assert lst.icon.meldungen[-1][1] == "Wechselfenster konnte nicht gestartet werden"
    log = capsys.readouterr().err
    assert "Wechselfenster konnte nicht gestartet werden (OSError)" in log and "geheimer Pfad" not in log


# --- Takt des Wechselassistenten --------------------------------------------------------------

def test_assistent_takt_laeuft_alle_zehn_sekunden_bis_zum_stopp(lst, monkeypatch):
    assert leiste.ASSISTENT_TAKT_SEKUNDEN == 10

    class StoppAttrappe:
        def __init__(self):
            self.warten = []
            self.gesetzt = False

        def is_set(self):
            return self.gesetzt

        def wait(self, sekunden):
            self.warten.append(sekunden)
            self.gesetzt = len(self.warten) >= 3
            return self.gesetzt

    schritte = []
    monkeypatch.setattr(lst, "_assistent_schritt", lambda: schritte.append(True))
    lst._stopp = StoppAttrappe()

    lst._assistent_takt()

    assert lst._stopp.warten == [10, 10, 10] and len(schritte) == 2          # nach dem Stopp kein weiterer Schritt


def test_beenden_stoppt_auch_den_assistententakt(lst):
    lst._beenden()
    lst._assistent_takt()                                                       # kehrt sofort zurück
    assert lst._stopp.is_set()


def test_schritt_setzt_jeden_offenen_vorgang_fort_und_keinen_endgueltigen(lst, monkeypatch):
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "abgabe_angefragt"), _wechsel_vorgang("w-2", "im_postfach"),
                       _wechsel_vorgang("w-3", "bestaetigt"), _wechsel_vorgang("w-4", "verworfen"))
    gerufen = []
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: gerufen.append(ident))

    lst._assistent_schritt()

    assert sorted(gerufen) == ["w-1", "w-2"]


def test_fehler_im_takt_laesst_die_leiste_leben_und_protokolliert_nur_die_klasse(lst, monkeypatch, capsys):
    _vorgaenge_ablegen(_wechsel_vorgang("GEHEIM-ID-1", "abgabe_angefragt"), _wechsel_vorgang("w-2", "im_postfach"))
    gerufen = []

    def kaputt(ident, **kw):
        gerufen.append(ident)
        raise av.AssistentFehler("C:/Users/sebas/geheimer Pfad")

    monkeypatch.setattr(leiste.assistent, "fortsetzen", kaputt)

    lst._assistent_schritt()                                                    # wirft nicht

    assert sorted(gerufen) == ["GEHEIM-ID-1", "w-2"]                            # der zweite Vorgang kommt trotzdem dran
    log = capsys.readouterr().err
    assert log.count("Wechselvorgang nicht fortgesetzt (AssistentFehler)") == 2
    assert "geheimer Pfad" not in log and "GEHEIM-ID-1" not in log
    lst._assistent_schritt()                                                    # und der Riegel ist wieder frei
    assert len(gerufen) == 4


def test_unlesbare_vorgangsdatei_im_takt_wirft_nicht(lst, monkeypatch, capsys):
    monkeypatch.setattr(av, "lesen", lambda *a, **k: (_ for _ in ()).throw(OSError("C:/geheim")))
    lst._assistent_schritt()
    log = capsys.readouterr().err
    assert "Wechselvorgänge nicht lesbar (OSError)" in log and "geheim" not in log


def test_parallele_schritte_werden_uebersprungen(lst, monkeypatch):
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "abgabe_angefragt"))
    gerufen = []
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: gerufen.append(ident))
    assert lst._assistent_sperre.acquire(blocking=False)
    try:
        lst._assistent_schritt()
    finally:
        lst._assistent_sperre.release()
    assert gerufen == []


def test_menue_wird_nach_phasenwechsel_aktualisiert_sonst_nicht(lst, monkeypatch):
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "abgabe_angefragt"))
    lst.aktualisieren()
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    vorher = lst.icon.menue_neu

    lst._assistent_schritt()
    assert lst.icon.menue_neu == vorher                                          # nichts geändert

    monkeypatch.setattr(leiste.assistent, "fortsetzen",
                        lambda ident, **kw: av.phase_wechseln(ident, ("abgabe_angefragt",), "abgegeben"))
    lst._assistent_schritt()
    assert lst.icon.menue_neu == vorher + 1
    assert [i.text for i in lst._menue() if i.text.startswith("Wechsel ")] == ["Wechsel engineering: Rolle wird gesetzt"]


# --- Windows-Hinweise ---------------------------------------------------------------------------

def _meldungen(lst):
    return [text for _, text in lst.icon.meldungen]


def test_hinweis_abgabe_offen_genau_einmal(lst, monkeypatch):
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    seit = datetime.now(timezone.utc) - timedelta(minutes=3)
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "abgabe_angefragt", zeit=seit, abgabe_seit=seit.isoformat()))

    lst._assistent_schritt()
    lst._assistent_schritt()

    texte = _meldungen(lst)
    assert len(texte) == 1
    assert texte[0].startswith("engineering: alter Chat hat noch nicht abgegeben – bitte kurz anstoßen (Frist bis ")


def test_kein_hinweis_vor_zwei_minuten(lst, monkeypatch):
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    seit = datetime.now(timezone.utc) - timedelta(seconds=90)
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "abgabe_angefragt", zeit=seit, abgabe_seit=seit.isoformat()))
    lst._assistent_schritt()
    assert _meldungen(lst) == []


def test_hinweise_im_verlauf_je_ereignis_einmal(lst, monkeypatch):
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "abgegeben", ziel="codex"))

    lst._assistent_schritt()
    assert _meldungen(lst) == []                                                  # Abgabe erledigt, Rolle noch nicht gesetzt

    av.aktualisieren("w-1", phase="rolle_gesetzt")
    lst._assistent_schritt()
    lst._assistent_schritt()
    assert _meldungen(lst) == ["engineering: Rolle jetzt bei Codex"]

    av.aktualisieren("w-1", phase="gesendet")                                     # weiter in „rolle“: kein zweiter Hinweis
    lst._assistent_schritt()
    assert len(_meldungen(lst)) == 1

    av.aktualisieren("w-1", phase="bestaetigt")
    lst._assistent_schritt()
    lst._assistent_schritt()
    assert _meldungen(lst)[1:] == ["engineering: Codex hat übernommen ✓"]


def test_uebernommen_ohne_zwischenmeldung_sagt_nicht_nachtraeglich_rolle_gesetzt(lst, monkeypatch):
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "bestaetigt", ziel="claude"))
    lst._assistent_schritt()
    av.aktualisieren("w-1", phase="rolle_gesetzt")                                # absurde Rückwärtsphase: nichts doppelt
    lst._assistent_schritt()
    assert _meldungen(lst) == ["engineering: Claude hat übernommen ✓"]


@pytest.mark.parametrize("phase", ["fehler", "unklar", "verworfen"])
def test_hinweis_blick_ins_fenster_bei_problemen_genau_einmal(lst, monkeypatch, phase):
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", phase, fehler="Grund"))
    lst._assistent_schritt()
    lst._assistent_schritt()
    assert _meldungen(lst) == ["engineering: Wechsel braucht Blick ins Fenster"]


def test_kein_hinweis_bei_abbruch_von_hand_und_nicht_bei_alten_vorgaengen(lst, monkeypatch):
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    alt = datetime.now(timezone.utc) - timedelta(hours=3)
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "verworfen", fehler=av.ABBRUCH_GRUND),
                       _wechsel_vorgang("w-2", "bestaetigt", zeit=alt))
    lst._assistent_schritt()
    assert _meldungen(lst) == []


def test_hinweise_je_vorgang_getrennt(lst, monkeypatch):
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "bestaetigt", thema="engineering"),
                       _wechsel_vorgang("w-2", "bestaetigt", thema="anderes-thema", ziel="claude"))
    lst._assistent_schritt()
    assert sorted(_meldungen(lst)) == ["anderes-thema: Claude hat übernommen ✓",
                                       "engineering: Hermes hat übernommen ✓"]


def test_fehlgeschlagener_hinweis_wird_nicht_endlos_wiederholt_und_wirft_nicht(lst, monkeypatch):
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    versuche = []
    monkeypatch.setattr(lst.icon, "notify", lambda *a: versuche.append(a) or (_ for _ in ()).throw(RuntimeError("x")))
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "bestaetigt"))
    lst._assistent_schritt()
    lst._assistent_schritt()
    assert len(versuche) == 1


def test_hinweise_nutzen_die_uebergebene_zeit(lst, monkeypatch):
    monkeypatch.setattr(leiste.assistent, "fortsetzen", lambda ident, **kw: None)
    jetzt = datetime.now(timezone.utc)
    _vorgaenge_ablegen(_wechsel_vorgang("w-1", "abgabe_angefragt", zeit=jetzt, abgabe_seit=jetzt.isoformat()))
    lst._assistent_schritt(jetzt + timedelta(minutes=1))
    assert _meldungen(lst) == []
    lst._assistent_schritt(jetzt + timedelta(minutes=2, seconds=1))
    assert len(_meldungen(lst)) == 1


# --- Start: Wiederaufnahme und Fäden ----------------------------------------------------------------

def test_start_ruft_die_wiederaufnahme_einmal_und_loggt_nur_zaehler(lst, monkeypatch, capsys):
    aufrufe = []
    ergebnis = [av.Wiederaufnahme("GEHEIM-ID-1", "engineering", "nachholbar", "C:/Users/sebas/geheim"),
                av.Wiederaufnahme("GEHEIM-ID-2", "engineering", "nachholbar", "x"),
                av.Wiederaufnahme("GEHEIM-ID-3", "engineering", "unklar", "y")]
    monkeypatch.setattr(av, "wiederaufnehmen", lambda *a, **k: aufrufe.append(True) or ergebnis)
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: _ThreadAttrappe(**kw))

    lst._start(lst.icon)

    assert aufrufe == [True]
    log = capsys.readouterr().err
    assert "Wiederaufnahme der Wechselvorgänge: nachholbar 2, unklar 1" in log
    assert "GEHEIM" not in log and "geheim" not in log


def test_wiederaufnahmefehler_beim_start_haelt_die_leiste_nicht_auf(lst, monkeypatch, capsys):
    monkeypatch.setattr(av, "wiederaufnehmen", lambda *a, **k: (_ for _ in ()).throw(OSError("C:/geheim")))
    threads = []
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: threads.append(kw) or _ThreadAttrappe(**kw))

    lst._start(lst.icon)

    assert len(threads) >= 2                                                       # beide Takte laufen trotzdem an
    log = capsys.readouterr().err
    assert "Wiederaufnahme der Wechselvorgänge fehlgeschlagen (OSError)" in log and "geheim" not in log


def test_start_startet_messtakt_und_assistententakt_je_einmal(lst, monkeypatch):
    threads = []
    monkeypatch.setattr(leiste.threading, "Thread", lambda **kw: threads.append(kw) or _ThreadAttrappe(**kw))

    lst._start(lst.icon)

    ziele = [kw["target"] for kw in threads]
    assert lst._takt in ziele and lst._assistent_takt in ziele
    assert all(kw["daemon"] is True for kw in threads)
