"""Spotify API wrapper using spotipy."""

import json
import os
import time
from pathlib import Path

_CACHE_FILE = Path(__file__).parent / ".track_cache.json"


def _load_cache() -> dict:
    if _CACHE_FILE.exists():
        try:
            return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

import spotipy
from spotipy.oauth2 import SpotifyOAuth


SCOPES = [
    "user-follow-read",
    "playlist-read-private",
    "playlist-modify-public",
    "playlist-modify-private",
    "ugc-image-upload",
]


class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=" ".join(SCOPES),
            ),
            requests_timeout=10,
            retries=3,
            backoff_factor=0.3,
        )

    # ------------------------------------------------------------------ #
    # Artists                                                              #
    # ------------------------------------------------------------------ #

    def get_followed_artists(self) -> list[dict]:
        """Return all artists the user follows (handles pagination)."""
        artists: list[dict] = []
        after: str | None = None

        while True:
            result = self.sp.current_user_followed_artists(limit=50, after=after)
            page = result["artists"]
            artists.extend(page["items"])
            after = page["cursors"]["after"]
            if not after:
                break

        token_info = self.sp.auth_manager.get_cached_token()
        if token_info:
            print(f"  Token scopes: {token_info.get('scope', 'unknown')}")
        print(f"  >> {len(artists)} followed artists fetched")
        return artists

    # ------------------------------------------------------------------ #
    # Tracks                                                               #
    # ------------------------------------------------------------------ #

    def get_best_tracks(
        self,
        artist_id: str,
        artist_name: str,
        max_tracks: int = 10,
        setlist_titles: list[str] | None = None,
        new_titles: list[str] | None = None,
        setlist_count: int = 8,
        new_count: int = 2,
        exclude_titles: list[str] | None = None,
    ) -> list[dict]:
        """
        Fetch tracks for an artist.

        If setlist_titles / new_titles are provided (from SetlistClient):
          - Rank album tracks by setlist frequency → pick top `setlist_count`
          - Append tracks matching new_titles → pick top `new_count`
        Otherwise fall back to first tracks from albums.
        exclude_titles: song names the user manually removed in the UI.
        """
        all_tracks = self._tracks_via_albums(artist_id)
        if not all_tracks:
            return []

        exclude_norms: set[str] = {_norm_title(t) for t in (exclude_titles or [])}

        if not setlist_titles and not new_titles:
            result = []
            for t in all_tracks:
                if len(result) >= max_tracks:
                    break
                if _norm_title(t.get("name", "")) not in exclude_norms:
                    result.append(t)
            return result

        # Build lookup: normalised title → track
        title_map: dict[str, dict] = {}
        for t in all_tracks:
            norm = _norm_title(t.get("name", ""))
            if norm and norm not in title_map:
                title_map[norm] = t

        selected: list[dict] = []
        seen_ids: set[str] = set()

        # 1) Setlist songs (ordered by frequency, already sorted by caller)
        for title in (setlist_titles or []):
            if len(selected) >= setlist_count:
                break
            if _norm_title(title) in exclude_norms:
                continue
            track = title_map.get(_norm_title(title))
            if track and track["id"] not in seen_ids:
                selected.append(track)
                seen_ids.add(track["id"])

        # 2) New bangers (recent unreleased-live songs)
        for title in (new_titles or []):
            if len(selected) >= setlist_count + new_count:
                break
            if _norm_title(title) in exclude_norms:
                continue
            track = title_map.get(_norm_title(title))
            if track and track["id"] not in seen_ids:
                selected.append(track)
                seen_ids.add(track["id"])

        # 3) Fill remaining slots with album tracks in order
        for track in all_tracks:
            if len(selected) >= max_tracks:
                break
            if track["id"] not in seen_ids and _norm_title(track.get("name", "")) not in exclude_norms:
                selected.append(track)
                seen_ids.add(track["id"])

        return selected[:max_tracks]

    def get_artist_top_tracks(self, artist_id: str, market: str = "DE") -> list[dict]:
        """Fetch the top 10 tracks for the artist directly from Spotify."""
        cache = _load_cache()
        cache_key = f"{artist_id}_top_tracks"
        if cache_key in cache:
            return cache[cache_key]

        try:
            time.sleep(0.15)  # Rate-limit safety
            result = self.sp.artist_top_tracks(artist_id, country=market)
            tracks = result.get("tracks", [])
            for track in tracks:
                if track.get("id"):
                    track["uri"] = track.get("uri") or f"spotify:track:{track['id']}"
            
            if tracks:
                cache[cache_key] = tracks
                _save_cache(cache)
            return tracks
        except Exception as e:
            print(f"      artist_top_tracks error: {e}")
            return []

    def _tracks_via_albums(self, artist_id: str) -> list[dict]:
        """Fetch tracks from the artist's 4 most recent albums/singles (cached)."""
        cache = _load_cache()
        if artist_id in cache:
            return cache[artist_id]

        track_map: dict[str, dict] = {}
        try:
            result = self.sp.artist_albums(
                artist_id,
                album_type="album,single",
                limit=20,
            )
            albums = result.get("items", [])
        except Exception as e:
            print(f"      albums error: {e}")
            return []

        for album in albums[:4]:
            album_id = album.get("id")
            if not album_id:
                continue
            try:
                time.sleep(0.15)
                result = self.sp.album_tracks(album_id, limit=50, market="DE")
                for track in result.get("items", []):
                    if track.get("id"):
                        track["uri"] = track.get("uri") or f"spotify:track:{track['id']}"
                        track_map[track["id"]] = track
            except Exception as e:
                print(f"      album_tracks error: {e}")
                continue

        tracks = list(track_map.values())
        if tracks:
            cache[artist_id] = tracks
            _save_cache(cache)
        return tracks

    # ------------------------------------------------------------------ #
    # Playlist                                                             #
    # ------------------------------------------------------------------ #

    def get_or_create_playlist(self, name: str) -> tuple[str, bool]:
        """Return (playlist_id, created). Finds existing playlist first."""
        user_id = self.sp.current_user()["id"]
        offset = 0
        while True:
            result = self.sp.current_user_playlists(limit=50, offset=offset)
            for pl in result.get("items", []):
                if pl["name"] == name and pl["owner"]["id"] == user_id:
                    return pl["id"], False
            if result.get("next") is None:
                break
            offset += 50

        # Use me/playlists endpoint (avoids 403 on users/{id}/playlists)
        new_pl = self.sp._post(
            "me/playlists",
            payload={"name": name, "public": False, "description": ""},
        )
        return new_pl["id"], True

    def update_playlist(
        self, playlist_id: str, track_uris: list[str], description: str
    ) -> tuple[int, int]:
        """
        Diff-based update: only replaces content if tracks changed.
        Returns (num_added, num_removed).
        """
        current_uris = self._get_track_uris(playlist_id)
        current_set = set(current_uris)
        desired_set = set(track_uris)

        added = desired_set - current_set
        removed = current_set - desired_set

        try:
            self.sp.playlist_change_details(playlist_id, description=description)
        except Exception:
            pass  # Description-Update nicht kritisch

        if added or removed:
            self.sp.playlist_replace_items(playlist_id, [])
            for i in range(0, len(track_uris), 100):
                self.sp.playlist_add_items(playlist_id, track_uris[i : i + 100])
                time.sleep(0.1)

        return len(added), len(removed)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _get_track_uris(self, playlist_id: str) -> list[str]:
        uris: list[str] = []
        offset = 0
        while True:
            result = self.sp.playlist_tracks(
                playlist_id, limit=100, offset=offset, fields="items(track(uri)),next"
            )
            for item in result.get("items", []):
                track = item.get("track")
                if track and track.get("uri"):
                    uris.append(track["uri"])
            if result.get("next") is None:
                break
            offset += 100
        return uris


def _norm_title(title: str) -> str:
    """Normalise a song title for matching (lowercase, no punctuation)."""
    import re
    t = title.lower()
    t = re.sub(r"\(.*?\)", "", t)   # remove "(feat. ...)", "(live)", etc.
    t = re.sub(r"[^\w\s]", "", t)   # remove punctuation
    t = re.sub(r"\s+", " ", t).strip()
    return t
