"""Synthetische Tests für die Claude-Usage-API ohne echten Zugang und Netzwerk."""
import io
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import pytest

from master_schalter import claude_messen, signale


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
        claude_messen.messen(credentials_datei=credentials, jetzt=JETZT)

    assert aufrufe == []
    assert str(fehler.value) == "Claude-Anmeldung abgelaufen – Claude Code einmal starten"
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
        assert str(fehler.value) == "Claude-Anmeldung abgelaufen – Claude Code einmal starten"
    if status == 429:
        assert fehler.value.status == 429


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
    assert TOKEN not in str(fehler.value)
    assert ziel.read_bytes() == alt


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
