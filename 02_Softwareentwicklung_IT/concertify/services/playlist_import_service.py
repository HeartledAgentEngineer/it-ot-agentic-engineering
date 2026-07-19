"""
services/playlist_import_service.py
=====================================
Service fuer das Wiederherstellen einer Konzertabend-Setlist aus einer
gespeicherten Playlist.

Use-Case (Sebastians Wunsch):
    "Wenn ich aus der Playlist-Ansicht eine gespeicherte Playlist
     importiere, sollen die Konzert-Daten und Setlisten wieder
     in der App geladen werden."

Engineering-Konzept: "Read-First, Write-Later"
    Diese Schicht macht ZUERST nur "Preview" — sie zeigt was importiert
    werden WUERDE, schreibt aber noch nichts. Der eigentliche Schreibzugriff
    auf concert_data.json kommt in Slice 4.2 wenn die ArtistRepository um
    save() erweitert ist.

    Vorteil: Wir koennen die Import-Logik isoliert entwickeln und testen
    ohne Daten zu zerstoeren.
"""

from dataclasses import dataclass, field

from domain.saved_playlist import SavedPlaylist
from repositories.base import ArtistRepository
from repositories.saved_playlist_repo import SavedPlaylistRepository


# ─── Wert-Klassen fuer Import-Preview ────────────────────────────────────────

@dataclass
class ArtistImportInfo:
    """Was wuerde mit einem Kuenstler beim Import passieren."""

    name: str
    is_support_act: bool
    exists_in_concerts: bool      # ist der Kuenstler bereits in concert_data.json?
    has_setlist_data: bool        # hat er bereits Setlist-Daten?
    songs_to_restore: list[str]   # Songs aus der SavedPlaylist
    songs_missing: list[str]      # davon nicht in vorhandener Setlist

    def action_summary(self) -> str:
        """Lesbarer Status."""
        if not self.exists_in_concerts:
            return "Kuenstler wird NEU angelegt"
        if not self.has_setlist_data:
            return "Setlist-Daten werden hinzugefuegt"
        if self.songs_missing:
            return f"{len(self.songs_missing)} Songs werden ergaenzt"
        return "Bereits vollstaendig vorhanden"


@dataclass
class ImportPreview:
    """Vorschau auf einen Playlist-Import."""

    spotify_id: str
    playlist_name: str
    playlist_type: str

    # Konzertabend-Daten (nur bei Typ konzertabend)
    event_date: str | None
    festival: str | None
    venue: str | None
    city: str | None

    # Pro Kuenstler die Info
    artists: list[ArtistImportInfo] = field(default_factory=list)

    def total_artists_to_create(self) -> int:
        return sum(1 for a in self.artists if not a.exists_in_concerts)

    def total_songs_to_add(self) -> int:
        return sum(len(a.songs_missing) for a in self.artists)

    def is_fully_present(self) -> bool:
        """True wenn alles schon in concert_data.json drin ist."""
        return self.total_artists_to_create() == 0 and self.total_songs_to_add() == 0


# ─── Service ─────────────────────────────────────────────────────────────────

class PlaylistImportService:
    """Liefert Preview was beim Import einer gespeicherten Playlist passieren wuerde.

    Schreibzugriff kommt in einem spaeteren Slice (4.2) — heute nur lesen + analysieren.
    """

    def __init__(
        self,
        playlist_repo: SavedPlaylistRepository,
        artist_repo: ArtistRepository,
    ):
        self._playlist_repo = playlist_repo
        self._artist_repo = artist_repo

    def preview(self, spotify_id: str) -> ImportPreview | None:
        """Erstellt eine Import-Vorschau fuer eine gespeicherte Playlist.

        Returns:
            ImportPreview oder None wenn die Playlist nicht existiert.
        """
        playlist = self._playlist_repo.get(spotify_id)
        if playlist is None:
            return None

        artist_infos: list[ArtistImportInfo] = []

        # Support Acts zuerst (so wie auf der Buehne)
        for name in playlist.support_acts:
            artist_infos.append(self._build_artist_info(
                name=name,
                is_support=True,
                playlist=playlist,
            ))

        # Dann Headliner
        for name in playlist.artists:
            artist_infos.append(self._build_artist_info(
                name=name,
                is_support=False,
                playlist=playlist,
            ))

        return ImportPreview(
            spotify_id=playlist.spotify_id,
            playlist_name=playlist.name,
            playlist_type=playlist.playlist_type,
            event_date=playlist.event_date.isoformat() if playlist.event_date else None,
            festival=playlist.festival,
            venue=playlist.venue,
            city=playlist.city,
            artists=artist_infos,
        )

    def list_importable(self) -> list[dict]:
        """Liste aller gespeicherten Playlists, mit Import-Aufwand-Hinweis.

        Returns:
            Liste von Dicts mit Eckdaten — fuer die Playlist-Tab-UI gedacht.
        """
        result = []
        for pl in self._playlist_repo.list_all():
            preview = self.preview(pl.spotify_id)
            if preview is None:
                continue
            result.append({
                "spotify_id": pl.spotify_id,
                "name": pl.name,
                "playlist_type": pl.playlist_type,
                "event_date": pl.event_date.isoformat() if pl.event_date else None,
                "festival": pl.festival,
                "artist_count": len(pl.all_artists()),
                "song_count": pl.total_song_count(),
                "artists_to_create": preview.total_artists_to_create(),
                "songs_to_add": preview.total_songs_to_add(),
                "is_fully_present": preview.is_fully_present(),
            })
        return result

    # ─── Interner Helfer ────────────────────────────────────────────────────

    def _build_artist_info(
        self,
        name: str,
        is_support: bool,
        playlist: SavedPlaylist,
    ) -> ArtistImportInfo:
        """Baut die Import-Info fuer einen einzelnen Kuenstler."""
        artist = self._artist_repo.get(name)
        exists = artist is not None
        has_setlist = exists and artist.has_setlist_data()

        # Songs aus der SavedPlaylist
        songs_in_playlist = playlist.songs_for_artist(name)

        # Davon: welche fehlen in der existierenden Setlist?
        if has_setlist:
            existing_titles = {s.title for s in artist.setlist.songs}
            missing = [s for s in songs_in_playlist if s not in existing_titles]
        else:
            # Keine Setlist da → alle Songs sind "fehlend"
            missing = list(songs_in_playlist)

        return ArtistImportInfo(
            name=name,
            is_support_act=is_support,
            exists_in_concerts=exists,
            has_setlist_data=has_setlist,
            songs_to_restore=list(songs_in_playlist),
            songs_missing=missing,
        )
