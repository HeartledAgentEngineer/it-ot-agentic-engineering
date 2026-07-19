"""
Regression checks fuer den Playlist-Import im grossen Template.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _template_text() -> str:
    return (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def test_import_button_does_not_embed_artist_json_in_onclick():
    text = _template_text()

    assert "onclick=\"_applyImportToMix(${JSON.stringify" not in text
    assert "window._pendingImportArtists" in text


def test_backup_restore_imports_all_artists_without_switching_tabs():
    text = _template_text()

    assert "async function _applyImportToMix" in text
    assert "_applyImportToMix(artists, {" in text
    assert "stayOnPage: true" in text
    assert "window.location.replace('/?imported=1')" not in text
    assert "mixTab.checked = true" not in text


def test_playlists_tab_buttons_do_not_use_broken_inline_onclick():
    text = _template_text()

    # Verify that the old buggy onclick lines are gone
    assert 'onclick="loadPlaylistToMix(' not in text
    assert 'onclick="startRename(this,' not in text
    assert 'onclick="generateCover(this,' not in text
    assert 'onclick="deletePlaylist(this,' not in text

    # Verify that event delegation setup and elements are present
    assert "playlistsGrid.addEventListener('click'" in text
    assert 'data-action="load-to-mix"' in text
    assert 'data-action="load-to-abend"' in text
    assert 'data-action="restore-backup"' in text
    assert 'data-action="rename"' in text
    assert 'data-action="ki-cover"' in text
    assert 'data-action="delete"' in text
    assert 'async function loadPlaylistToAbend(' in text

