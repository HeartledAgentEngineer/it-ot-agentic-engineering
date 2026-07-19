"""
domain/__init__.py
====================
Marker-Datei: dieses Verzeichnis ist ein Python-Modul.
Aehnlich einer Header-Datei in C die andere Header verfuegbar macht.

Hier exportieren wir die wichtigsten Klassen, sodass andere Module
einfach schreiben koennen:

    from domain import Artist, Concert, Setlist, Song

statt dem laengeren:

    from domain.artist import Artist
    from domain.concert import Concert
    from domain.setlist import Setlist
    from domain.song import Song

Engineering-Konzept: "Public API eines Moduls"
    Welche Klassen darf der Rest der Anwendung benutzen?
    Was ist interne Implementierung?
    → Hier wird das festgelegt.
"""

from domain.artist import Artist
from domain.concert import Concert
from domain.saved_playlist import (
    PLAYLIST_TYPE_KONZERTABEND,
    PLAYLIST_TYPE_SETLIST_MIX,
    SavedPlaylist,
)
from domain.setlist import Setlist
from domain.song import Song

# `__all__` ist Python-Konvention fuer "das hier sind die oeffentlichen Namen".
# Wenn jemand `from domain import *` schreibt, bekommt er nur diese Klassen.
# Ohne __all__ wuerde Python auch interne Hilfsobjekte exportieren.
__all__ = [
    "Artist",
    "Concert",
    "PLAYLIST_TYPE_KONZERTABEND",
    "PLAYLIST_TYPE_SETLIST_MIX",
    "SavedPlaylist",
    "Setlist",
    "Song",
]
