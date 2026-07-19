"""
repositories/saved_playlist_repo.py
=====================================
Persistenz fuer SavedPlaylist-Objekte.

Heute: JSON-Datei `saved_playlists.json` (eigene Datei, getrennt von
       concert_data.json).
Morgen: SQLite-Tabelle `saved_playlists` (siehe alignment.md).

Engineering-Konzept: "Repository per Aggregate Root"
    Jede grosse Domain-Klasse (Artist, SavedPlaylist) bekommt ihr eigenes
    Repository. So bleibt jede Persistenz-Klasse klein und fokussiert.
"""

import json
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path
from threading import Lock

from domain.saved_playlist import SavedPlaylist


# ─── Abstrakte Basis ─────────────────────────────────────────────────────────

class SavedPlaylistRepository(ABC):
    """Interface fuer alle SavedPlaylist-Repos (JSON, SQLite, ...)."""

    @abstractmethod
    def get(self, spotify_id: str) -> SavedPlaylist | None: ...

    @abstractmethod
    def list_all(self) -> list[SavedPlaylist]: ...

    @abstractmethod
    def list_by_type(self, playlist_type: str) -> list[SavedPlaylist]: ...

    @abstractmethod
    def save(self, playlist: SavedPlaylist) -> None: ...

    @abstractmethod
    def delete(self, spotify_id: str) -> bool:
        """Loescht eine Playlist. Returns True wenn vorhanden, sonst False."""
        ...


# ─── JSON-Implementation ─────────────────────────────────────────────────────

class JsonSavedPlaylistRepository(SavedPlaylistRepository):
    """Speichert SavedPlaylists in einer JSON-Datei.

    Format:
        {
          "playlists": [
            {"spotify_id": "abc", "name": "...", "playlist_type": "...", ...},
            ...
          ]
        }

    Atomares Schreiben:
        Wir schreiben erst in eine .tmp-Datei und ersetzen dann die Zieldatei.
        So bleibt die Datei NIE in einem halb-geschriebenen Zustand
        (auch nicht wenn das Programm zwischendurch abstuerzt).
    """

    def __init__(self, data_file: Path):
        self._data_file = data_file
        self._lock = Lock()
        self._cache: dict[str, SavedPlaylist] | None = None

    # ─── Oeffentliche API ───────────────────────────────────────────────────

    def get(self, spotify_id: str) -> SavedPlaylist | None:
        return self._load().get(spotify_id)

    def list_all(self) -> list[SavedPlaylist]:
        # Sortierung: zuletzt geaendert zuerst
        return sorted(
            self._load().values(),
            key=lambda pl: pl.updated_at,
            reverse=True,
        )

    def list_by_type(self, playlist_type: str) -> list[SavedPlaylist]:
        return [pl for pl in self.list_all() if pl.playlist_type == playlist_type]

    def save(self, playlist: SavedPlaylist) -> None:
        with self._lock:
            data = self._load_unlocked()
            data[playlist.spotify_id] = playlist
            self._cache = data
            self._write_to_disk(data)

    def delete(self, spotify_id: str) -> bool:
        with self._lock:
            data = self._load_unlocked()
            if spotify_id not in data:
                return False
            del data[spotify_id]
            self._cache = data
            self._write_to_disk(data)
            return True

    # ─── Interne Helfer ─────────────────────────────────────────────────────

    def _load(self) -> dict[str, SavedPlaylist]:
        """Thread-safer Cache-Loader."""
        with self._lock:
            return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, SavedPlaylist]:
        """Loader OHNE Lock — nur aufrufen wenn Lock schon gehalten wird."""
        if self._cache is not None:
            return self._cache

        if not self._data_file.exists():
            self._cache = {}
            return self._cache

        text = self._data_file.read_text(encoding="utf-8")
        raw = json.loads(text) if text.strip() else {"playlists": []}

        playlists: dict[str, SavedPlaylist] = {}
        for entry in raw.get("playlists", []):
            pl = self._from_dict(entry)
            playlists[pl.spotify_id] = pl

        self._cache = playlists
        return self._cache

    def _write_to_disk(self, data: dict[str, SavedPlaylist]) -> None:
        """Atomares Schreiben: erst .tmp, dann rename."""
        raw = {"playlists": [self._to_dict(pl) for pl in data.values()]}
        tmp = self._data_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # os.replace() ist atomar auf jedem Betriebssystem
        import os
        os.replace(tmp, self._data_file)

    # ─── Mapping zwischen Dict und Klasse ───────────────────────────────────
    # Hier "uebersetzen" wir zwischen JSON-Form und SavedPlaylist-Objekt.

    @staticmethod
    def _to_dict(pl: SavedPlaylist) -> dict:
        """Wandelt SavedPlaylist → JSON-taugliches Dict.

        Datetime und date werden zu ISO-Strings.
        """
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
        }

    @staticmethod
    def _from_dict(d: dict) -> SavedPlaylist:
        """Wandelt JSON-Dict → SavedPlaylist-Objekt.

        ISO-Strings werden zu datetime/date.
        """
        return SavedPlaylist(
            spotify_id=d["spotify_id"],
            name=d["name"],
            playlist_type=d["playlist_type"],
            description=d.get("description", ""),
            cover_url=d.get("cover_url"),
            created_at=datetime.fromisoformat(d["created_at"]) if d.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(d["updated_at"]) if d.get("updated_at") else datetime.now(),
            event_date=date.fromisoformat(d["event_date"]) if d.get("event_date") else None,
            venue=d.get("venue"),
            city=d.get("city"),
            festival=d.get("festival"),
            stages=list(d.get("stages", [])),
            artists=list(d.get("artists", [])),
            support_acts=list(d.get("support_acts", [])),
            artist_selections=dict(d.get("artist_selections", {})),
            config=dict(d.get("config", {})),
        )
