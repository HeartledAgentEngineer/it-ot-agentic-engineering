"""
tests/test_more_songs_ratelimit.py
==================================
Regression: /more_songs darf beim Force-Reload NICHT crashen, wenn setlist.fm
rate-limited ist. Frueher griff der Rate-Limit-Fallback auf die Variable
`_remaining` zu, die im Force-Refresh-Pfad nie definiert wurde
(UnboundLocalError -> HTTP 500 -> HTML statt JSON). Erwartet: sauberer
Fallback auf die gecachte Setlist.
"""

import json

import pytest

import app as app_module


class _RateLimitedSetlistClient:
    """Stub, der wie setlist.fm im Rate-Limit reagiert."""

    def __init__(self, *args, **kwargs):
        pass

    def get_setlist_ordered(self, *args, **kwargs):
        raise RuntimeError("rate_limited:123")


@pytest.fixture
def cached_data(tmp_path, monkeypatch):
    """Legt eine concert_data.json mit gecachter Setlist an und biegt BASE_DIR um."""
    cd = {
        "setlist_data": {
            "Testband": {
                "setlist_titles": ["Numb", "Faint", "Lost"],
                "scores": {"Numb": 0.9, "Faint": 0.8, "Lost": 0.5},
                "badges": {"Numb": "setlist", "Faint": "setlist", "Lost": "setlist"},
                "spotify_uris": {},
            }
        }
    }
    (tmp_path / "concert_data.json").write_text(json.dumps(cd), encoding="utf-8")
    monkeypatch.setattr(app_module, "BASE_DIR", tmp_path)
    # setlist.fm-Key vorhanden -> Mode-Pfad wird betreten; Gemini aus.
    monkeypatch.setattr(
        app_module, "dotenv_values",
        lambda *a, **k: {"SETLISTFM_API_KEY": "dummy", "GEMINI_API_KEY": ""},
    )
    monkeypatch.setattr("setlist_client.SetlistClient", _RateLimitedSetlistClient)
    return tmp_path


def test_force_reload_when_ratelimited_falls_back_to_cache(cached_data):
    client = app_module.app.test_client()
    resp = client.post(
        "/more_songs",
        json={"artist": "Testband", "needed": 5, "mode": "concert", "force": True},
    )
    assert resp.status_code == 200  # vor dem Fix: 500 (UnboundLocalError)
    body = resp.get_json()
    assert body is not None
    assert "Numb" in body["songs"]


def test_ratelimit_is_recorded_even_with_cache(cached_data, monkeypatch):
    """Auch wenn der Cache greift, MUSS der Rate-Limit in _api_health landen —
    sonst ueberspringt _sl_blocked folgende (force-)Calls nicht und setlist.fm
    wird weiter angestossen."""
    monkeypatch.setattr(app_module, "_api_health", {})
    client = app_module.app.test_client()
    client.post(
        "/more_songs",
        json={"artist": "Testband", "needed": 5, "mode": "concert", "force": True},
    )
    health = app_module._api_health.get("setlist")
    assert health is not None, "Rate-Limit wurde nicht in _api_health eingetragen"
    assert health["ok"] is False
    assert health["retry_after"] > 0


def test_blocked_setlist_skips_real_call_even_with_force(tmp_path, monkeypatch):
    """Ist setlist.fm als gesperrt vermerkt, darf auch force:true KEINEN echten
    setlist.fm-Aufruf ausloesen (Schutz vor weiterem Anstossen des Limits)."""
    import time

    cd = {
        "setlist_data": {
            "Testband": {
                "setlist_titles": ["Numb", "Faint", "Lost"],
                "scores": {"Numb": 0.9, "Faint": 0.8, "Lost": 0.5},
                "badges": {}, "spotify_uris": {},
            }
        }
    }
    (tmp_path / "concert_data.json").write_text(json.dumps(cd), encoding="utf-8")
    monkeypatch.setattr(app_module, "BASE_DIR", tmp_path)
    monkeypatch.setattr(
        app_module, "dotenv_values",
        lambda *a, **k: {"SETLISTFM_API_KEY": "dummy", "GEMINI_API_KEY": ""},
    )
    # setlist.fm als gesperrt markieren (innerhalb des Retry-Fensters)
    monkeypatch.setattr(app_module, "_api_health", {
        "setlist": {"ok": False, "checked": int(time.time()),
                    "retry_after": 3600, "error": "rate_limited"}
    })

    class _SpySetlistClient:
        calls = 0

        def __init__(self, *args, **kwargs):
            _SpySetlistClient.calls += 1

        def get_setlist_ordered(self, *a, **k):
            return {"ordered": [], "positions": {}, "is_encore": {}}

        def get_setlist_tracks(self, *a, **k):
            return {"setlist_titles": [], "new_titles": [], "frequencies": {}}

    monkeypatch.setattr("setlist_client.SetlistClient", _SpySetlistClient)

    client = app_module.app.test_client()
    resp = client.post(
        "/more_songs",
        json={"artist": "Testband", "needed": 5, "mode": "concert", "force": True},
    )
    assert resp.status_code == 200
    assert _SpySetlistClient.calls == 0, "setlist.fm wurde trotz Sperre aufgerufen"


def test_tour_options_uses_retry_after_value(tmp_path, monkeypatch):
    """Auch der Tour-Endpunkt muss den echten Retry-After-Wert (Sekunden)
    aus 'rate_limited:N' uebernehmen statt pauschal bis Mitternacht zu sperren."""
    monkeypatch.setattr(app_module, "BASE_DIR", tmp_path)
    monkeypatch.setattr(
        app_module, "dotenv_values", lambda *a, **k: {"SETLISTFM_API_KEY": "dummy"}
    )
    monkeypatch.setattr(app_module, "_api_health", {})

    class _RateLimitedTour:
        def __init__(self, *a, **k):
            pass

        def get_tour_options(self, *a, **k):
            raise RuntimeError("rate_limited:300")  # kurze Drosselung, 300s

    monkeypatch.setattr("setlist_client.SetlistClient", _RateLimitedTour)

    client = app_module.app.test_client()
    resp = client.get("/get_tour_options?artist=Testband")
    assert resp.status_code == 200
    assert resp.get_json().get("error") == "rate_limited"
    health = app_module._api_health.get("setlist")
    assert health is not None
    assert health["retry_after"] == 300, (
        "Tour-Endpunkt ignoriert den Retry-After-Wert (sperrt pauschal bis Mitternacht)"
    )
