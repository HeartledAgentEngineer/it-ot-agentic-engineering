"""
routes/imports.py
===================
Flask Blueprint fuer Playlist-Import-Preview.

Endpunkte:
    GET /api/v2/imports/available         → alle importierbaren Playlists
    GET /api/v2/imports/preview/<spotify_id> → Preview was beim Import passieren wuerde
"""

from pathlib import Path

from flask import Blueprint, abort, jsonify

from repositories.json_repo import JsonArtistRepository
from repositories.saved_playlist_repo import JsonSavedPlaylistRepository
from services.playlist_import_service import (
    ArtistImportInfo,
    ImportPreview,
    PlaylistImportService,
)

imports_bp = Blueprint("imports", __name__, url_prefix="/api/v2/imports")


# ─── Service-Setup ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
_artist_repo = JsonArtistRepository(BASE_DIR / "concert_data.json")
_playlist_repo = JsonSavedPlaylistRepository(BASE_DIR / "saved_playlists.json")
_service = PlaylistImportService(_playlist_repo, _artist_repo)


# ─── Routen ──────────────────────────────────────────────────────────────────

@imports_bp.route("/available", methods=["GET"])
def list_available():
    """Liefert alle gespeicherten Playlists mit Import-Status-Info.

    Diese Liste zeigt die UI an um dem User zu sagen "diese Playlists kannst
    du importieren — beim Import passiert das und das".
    """
    items = _service.list_importable()
    return jsonify({"count": len(items), "imports": items})


@imports_bp.route("/preview/<spotify_id>", methods=["GET"])
def get_preview(spotify_id: str):
    """Detail-Preview fuer eine konkrete Playlist.

    Zeigt pro Kuenstler:
    - existiert er bereits in concert_data.json?
    - hat er Setlist-Daten?
    - welche Songs muessten neu angelegt werden?
    """
    preview = _service.preview(spotify_id)
    if preview is None:
        abort(404, description=f"Playlist {spotify_id!r} nicht gefunden")
    return jsonify(_preview_to_dict(preview))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _artist_info_to_dict(info: ArtistImportInfo) -> dict:
    return {
        "name": info.name,
        "is_support_act": info.is_support_act,
        "exists_in_concerts": info.exists_in_concerts,
        "has_setlist_data": info.has_setlist_data,
        "songs_to_restore": info.songs_to_restore,
        "songs_missing": info.songs_missing,
        "action_summary": info.action_summary(),
    }


def _preview_to_dict(p: ImportPreview) -> dict:
    return {
        "spotify_id": p.spotify_id,
        "playlist_name": p.playlist_name,
        "playlist_type": p.playlist_type,
        "event_date": p.event_date,
        "festival": p.festival,
        "venue": p.venue,
        "city": p.city,
        "is_fully_present": p.is_fully_present(),
        "total_artists_to_create": p.total_artists_to_create(),
        "total_songs_to_add": p.total_songs_to_add(),
        "artists": [_artist_info_to_dict(a) for a in p.artists],
    }
