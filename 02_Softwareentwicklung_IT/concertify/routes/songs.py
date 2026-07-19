"""
routes/songs.py
=================
Flask Blueprint fuer Song-/Setlist-bezogene HTTP-Routen.

Engineering-Konzept: "Dünne Route"
    Routen sollen NUR machen:
    1. Request-Parameter auslesen
    2. Service aufrufen
    3. Response zurueckgeben (JSON oder HTML)

    KEINE Business-Logik. Das ist die Aufgabe des Service.

Brueckenwissen:
    C# / ASP.NET: Wie ein Controller mit [HttpGet]-Action-Methoden.
    REST:         Endpunkt /api/v2/... liefert JSON, leicht zu testen.
"""

from pathlib import Path

from flask import Blueprint, abort, jsonify

from repositories.json_repo import JsonArtistRepository
from services.setlist_service import SetlistService

# ─── Blueprint-Setup ─────────────────────────────────────────────────────────
# `url_prefix='/api/v2'` → ALLE Routen hier beginnen mit /api/v2/...
# Das macht klar: das ist die neue API-Version, parallel zur alten /more_songs.

songs_bp = Blueprint("songs", __name__, url_prefix="/api/v2")


# ─── Service-Initialisierung ─────────────────────────────────────────────────
# Im Moment einfach am Modul-Level. Spaeter kann man das in eine Factory
# packen (`create_app()` Pattern). Fuer Slice 1 reicht das.

BASE_DIR = Path(__file__).resolve().parent.parent
_repo = JsonArtistRepository(BASE_DIR / "concert_data.json")
_service = SetlistService(_repo)


# ─── Routen ──────────────────────────────────────────────────────────────────

@songs_bp.route("/setlist/<artist_name>", methods=["GET"])
def get_setlist(artist_name: str):
    """Liefert die Setlist eines Kuenstlers als JSON.

    Beispiel:
        GET /api/v2/setlist/H-Blockx
    """
    summary = _service.setlist_summary(artist_name)
    if summary is None:
        abort(404, description=f"Keine Setlist fuer {artist_name!r} gefunden")

    songs = _service.get_display_songs(artist_name)

    return jsonify({
        "summary": summary,
        "songs": [_song_to_dict(s) for s in songs],
    })


@songs_bp.route("/setlist/<artist_name>/songs", methods=["GET"])
def get_songs(artist_name: str):
    """Liefert nur die Songs (ohne Summary), evtl. limitiert.

    Beispiel:
        GET /api/v2/setlist/Linkin Park/songs?limit=10&likely=true
    """
    from flask import request

    # Query-Parameter auslesen (alles ist erstmal String)
    limit_str = request.args.get("limit")
    limit = int(limit_str) if limit_str and limit_str.isdigit() else None
    only_likely = request.args.get("likely", "").lower() in ("1", "true", "yes")

    songs = _service.get_display_songs(
        artist_name,
        limit=limit,
        only_likely=only_likely,
    )

    if not songs:
        # Pruefen ob der Kuenstler existiert (Unterschied: leere Liste vs 404)
        if _service.get_setlist(artist_name) is None:
            abort(404, description=f"Keine Setlist fuer {artist_name!r}")

    return jsonify({
        "artist_name": artist_name,
        "count": len(songs),
        "songs": [_song_to_dict(s) for s in songs],
    })


@songs_bp.route("/artists", methods=["GET"])
def list_artists():
    """Liefert die Liste aller bekannten Kuenstler-Namen.

    Beispiel:
        GET /api/v2/artists
    """
    names = _repo.list_names()
    return jsonify({"count": len(names), "names": names})


# ─── Helper: Domain-Objekt → Dict fuer JSON ──────────────────────────────────

def _song_to_dict(song) -> dict:
    """Serialisiert ein Song-Objekt zu einem JSON-tauglichen Dict.

    Hinweis: Wir koennten auch `dataclasses.asdict(song)` nutzen, aber
    so haben wir die Kontrolle ueber Feldnamen und koennen abgeleitete
    Werte (position_range, average_position) gleich mitliefern.
    """
    pos_range = song.position_range()
    return {
        "title": song.title,
        "spotify_uri": song.spotify_uri,
        "score": song.score,
        "play_count": song.play_count,
        "positions_hist": song.positions_hist,
        "position_range": list(pos_range) if pos_range else None,
        "average_position": song.average_position(),
        "badge": song.badge,
        "has_uri": song.has_uri(),
        "is_likely_played": song.is_likely_played(),
    }
