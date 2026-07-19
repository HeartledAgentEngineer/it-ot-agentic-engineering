"""
domain/saved_playlist.py
==========================
Klasse fuer dauerhaft gespeicherte Playlists — inklusive Konzertabend-Kontext.

Engineering-Konzept: "Snapshot / Memento"
    Eine SavedPlaylist ist ein Snapshot zu einem bestimmten Zeitpunkt:
    welche Kuenstler, welche Songs in welcher Reihenfolge, welche Konfiguration.
    So koennen wir spaeter den Zustand wiederherstellen (Slice 4).

Warum eine separate Klasse?
    Eine Spotify-Playlist enthaelt nur Track-URIs — kein Wissen ueber:
    - welcher Termin gehoert dazu
    - welche Buehnen / Festivals
    - welche Setlist-Konfiguration wurde verwendet
    - welche Support-Acts
    Diese Meta-Daten gehoeren in unsere App, nicht zu Spotify.

Brueckenwissen:
    IEC 61131-3:  Wie ein DATEN-PERSISTENT struct — bleibt ueber Reboots erhalten.
    C#:           Wie ein DTO / Entity in einer Datenbank.
"""

from dataclasses import dataclass, field
from datetime import date, datetime


# ─── Playlist-Typen als Konstanten ──────────────────────────────────────────
# Statt "magic strings" verwenden wir Konstanten. Tippfehler werden vom
# Linter erkannt, und der Wertebereich ist dokumentiert.

PLAYLIST_TYPE_SETLIST_MIX = "setlist_mix"   # Sammlung mehrerer Konzerte
PLAYLIST_TYPE_KONZERTABEND = "konzertabend"  # EIN konkretes Konzert
PLAYLIST_TYPES_VALID = {PLAYLIST_TYPE_SETLIST_MIX, PLAYLIST_TYPE_KONZERTABEND}


@dataclass
class SavedPlaylist:
    """Eine gespeicherte Playlist mit allen Meta-Daten.

    Attribute (gespeichert):
        spotify_id:        Spotify-Playlist-ID (Primary Key in unserem Repo)
        name:              Anzeigename (z.B. "Rock im Park 2026 - Tag 1")
        description:       Spotify-Beschreibung (User-sichtbar)
        playlist_type:     'setlist_mix' oder 'konzertabend' (siehe Konstanten)
        created_at:        Erstellungs-Zeitpunkt
        updated_at:        Letzte Aenderung
        cover_url:         URL des Cover-Bilds, None wenn Spotify-Default

    Konzertabend-Spezifisch (alle optional, nur bei type='konzertabend' gefuellt):
        event_date:        Datum des Konzerts
        venue:             Venue / Festival-Gelaende
        city:              Stadt
        festival:          Festival-Name (None bei normalem Konzert)
        stages:            Liste der Buehnen (bei Multi-Stage-Festivals)

    Pro Kuenstler:
        artists:           Reihenfolge der Hauptkuenstler (= Reihenfolge der Songs)
        support_acts:      Vorgruppen (Songs kommen vor den Hauptkuenstlern)
        artist_selections: Pro Kuenstler die ausgewaehlten Song-Titel
                           z.B. {"Linkin Park": ["Numb", "In the End", ...]}

    Wiederherstellungs-Daten:
        config:            Konfiguration zur Wiederherstellung
                           z.B. {"limit_per_artist": 22, "only_likely": false}
    """

    # Pflichtfelder
    spotify_id: str
    name: str
    playlist_type: str

    # Optionale Felder mit Defaults
    description: str = ""
    cover_url: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Konzertabend-Kontext (optional)
    event_date: date | None = None
    venue: str | None = None
    city: str | None = None
    festival: str | None = None
    stages: list[str] = field(default_factory=list)

    # Kuenstler-Daten
    artists: list[str] = field(default_factory=list)
    support_acts: list[str] = field(default_factory=list)
    artist_selections: dict[str, list[str]] = field(default_factory=dict)

    # Konfigurations-Daten zur Wiederherstellung
    config: dict = field(default_factory=dict)

    # ─── Validierung beim Anlegen ───────────────────────────────────────────
    # __post_init__ wird automatisch nach __init__ aufgerufen (dataclass-Feature).
    # Hier pruefen wir Domain-Invarianten.

    def __post_init__(self):
        """Validiert die Attribute beim Anlegen."""
        if self.playlist_type not in PLAYLIST_TYPES_VALID:
            raise ValueError(
                f"playlist_type muss eines von {PLAYLIST_TYPES_VALID} sein, "
                f"war: {self.playlist_type!r}"
            )
        if not self.spotify_id:
            raise ValueError("spotify_id darf nicht leer sein")
        if not self.name:
            raise ValueError("name darf nicht leer sein")

    # ─── Verhalten ──────────────────────────────────────────────────────────

    def is_konzertabend(self) -> bool:
        """True wenn diese Playlist fuer EIN konkretes Konzert ist."""
        return self.playlist_type == PLAYLIST_TYPE_KONZERTABEND

    def is_setlist_mix(self) -> bool:
        """True wenn diese Playlist eine Sammlung mehrerer Konzerte ist."""
        return self.playlist_type == PLAYLIST_TYPE_SETLIST_MIX

    def all_artists(self) -> list[str]:
        """Alle Kuenstler (Hauptacts + Support Acts) als eine Liste.

        Returns:
            Liste der Namen, Support Acts ZUERST (so wie sie auf der Buehne
            stehen — Vorgruppe vor Headliner).
        """
        return list(self.support_acts) + list(self.artists)

    def total_song_count(self) -> int:
        """Gesamtzahl aller ausgewaehlten Songs ueber alle Kuenstler."""
        return sum(len(songs) for songs in self.artist_selections.values())

    def has_artist(self, artist_name: str) -> bool:
        """True wenn dieser Kuenstler in der Playlist ist (Haupt oder Support)."""
        return artist_name in self.all_artists()

    def songs_for_artist(self, artist_name: str) -> list[str]:
        """Liefert die ausgewaehlten Songs fuer einen Kuenstler.

        Returns:
            Liste der Song-Titel in Reihenfolge, oder leere Liste.
        """
        return list(self.artist_selections.get(artist_name, []))

    def touch(self) -> None:
        """Aktualisiert `updated_at` auf jetzt.

        Engineering-Konzept: "Audit Field"
            Wir tracken wann das Objekt zuletzt geaendert wurde — wichtig
            fuer Sync, Cache-Invalidation, Sortierung in der UI.
        """
        self.updated_at = datetime.now()

    def add_artist(self, artist_name: str, is_support: bool = False) -> None:
        """Fuegt einen Kuenstler zur Playlist hinzu.

        Args:
            artist_name: Name des Kuenstlers.
            is_support: True wenn Vorgruppe, False wenn Hauptact.

        Raises:
            ValueError wenn der Kuenstler bereits drin ist.
        """
        if self.has_artist(artist_name):
            raise ValueError(f"Kuenstler {artist_name!r} bereits in Playlist")
        if is_support:
            self.support_acts.append(artist_name)
        else:
            self.artists.append(artist_name)
        # Selections-Dict initialisieren (leer)
        self.artist_selections.setdefault(artist_name, [])
        self.touch()

    def set_songs_for_artist(self, artist_name: str, song_titles: list[str]) -> None:
        """Setzt die ausgewaehlten Songs eines Kuenstlers (in Reihenfolge)."""
        if not self.has_artist(artist_name):
            raise ValueError(f"Kuenstler {artist_name!r} nicht in Playlist")
        self.artist_selections[artist_name] = list(song_titles)
        self.touch()
