"""
repositories/base.py
======================
Abstrakte Basisklasse fuer alle ArtistRepository-Implementierungen.

Engineering-Konzept: "Interface" / "Abstract Base Class (ABC)"
    Definiert WAS eine Klasse koennen muss, aber nicht WIE.
    Erst die konkreten Unterklassen (JsonArtistRepository, SqliteRepository, ...)
    implementieren das WIE.

Brueckenwissen:
    C#:           Wie `interface IArtistRepository { Artist Get(string name); ... }`
    IEC 61131-3:  Wie INTERFACE IArtistRepository — Methoden ohne Body.
    C:            Aehnlich einer Header-Datei mit Funktions-Prototypen,
                  aber an Klassen gebunden.

Warum so?
    Der Service-Code arbeitet gegen das Interface, nicht gegen die konkrete
    Klasse. Wir koennen also zur Laufzeit JSON oder SQLite einsetzen
    OHNE den Service-Code zu aendern. Das ist "Dependency Inversion".

    Beispiel:
        # Heute mit JSON
        repo = JsonArtistRepository(Path("concert_data.json"))
        service = SetlistService(repo)

        # Morgen mit SQLite — der Service merkt NICHTS:
        repo = SqliteArtistRepository("data.db")
        service = SetlistService(repo)
"""

from abc import ABC, abstractmethod

from domain.artist import Artist
from domain.setlist import Setlist


class ArtistRepository(ABC):
    """Abstrakte Schnittstelle fuer Artist-Persistenz.

    Wer von dieser Klasse erbt MUSS alle @abstractmethod-Methoden
    implementieren — sonst gibt es einen Fehler beim Instanziieren.
    """

    @abstractmethod
    def get(self, name: str) -> Artist | None:
        """Laedt einen Artist nach Name.

        Args:
            name: Eindeutiger Kuenstler-Name (Primary Key).

        Returns:
            Artist-Objekt mit Concerts + Setlist, oder None wenn nicht gefunden.
        """
        ...

    @abstractmethod
    def list_names(self) -> list[str]:
        """Liste aller bekannten Kuenstler-Namen.

        Returns:
            Sortierte Liste der Namen (sortiert fuer deterministische Outputs).
        """
        ...

    @abstractmethod
    def get_setlist(self, name: str) -> Setlist | None:
        """Laedt nur die Setlist eines Kuenstlers (ohne Concert-Daten).

        Spart Zeit wenn man nur Setlist-Infos braucht.

        Returns:
            Setlist-Objekt oder None wenn der Kuenstler keine Setlist hat.
        """
        ...
