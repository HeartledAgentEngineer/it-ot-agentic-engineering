"""
tests/test_setlist_quota.py
===========================
Prueft, dass SetlistClient den taeglichen setlist.fm-Zaehler (SetlistFmQuota)
respektiert: bei erreichtem Limit geht KEIN Request mehr raus (vermeidet die
24h-Eskalations-Sperre), sonst wird jeder abgesetzte Call mitgezaehlt.
Der Zaehler wird per Dependency Injection eingehaengt, damit ohne Netz und
ohne echte JSON-Datei getestet werden kann.
"""

import pytest

from setlist_client import SetlistClient

_BASE = "https://api.setlist.fm/rest/1.0"


class _FakeQuota:
    """Minimaler Ersatz fuer SetlistFmQuota."""

    def __init__(self, allowed: bool):
        self._allowed = allowed
        self.recorded = 0

    def can_make_request(self) -> bool:
        return self._allowed

    def record_request(self) -> int:
        self.recorded += 1
        return self.recorded


class _FakeResponse:
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return {"artist": []}


class _FakeSession:
    def __init__(self):
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return _FakeResponse()


def test_kein_request_wenn_limit_erreicht():
    client = SetlistClient("dummy-key", quota=_FakeQuota(allowed=False))
    client.session = _FakeSession()
    with pytest.raises(RuntimeError, match="rate_limited:quota"):
        client._get(f"{_BASE}/search/artists", params={"artistName": "X"})
    assert client.session.calls == 0  # Call ging NICHT raus


def test_erlaubter_request_wird_mitgezaehlt():
    q = _FakeQuota(allowed=True)
    client = SetlistClient("dummy-key", quota=q)
    client.session = _FakeSession()
    resp = client._get(f"{_BASE}/search/artists", params={"artistName": "X"})
    assert client.session.calls == 1
    assert q.recorded == 1
    assert resp.status_code == 200


def test_default_quota_wird_angelegt():
    # Ohne injizierten Quota soll ein echter Zaehler vorhanden sein.
    client = SetlistClient("dummy-key")
    assert hasattr(client, "_quota")
    assert client._quota.can_make_request() in (True, False)
