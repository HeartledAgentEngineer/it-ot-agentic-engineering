"""
services/song_state_service.py
==============================
Reine Service-Logik fuer Song-Steuerung (Ausgrauen & Drag & Drop).

Diese Funktionen arbeiten rein auf In-Memory-Werten (concert_data) und
verzichten komplett auf Datei-IO, was sie 100% isoliert unit-testbar macht.
"""


def toggle_song_excluded(concert_data: dict, artist: str, song: str, excluded: bool) -> tuple[bool, str | None]:
    """Toggelt den Ausschluss eines Songs aus der Playlist-Generierung.

    Args:
        concert_data: Geladene concert_data.json-Struktur (wird mutiert).
        artist: Name des Hauptkuenstlers.
        song: Name des Songs.
        excluded: True zum Ausschliessen, False zum Wiederaufnehmen.

    Returns:
        (ok, error). Bei ok=True wurde der Zustand persistent in der Datenstruktur gesetzt.
    """
    artist_data = concert_data.get("setlist_data", {}).get(artist)
    if not artist_data:
        return False, "unknown artist"

    if "excluded_songs" not in artist_data:
        artist_data["excluded_songs"] = []

    excluded_list = artist_data["excluded_songs"]
    if excluded:
        if song not in excluded_list:
            excluded_list.append(song)
    else:
        if song in excluded_list:
            excluded_list.remove(song)

    return True, None


def reorder_songs(concert_data: dict, artist: str, order: list[str]) -> tuple[bool, str | None]:
    """Speichert eine manuelle Drag-Reihenfolge der Songs eines Kuenstlers.

    Args:
        concert_data: Geladene concert_data.json-Struktur (wird mutiert).
        artist: Name des Hauptkuenstlers.
        order: Gewuenschte neue Reihenfolge der Songnamen.

    Returns:
        (ok, error). Bei ok=True wurde manual_order aktualisiert.
    """
    artist_data = concert_data.get("setlist_data", {}).get(artist)
    if not artist_data:
        return False, "unknown artist"

    artist_data["manual_order"] = list(order)
    return True, None
