"""
repositories/__init__.py
==========================
Daten-Zugriffsschicht. Vermittelt zwischen Domain-Klassen und Persistenz.

Heute: JSON-Datei. Morgen: SQLite. Uebermorgen: Cloud-DB.
Der Service-Code merkt davon nichts — Dank Repository Pattern.
"""

from repositories.base import ArtistRepository
from repositories.json_repo import JsonArtistRepository
from repositories.saved_playlist_repo import (
    JsonSavedPlaylistRepository,
    SavedPlaylistRepository,
)

__all__ = [
    "ArtistRepository",
    "JsonArtistRepository",
    "JsonSavedPlaylistRepository",
    "SavedPlaylistRepository",
]
