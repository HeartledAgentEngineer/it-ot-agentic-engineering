"""
services/setlist_service.py
=============================
Service fuer Setlist-bezogene Anwendungs-Logik.

Engineering-Konzept: "Dependency Injection (DI)"
    Der Service bekommt sein Repository im Konstruktor (statt es selbst zu
    erzeugen). Das hat 2 Vorteile:

    1. Austauschbarkeit:
       Heute → JsonArtistRepository
       Morgen → SqliteArtistRepository
       Der Service merkt nichts davon — er sieht nur "ArtistRepository".

    2. Testbarkeit:
       Im Test koennen wir ein Mock-Repository einsetzen, das vordefinierte
       Daten zurueckgibt. So testen wir die Service-Logik ohne echte JSON.

Brueckenwissen:
    C#:           Konstruktor-Injection: `public SetlistService(IRepo repo)`
    IEC 61131-3:  Wie wenn man einem FB einen anderen FB als VAR_INPUT gibt.
"""

from domain.setlist import Setlist
from domain.song import Song
from repositories.base import ArtistRepository


class SetlistService:
    """Anwendungs-Logik fuer Setlist-Abfragen.

    Beispiel:
        repo = JsonArtistRepository(Path("concert_data.json"))
        service = SetlistService(repo)
        songs = service.get_display_songs("Linkin Park", limit=22)
    """

    def __init__(self, repository: ArtistRepository):
        """Konstruktor mit Repository als Abhaengigkeit.

        Args:
            repository: Implementierung von ArtistRepository.
                       Heute JsonArtistRepository, morgen vielleicht SQLite.
        """
        self._repo = repository

    # ─── Lese-Operationen ────────────────────────────────────────────────────

    def get_setlist(self, artist_name: str) -> Setlist | None:
        """Holt die Setlist eines Kuenstlers.

        Returns:
            Setlist-Objekt oder None wenn keine Daten vorhanden.
        """
        return self._repo.get_setlist(artist_name)

    def get_display_songs(
        self,
        artist_name: str,
        *,
        limit: int | None = None,
        only_likely: bool = False,
    ) -> list[Song]:
        """Liefert die anzuzeigenden Songs eines Kuenstlers.

        Args:
            artist_name: Wie heisst der Kuenstler.
            limit: Max. Anzahl Songs (default: alle).
            only_likely: Wenn True, nur Songs mit Score >= 0.5.

        Returns:
            Liste der Songs, sortiert: zuerst die mit echtem play_count > 0
            (absteigend nach play_count), dann die anderen (nach score).

        Beispiel:
            # alle gespielten LP-Songs
            songs = service.get_display_songs("Linkin Park")

            # nur die 10 wahrscheinlichsten
            songs = service.get_display_songs("Linkin Park", limit=10, only_likely=True)
        """
        # Stern (*) im Argument-Header: alle folgenden Args MUESSEN als
        # keyword-args uebergeben werden (limit=10), nicht als Position.
        # Das macht den Aufruf lesbarer.

        setlist = self._repo.get_setlist(artist_name)
        if setlist is None:
            return []

        # Sortierung in zwei Stufen:
        # 1. Echte gespielte Songs (play_count > 0) absteigend nach play_count
        # 2. Andere Songs (Schaetzungen) absteigend nach score
        played = sorted(
            [s for s in setlist.songs if s.play_count > 0],
            key=lambda s: -s.play_count,
        )
        not_played = sorted(
            [s for s in setlist.songs if s.play_count == 0],
            key=lambda s: -s.score,
        )
        all_sorted = played + not_played

        if only_likely:
            all_sorted = [s for s in all_sorted if s.is_likely_played()]

        if limit is not None:
            all_sorted = all_sorted[:limit]

        return all_sorted

    def setlist_summary(self, artist_name: str) -> dict | None:
        """Kompakte Zusammenfassung fuer die UI.

        Returns:
            Dict mit Eckdaten oder None wenn keine Setlist da.
            Felder: total_songs, played_songs, total_concerts, set_type
        """
        setlist = self._repo.get_setlist(artist_name)
        if setlist is None:
            return None

        return {
            "artist_name": setlist.artist_name,
            "total_songs": len(setlist.songs),
            "played_songs": len(setlist.played_songs()),
            "total_concerts": setlist.total_concerts_analyzed,
            "set_type": setlist.set_type,
            "has_real_data": setlist.has_real_data(),
        }
