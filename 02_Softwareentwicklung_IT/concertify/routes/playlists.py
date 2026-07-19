"""
routes/playlists.py
=====================
Flask Blueprint fuer SavedPlaylist-Endpunkte.

Endpunkte unter /api/v2/playlists/...

Engineering-Konzept: "REST-style HTTP-API"
    GET    /api/v2/playlists                 → liste aller gespeicherten
    GET    /api/v2/playlists/<id>            → einzelne Playlist
    POST   /api/v2/playlists/save_mix        → Setlist-Mix speichern
    POST   /api/v2/playlists/save_evening    → Konzertabend speichern
    DELETE /api/v2/playlists/<id>            → loescht eine Playlist
"""

from datetime import date
from pathlib import Path

from flask import Blueprint, abort, jsonify, request

from domain.saved_playlist import SavedPlaylist
from repositories.saved_playlist_repo import JsonSavedPlaylistRepository
from services.playlist_save_service import PlaylistSaveService

playlists_bp = Blueprint("playlists", __name__, url_prefix="/api/v2/playlists")


# ─── Service-Initialisierung ─────────────────────────────────────────────────
# Die JSON-Datei liegt im Projektroot neben concert_data.json.

BASE_DIR = Path(__file__).resolve().parent.parent
_repo = JsonSavedPlaylistRepository(BASE_DIR / "saved_playlists.json")
_service = PlaylistSaveService(_repo)


# ─── Lese-Routen ─────────────────────────────────────────────────────────────

@playlists_bp.route("", methods=["GET"])
def list_playlists():
    """Liefert alle gespeicherten Playlists.

    Query-Parameter:
        type=konzertabend|setlist_mix  (optional Filter)
    """
    playlist_type = request.args.get("type", "").strip().lower()
    if playlist_type == "konzertabend":
        items = _service.list_konzertabende()
    elif playlist_type == "setlist_mix":
        items = _service.list_setlist_mixes()
    else:
        items = _service.list_all()

    return jsonify({
        "count": len(items),
        "playlists": [_playlist_to_dict(pl) for pl in items],
    })


@playlists_bp.route("/<spotify_id>", methods=["GET"])
def get_playlist(spotify_id: str):
    """Liefert eine einzelne gespeicherte Playlist mit allen Details."""
    pl = _service.get(spotify_id)
    if pl is None:
        abort(404, description=f"Playlist {spotify_id!r} nicht gefunden")
    return jsonify(_playlist_to_dict(pl))


# ─── Speicher-Routen ─────────────────────────────────────────────────────────

@playlists_bp.route("/save_mix", methods=["POST"])
def save_setlist_mix():
    """Speichert (oder ueberschreibt) eine Setlist-Mix-Playlist.

    Request-Body (JSON):
        {
          "spotify_id": "abc...",
          "name": "Sommer-Mix 2026",
          "description": "optional",
          "cover_url": "optional",
          "artists": ["LP", "BB"],
          "artist_selections": {"LP": ["Numb"], "BB": ["Diary"]},
          "config": {"limit_per_artist": 22}
        }
    """
    payload = request.get_json(force=True) or {}
    try:
        pl = _service.save_setlist_mix(
            spotify_id=payload["spotify_id"],
            name=payload["name"],
            description=payload.get("description", ""),
            cover_url=payload.get("cover_url"),
            artists=payload.get("artists"),
            artist_selections=payload.get("artist_selections"),
            config=payload.get("config"),
        )
    except KeyError as e:
        abort(400, description=f"Pflichtfeld fehlt: {e}")
    except ValueError as e:
        abort(400, description=str(e))

    return jsonify({"ok": True, "playlist": _playlist_to_dict(pl)}), 201


@playlists_bp.route("/save_evening", methods=["POST"])
def save_konzertabend():
    """Speichert einen Konzertabend mit Termin, Buehnen, Setlisten.

    Request-Body (JSON):
        {
          "spotify_id": "xyz...",
          "name": "Rock im Park Tag 1",
          "event_date": "2026-06-05",
          "festival": "Rock im Park",
          "venue": "Zeppelinfeld",
          "city": "Nuernberg",
          "stages": ["Mandora", "Utopia"],
          "artists": ["Linkin Park"],
          "support_acts": ["Spiritbox"],
          "artist_selections": {
            "Linkin Park": ["Numb", "In the End"],
            "Spiritbox": ["Holy Roller"]
          },
          "config": {"limit_per_artist": 15}
        }
    """
    payload = request.get_json(force=True) or {}

    event_date_str = payload.get("event_date")
    event_date = date.fromisoformat(event_date_str) if event_date_str else None

    try:
        pl = _service.save_konzertabend(
            spotify_id=payload["spotify_id"],
            name=payload["name"],
            description=payload.get("description", ""),
            cover_url=payload.get("cover_url"),
            event_date=event_date,
            venue=payload.get("venue"),
            city=payload.get("city"),
            festival=payload.get("festival"),
            stages=payload.get("stages"),
            artists=payload.get("artists"),
            support_acts=payload.get("support_acts"),
            artist_selections=payload.get("artist_selections"),
            config=payload.get("config"),
        )
    except KeyError as e:
        abort(400, description=f"Pflichtfeld fehlt: {e}")
    except ValueError as e:
        abort(400, description=str(e))

    return jsonify({"ok": True, "playlist": _playlist_to_dict(pl)}), 201


# ─── Loesch-Route ────────────────────────────────────────────────────────────

@playlists_bp.route("/<spotify_id>", methods=["DELETE"])
def delete_playlist(spotify_id: str):
    """Loescht eine gespeicherte Playlist (nur unseren Snapshot, nicht Spotify)."""
    ok = _service.delete(spotify_id)
    if not ok:
        abort(404, description=f"Playlist {spotify_id!r} nicht gefunden")
    return jsonify({"ok": True})


# ─── Helper: Domain → Dict ────────────────────────────────────────────────────

def _playlist_to_dict(pl: SavedPlaylist) -> dict:
    """Serialisiert eine SavedPlaylist zu JSON-tauglichem Dict."""
    return {
        "spotify_id": pl.spotify_id,
        "name": pl.name,
        "playlist_type": pl.playlist_type,
        "description": pl.description,
        "cover_url": pl.cover_url,
        "created_at": pl.created_at.isoformat(),
        "updated_at": pl.updated_at.isoformat(),
        "event_date": pl.event_date.isoformat() if pl.event_date else None,
        "venue": pl.venue,
        "city": pl.city,
        "festival": pl.festival,
        "stages": pl.stages,
        "artists": pl.artists,
        "support_acts": pl.support_acts,
        "artist_selections": pl.artist_selections,
        "config": pl.config,
        "total_song_count": pl.total_song_count(),
    }
