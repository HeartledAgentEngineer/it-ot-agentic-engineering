"""Tests für die Taskleisten-Oberfläche – ohne Fenster: Menüeinträge prüfen, Klicks per Attrappe auslösen."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pystray = pytest.importorskip("pystray")

from master_schalter import anzeige, leiste, modi, paare, signale, vorgaenge, wechsel, zustand  # noqa: E402

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
    lst.aktualisieren()
    texte = _texte(lst._menue())
    assert "Master wechseln" in texte and "Wechsel-Schwelle" in texte
    assert "Aktualisieren" in texte and "Beenden" in texte


def test_modusmenue_zeigt_beide_radiooptionen_und_geschuetzten_status(lst):
    thema = "personal-ai-agent"
    paare.setzen(thema, "00000000-0000-4000-8000-000000000001",
                 paare.laufend_bilden(thema), aktiv=True)
    modi.setzen(thema, modi.HERMES_CODEX)
    lst.aktualisieren()
    items = list(lst._menue())

    assert any(i.text.startswith("Hermes führt – Codex nur Ausführer") for i in items)
    themen = _eintrag(items, "Arbeitsmodus je Thema").submenu.items
    optionen = _eintrag(list(themen), thema).submenu.items
    assert _texte(optionen) == ["Nach Kontingent", "Hermes führt · Codex Luna codiert"]
    assert all(i.radio for i in optionen)
    assert [i.checked for i in optionen] == [False, True]


def test_modus_radio_haken_nutzt_nur_den_snapshot(lst, monkeypatch):
    thema = "engineering"
    paare.setzen(thema, "00000000-0000-4000-8000-000000000001",
                 paare.laufend_bilden(thema), aktiv=True)
    lst.aktualisieren()
    monkeypatch.setattr(modi, "snapshot", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("Dateizugriff")))

    optionen = _eintrag(list(lst._menue()), "Arbeitsmodus je Thema").submenu.items
    radios = _eintrag(list(optionen), thema).submenu.items
    assert radios[0].checked is True
    assert radios[1].checked is False


def test_modusaktion_meldet_belegte_sperre_ohne_warten(lst, monkeypatch):
    from contextlib import contextmanager

    @contextmanager
    def belegt(*_args, **_kwargs):
        yield False

    class Sofort:
        def __init__(self, *, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(leiste.zustand, "thema_sperre", belegt)
    monkeypatch.setattr(leiste.threading, "Thread", Sofort)
    lst._modus_aktion("engineering", modi.HERMES_CODEX)()

    assert lst.icon.meldungen[-1][1] == "Übergabe läuft – Modus gleich erneut wählen"


def test_modus_snapshot_fehler_zeigt_status_und_deaktiviert_optionen(lst, monkeypatch):
    def kaputt(*_args, **_kwargs):
        raise modi.ModusFehler("synthetischer Lesefehler")

    monkeypatch.setattr(modi, "snapshot", kaputt)
    lst.aktualisieren()
    items = list(lst._menue())

    assert any(i.text == "Arbeitsmodus: nicht verfügbar: synthetischer Lesefehler" for i in items)
    submenu = _eintrag(items, "Arbeitsmodus je Thema").submenu.items
    assert len(submenu) == 1
    assert submenu[0].text == "Modusdaten nicht lesbar"
    assert submenu[0].enabled is False


def test_modus_klick_schreibfehler_beendet_leiste_nicht(lst, monkeypatch):
    def kaputt(*_args, **_kwargs):
        raise OSError("synthetischer Schreibfehler")

    monkeypatch.setattr(modi, "_setzen_gesperrt", kaputt)
    lst._modus_hintergrund("engineering", modi.HERMES_CODEX)

    assert lst.icon.meldungen[-1][1] == "Modus nicht geändert: synthetischer Schreibfehler"


def test_master_wechseln_optionsfelder_aktiver_angehakt(lst):
    zustand.aendern(lambda z: z.__class__("codex", JETZT.isoformat(), None))
    lst.aktualisieren()
    sub = _eintrag(list(lst._menue()), "Master wechseln").submenu.items
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
    sub = _eintrag(list(lst._menue()), "Master wechseln").submenu.items
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
    sub = _eintrag(list(lst._menue()), "Master wechseln").submenu.items
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
    sub = _eintrag(list(lst._menue()), "Master wechseln").submenu.items
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
    sub = _eintrag(list(lst._menue()), "Wechsel-Schwelle").submenu.items
    assert _texte(sub) == ["80 %", "90 %", "95 %", "97 %", "100 %"]
    assert all(i.radio for i in sub)
    assert [i.checked for i in sub] == [False, False, False, True, False]


def test_klick_auf_schwelle_schreibt_datei_und_zeichnet_neu(lst):
    lst.aktualisieren()
    sub = _eintrag(list(lst._menue()), "Wechsel-Schwelle").submenu.items
    _eintrag(sub, "90 %")(lst.icon)
    assert anzeige.schwelle() == 90
    sub = _eintrag(list(lst._menue()), "Wechsel-Schwelle").submenu.items
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
    assert "Chats übergeben" in texte
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
    sub = _eintrag(list(lst._menue()), "Chats übergeben").submenu.items
    assert _texte(sub) == ["engineering: bereit"]
    assert sub[0].checked is True


def test_chat_untermenue_ohne_paare(lst):
    sub = _eintrag(list(lst._menue()), "Chats übergeben").submenu.items
    assert _texte(sub) == ["keine Paare angelegt"]
    assert not sub[0].enabled


def test_paar_haken_schaltet_das_paar_um(lst):
    paare.setzen("engineering", THREAD, ".hermes/uebergabe/laufend/engineering.md", aktiv=False)
    lst.aktualisieren()
    sub = _eintrag(list(lst._menue()), "Chats übergeben").submenu.items
    sub[0](lst.icon)
    assert paare.lesen()[0].aktiv is True


def test_chat_untermenue_zeigt_bestaetigten_status(lst):
    d = leiste.vorgaenge.Vorgang("engineering@1", "engineering", "l", "bestaetigt", JETZT.isoformat())
    leiste.vorgaenge.aendern(lambda alt: [*alt, d])
    paare.setzen("engineering", THREAD, ".hermes/uebergabe/laufend/engineering.md", aktiv=True)
    lst.aktualisieren()
    sub = _eintrag(list(lst._menue()), "Chats übergeben").submenu.items
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
