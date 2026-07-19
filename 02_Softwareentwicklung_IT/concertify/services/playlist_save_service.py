"""
services/playlist_save_service.py
===================================
Service fuer das Speichern und Laden von SavedPlaylists.

Diese Schicht orchestriert das Speichern eines Playlist-Snapshots inkl.
Konzertabend-Kontext (Termin, Buehnen, Setlisten, Konfiguration).
"""

from datetime import date, datetime

from domain.saved_playlist import (
    PLAYLIST_TYPE_KONZERTABEND,
    PLAYLIST_TYPE_SETLIST_MIX,
    SavedPlaylist,
)
from repositories.saved_playlist_repo import SavedPlaylistRepository


class PlaylistSaveService:
    """Anwendungs-Logik fuer gespeicherte Playlists.

    Beispiele:
        # Setlist-Mix speichern
        service.save_setlist_mix(
            spotify_id="abc",
            name="Sommerkonzerte 2026",
            description="Best of Rock im Park + Hamburg-Konzerte",
            artist_selections={"LP": ["Numb"], "BB": ["Diary of Jane"]},
            config={"limit_per_artist": 22},
        )

        # Konzertabend speichern
        service.save_konzertabend(
            spotify_id="xyz",
            name="Rock im Park Tag 1",
            event_date=date(2026, 6, 5),
            festival="Rock im Park",
            city="Nuernberg",
            artists=["Linkin Park"],
            support_acts=["Spiritbox"],
            artist_selections={
                "Linkin Park": ["Numb", "In the End"],
                "Spiritbox": ["Holy Roller"],
            },
        )
    """

    def __init__(self, repository: SavedPlaylistRepository):
        self._repo = repository

    # ─── Speichern ───────────────────────────────────────────────────────────

    def save_setlist_mix(
        self,
        spotify_id: str,
        name: str,
        *,
        description: str = "",
        cover_url: str | None = None,
        artists: list[str] | None = None,
        artist_selections: dict[str, list[str]] | None = None,
        config: dict | None = None,
    ) -> SavedPlaylist:
        """Speichert eine Setlist-Mix-Playlist (mehrere Konzerte gesammelt)."""
        playlist = SavedPlaylist(
            spotify_id=spotify_id,
            name=name,
            playlist_type=PLAYLIST_TYPE_SETLIST_MIX,
            description=description,
            cover_url=cover_url,
            artists=list(artists or []),
            artist_selections=dict(artist_selections or {}),
            config=dict(config or {}),
        )
        self._repo.save(playlist)
        return playlist

    def save_konzertabend(
        self,
        spotify_id: str,
        name: str,
        *,
        description: str = "",
        cover_url: str | None = None,
        event_date: date | None = None,
        venue: str | None = None,
        city: str | None = None,
        festival: str | None = None,
        stages: list[str] | None = None,
        artists: list[str] | None = None,
        support_acts: list[str] | None = None,
        artist_selections: dict[str, list[str]] | None = None,
        config: dict | None = None,
    ) -> SavedPlaylist:
        """Speichert einen Konzertabend (EIN Konzert mit Buehnen, Support, etc.)."""
        playlist = SavedPlaylist(
            spotify_id=spotify_id,
            name=name,
            playlist_type=PLAYLIST_TYPE_KONZERTABEND,
            description=description,
            cover_url=cover_url,
            event_date=event_date,
            venue=venue,
            city=city,
            festival=festival,
            stages=list(stages or []),
            artists=list(artists or []),
            support_acts=list(support_acts or []),
            artist_selections=dict(artist_selections or {}),
            config=dict(config or {}),
        )
        self._repo.save(playlist)
        return playlist

    def update(self, playlist: SavedPlaylist) -> None:
        """Speichert Aenderungen einer existierenden Playlist."""
        playlist.touch()  # updated_at refreshen
        self._repo.save(playlist)

    # ─── Lesen ──────────────────────────────────────────────────────────────

    def get(self, spotify_id: str) -> SavedPlaylist | None:
        return self._repo.get(spotify_id)

    def list_all(self) -> list[SavedPlaylist]:
        return self._repo.list_all()

    def list_konzertabende(self) -> list[SavedPlaylist]:
        return self._repo.list_by_type(PLAYLIST_TYPE_KONZERTABEND)

    def list_setlist_mixes(self) -> list[SavedPlaylist]:
        return self._repo.list_by_type(PLAYLIST_TYPE_SETLIST_MIX)

    # ─── Loeschen ───────────────────────────────────────────────────────────

    def delete(self, spotify_id: str) -> bool:
        """Loescht eine Playlist. Returns True wenn vorhanden, sonst False."""
        return self._repo.delete(spotify_id)
