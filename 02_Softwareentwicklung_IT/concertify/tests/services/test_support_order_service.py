"""
tests/services/test_support_order_service.py
=============================================
Tests fuer reorder_support_acts (reine Sortier-Logik, kein IO).
"""

from services.support_order_service import reorder_support_acts


def _cd():
    return {"support_acts": {"Linkin Park": {"2026-06-01": ["Clipse", "Phantogram"]}}}


def test_reorder_success_changes_list_order():
    cd = _cd()
    ok, err = reorder_support_acts(cd, "Linkin Park", "2026-06-01",
                                   ["Phantogram", "Clipse"])
    assert ok is True
    assert err is None
    assert cd["support_acts"]["Linkin Park"]["2026-06-01"] == ["Phantogram", "Clipse"]


def test_reorder_rejects_different_set_extra_act():
    cd = _cd()
    ok, err = reorder_support_acts(cd, "Linkin Park", "2026-06-01",
                                   ["Phantogram", "Clipse", "Fremd"])
    assert ok is False
    assert err == "order mismatch"
    assert cd["support_acts"]["Linkin Park"]["2026-06-01"] == ["Clipse", "Phantogram"]


def test_reorder_rejects_missing_act():
    cd = _cd()
    ok, err = reorder_support_acts(cd, "Linkin Park", "2026-06-01", ["Clipse"])
    assert ok is False
    assert err == "order mismatch"
    assert cd["support_acts"]["Linkin Park"]["2026-06-01"] == ["Clipse", "Phantogram"]


def test_reorder_unknown_artist_or_date():
    cd = _cd()
    ok, err = reorder_support_acts(cd, "Unbekannt", "2026-06-01", [])
    assert ok is False
    assert err == "unknown artist/date"
    ok2, err2 = reorder_support_acts(cd, "Linkin Park", "1999-01-01", [])
    assert ok2 is False
    assert err2 == "unknown artist/date"
