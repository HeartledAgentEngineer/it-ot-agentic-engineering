"""
tests/test_song_states_ui.py
============================
Regression: Checkboxes, Drag-Handles & Drag&Drop endpoints for Song Exclusion and Reordering.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _template_text() -> str:
    return (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def test_song_exclude_checkboxes_present():
    text = _template_text()
    # Check that checkboxes are defined both in HTML/Jinja and dynamic JS renders
    assert 'class="song-exclude-checkbox"' in text
    assert 'input type="checkbox" class="song-exclude-checkbox"' in text


def test_song_excluded_css_styles():
    text = _template_text()
    # Verify that CSS styling for excluded/greyed out songs is defined
    assert '.song-row.excluded' in text
    assert 'text-decoration: line-through;' in text


def test_song_state_js_variables_and_hydration():
    text = _template_text()
    # Verify the global Set for excluded songs exists and is hydrated from Jinja
    assert 'const excludedSongs = new Set([' in text
    assert 'excluded_songs' in text


def test_song_states_endpoints_in_js():
    text = _template_text()
    # Verify that dynamic events communicate with the correct endpoints
    assert '/toggle_song_excluded' in text
    assert '/reorder_songs' in text


def test_global_drag_and_drop_listeners():
    text = _template_text()
    # Verify that the new central HTML5 delegation listeners are registered on document
    assert "document.addEventListener('dragstart'" in text
    assert "document.addEventListener('dragend'" in text
    assert "document.addEventListener('dragover'" in text
    assert "document.addEventListener('drop'" in text
    assert "_dragRow" in text
    assert "_dragOverRow" in text


def test_song_drag_handles_and_draggable():
    text = _template_text()
    # Check that draggable handles (grip character) exist in the HTML structure
    assert 'draggable="true"' in text
    assert '⠿' in text


def test_excluded_songs_skipped_in_playlist_creation():
    text = _template_text()
    # Verify that excluded songs are skipped during playlist creation in both tabs
    # (Checking that row.classList.contains('excluded') is used inside loops)
    assert "row.classList.contains('excluded')" in text
    assert text.count("row.classList.contains('excluded')") >= 4


def test_abend_toggle_all_songs_and_auto_open_support():
    text = _template_text()
    # Verify the global toggler for all artists (main + support) exists in templates/index.html
    assert 'id="abend-toggle-all-songs"' in text
    assert 'onclick="abendToggleAllSongs(this)"' in text
    assert 'function abendToggleAllSongs(' in text
    assert '_abendSongsVisible' in text


def test_abend_support_exclude_checkboxes():
    text = _template_text()
    # Checkboxen fuer Support-Acts im Konzertabend-Tab muessen vorhanden sein
    assert 'name="include_support_artists"' in text
    assert 'toggleAbendSupportExclude(this)' in text
    # CSS-Selektor fuer das Ausgrauen abgewaehlter Support-Acts muss vorhanden sein
    assert '.support-act-item:has(input[name="include_support_artists"]:not(:checked))' in text
    # Speicher- und Lade-Logik muss vorhanden sein
    assert 'function saveUncheckedSupports(' in text
    assert 'function loadUncheckedSupports(' in text
    # Ausschluss bei Playlist-Erstellung und Beschreibung
    assert 'input[name="include_support_artists"]' in text


def test_bulk_exclusion_buttons_present():
    text = _template_text()
    # Verify that the two new Pill-Buttons for bulk-exclusion exist in templates/index.html
    assert 'toggleSongsByColor(this, \'grey\')' in text
    assert 'toggleSongsByColor(this, \'yellow\')' in text
    assert 'class="pill-btn grey-toggle-btn"' in text
    assert 'class="pill-btn yellow-toggle-btn"' in text
    assert 'AUTO-AUSGRAUEN:' in text


def test_playlist_name_manual_edit_protection():
    text = _template_text()
    # Verify that dataset.userEdited protection is defined for both tabs
    assert 'document.getElementById(\'playlistName\').dataset.userEdited' in text
    assert 'document.getElementById(\'abend-playlist-name\').dataset.userEdited' in text
    assert 'delete nameInput.dataset.userEdited;' in text
    assert 'delete document.getElementById(\'abend-playlist-name\').dataset.userEdited;' in text


def test_create_abend_playlist_sends_artist_snapshot():
    text = _template_text()
    # Sichert ab, dass der artistSnapshot im Konzertabend-Tab erstellt und an den Server gesendet wird
    assert 'artistSnapshot[_abendArtist] = {' in text
    assert 'artistSnapshot[actName] = {' in text
    assert 'body: JSON.stringify({playlist_name: name, track_uris: uris, description: desc, artist_snapshot: artistSnapshot})' in text




