"""Tests für die Taskleisten-Oberfläche – ohne Fenster: Menüeinträge prüfen, Klicks per Attrappe auslösen."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pystray = pytest.importorskip("pystray")

from master_schalter import anzeige, leiste, signale, wechsel, zustand  # noqa: E402

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
    lst.aktualisieren()
    sub = _eintrag(list(lst._menue()), "Master wechseln").submenu.items
    _eintrag(sub, "Codex")(lst.icon)   # MenuItem.__call__ führt die Aktion aus

    assert aufrufe == ["codex"]
    assert lst.icon.title.startswith("M Codex L")
    assert lst.icon.meldungen[-1][1] == f"Master jetzt Codex – Übergabe: {paket.name}. Im Codex-Chat lesen lassen."


def test_klick_auf_hermes_wechselt(lst, tmp_path, monkeypatch):
    aufrufe = []
    paket = tmp_path / "2026-10-15_142540_masterwechsel-codex-hermes.md"

    def attrappe(nach, hinweis=None, **kw):
        aufrufe.append(nach)
        zustand.aendern(lambda z: z.__class__(nach, JETZT.isoformat(), str(paket)))
        return wechsel.Ergebnis("gewechselt", nach, paket, "")

    monkeypatch.setattr(wechsel, "wechseln", attrappe)
    lst.aktualisieren()
    sub = _eintrag(list(lst._menue()), "Master wechseln").submenu.items
    _eintrag(sub, "Hermes")(lst.icon)

    assert aufrufe == ["hermes"]
    assert lst.icon.title.startswith("M Hermes L")
    assert lst.icon.meldungen[-1][1] == f"Master jetzt Hermes – Übergabe: {paket.name}. Im Hermes-Chat lesen lassen."


def test_fehlschlag_beim_wechsel_zeigt_meldung_und_stuerzt_nicht(lst, monkeypatch):
    def kaputt(nach, hinweis=None, **kw):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(wechsel, "wechseln", kaputt)
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
