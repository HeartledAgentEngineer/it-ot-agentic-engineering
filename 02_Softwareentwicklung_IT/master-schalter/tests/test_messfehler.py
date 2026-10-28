"""Tests des Messfehler-Status `messfehler.json`: Speichern/Rücksetzen in den zentralen Messfunktionen, Anzeige in `kurz`.

Alles synthetisch: kein Netz, kein echtes `codex.exe`, der Datenordner liegt unter `tmp_path`.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from master_schalter import claude_messen, cli, codex_messen, kurz, signale

UTC = timezone.utc
T0 = datetime(2026, 10, 28, 8, 0, tzinfo=UTC)
TOKEN = "synthetischer-geheim-token"


@pytest.fixture
def daten(tmp_path, monkeypatch) -> Path:
    ordner = tmp_path / "daten"
    ordner.mkdir()
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(ordner))
    return ordner


def _datei(daten: Path) -> Path:
    return daten / "messfehler.json"


def _roh(daten: Path) -> dict:
    return json.loads(_datei(daten).read_text(encoding="utf-8"))


# --- signale: Speichern, Serie, Löschen, Lesen -----------------------------------------------------------

def test_datei_liegt_im_datenordner(daten):
    assert signale.messfehler_datei() == daten / "messfehler.json"


def test_setzen_schreibt_eintrag_mit_seit_und_zuletzt(daten):
    signale.messfehler_setzen("claude", "netz", "Claude-Kontingent konnte nicht gelesen werden", jetzt=T0)

    assert _roh(daten) == {"claude": {"kategorie": "netz", "text": "Claude-Kontingent konnte nicht gelesen werden",
                                      "seit": T0.isoformat(), "zuletzt": T0.isoformat()}}
    eintrag = signale.messfehler_lesen()["claude"]
    assert (eintrag.kategorie, eintrag.seit, eintrag.zuletzt) == ("netz", T0, T0)


def test_folgefehler_behaelt_seit_und_setzt_zuletzt(daten):
    signale.messfehler_setzen("claude", "netz", "Text eins", jetzt=T0)
    signale.messfehler_setzen("claude", "http", "Text zwei", jetzt=T0 + timedelta(minutes=30))

    eintrag = signale.messfehler_lesen()["claude"]
    assert eintrag.seit == T0 and eintrag.zuletzt == T0 + timedelta(minutes=30)
    assert (eintrag.kategorie, eintrag.text) == ("http", "Text zwei")        # aktueller Grund, Serie bleibt


def test_quellen_sind_unabhaengig_und_loeschen_trifft_nur_die_eigene(daten):
    signale.messfehler_setzen("claude", "netz", "C", jetzt=T0)
    signale.messfehler_setzen("codex", "Zeitüberschreitung", "X", jetzt=T0)

    signale.messfehler_loeschen("claude")

    assert set(_roh(daten)) == {"codex"}
    assert set(signale.messfehler_lesen()) == {"codex"}


def test_neue_serie_nach_loeschen_beginnt_mit_neuem_seit(daten):
    signale.messfehler_setzen("codex", "a", "A", jetzt=T0)
    signale.messfehler_loeschen("codex")
    signale.messfehler_setzen("codex", "a", "A", jetzt=T0 + timedelta(hours=3))

    assert signale.messfehler_lesen()["codex"].seit == T0 + timedelta(hours=3)


def test_loeschen_ohne_eintrag_schreibt_nichts(daten):
    signale.messfehler_loeschen("claude")
    assert not _datei(daten).exists()


def test_schreiben_ist_atomar(daten, monkeypatch):
    aufrufe = []
    original = signale._atomar_schreiben
    monkeypatch.setattr(signale, "_atomar_schreiben", lambda d, i: aufrufe.append(d.name) or original(d, i))
    signale.messfehler_setzen("claude", "netz", "T", jetzt=T0)
    assert aufrufe == ["messfehler.json"]


def test_keine_verfallsgrenze_eintrag_gilt_nach_60_minuten_und_laenger(daten):
    signale.messfehler_setzen("claude", "netz", "T", jetzt=T0)
    spaeter = T0 + timedelta(days=3)      # lesen kennt keine Uhr: der Eintrag gilt, bis eine Messung gelingt
    assert "claude" in signale.messfehler_lesen()
    zeilen = kurz.messfehler_zeilen(signale.messfehler_lesen(), spaeter, UTC)
    assert zeilen == ["Claude-Messung scheitert seit 28.10. 08:00 (letzter Versuch 28.10. 08:00): T"]


@pytest.mark.parametrize("inhalt", ["", "{kaputt", "[]", "null", '"text"', "123"])
def test_kaputte_datei_ergibt_leeres_ergebnis_ohne_absturz(daten, inhalt):
    _datei(daten).write_text(inhalt, encoding="utf-8")
    assert signale.messfehler_lesen() == {}
    # …und der nächste Fehler heilt die Datei:
    signale.messfehler_setzen("claude", "netz", "T", jetzt=T0)
    assert set(_roh(daten)) == {"claude"}


def test_kaputte_bytes_ergeben_leeres_ergebnis(daten):
    _datei(daten).write_bytes(b"\xff\xfe\x00kaputt")
    assert signale.messfehler_lesen() == {}


@pytest.mark.parametrize("eintrag", [
    "text", None, [], {}, {"kategorie": "x", "text": "t"},
    {"kategorie": "x", "text": "t", "seit": "gestern", "zuletzt": T0.isoformat()},
    {"kategorie": "x", "text": "t", "seit": T0.isoformat(), "zuletzt": 5},
    {"kategorie": 1, "text": "t", "seit": T0.isoformat(), "zuletzt": T0.isoformat()},
    {"kategorie": "x", "text": "  ", "seit": T0.isoformat(), "zuletzt": T0.isoformat()},
])
def test_ungueltiger_einzeleintrag_wird_uebergangen_der_andere_bleibt(daten, eintrag):
    gut = {"kategorie": "x", "text": "ok", "seit": T0.isoformat(), "zuletzt": T0.isoformat()}
    _datei(daten).write_text(json.dumps({"claude": eintrag, "codex": gut}), encoding="utf-8")
    assert set(signale.messfehler_lesen()) == {"codex"}


def test_text_wird_einzeilig_und_begrenzt_gelesen(daten):
    lang = "A\nB\r\n" + "x" * 500
    _datei(daten).write_text(json.dumps({"claude": {
        "kategorie": "x", "text": lang, "seit": T0.isoformat(), "zuletzt": T0.isoformat()}}), encoding="utf-8")
    text = signale.messfehler_lesen()["claude"].text
    assert "\n" not in text and "\r" not in text and len(text) <= signale.MESSFEHLER_TEXT_MAX


def test_setzen_und_loeschen_verschlucken_schreibfehler(daten, monkeypatch):
    def kaputt(*_a, **_k):
        raise OSError("C:/geheim/pfad")

    monkeypatch.setattr(signale, "_atomar_schreiben", kaputt)
    signale.messfehler_setzen("claude", "netz", "T", jetzt=T0)       # wirft nicht
    signale.messfehler_setzen("codex", "netz", "T", jetzt=T0)
    signale.messfehler_loeschen("claude")


# --- Claude: zentrale Messfunktion ----------------------------------------------------------------------------

def _credentials(pfad: Path, expires_at=1_900_000_000_000) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"claudeAiOauth": {"accessToken": TOKEN, "expiresAt": expires_at}}), encoding="utf-8")
    return pfad


class _Antwort:
    status = 200

    def __init__(self, inhalt: bytes):
        self._inhalt = inhalt

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._inhalt


def _gute_antwort() -> bytes:
    return json.dumps({"five_hour": {"utilization": 10.0, "resets_at": "2026-10-28T12:00:00Z"},
                       "seven_day": {"utilization": 20.0, "resets_at": "2026-11-01T12:00:00Z"}}).encode()


def test_claude_fehler_setzt_eintrag_ohne_token_und_erfolg_loescht_ihn(daten, tmp_path):
    fehlt = tmp_path / "nichts" / ".credentials.json"
    with pytest.raises(claude_messen.MessFehler):
        claude_messen.messen(credentials_datei=fehlt, ziel=tmp_path / "k.json", jetzt=T0)

    eintrag = signale.messfehler_lesen()["claude"]
    assert eintrag.kategorie == "anmeldung_fehlt" and eintrag.text == claude_messen.ANMELDUNG_FEHLT
    assert eintrag.seit == T0 and TOKEN not in _datei(daten).read_text(encoding="utf-8")

    echt = _credentials(tmp_path / "echt" / ".credentials.json")
    assert claude_messen.messen(credentials_datei=echt, ziel=tmp_path / "k.json", jetzt=T0 + timedelta(minutes=1),
                                transport=lambda *a, **k: _Antwort(_gute_antwort()))
    assert "claude" not in signale.messfehler_lesen()


def test_claude_folgefehler_behaelt_seit(daten, tmp_path):
    fehlt = tmp_path / "nichts" / ".credentials.json"
    for minuten in (0, 45):
        with pytest.raises(claude_messen.MessFehler):
            claude_messen.messen(credentials_datei=fehlt, jetzt=T0 + timedelta(minutes=minuten))
    eintrag = signale.messfehler_lesen()["claude"]
    assert eintrag.seit == T0 and eintrag.zuletzt == T0 + timedelta(minutes=45)


def test_claude_fehlerkategorien_aus_dem_netz(daten, tmp_path):
    echt = _credentials(tmp_path / ".credentials.json")
    with pytest.raises(claude_messen.MessFehler):
        claude_messen.messen(credentials_datei=echt, jetzt=T0,
                             transport=lambda *a, **k: (_ for _ in ()).throw(OSError(TOKEN)))
    eintrag = signale.messfehler_lesen()["claude"]
    assert (eintrag.kategorie, eintrag.text) == ("netz", claude_messen.MESSUNG_FEHLGESCHLAGEN)
    assert TOKEN not in _datei(daten).read_text(encoding="utf-8")


def test_claude_unerwartete_ausnahme_wird_notiert_und_weitergereicht(daten, tmp_path, monkeypatch):
    def kaputt(*_a, **_k):
        raise RuntimeError(TOKEN)

    monkeypatch.setattr(claude_messen, "_messen", kaputt)
    with pytest.raises(RuntimeError):
        claude_messen.messen(jetzt=T0)
    eintrag = signale.messfehler_lesen()["claude"]
    assert eintrag.kategorie == "unerwartet" and TOKEN not in eintrag.text


def test_claude_statusdatei_nicht_schreibbar_aendert_das_messergebnis_nicht(daten, tmp_path, monkeypatch):
    echt = _credentials(tmp_path / ".credentials.json")
    ziel = tmp_path / "k.json"
    original = signale._atomar_schreiben

    def nur_status_kaputt(datei, inhalt):
        if datei.name == "messfehler.json":
            raise OSError("gesperrt")
        return original(datei, inhalt)

    monkeypatch.setattr(signale, "_atomar_schreiben", nur_status_kaputt)

    # Erfolg bleibt Erfolg …
    assert claude_messen.messen(credentials_datei=echt, ziel=ziel, jetzt=T0,
                                transport=lambda *a, **k: _Antwort(_gute_antwort())) is True
    # … und derselbe Fehler (MessFehler) wird unverändert geworfen.
    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=tmp_path / "weg.json", jetzt=T0)
    assert fehler.value.kategorie == "anmeldung_fehlt"


# --- Codex: zentrale Messfunktion -------------------------------------------------------------------------------

def _codex_ergebnis():
    reset = int((T0 + timedelta(hours=3)).timestamp())
    return {"5h": {"used_percent": 12.0, "resets_at": reset}, "Woche": {"used_percent": 30.0, "resets_at": reset + 86400}}


def test_codex_fehler_setzt_eintrag_mit_klasse_und_erfolg_loescht_ihn(daten, monkeypatch):
    def keine_antwort(programm, frist):
        raise codex_messen.MessFehler(codex_messen.ZEIT)

    monkeypatch.setattr(codex_messen, "_abfragen", keine_antwort)
    k = codex_messen.messen(programm="x.exe", jetzt=T0)
    assert k.fehler == "Codex-Messung fehlgeschlagen (Zeitüberschreitung)"

    eintrag = signale.messfehler_lesen()["codex"]
    assert (eintrag.kategorie, eintrag.text, eintrag.seit) == ("Zeitüberschreitung", k.fehler, T0)

    monkeypatch.setattr(codex_messen, "_abfragen", lambda programm, frist: _codex_ergebnis())
    ok = codex_messen.messen(programm="x.exe", jetzt=T0 + timedelta(minutes=5))
    assert ok.fehler is None
    assert "codex" not in signale.messfehler_lesen()


def test_codex_folgefehler_behaelt_seit(daten, monkeypatch):
    def kaputt(programm, frist):
        raise RuntimeError("C:/geheim")

    monkeypatch.setattr(codex_messen, "_abfragen", kaputt)
    codex_messen.messen(programm="x.exe", jetzt=T0)
    codex_messen.messen(programm="x.exe", jetzt=T0 + timedelta(minutes=70))

    eintrag = signale.messfehler_lesen()["codex"]
    assert eintrag.seit == T0 and eintrag.zuletzt == T0 + timedelta(minutes=70)
    assert eintrag.kategorie == "RuntimeError" and "geheim" not in _datei(daten).read_text(encoding="utf-8")


def test_codex_programm_fehlt_ist_ein_eintrag(daten, monkeypatch):
    monkeypatch.setattr(codex_messen.codex_senden, "programm", lambda: None)
    codex_messen.messen(jetzt=T0)
    assert signale.messfehler_lesen()["codex"].kategorie == codex_messen.PROGRAMM


def test_codex_statusdatei_nicht_schreibbar_aendert_das_messergebnis_nicht(daten, monkeypatch):
    original = signale._atomar_schreiben

    def nur_status_kaputt(datei, inhalt):
        if datei.name == "messfehler.json":
            raise OSError("gesperrt")
        return original(datei, inhalt)

    monkeypatch.setattr(signale, "_atomar_schreiben", nur_status_kaputt)
    monkeypatch.setattr(codex_messen, "_abfragen", lambda programm, frist: _codex_ergebnis())
    assert codex_messen.messen(programm="x.exe", jetzt=T0).fehler is None

    def kaputt(programm, frist):
        raise codex_messen.MessFehler(codex_messen.ANTWORT)

    monkeypatch.setattr(codex_messen, "_abfragen", kaputt)
    assert codex_messen.messen(programm="x.exe", jetzt=T0).fehler == codex_messen.fehlertext(codex_messen.ANTWORT)


# --- Verschiedene Wege: Leiste, CLI -------------------------------------------------------------------------------

def test_fehler_per_cli_ist_sichtbar_und_erfolg_per_cli_raeumt_ab(daten, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(claude_messen, "_konfigurierte_credentials_datei", lambda: tmp_path / "weg" / "c.json")
    assert cli.main(["claude-messen"]) != 0
    assert "claude" in signale.messfehler_lesen()
    assert "Claude-Messung scheitert seit" in "\n".join(kurz.sammeln())

    echt = _credentials(tmp_path / "echt" / ".credentials.json")
    monkeypatch.setattr(claude_messen, "_konfigurierte_credentials_datei", lambda: echt)
    monkeypatch.setattr(claude_messen, "_transport", lambda *a, **k: _Antwort(_gute_antwort()))
    assert cli.main(["claude-messen"]) == 0
    assert "claude" not in signale.messfehler_lesen()
    assert "Messung scheitert" not in "\n".join(kurz.sammeln())


def test_fehler_in_der_leiste_erfolg_per_cli_raeumt_ab(daten, tmp_path, monkeypatch):
    pystray = pytest.importorskip("pystray")
    from master_schalter import leiste

    monkeypatch.setattr(claude_messen, "_konfigurierte_credentials_datei", lambda: tmp_path / "weg" / "c.json")
    monkeypatch.setattr(leiste.pystray, "Icon", lambda *a, **k: type("I", (), {
        "title": "", "icon": None, "update_menu": lambda s: None, "notify": lambda s, *a: None})())
    lst = leiste.Leiste()
    lst._messung_ausfuehren()                       # Messweg 1: Leiste (Takt) – scheitert
    assert signale.messfehler_lesen()["claude"].kategorie == "anmeldung_fehlt"

    echt = _credentials(tmp_path / "echt" / ".credentials.json")
    monkeypatch.setattr(claude_messen, "_konfigurierte_credentials_datei", lambda: echt)
    monkeypatch.setattr(claude_messen, "_transport", lambda *a, **k: _Antwort(_gute_antwort()))
    assert cli.main(["claude-messen"]) == 0         # Messweg 2: CLI – gelingt
    assert "claude" not in signale.messfehler_lesen()


# --- Anzeige in `kurz` ------------------------------------------------------------------------------------------------

def _gesamt(**kw):
    from master_schalter.signale import Fenster, Kontingent
    k = lambda n: Kontingent(n, (Fenster("5h", 10, T0 + timedelta(hours=1)), Fenster("Woche", 20, T0 + timedelta(days=1))), T0)
    return kurz.zeilen([k("Claude"), k("Codex")], [], [], schwelle=95, automatik_global=False, jetzt=T0, zone=UTC, **kw)


def test_kurz_zeigt_messfehler_mit_seit_und_letztem_versuch(daten):
    mf = {"claude": signale.Messfehler("claude", "netz", "Claude-Kontingent konnte nicht gelesen werden",
                                       datetime(2026, 10, 28, 7, 12, tzinfo=UTC), datetime(2026, 10, 28, 7, 42, tzinfo=UTC)),
          "codex": signale.Messfehler("codex", "Zeitüberschreitung", "Codex-Messung fehlgeschlagen (Zeitüberschreitung)",
                                      datetime(2026, 10, 28, 6, 0, tzinfo=UTC), datetime(2026, 10, 28, 7, 55, tzinfo=UTC))}
    zeilen = _gesamt(messfehler=mf)
    assert ("Claude-Messung scheitert seit 07:12 (letzter Versuch 07:42): "
            "Claude-Kontingent konnte nicht gelesen werden") in zeilen
    assert ("Codex-Messung scheitert seit 06:00 (letzter Versuch 07:55): "
            "Codex-Messung fehlgeschlagen (Zeitüberschreitung)") in zeilen
    kontingent = max(i for i, z in enumerate(zeilen) if z.startswith("  Codex:"))
    assert zeilen[kontingent + 1].startswith("Claude-Messung scheitert")           # direkt unter den Kontingentzeilen


def test_kurz_ohne_messfehler_keine_zeile(daten):
    assert not any("scheitert" in z for z in _gesamt())


def test_kurz_sammeln_mit_kaputter_statusdatei_stuerzt_nicht_ab(daten, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    _datei(daten).write_text("{kaputt", encoding="utf-8")
    text = "\n".join(kurz.sammeln())
    assert "Master-Schalter" in text and "scheitert" not in text


def test_kurz_sammeln_zeigt_eintrag_nach_60_minuten_weiter(daten, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setenv("MASTER_SCHALTER_REPO", str(repo))
    vor_zwei_stunden = datetime.now(UTC) - timedelta(hours=2)
    signale.messfehler_setzen("claude", "netz", "Claude-Kontingent konnte nicht gelesen werden", jetzt=vor_zwei_stunden)
    assert "Claude-Messung scheitert seit" in "\n".join(kurz.sammeln())


# --- Sperre um Lesen-Ändern-Schreiben (R1-Befund 1) ------------------------------------------------------

def test_loeschen_wartet_auf_die_sperre_und_ueberschreibt_keinen_fremden_stand(daten):
    """Hält ein Messweg die Sperre, wartet der andere; danach sieht er den neuen Stand und schreibt nichts Altes zurück."""
    import threading
    signale.messfehler_setzen("claude", "netz", "alt", jetzt=T0)
    signale.messfehler_setzen("codex", "netz", "codex", jetzt=T0)
    fertig = threading.Event()

    def codex_erfolg():
        signale.messfehler_loeschen("codex")
        fertig.set()

    with signale._messfehler_sperre(_datei(daten)):
        faden = threading.Thread(target=codex_erfolg)
        faden.start()
        assert not fertig.wait(0.3)                                  # blockiert, solange die Sperre gehalten wird
        roh = _roh(daten)
        del roh["claude"]                                            # Claude-Erfolg „unter der Sperre“
        _datei(daten).write_text(json.dumps(roh), encoding="utf-8")
    faden.join(5)
    assert fertig.is_set()
    assert _roh(daten) == {}                                         # der erledigte Claude-Fehler kehrt nicht zurück


def test_belegte_sperre_laesst_das_update_aus_ohne_ausnahme(daten, monkeypatch):
    signale.messfehler_setzen("claude", "netz", "alt", jetzt=T0)
    vorher = _datei(daten).read_bytes()
    original = signale._messfehler_sperre
    monkeypatch.setattr(signale, "_messfehler_sperre", lambda datei: original(datei, frist=0.1))
    with original(_datei(daten)):
        signale.messfehler_setzen("claude", "http", "neu", jetzt=T0 + timedelta(minutes=1))   # wirft nicht
        signale.messfehler_loeschen("claude")
    assert _datei(daten).read_bytes() == vorher
