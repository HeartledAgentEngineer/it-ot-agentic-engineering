"""Synthetische Tests für die Claude-Usage-API ohne echten Zugang und Netzwerk."""
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import pytest

from master_schalter import claude_messen, signale, zustand


JETZT = datetime(2026, 10, 14, 22, 0, tzinfo=timezone.utc)
TOKEN = "synthetischer-geheim-token"


def test_python_default_redirect_handler_leitet_authorization_an_anderen_host_weiter():
    """Prüft den echten urllib-Handler ohne Anfrage an ein Netzwerk zu senden."""
    request = Request("https://api.anthropic.com/api/oauth/usage",
                      headers={"Authorization": f"Bearer {TOKEN}"})
    handler = next(h for h in build_opener().handlers if type(h) is HTTPRedirectHandler)

    weitergeleitet = handler.redirect_request(
        request, None, 302, "Found", {}, "https://anderer-host.example/usage"
    )

    assert weitergeleitet.full_url == "https://anderer-host.example/usage"
    assert weitergeleitet.get_header("Authorization") == f"Bearer {TOKEN}"


class Antwort(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _antwort(fuenf=81.5, woche=45.0):
    return json.dumps({
        "five_hour": {"utilization": fuenf, "resets_at": "2026-10-14T23:00:00Z"},
        "seven_day": {"utilization": woche, "resets_at": "2026-10-20T23:00:00+00:00"},
    }).encode()


def _credentials(pfad, expires_at=1_900_000_000_000):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"claudeAiOauth": {
        "accessToken": TOKEN, "refreshToken": "synthetischer-refresh-token", "expiresAt": expires_at,
    }}), encoding="utf-8")


def test_credentials_datei_nutzt_config_dir_oder_standard(tmp_path, monkeypatch):
    konfig = tmp_path / "eigene-konfiguration"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(konfig))
    assert claude_messen.credentials_datei() == konfig / ".credentials.json"

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "")
    monkeypatch.setattr(claude_messen, "_standard_credentials_datei",
                        lambda: tmp_path / "home" / ".claude" / ".credentials.json")
    assert claude_messen.credentials_datei() == tmp_path / "home" / ".claude" / ".credentials.json"

    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    assert claude_messen.credentials_datei() == tmp_path / "home" / ".claude" / ".credentials.json"


@pytest.mark.parametrize("inhalt, kategorie", [
    (None, "anmeldung_fehlt"),
    ("kaputt", "anmeldung_defekt"),
    ({"claudeAiOauth": {"accessToken": TOKEN, "expiresAt": 1}}, "anmeldung_abgelaufen"),
])
def test_authfehler_sind_unterschieden_und_erneuern_keinen_cache(tmp_path, inhalt, kategorie):
    credentials = tmp_path / "synthetisch" / ".credentials.json"
    if inhalt is not None:
        credentials.parent.mkdir(parents=True, exist_ok=True)
        credentials.write_text(inhalt if isinstance(inhalt, str) else json.dumps(inhalt), encoding="utf-8")
    ziel = tmp_path / "kontingent-claude.json"
    signale.claude_schreiben({
        "five_hour": {"used_percentage": 40, "resets_at": 1_900_000_000},
        "seven_day": {"used_percentage": 50, "resets_at": 1_900_000_000},
    }, ziel, jetzt=JETZT)
    alt = ziel.read_bytes()

    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, ziel=ziel, jetzt=JETZT)

    assert fehler.value.kategorie == kategorie
    assert ziel.read_bytes() == alt
    assert TOKEN not in str(fehler.value)
    assert "Claude Code" in str(fehler.value) and "auth login --claudeai" in str(fehler.value)
    assert "Desktop" not in str(fehler.value) or "nicht" in str(fehler.value)


def test_server_401_ist_abgelehnte_anmeldung_mit_sicherem_text(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.json"
    _credentials(credentials)
    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, jetzt=JETZT,
                             transport=lambda *a, **k: (_ for _ in ()).throw(
                                 HTTPError("https://example.invalid", 401, TOKEN, None, None)))

    assert fehler.value.kategorie == "anmeldung_abgelehnt"
    assert fehler.value.status == 401
    assert TOKEN not in str(fehler.value)


def test_messen_ruft_usage_api_ab_und_speichert_nur_validierte_fenster(tmp_path, monkeypatch):
    credentials = tmp_path / ".claude" / ".credentials.json"
    ziel = tmp_path / "kontingent-claude.json"
    _credentials(credentials)
    aufruf = {}

    def urlopen(request, timeout):
        aufruf.update(url=request.full_url, token=request.get_header("Authorization"),
                      beta=request.get_header("Anthropic-beta"), timeout=timeout)
        return Antwort(_antwort())

    assert claude_messen.messen(credentials_datei=credentials, ziel=ziel, jetzt=JETZT,
                                transport=urlopen)

    kontingent = signale.claude_lesen(ziel, jetzt=JETZT)
    assert aufruf == {
        "url": "https://api.anthropic.com/api/oauth/usage",
        "token": f"Bearer {TOKEN}", "beta": "oauth-2025-04-20", "timeout": 10,
    }
    assert kontingent.fenster_nach_name("5h").prozent == 81.5
    assert kontingent.fenster_nach_name("Woche").prozent == 45.0
    assert TOKEN not in ziel.read_text(encoding="utf-8")


@pytest.mark.parametrize("fehler", ["missing", "json", "field", "bool", "nan", "low", "high", "reset"])
def test_ungueltige_api_antwort_laesst_alten_wert_unveraendert(tmp_path, monkeypatch, fehler):
    credentials = tmp_path / "credentials.json"
    ziel = tmp_path / "kontingent-claude.json"
    _credentials(credentials)
    signale.claude_schreiben({
        "five_hour": {"used_percentage": 40, "resets_at": 1_900_000_000},
        "seven_day": {"used_percentage": 50, "resets_at": 1_900_000_000},
    }, ziel, jetzt=JETZT)
    alt = ziel.read_bytes()
    body = json.loads(_antwort())
    if fehler == "missing":
        del body["seven_day"]
    elif fehler == "field":
        del body["five_hour"]["utilization"]
    elif fehler == "bool":
        body["five_hour"]["utilization"] = True
    elif fehler == "nan":
        body["five_hour"]["utilization"] = float("nan")
    elif fehler == "low":
        body["five_hour"]["utilization"] = -1
    elif fehler == "high":
        body["five_hour"]["utilization"] = 100.5
    elif fehler == "reset":
        body["five_hour"]["resets_at"] = "morgen"
    data = b"{" if fehler == "json" else json.dumps(body).encode()
    monkeypatch.setattr(claude_messen, "_transport", lambda *a, **k: Antwort(data))

    with pytest.raises(claude_messen.MessFehler):
        claude_messen.messen(credentials_datei=credentials, ziel=ziel, jetzt=JETZT)

    assert ziel.read_bytes() == alt


def test_abgelaufener_token_macht_keinen_netzaufruf_und_gibt_keinen_token_preis(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.json"
    _credentials(credentials, expires_at=1)
    aufrufe = []
    monkeypatch.setattr(claude_messen, "_transport", lambda *a, **k: aufrufe.append(a))

    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, jetzt=JETZT, erneuern=False)

    assert aufrufe == []
    assert str(fehler.value) == claude_messen.ANMELDUNG_ABGELAUFEN
    assert TOKEN not in str(fehler.value)


@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_fehler_bleibt_generisch_und_enthaelt_keinen_token(tmp_path, monkeypatch, status):
    credentials = tmp_path / "credentials.json"
    ziel = tmp_path / "kontingent-claude.json"
    _credentials(credentials)
    signale.claude_schreiben({
        "five_hour": {"used_percentage": 40, "resets_at": 1_900_000_000},
        "seven_day": {"used_percentage": 50, "resets_at": 1_900_000_000},
    }, ziel, jetzt=JETZT)
    alt = ziel.read_bytes()

    def urlopen(*args, **kwargs):
        raise HTTPError("https://api.anthropic.com/api/oauth/usage", status, TOKEN, None, None)

    monkeypatch.setattr(claude_messen, "_transport", urlopen)
    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, ziel=ziel, jetzt=JETZT)

    assert TOKEN not in str(fehler.value)
    assert "Traceback" not in str(fehler.value)
    assert ziel.read_bytes() == alt
    if status == 401:
        assert str(fehler.value) == claude_messen.ANMELDUNG_ABGELEHNT
    if status == 429:
        assert fehler.value.status == 429
    if status != 401:
        assert fehler.value.kategorie == "http" and fehler.value.status == status


@pytest.mark.parametrize("netzfehler", [URLError(TOKEN), TimeoutError(TOKEN)])
def test_netzfehler_und_timeout_werden_sicher_gekuerzt(tmp_path, monkeypatch, netzfehler):
    credentials = tmp_path / "credentials.json"
    ziel = tmp_path / "kontingent-claude.json"
    _credentials(credentials)
    signale.claude_schreiben({
        "five_hour": {"used_percentage": 40, "resets_at": 1_900_000_000},
        "seven_day": {"used_percentage": 50, "resets_at": 1_900_000_000},
    }, ziel, jetzt=JETZT)
    alt = ziel.read_bytes()
    monkeypatch.setattr(claude_messen, "_transport",
                        lambda *a, **k: (_ for _ in ()).throw(netzfehler))

    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, ziel=ziel, jetzt=JETZT)

    assert str(fehler.value) == claude_messen.MESSUNG_FEHLGESCHLAGEN
    assert fehler.value.kategorie == "netz" and fehler.value.status is None
    assert TOKEN not in str(fehler.value)
    assert ziel.read_bytes() == alt


def test_kaputte_antwort_hat_die_fehlerart_antwort(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.json"
    _credentials(credentials)

    class Antwort:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"kein json"

    monkeypatch.setattr(claude_messen, "_transport", lambda *a, **k: Antwort())
    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, ziel=tmp_path / "k.json", jetzt=JETZT)
    assert fehler.value.kategorie == "antwort" and str(fehler.value) == claude_messen.MESSUNG_FEHLGESCHLAGEN


def test_scheitert_das_speichern_hat_die_fehlerart_speichern(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.json"
    _credentials(credentials)

    class Antwort:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"five_hour": {"utilization": 40, "resets_at": "2030-01-01T00:00:00+00:00"},'                    b' "seven_day": {"utilization": 50, "resets_at": "2030-01-01T00:00:00+00:00"}}'

    monkeypatch.setattr(claude_messen, "_transport", lambda *a, **k: Antwort())
    monkeypatch.setattr(claude_messen, "_validierte_fenster", lambda daten: {"five_hour": {}, "seven_day": {}})
    monkeypatch.setattr(claude_messen.signale, "claude_schreiben", lambda *a, **k: False)
    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, ziel=tmp_path / "k.json", jetzt=JETZT)
    assert fehler.value.kategorie == "speichern"


def test_eigener_redirect_handler_blockiert_jedes_weiterleitungsziel():
    request = Request("https://api.anthropic.com/api/oauth/usage",
                      headers={"Authorization": f"Bearer {TOKEN}"})
    handler = claude_messen._KeineWeiterleitung()

    assert handler.redirect_request(
        request, None, 302, "Found", {}, "https://anderer-host.example/usage"
    ) is None


def test_redirect_http_fehler_laesst_alten_wert_unveraendert(tmp_path):
    credentials = tmp_path / "credentials.json"
    ziel = tmp_path / "kontingent-claude.json"
    _credentials(credentials)
    signale.claude_schreiben({
        "five_hour": {"used_percentage": 40, "resets_at": 1_900_000_000},
        "seven_day": {"used_percentage": 50, "resets_at": 1_900_000_000},
    }, ziel, jetzt=JETZT)
    alt = ziel.read_bytes()

    def redirect_antwort(anfrage, timeout):
        assert anfrage.get_header("Authorization") == f"Bearer {TOKEN}"
        assert timeout == 10
        raise HTTPError(anfrage.full_url, 302, "Found", {}, None)

    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, ziel=ziel, jetzt=JETZT,
                             transport=redirect_antwort)

    assert str(fehler.value) == claude_messen.MESSUNG_FEHLGESCHLAGEN
    assert TOKEN not in str(fehler.value)
    assert ziel.read_bytes() == alt


def test_leeres_fenster_ohne_resetzeit_wird_als_null_prozent_gelesen(tmp_path, monkeypatch):
    """API-Form ab 16.10.2026: kein offenes 5h-Fenster → utilization 0.0, resets_at null."""
    credentials = tmp_path / "credentials.json"
    ziel = tmp_path / "kontingent-claude.json"
    _credentials(credentials)
    body = json.dumps({
        "five_hour": {"utilization": 0.0, "resets_at": None},
        "seven_day": {"utilization": 100.0, "resets_at": "2026-10-18T20:59:59+00:00"},
    }).encode()
    monkeypatch.setattr(claude_messen, "_transport", lambda *a, **k: Antwort(body))

    assert claude_messen.messen(credentials_datei=credentials, ziel=ziel, jetzt=JETZT)

    kontingent = signale.claude_lesen(ziel, jetzt=JETZT)
    fuenf = kontingent.fenster_nach_name("5h")
    assert fuenf.prozent == 0.0 and fuenf.reset is None
    assert kontingent.fenster_nach_name("Woche").prozent == 100.0


def test_verbrauch_ohne_resetzeit_bleibt_ungueltig(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials.json"
    ziel = tmp_path / "kontingent-claude.json"
    _credentials(credentials)
    signale.claude_schreiben({
        "five_hour": {"used_percentage": 40, "resets_at": 1_900_000_000},
        "seven_day": {"used_percentage": 50, "resets_at": 1_900_000_000},
    }, ziel, jetzt=JETZT)
    alt = ziel.read_bytes()
    body = json.dumps({
        "five_hour": {"utilization": 12.0, "resets_at": None},
        "seven_day": {"utilization": 50.0, "resets_at": "2026-10-20T23:00:00+00:00"},
    }).encode()
    monkeypatch.setattr(claude_messen, "_transport", lambda *a, **k: Antwort(body))

    with pytest.raises(claude_messen.MessFehler):
        claude_messen.messen(credentials_datei=credentials, ziel=ziel, jetzt=JETZT)

    assert ziel.read_bytes() == alt


# --- Selbsterneuerung des abgelaufenen Messzugangs (gedrosselt, prozessübergreifend) ---------------------------

ABGELAUFEN = 1   # expiresAt in Unix-Millisekunden: längst vorbei


class _Messungen:
    """Zählt die Aufrufe von `_messen` (erster Versuch plus höchstens ein zweiter)."""

    def __init__(self, monkeypatch):
        self.anzahl = 0
        echt = claude_messen._messen

        def zaehlend(*args, **kwargs):
            self.anzahl += 1
            return echt(*args, **kwargs)

        monkeypatch.setattr(claude_messen, "_messen", zaehlend)


def _abgelaufene_credentials(tmp_path):
    pfad = tmp_path / "credentials.json"
    _credentials(pfad, expires_at=ABGELAUFEN)
    return pfad


def _erneuernde_cli(credentials, erneuerungen):
    """Fälschung von `claude auth status`: zählt und schreibt gültige Credentials, als hätte die CLI erneuert."""

    def erneuern(*args, **kwargs):
        erneuerungen.append(1)
        _credentials(credentials)
        return True

    return erneuern


def _messen_erwartet_fehler(credentials, jetzt=JETZT):
    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, ziel=credentials.parent / "k.json", jetzt=jetzt,
                             transport=lambda *a, **k: Antwort(_antwort()))
    return fehler.value


def test_abgelaufen_erneuert_genau_einmal_und_liest_genau_einmal_neu(tmp_path, monkeypatch, erneuerungen):
    credentials = _abgelaufene_credentials(tmp_path)
    ziel = tmp_path / "k.json"
    messungen = _Messungen(monkeypatch)
    monkeypatch.setattr(claude_messen, "cli_erneuern", _erneuernde_cli(credentials, erneuerungen))

    assert claude_messen.messen(credentials_datei=credentials, ziel=ziel, jetzt=JETZT,
                                transport=lambda *a, **k: Antwort(_antwort()))

    assert len(erneuerungen) == 1
    assert messungen.anzahl == 2
    assert signale.claude_lesen(ziel, jetzt=JETZT).fenster_nach_name("5h").prozent == 81.5
    assert "claude" not in signale.messfehler_lesen()


def test_weiterhin_abgelaufen_nennt_ohne_erfolg_und_die_uhrzeit(tmp_path, monkeypatch, erneuerungen):
    credentials = _abgelaufene_credentials(tmp_path)
    messungen = _Messungen(monkeypatch)

    fehler = _messen_erwartet_fehler(credentials)

    uhrzeit = JETZT.astimezone().strftime("%H:%M")
    erwartet = (f"Claude-Messzugang abgelaufen – automatische Erneuerung um {uhrzeit} ohne Erfolg; "
                "Claude Code auth login --claudeai ausführen")
    assert str(fehler) == erwartet and fehler.kategorie == "anmeldung_abgelaufen"
    assert len(erneuerungen) == 1 and messungen.anzahl == 2
    eintrag = signale.messfehler_lesen()["claude"]
    assert eintrag.kategorie == "anmeldung_abgelaufen" and eintrag.text == erwartet
    assert TOKEN not in str(fehler)


def test_drossel_zweiter_fehler_binnen_30_minuten_erneuert_nicht_noch_einmal(tmp_path, monkeypatch, erneuerungen):
    credentials = _abgelaufene_credentials(tmp_path)
    messungen = _Messungen(monkeypatch)
    _messen_erwartet_fehler(credentials, JETZT)
    assert len(erneuerungen) == 1 and messungen.anzahl == 2

    spaeter = _messen_erwartet_fehler(credentials, JETZT + timedelta(minutes=29))

    assert len(erneuerungen) == 1          # gedrosselt
    assert messungen.anzahl == 3           # nur der erste Versuch, kein zweiter ohne Erneuerung
    assert JETZT.astimezone().strftime("%H:%M") in str(spaeter) and "ohne Erfolg" in str(spaeter)

    _messen_erwartet_fehler(credentials, JETZT + timedelta(minutes=31))
    assert len(erneuerungen) == 2          # Drossel abgelaufen


def test_zeitstempel_wird_vor_dem_start_der_erneuerung_geschrieben(tmp_path, monkeypatch):
    credentials = _abgelaufene_credentials(tmp_path)
    gesehen = []

    def erneuern(*args, **kwargs):
        gesehen.append(json.loads(claude_messen._erneuerung_datei().read_text(encoding="utf-8")))
        return False

    monkeypatch.setattr(claude_messen, "cli_erneuern", erneuern)

    _messen_erwartet_fehler(credentials)

    assert gesehen == [{"zeit": JETZT.isoformat()}]


def test_belegte_sperre_bedeutet_kein_erneuern(tmp_path, monkeypatch, erneuerungen):
    credentials = _abgelaufene_credentials(tmp_path)
    messungen = _Messungen(monkeypatch)

    with zustand.instanz_sperre(claude_messen.ERNEUERUNG_NAME) as frei:
        assert frei
        fehler = _messen_erwartet_fehler(credentials)

    assert erneuerungen == [] and messungen.anzahl == 1
    assert fehler.kategorie == "anmeldung_abgelaufen"
    assert str(fehler) == claude_messen.ANMELDUNG_ABGELAUFEN     # kein Versuch bekannt ⇒ fester Grundtext
    assert not claude_messen._erneuerung_datei().exists()


def test_nicht_schreibbare_reservierung_bedeutet_kein_erneuern_bei_jeder_messung(tmp_path, monkeypatch, erneuerungen):
    credentials = _abgelaufene_credentials(tmp_path)
    messungen = _Messungen(monkeypatch)
    # Ein Ordner an der Stelle des Zeitstempels: lesbar als „alt“, aber nicht atomar überschreibbar.
    claude_messen._erneuerung_datei().mkdir(parents=True)

    for minuten in (0, 5, 45, 90):
        fehler = _messen_erwartet_fehler(credentials, JETZT + timedelta(minutes=minuten))
        assert fehler.kategorie == "anmeldung_abgelaufen"

    assert erneuerungen == []
    assert messungen.anzahl == 4          # nur die ersten Versuche, nie ein zweiter


def test_kaputte_zeitstempeldatei_gilt_als_alt_danach_wirkt_die_drossel(tmp_path, monkeypatch, erneuerungen):
    credentials = _abgelaufene_credentials(tmp_path)
    claude_messen._erneuerung_datei().parent.mkdir(parents=True, exist_ok=True)
    claude_messen._erneuerung_datei().write_text("kein json {", encoding="utf-8")

    _messen_erwartet_fehler(credentials)
    assert len(erneuerungen) == 1
    assert json.loads(claude_messen._erneuerung_datei().read_text(encoding="utf-8")) == {"zeit": JETZT.isoformat()}

    _messen_erwartet_fehler(credentials, JETZT + timedelta(minutes=1))
    assert len(erneuerungen) == 1


def test_zeitstempel_in_der_zukunft_sperrt_die_erneuerung_nicht_dauerhaft(tmp_path, erneuerungen):
    credentials = _abgelaufene_credentials(tmp_path)
    claude_messen._erneuerung_datei().parent.mkdir(parents=True, exist_ok=True)
    claude_messen._erneuerung_datei().write_text(
        json.dumps({"zeit": (JETZT + timedelta(days=400)).isoformat()}), encoding="utf-8")

    _messen_erwartet_fehler(credentials)

    assert len(erneuerungen) == 1


@pytest.mark.parametrize("inhalt, transport_fehler, kategorie", [
    (None, None, "anmeldung_fehlt"),
    ("kaputt", None, "anmeldung_defekt"),
    ("gueltig", HTTPError("https://example.invalid", 401, "x", None, None), "anmeldung_abgelehnt"),
    ("gueltig", HTTPError("https://example.invalid", 500, "x", None, None), "http"),
    ("gueltig", URLError("netz"), "netz"),
])
def test_andere_fehlerarten_erneuern_nie(tmp_path, monkeypatch, erneuerungen, inhalt, transport_fehler, kategorie):
    credentials = tmp_path / "credentials.json"
    if inhalt == "kaputt":
        credentials.write_text("kein json", encoding="utf-8")
    elif inhalt == "gueltig":
        _credentials(credentials)
    messungen = _Messungen(monkeypatch)

    def transport(*args, **kwargs):
        raise transport_fehler

    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, ziel=tmp_path / "k.json", jetzt=JETZT,
                             transport=transport)

    assert fehler.value.kategorie == kategorie
    assert erneuerungen == [] and messungen.anzahl == 1
    assert not claude_messen._erneuerung_datei().exists()


def test_ohne_erneuern_wird_nicht_erneuert(tmp_path, erneuerungen):
    credentials = _abgelaufene_credentials(tmp_path)

    with pytest.raises(claude_messen.MessFehler) as fehler:
        claude_messen.messen(credentials_datei=credentials, jetzt=JETZT, erneuern=False)

    assert str(fehler.value) == claude_messen.ANMELDUNG_ABGELAUFEN
    assert erneuerungen == []


def test_erneuerung_die_wirft_stoert_die_messung_nicht(tmp_path, monkeypatch):
    credentials = _abgelaufene_credentials(tmp_path)

    def kaputt(*args, **kwargs):
        raise RuntimeError(TOKEN)

    monkeypatch.setattr(claude_messen, "cli_erneuern", kaputt)

    fehler = _messen_erwartet_fehler(credentials)

    assert fehler.kategorie == "anmeldung_abgelaufen" and TOKEN not in str(fehler)


_PARALLEL_SKRIPT = """
import sys, time
from pathlib import Path
from master_schalter import claude_messen

zaehler, credentials, start = sys.argv[1:4]


def erneuern(*args, **kwargs):
    with open(zaehler, "a", encoding="utf-8") as datei:
        datei.write("x\\n")
    time.sleep(1.0)      # lange genug, damit der andere Prozess die Sperre belegt findet
    return False


claude_messen.cli_erneuern = erneuern
while time.time() < float(start):
    time.sleep(0.005)
try:
    claude_messen.messen(credentials_datei=Path(credentials))
except claude_messen.MessFehler:
    pass
"""


def test_zwei_prozesse_gleichzeitig_erneuern_genau_einmal(tmp_path):
    credentials = _abgelaufene_credentials(tmp_path)
    zaehler = tmp_path / "erneuerungen.txt"
    daten = tmp_path / "parallel-daten"
    umgebung = {**os.environ, "MASTER_SCHALTER_DATEN": str(daten),
                "PYTHONPATH": str(Path(claude_messen.__file__).resolve().parent.parent)}
    start = time.time() + 1.5
    prozesse = [subprocess.Popen([sys.executable, "-c", _PARALLEL_SKRIPT, str(zaehler), str(credentials), str(start)],
                                 env=umgebung, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                for _ in range(2)]
    for prozess in prozesse:
        _, stderr = prozess.communicate(timeout=60)
        assert prozess.returncode == 0, stderr.decode("utf-8", "replace")

    assert zaehler.read_text(encoding="utf-8").splitlines() == ["x"]


def test_alle_messwege_laufen_durch_messen_cli_erneuert_beim_abgelaufenen_zugang(tmp_path, monkeypatch, erneuerungen,
                                                                                  capsys):
    """`claude-messen` ruft ohne Umweg `claude_messen.messen()`: abgelaufener Zugang ⇒ ein Erneuerungsversuch."""
    from master_schalter import cli

    konfig = tmp_path / "claude-konfiguration"
    _credentials(konfig / ".credentials.json", expires_at=ABGELAUFEN)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(konfig))

    assert cli.main(["claude-messen"]) == 1

    assert len(erneuerungen) == 1
    assert "ohne Erfolg" in capsys.readouterr().err


# --- Ergebnisprüfung R1-1: Uhrzeit erst unter der Sperre, knapp spätere Reservierung sperrt --------------------------

def test_spaetere_reservierung_eines_anderen_prozesses_sperrt_den_frueheren(tmp_path, erneuerungen):
    """A hat seine Zeit vor B genommen; B hat inzwischen reserviert ⇒ A erneuert nicht (kein zweiter Versuch)."""
    claude_messen._erneuerung_datei().parent.mkdir(parents=True, exist_ok=True)
    claude_messen._erneuerung_datei().write_text(
        json.dumps({"zeit": (JETZT + timedelta(minutes=1)).isoformat()}), encoding="utf-8")   # B, nach A's Uhrzeit

    assert claude_messen._erneuerung_versuchen(JETZT) is None
    assert erneuerungen == []


def test_ohne_vorgabe_wird_die_uhrzeit_erst_unter_der_sperre_genommen(tmp_path, erneuerungen, monkeypatch):
    reihenfolge = []
    echte_sperre = claude_messen.zustand.instanz_sperre

    class Uhr(claude_messen.datetime):
        @classmethod
        def now(cls, tz=None):
            reihenfolge.append("uhr")
            return JETZT

    def sperre(name):
        reihenfolge.append("sperre")
        return echte_sperre(name)

    monkeypatch.setattr(claude_messen, "datetime", Uhr)
    monkeypatch.setattr(claude_messen.zustand, "instanz_sperre", sperre)
    assert claude_messen._erneuerung_versuchen() == JETZT
    assert reihenfolge[:2] == ["sperre", "uhr"] and len(erneuerungen) == 1


@pytest.mark.parametrize("abstand, erwartet", [(timedelta(minutes=29), 0), (timedelta(minutes=31), 1)])
def test_zeitstempel_knapp_in_der_zukunft_sperrt_weit_in_der_zukunft_nicht(tmp_path, erneuerungen, abstand, erwartet):
    claude_messen._erneuerung_datei().parent.mkdir(parents=True, exist_ok=True)
    claude_messen._erneuerung_datei().write_text(json.dumps({"zeit": (JETZT + abstand).isoformat()}), encoding="utf-8")
    claude_messen._erneuerung_versuchen(JETZT)
    assert len(erneuerungen) == erwartet
