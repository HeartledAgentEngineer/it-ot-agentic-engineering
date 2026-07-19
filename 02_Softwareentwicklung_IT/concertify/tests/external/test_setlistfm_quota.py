"""
tests/external/test_setlistfm_quota.py
========================================
Tests fuer den setlist.fm Daily-Request-Counter.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from external.setlistfm_quota import SetlistFmQuota


# ─── Basis-Verhalten ─────────────────────────────────────────────────────────

def test_new_file_starts_at_zero(tmp_path):
    quota = SetlistFmQuota(tmp_path / "q.json")
    assert quota.requests_today() == 0
    assert quota.can_make_request() is True


def test_record_request_increments(tmp_path):
    quota = SetlistFmQuota(tmp_path / "q.json")
    assert quota.record_request() == 1
    assert quota.record_request() == 2
    assert quota.record_request() == 3
    assert quota.requests_today() == 3


def test_record_persists_to_file(tmp_path):
    """Nach record_request sollte die Datei den Wert enthalten."""
    file = tmp_path / "q.json"
    quota = SetlistFmQuota(file)
    quota.record_request()
    quota.record_request()

    data = json.loads(file.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert "date_utc" in data
    assert "last_request_iso" in data


def test_new_quota_object_reads_existing_file(tmp_path):
    """Wenn man ein neues Quota-Objekt erstellt, sollte es bestehende Daten lesen."""
    file = tmp_path / "q.json"
    q1 = SetlistFmQuota(file)
    q1.record_request()
    q1.record_request()

    # Neues Objekt — soll den Zaehler kennen
    q2 = SetlistFmQuota(file)
    assert q2.requests_today() == 2


# ─── Soft Limit ──────────────────────────────────────────────────────────────

def test_can_make_request_blocks_at_soft_limit(tmp_path):
    quota = SetlistFmQuota(tmp_path / "q.json", soft_limit=3)
    for _ in range(3):
        quota.record_request()
    assert quota.can_make_request() is False


def test_remaining_decreases(tmp_path):
    quota = SetlistFmQuota(tmp_path / "q.json", soft_limit=10)
    assert quota.remaining_today() == 10
    quota.record_request()
    assert quota.remaining_today() == 9


def test_remaining_never_negative(tmp_path):
    quota = SetlistFmQuota(tmp_path / "q.json", soft_limit=2)
    quota.record_request()
    quota.record_request()
    quota.record_request()  # ueber Limit
    assert quota.remaining_today() == 0


# ─── Tagesreset ──────────────────────────────────────────────────────────────

def test_reset_on_new_day(tmp_path):
    """Wenn das gespeicherte date_utc anders ist als heute, wird auf 0 zurueck-
    gesetzt."""
    file = tmp_path / "q.json"
    # Simuliere Daten von gestern
    file.write_text(json.dumps({
        "date_utc": "1999-01-01",
        "count": 999,
        "last_request_iso": "1999-01-01T12:00:00+00:00",
    }), encoding="utf-8")

    quota = SetlistFmQuota(file)
    assert quota.requests_today() == 0  # gestern zaehlt nicht

    # Nach record_request beginnt der neue Tag bei 1
    quota.record_request()
    data = json.loads(file.read_text(encoding="utf-8"))
    assert data["count"] == 1
    assert data["date_utc"] != "1999-01-01"


# ─── Status / Reset-Time ─────────────────────────────────────────────────────

def test_status_returns_complete_info(tmp_path):
    quota = SetlistFmQuota(tmp_path / "q.json", soft_limit=100)
    quota.record_request()
    quota.record_request()

    status = quota.status()
    assert status["used"] == 2
    assert status["limit"] == 100
    assert status["remaining"] == 98
    assert status["can_request"] is True
    assert status["reset_in_seconds"] > 0


def test_reset_in_seconds_is_positive(tmp_path):
    quota = SetlistFmQuota(tmp_path / "q.json")
    secs = quota.reset_in_seconds()
    assert 0 < secs <= 86400  # zwischen 0 und 24h


# ─── Korrupte Datei ──────────────────────────────────────────────────────────

def test_corrupt_file_starts_fresh(tmp_path):
    """Wenn die JSON-Datei korrupt ist, faengt der Counter bei 0 an."""
    file = tmp_path / "q.json"
    file.write_text("not valid json {", encoding="utf-8")

    quota = SetlistFmQuota(file)
    assert quota.requests_today() == 0
    assert quota.record_request() == 1  # funktioniert trotzdem
