"""Tests für das Lesen der Kontingente – nur synthetische Dateien, nie echte Sitzungen."""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from master_schalter import signale

JETZT = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)
SPAETER = int((JETZT + timedelta(hours=2)).timestamp())
FRUEHER = int((JETZT - timedelta(minutes=5)).timestamp())


def _token_count(zeit: str, limit_id: str = "codex", primary: Any = ..., secondary: Any = ...) -> str:
    if primary is ...:
        primary = {"used_percent": 24.0, "window_minutes": 300, "resets_at": SPAETER}
    if secondary is ...:
        secondary = {"used_percent": 20.0, "window_minutes": 10080, "resets_at": SPAETER}
    return json.dumps({
        "timestamp": zeit,
        "type": "event_msg",
        "payload": {"type": "token_count", "info": {"geheim": "Chatinhalt"},
                    "rate_limits": {"limit_id": limit_id, "primary": primary, "secondary": secondary}},
    })


def _rollout(ordner, name, zeilen, mtime):
    datei = ordner / "2026" / "10" / "14" / name
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    os.utime(datei, (mtime, mtime))
    return datei


# --- Codex -------------------------------------------------------------------

def test_codex_liest_neuesten_eintrag_mit_werten(tmp_path):
    _rollout(tmp_path, "rollout-a.jsonl", [
        '{"type":"session_meta","payload":{"text":"Hallo"}}',
        _token_count("2026-10-14T10:00:00.000Z"),
        _token_count("2026-10-14T11:00:00.000Z", primary={"used_percent": 61.5, "window_minutes": 300, "resets_at": SPAETER}),
    ], mtime=1000)

    k = signale.codex_lesen(tmp_path, jetzt=JETZT)

    assert k.fehler is None
    assert k.master == "Codex"
    assert k.stand == datetime(2026, 10, 14, 11, 0, tzinfo=timezone.utc)
    assert k.fenster_nach_name("5h").prozent == 61.5
    assert k.fenster_nach_name("Woche").prozent == 20.0
    assert k.fenster_nach_name("5h").reset == datetime.fromtimestamp(SPAETER, timezone.utc)


def test_codex_ueberspringt_leere_und_fremde_limits(tmp_path):
    _rollout(tmp_path, "rollout-alt.jsonl", [_token_count("2026-10-12T17:55:00.000Z")], mtime=1000)
    _rollout(tmp_path, "rollout-neu.jsonl", [
        _token_count("2026-10-14T12:00:00.000Z", limit_id="premium", primary=None, secondary=None),
        _token_count("2026-10-14T12:01:00.000Z", primary=None),
    ], mtime=2000)

    k = signale.codex_lesen(tmp_path, jetzt=JETZT)

    assert k.stand == datetime(2026, 10, 12, 17, 55, tzinfo=timezone.utc)
    assert k.fenster_nach_name("5h").prozent == 24.0


def _epoche(text):
    return datetime.fromisoformat(text).timestamp()


def test_codex_nimmt_neuesten_eintrag_ueber_alle_dateien(tmp_path):
    # Live-Befund 14.10.: Die zuletzt geänderte Datei enthielt einen ÄLTEREN Eintrag als eine andere.
    _rollout(tmp_path, "rollout-lang.jsonl", [_token_count("2026-10-12T15:11:00.000Z",
              primary={"used_percent": 29.0, "resets_at": SPAETER})], mtime=_epoche("2026-10-14T17:11:00+00:00"))
    _rollout(tmp_path, "rollout-kurz.jsonl", [_token_count("2026-10-12T17:55:00.000Z",
              primary={"used_percent": 32.0, "resets_at": SPAETER})], mtime=_epoche("2026-10-12T17:56:00+00:00"))
    uralt = _rollout(tmp_path, "rollout-uralt.jsonl", [_token_count("2026-10-01T08:00:00.000Z")],
                     mtime=_epoche("2026-10-01T08:01:00+00:00"))
    leser = signale.CodexLeser()

    k = signale.codex_lesen(tmp_path, jetzt=JETZT, leser=leser)

    assert k.stand == datetime(2026, 10, 12, 17, 55, tzinfo=timezone.utc)
    assert k.fenster_nach_name("5h").prozent == 32.0
    # Änderungszeit ist Obergrenze: eine Datei, die vor 17:55 zuletzt geändert wurde, kann
    # keinen neueren Eintrag haben und wird gar nicht erst gelesen.
    assert uralt not in leser.gelesen


def test_codex_leser_liest_nur_angehaengtes(tmp_path):
    leser = signale.CodexLeser()
    datei = _rollout(tmp_path, "rollout-a.jsonl", [_token_count("2026-10-14T08:00:00.000Z")], mtime=1000)
    assert signale.codex_lesen(tmp_path, jetzt=JETZT, leser=leser).stand.hour == 8
    groesse_vorher = datei.stat().st_size

    with datei.open("a", encoding="utf-8") as f:
        f.write(_token_count("2026-10-14T09:00:00.000Z") + "\n")
    os.utime(datei, (1100, 1100))

    assert signale.codex_lesen(tmp_path, jetzt=JETZT, leser=leser).stand.hour == 9
    assert leser.gelesen[datei] == datei.stat().st_size > groesse_vorher

    # unvollständige letzte Zeile wird erst gelesen, wenn sie fertig ist
    with datei.open("a", encoding="utf-8") as f:
        f.write(_token_count("2026-10-14T10:00:00.000Z")[:40])
    os.utime(datei, (1200, 1200))
    assert signale.codex_lesen(tmp_path, jetzt=JETZT, leser=leser).stand.hour == 9


def test_codex_gekuerzte_datei_wird_von_vorn_gelesen(tmp_path):
    leser = signale.CodexLeser()
    datei = _rollout(tmp_path, "rollout-a.jsonl", [_token_count("2026-10-14T08:00:00.000Z")] * 3, mtime=1000)
    signale.codex_lesen(tmp_path, jetzt=JETZT, leser=leser)
    groesse = datei.stat().st_size

    datei.write_text("", encoding="utf-8")  # auf null Bytes gekürzt
    os.utime(datei, (1100, 1100))
    assert signale.codex_lesen(tmp_path, jetzt=JETZT, leser=leser).fehler == "keine Daten"
    assert leser.gelesen[datei] == 0

    # wächst wieder über die alte Größe hinaus: der neue Anfang darf nicht übersprungen werden
    datei.write_text("\n".join([_token_count("2026-10-14T09:30:00.000Z")] * 4) + "\n", encoding="utf-8")
    os.utime(datei, (1200, 1200))
    assert datei.stat().st_size > groesse
    assert signale.codex_lesen(tmp_path, jetzt=JETZT, leser=leser).stand.minute == 30


def test_codex_neu_geschriebene_datei_zwischen_zwei_abfragen(tmp_path):
    # Codex-Einwand R3: gekürzt UND wieder länger beschrieben, ohne Abfrage dazwischen.
    leser = signale.CodexLeser()
    datei = _rollout(tmp_path, "rollout-a.jsonl",
                     ['{"type":"session_meta","payload":{"id":"alt"}}', _token_count("2026-10-14T08:00:00.000Z")],
                     mtime=1000)
    assert signale.codex_lesen(tmp_path, jetzt=JETZT, leser=leser).stand.hour == 8
    groesse = datei.stat().st_size

    datei.write_text("\n".join(['{"type":"session_meta","payload":{"id":"neu"}}',
                                _token_count("2026-10-14T09:45:00.000Z")] + ['{"type":"x"}'] * 20) + "\n",
                     encoding="utf-8")
    os.utime(datei, (1100, 1100))
    assert datei.stat().st_size > groesse

    assert signale.codex_lesen(tmp_path, jetzt=JETZT, leser=leser).stand.minute == 45


def test_codex_sucht_weiter_wenn_neueste_dateien_leer_sind(tmp_path):
    _rollout(tmp_path, "rollout-alt.jsonl", [_token_count("2026-10-10T10:00:00.000Z")], mtime=1000)
    _rollout(tmp_path, "rollout-neu.jsonl", ['{"type":"session_meta"}'], mtime=2000)

    k = signale.codex_lesen(tmp_path, jetzt=JETZT, leser=signale.CodexLeser())

    assert k.fehler is None
    assert k.stand == datetime(2026, 10, 10, 10, 0, tzinfo=timezone.utc)


def test_codex_zwischenspeicher_haelt_nur_zahlen(tmp_path):
    leser = signale.CodexLeser()
    datei = _rollout(tmp_path, "rollout-a.jsonl", [_token_count(
        "2026-10-14T08:00:00.000Z",
        primary={"used_percent": 12.0, "resets_at": SPAETER, "notiz": "Chatinhalt"},
        secondary={"used_percent": "viel", "resets_at": SPAETER, "plan": "plus"},
    )], mtime=1000)

    _, grenzen = leser.bester_eintrag(datei)

    assert grenzen == {"primary": {"used_percent": 12.0, "resets_at": float(SPAETER)},
                       "secondary": {"used_percent": None, "resets_at": float(SPAETER)}}


def test_codex_kaputte_zeilen_brechen_nichts(tmp_path):
    _rollout(tmp_path, "rollout-a.jsonl", [
        '{"rate_limits": kaputt',
        '["rate_limits"]',
        json.dumps({"timestamp": "kein Datum", "payload": {"type": "token_count", "rate_limits": {"limit_id": "codex", "primary": {"used_percent": 5}}}}),
        _token_count("2026-10-14T09:00:00.000Z", primary={"used_percent": True, "resets_at": "morgen"}),
        _token_count("2026-10-14T08:00:00.000Z"),
    ], mtime=1000)

    k = signale.codex_lesen(tmp_path, jetzt=JETZT)

    # Der Eintrag mit True/„morgen" zählt als vorhanden, aber ohne gültige Zahlen.
    assert k.stand == datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
    assert k.fenster_nach_name("5h").prozent is None
    assert k.fenster_nach_name("5h").reset is None


def test_codex_abgelaufenes_fenster_gilt_als_zurueckgesetzt(tmp_path):
    _rollout(tmp_path, "rollout-a.jsonl", [_token_count(
        "2026-10-14T09:00:00.000Z",
        primary={"used_percent": 99.0, "window_minutes": 300, "resets_at": FRUEHER},
    )], mtime=1000)

    fenster = signale.codex_lesen(tmp_path, jetzt=JETZT).fenster_nach_name("5h")

    assert fenster.zurueckgesetzt is True
    assert fenster.prozent == 0.0


def test_codex_ohne_ordner_oder_eintraege_meldet_keine_daten(tmp_path):
    assert signale.codex_lesen(tmp_path / "fehlt", jetzt=JETZT).fehler == "keine Daten"
    _rollout(tmp_path, "rollout-a.jsonl", ['{"type":"session_meta"}'], mtime=1000)
    assert signale.codex_lesen(tmp_path, jetzt=JETZT).fehler == "keine Daten"


def test_codex_ordner_aus_umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_CODEX_SESSIONS", str(tmp_path))
    assert signale.codex_ordner() == tmp_path


@pytest.mark.parametrize("wert", [-5, 100.1, 150, float("nan"), float("inf"), -0.5])
def test_codex_ungueltige_prozentwerte_gelten_als_unbekannt(tmp_path, wert):
    """Gültig ist nur 0–100; alles andere darf nie als „frei\" durchgehen."""
    _rollout(tmp_path, "rollout-a.jsonl", [_token_count(
        "2026-10-14T09:00:00.000Z", primary={"used_percent": wert, "resets_at": SPAETER})], mtime=1000)

    fenster = signale.codex_lesen(tmp_path, jetzt=JETZT).fenster_nach_name("5h")

    assert fenster.prozent is None
    assert fenster.reset is not None          # die Rücksetzzeit bleibt erhalten


@pytest.mark.parametrize("wert", [0, 0.5, 100])
def test_codex_grenzwerte_sind_gueltig(tmp_path, wert):
    _rollout(tmp_path, "rollout-a.jsonl", [_token_count(
        "2026-10-14T09:00:00.000Z", primary={"used_percent": wert, "resets_at": SPAETER})], mtime=1000)

    assert signale.codex_lesen(tmp_path, jetzt=JETZT).fenster_nach_name("5h").prozent == float(wert)


def test_codex_zwischenspeicher_wirft_ungueltige_prozente_weg(tmp_path):
    leser = signale.CodexLeser()
    datei = _rollout(tmp_path, "rollout-a.jsonl", [_token_count(
        "2026-10-14T08:00:00.000Z", primary={"used_percent": -5, "resets_at": SPAETER})], mtime=1000)

    _, grenzen = leser.bester_eintrag(datei)

    assert grenzen["primary"]["used_percent"] is None


# --- Claude ------------------------------------------------------------------

def _rate_limits(fuenf=79, woche=58, reset=SPAETER) -> dict[str, Any]:
    return {"five_hour": {"used_percentage": fuenf, "resets_at": reset},
            "seven_day": {"used_percentage": woche, "resets_at": reset}}


def test_claude_schreiben_und_lesen(tmp_path):
    datei = tmp_path / "kontingent-claude.json"

    assert signale.claude_schreiben(_rate_limits(), datei, jetzt=JETZT) is True
    k = signale.claude_lesen(datei, jetzt=JETZT)

    assert k.master == "Claude"
    assert k.fehler is None
    assert k.stand == JETZT
    assert k.fenster_nach_name("5h").prozent == 79
    assert k.fenster_nach_name("Woche").prozent == 58


def test_claude_schreiben_speichert_nur_kontingentfelder(tmp_path):
    datei = tmp_path / "kontingent-claude.json"
    roh = _rate_limits()
    roh["five_hour"]["fremd"] = "Chatinhalt"
    roh["spend_limit"] = {"used_usd": 3}

    signale.claude_schreiben(roh, datei, jetzt=JETZT)

    gespeichert = json.loads(datei.read_text(encoding="utf-8"))
    assert set(gespeichert) == {"gelesen_um", "rate_limits"}
    assert set(gespeichert["rate_limits"]) == {"five_hour", "seven_day"}
    assert set(gespeichert["rate_limits"]["five_hour"]) == {"used_percentage", "resets_at"}


def test_claude_schreiben_ohne_werte_laesst_alte_datei_stehen(tmp_path):
    datei = tmp_path / "kontingent-claude.json"
    signale.claude_schreiben(_rate_limits(fuenf=40), datei, jetzt=JETZT)

    assert signale.claude_schreiben({}, datei, jetzt=JETZT) is False
    assert signale.claude_schreiben(None, datei, jetzt=JETZT) is False
    assert signale.claude_schreiben({"five_hour": {"used_percentage": "viel"}}, datei, jetzt=JETZT) is False

    assert signale.claude_lesen(datei, jetzt=JETZT).fenster_nach_name("5h").prozent == 40


@pytest.mark.parametrize("wert", [float("nan"), float("inf"), float("-inf"), 1e309, 10**1000])
def test_zahl_lehnt_nicht_endliche_oder_nicht_umwandelbare_werte_ab(wert):
    assert signale._zahl(wert) is None


def test_zahl_begrenzt_zeitstempel_nicht_auf_prozentbereich():
    assert signale._zahl(1e300) == 1e300


@pytest.mark.parametrize("wert", [float("nan"), 1e309, -1, 100.5, True])
def test_claude_ungueltiger_prozentwert_erhaelt_alte_datei(tmp_path, wert):
    datei = tmp_path / "kontingent-claude.json"
    assert signale.claude_schreiben(_rate_limits(), datei, jetzt=JETZT)
    alt = datei.read_bytes()
    neu = _rate_limits(fuenf=wert)

    assert signale.claude_schreiben(neu, datei, jetzt=JETZT) is False
    assert datei.read_bytes() == alt


@pytest.mark.parametrize("fehlend", ["five_hour", "seven_day"])
def test_claude_fehlendes_fenster_erhaelt_alte_datei(tmp_path, fehlend):
    datei = tmp_path / "kontingent-claude.json"
    assert signale.claude_schreiben(_rate_limits(), datei, jetzt=JETZT)
    alt = datei.read_bytes()
    neu = _rate_limits()
    del neu[fehlend]

    assert signale.claude_schreiben(neu, datei, jetzt=JETZT) is False
    assert datei.read_bytes() == alt


def test_claude_nicht_parsebarer_reset_erhaelt_alte_datei(tmp_path):
    datei = tmp_path / "kontingent-claude.json"
    assert signale.claude_schreiben(_rate_limits(), datei, jetzt=JETZT)
    alt = datei.read_bytes()

    assert signale.claude_schreiben(_rate_limits(reset=1e300), datei, jetzt=JETZT) is False
    assert datei.read_bytes() == alt


@pytest.mark.parametrize("wert", [float("nan"), float("inf"), -1, 100.5, True])
def test_claude_ungueltiger_prozentwert_aus_datei_ergibt_keine_daten(tmp_path, wert):
    datei = tmp_path / "kontingent-claude.json"
    rate_limits = _rate_limits()
    rate_limits["five_hour"]["used_percentage"] = wert
    datei.write_text(json.dumps({"gelesen_um": JETZT.isoformat(), "rate_limits": rate_limits}), encoding="utf-8")

    k = signale.claude_lesen(datei, jetzt=JETZT)

    assert k.fehler == "keine Daten"
    assert k.fenster == ()


def test_claude_schreiben_hinterlaesst_keine_temp_datei(tmp_path):
    datei = tmp_path / "unter" / "kontingent-claude.json"
    signale.claude_schreiben(_rate_limits(), datei, jetzt=JETZT)
    assert [p.name for p in datei.parent.iterdir()] == ["kontingent-claude.json"]


def test_claude_fehlende_oder_kaputte_datei(tmp_path):
    datei = tmp_path / "kontingent-claude.json"
    assert signale.claude_lesen(datei, jetzt=JETZT).fehler == "keine Daten"
    datei.write_text("{kaputt", encoding="utf-8")
    assert signale.claude_lesen(datei, jetzt=JETZT).fehler == "keine Daten"
    datei.write_text("[1, 2]", encoding="utf-8")
    assert signale.claude_lesen(datei, jetzt=JETZT).fehler == "keine Daten"


def test_claude_abgelaufenes_fenster(tmp_path):
    datei = tmp_path / "kontingent-claude.json"
    signale.claude_schreiben(_rate_limits(fuenf=97, reset=FRUEHER), datei, jetzt=JETZT - timedelta(hours=1))
    fenster = signale.claude_lesen(datei, jetzt=JETZT).fenster_nach_name("5h")
    assert fenster.zurueckgesetzt is True
    assert fenster.prozent == 0.0


def test_daten_ordner_aus_umgebung(tmp_path, monkeypatch):
    monkeypatch.setenv("MASTER_SCHALTER_DATEN", str(tmp_path))
    assert signale.claude_datei() == tmp_path / "kontingent-claude.json"


def test_daten_ordner_liegt_unter_home_nicht_unter_localappdata(monkeypatch, tmp_path):
    """Claude und Codex sind MSIX-Pakete – `%LOCALAPPDATA%` wäre je Starter ein anderer Ordner."""
    monkeypatch.delenv("MASTER_SCHALTER_DATEN", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata" / "Local"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profil"))
    monkeypatch.setattr(signale.Path, "home", classmethod(lambda cls: tmp_path / "profil"))

    ordner = signale.daten_ordner()

    assert ordner == tmp_path / "profil" / ".master-schalter"
    assert str(tmp_path / "appdata") not in str(ordner)   # nicht unter LOCALAPPDATA umgeleitet
    assert signale.claude_datei() == ordner / "kontingent-claude.json"


# --- Claude ------------------------------------------------------------------

def test_claude_fenster_ohne_resetzeit_nur_bei_null_prozent(tmp_path):
    ziel = tmp_path / "kontingent-claude.json"
    ok = signale.claude_schreiben({
        "five_hour": {"used_percentage": 0.0, "resets_at": None},
        "seven_day": {"used_percentage": 40.0, "resets_at": SPAETER},
    }, ziel, jetzt=JETZT)
    assert ok

    kontingent = signale.claude_lesen(ziel, jetzt=JETZT)
    fuenf = kontingent.fenster_nach_name("5h")
    assert fuenf.prozent == 0.0 and fuenf.reset is None and not fuenf.zurueckgesetzt

    not_ok = signale.claude_schreiben({
        "five_hour": {"used_percentage": 7.0, "resets_at": None},
        "seven_day": {"used_percentage": 40.0, "resets_at": SPAETER},
    }, ziel, jetzt=JETZT)
    assert not not_ok
    assert signale.claude_lesen(ziel, jetzt=JETZT).fenster_nach_name("5h").prozent == 0.0


def test_claude_lesen_lehnt_verbrauch_ohne_resetzeit_ab(tmp_path):
    ziel = tmp_path / "kontingent-claude.json"
    ziel.write_text(json.dumps({
        "gelesen_um": "2026-10-14T18:00:00+00:00",
        "rate_limits": {
            "five_hour": {"used_percentage": 12.0, "resets_at": None},
            "seven_day": {"used_percentage": 40.0, "resets_at": SPAETER},
        },
    }), encoding="utf-8")
    k = signale.claude_lesen(ziel, jetzt=JETZT)
    assert k.fehler == "keine Daten" and k.fenster == ()
