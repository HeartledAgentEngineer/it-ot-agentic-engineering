"""
tests/test_setlist_snapshots_ui.py
===================================
Statische Regression: prueft, dass die Snapshot-/Reload-UI im Template
vorhanden ist (kein Browser noetig).
"""

from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "index.html"


@pytest.fixture(scope="module")
def html():
    return TEMPLATE.read_text(encoding="utf-8")


# --- Task 6: force-Reload ---

def test_fetch_songs_accepts_force_param(html):
    assert "function fetchSongsForArtist(listEl, needed, force" in html


def test_more_songs_body_includes_force(html):
    # In beiden Request-Bodies an /more_songs muss force mitgehen
    # JS shorthand property: "force" ohne Doppelpunkt (z.B. {..., force})
    assert html.count(", force}") + html.count(", force,") >= 2


def test_abend_fetch_accepts_force(html):
    assert "async function _abendFetchSongs(mode" in html
    assert "force" in html.split("async function _abendFetchSongs(mode")[1][:600]


# --- Task 7: Snapshot-Button + Panel ---

def test_snapshot_button_present(html):
    assert "snapshot-btn" in html
    assert "saveSnapshotForArtist" in html


def test_snapshot_panel_functions_present(html):
    for fn in ("loadSnapshotPanel", "restoreSnapshot", "renameSnapshot", "deleteSnapshot"):
        assert f"function {fn}" in html


def test_snapshot_endpoints_referenced(html):
    assert "/snapshots/create" in html
    assert "/snapshots/list" in html
    assert "/snapshots/restore" in html
    assert "/snapshots/rename" in html
    assert "/snapshots/delete" in html


# --- Task 8: Vergleichsansicht ---

def test_compare_view_helpers_present(html):
    assert "function showSetlistDiff" in html
    assert "/snapshots/is_saved" in html


def test_compare_view_has_keep_and_apply(html):
    # Buttons "Behalten" und "Übernehmen" muessen im Diff-UI auftauchen
    assert "Behalten" in html
    assert "Übernehmen" in html
