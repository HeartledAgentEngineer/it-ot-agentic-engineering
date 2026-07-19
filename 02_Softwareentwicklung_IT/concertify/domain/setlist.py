"""
domain/setlist.py
==================
Die Setlist-Klasse buendelt alle Songs die ein Kuenstler bei seinen
Konzerten spielt — inkl. Statistiken ueber wie oft jeder Song vorkommt.

Engineering-Konzept: "Aggregate Root"
    Eine Klasse die andere Objekte zusammenhaelt (hier: Liste von Songs)
    und Regeln fuer die ganze Gruppe sicherstellt (z.B. keine Duplikate).

Brueckenwissen:
    IEC 61131-3:  Wie ein FUNCTION_BLOCK das eine ARRAY[] OF FB_Song verwaltet
                  und Methoden fuer das Hinzufuegen/Filtern hat.
    C#:           Eine Klasse die eine List<Song> enthaelt + Methoden drumherum.

Beispiel:
    setlist = Setlist(artist_name="Linkin Park")
    setlist.add_song(Song(title="Numb", play_count=83, score=1.0))
    setlist.add_song(Song(title="Faint", play_count=60, score=0.72))
    top3 = setlist.top_songs(n=3)
"""

from dataclasses import dataclass, field

from domain.song import Song


@dataclass
class Setlist:
    """Eine Setlist gehoert genau zu einem Kuenstler.

    Attribute:
        artist_name:              Name des Kuenstlers (Schluessel-Beziehung)
        songs:                    Liste aller Songs in der Setlist
        total_concerts_analyzed:  Wie viele Konzerte wurden ausgewertet (z.B. 83
                                  fuer die LP-Tour). 0 = keine echten Daten,
                                  alle Scores sind dann Schaetzungen.
        source:                   Wo kommen die Daten her: 'setlist.fm',
                                  'gemini', 'manual', 'mixed'
        set_type:                 'Tour-Name', '__festival__', '__concert__'
                                  Steuert wie die Daten beim API-Fetch
                                  gefiltert werden.
    """

    artist_name: str
    # field(default_factory=list) = leere Liste als Default (siehe Kommentar
    # in song.py — gleicher Grund: nicht `= []` schreiben)
    songs: list[Song] = field(default_factory=list)
    total_concerts_analyzed: int = 0
    source: str = ""
    set_type: str = ""

    # ─── Verhalten ──────────────────────────────────────────────────────────

    def add_song(self, song: Song) -> None:
        """Fuegt einen Song zur Setlist hinzu.

        Wirft ValueError wenn der Songtitel bereits existiert.
        Das ist eine Domain-Regel: ein Titel ist eindeutig pro Setlist.

        Beispiel (was passiert wenn man doppelt hinzufuegt):
            setlist.add_song(Song(title="Numb"))
            setlist.add_song(Song(title="Numb"))  → ValueError
        """
        if self._has_song(song.title):
            raise ValueError(
                f"Song {song.title!r} bereits in Setlist von {self.artist_name!r}"
            )
        self.songs.append(song)

    def find_song(self, title: str) -> Song | None:
        """Sucht einen Song nach Titel. Gibt None zurueck wenn nicht gefunden.

        Returns:
            Das Song-Objekt oder None.
        """
        for song in self.songs:
            if song.title == title:
                return song
        return None

    def _has_song(self, title: str) -> bool:
        """Interne Helper-Methode (Unterstrich = nicht oeffentlich gemeint).

        Konvention in Python: Methoden mit `_` am Anfang sind "privat" —
        andere Module sollten sie nicht direkt aufrufen.

        IEC-Analogie: VAR_TEMP — interne Helfer, nicht Teil der Schnittstelle.
        """
        return self.find_song(title) is not None

    def played_songs(self) -> list[Song]:
        """Nur Songs die nachweislich gespielt wurden (play_count > 0).

        Returns:
            Neue Liste, sortiert nach play_count absteigend.
            Die Original-Liste wird nicht veraendert.
        """
        # List Comprehension: kurze Form fuer "fuer jeden Song aus self.songs,
        # nimm ihn wenn play_count > 0".
        # Vergleich C# LINQ: songs.Where(s => s.play_count > 0).OrderByDescending(...)
        filtered = [s for s in self.songs if s.play_count > 0]
        # sorted(..., key=lambda) = sortieren nach einem Schluessel
        # `-s.play_count` = absteigend (negatives Vorzeichen)
        return sorted(filtered, key=lambda s: -s.play_count)

    def top_songs(self, n: int = 10) -> list[Song]:
        """Die n wahrscheinlichsten Songs (nach score sortiert).

        Args:
            n: Anzahl zurueckzugebender Songs (default 10).

        Returns:
            Liste mit max. n Songs, hoechster score zuerst.
        """
        # `[:n]` = nimm nur die ersten n Eintraege (Slice-Operator)
        return sorted(self.songs, key=lambda s: -s.score)[:n]

    def has_real_data(self) -> bool:
        """True wenn echte Setlist-Daten vorliegen (nicht nur Schaetzungen)."""
        return self.total_concerts_analyzed > 0
