"""
services/__init__.py
======================
Anwendungs-Logik-Schicht.

Services orchestrieren Domain-Objekte und Repositories — sie sind die
"Wie funktioniert das?"-Schicht zwischen Routes und Domain.

Warum braucht es diese Schicht?
    - Routes (HTTP) sollen duenn sein: nur Request rein → Response raus.
    - Domain-Klassen sollen rein bleiben (kein I/O).
    - ABER: Eine Anfrage wie "Hol mir alle Songs eines Kuenstlers, sortiert
      nach Wahrscheinlichkeit, limitiert auf 22" ist Anwendungs-Logik.
      → Genau das gehoert in einen Service.
"""

from services.playlist_import_service import (
    ArtistImportInfo,
    ImportPreview,
    PlaylistImportService,
)
from services.playlist_save_service import PlaylistSaveService
from services.setlist_service import SetlistService

__all__ = [
    "ArtistImportInfo",
    "ImportPreview",
    "PlaylistImportService",
    "PlaylistSaveService",
    "SetlistService",
]
