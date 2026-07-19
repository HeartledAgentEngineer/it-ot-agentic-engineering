"""
repositories/json_repo.py
===========================
Konkrete Implementation: liest und schreibt concert_data.json.

Engineering-Konzept: "Mapper"
    Diese Klasse uebersetzt zwischen JSON-Dicts (rohe Daten) und
    Domain-Klassen (Artist, Setlist, Song, Concert).

Brueckenwissen:
    IEC 61131-3:  Wie ein FB der von einer SPS-Datenbank Werte liest und
                  in seine internen STRUCTs sortiert.
    C#:           Wie ein DTO-Mapper mit AutoMapper.

Warum eine eigene Klasse?
    Der Mapping-Code soll an EINER Stelle stehen. Wenn die JSON-Struktur
    sich aendert, aendern wir nur hier — der Rest der Anwendung merkt nichts.
"""

import json
from datetime import date
from pathlib import Path
from threading import Lock

from domain.artist import Artist
from domain.concert import Concert
from domain.setlist import Setlist
from domain.song import Song
from repositories.base import ArtistRepository


class JsonArtistRepository(ArtistRepository):
    """JSON-Datei-basiertes Repository fuer Artists.

    Liest concert_data.json beim ersten Zugriff (lazy load) und haelt
    die Daten im Speicher. Schreibt atomar zurueck wenn save() aufgerufen wird.

    Thread-Safety:
        Eine `Lock` (= Mutex in C/C# Sprache) schuetzt vor Race Conditions
        wenn mehrere Flask-Requests gleichzeitig zugreifen.
    """

    def __init__(self, data_file: Path):
        """
        Args:
            data_file: Pfad zur concert_data.json
        """
        self._data_file = data_file
        self._cache: dict | None = None
        self._lock = Lock()

    # ─── Oeffentliche API (von ArtistRepository vorgegeben) ────────────────

    def get(self, name: str) -> Artist | None:
        data = self._load()
        if not self._artist_exists(data, name):
            return None
        return self._to_artist(data, name)

    def list_names(self) -> list[str]:
        data = self._load()
        # Alle Namen aus den drei Bereichen sammeln + Duplikate entfernen
        # `set()` = Datenstruktur ohne Duplikate (wie HashSet in C#).
        all_names: set[str] = set()
        all_names.update(data.get("hamburg_artists", {}).keys())
        all_names.update(data.get("rip_artists", {}).keys())
        all_names.update(data.get("setlist_data", {}).keys())
        return sorted(all_names)

    def get_setlist(self, name: str) -> Setlist | None:
        data = self._load()
        sd = data.get("setlist_data", {}).get(name)
        if not sd:
            return None
        return self._to_setlist(name, sd)

    # ─── Interne Mapping-Methoden (Unterstrich = privat gemeint) ────────────

    def _load(self) -> dict:
        """Liest die JSON-Datei (mit Cache).

        Beim ersten Aufruf wird die Datei eingelesen. Danach wird der Cache
        verwendet. Mit _invalidate_cache() kann man den Cache loeschen.
        """
        with self._lock:
            if self._cache is None:
                if self._data_file.exists():
                    text = self._data_file.read_text(encoding="utf-8")
                    self._cache = json.loads(text)
                else:
                    self._cache = {}
            return self._cache

    def _invalidate_cache(self) -> None:
        """Naechster _load() liest die Datei frisch."""
        with self._lock:
            self._cache = None

    def _artist_exists(self, data: dict, name: str) -> bool:
        """True wenn der Artist in mindestens einem Bereich vorkommt."""
        return (
            name in data.get("hamburg_artists", {})
            or name in data.get("rip_artists", {})
            or name in data.get("setlist_data", {})
        )

    def _to_artist(self, data: dict, name: str) -> Artist:
        """Baut ein Artist-Objekt aus den drei JSON-Bereichen.

        - hamburg_artists[name]  → Concerts mit Festival=None
        - rip_artists[name]      → Concerts mit Festival="Rock im Park" (etc.)
        - setlist_data[name]     → Setlist mit Songs
        """
        concerts = self._collect_concerts(data, name)

        sd = data.get("setlist_data", {}).get(name)
        setlist = self._to_setlist(name, sd) if sd else None

        return Artist(
            name=name,
            concerts=concerts,
            setlist=setlist,
            # is_followed wird heute nicht in der JSON gespeichert —
            # spaeter koennen wir das ergaenzen
            is_followed=False,
        )

    def _collect_concerts(self, data: dict, name: str) -> list[Concert]:
        """Sammelt alle Konzerte fuer den Kuenstler aus den zwei Bereichen."""
        concerts: list[Concert] = []

        # Hamburg-Konzerte
        ha = data.get("hamburg_artists", {}).get(name, {})
        for date_str in ha.get("dates", []):
            venue = (ha.get("venues") or {}).get(date_str) or ha.get("venue", "")
            city = (ha.get("cities") or {}).get(date_str) or ha.get("city", "Hamburg")
            concerts.append(Concert(
                artist_name=name,
                date=self._parse_date(date_str),
                venue=venue,
                city=city,
            ))

        # Festival-Konzerte (Rock im Park etc.)
        ra = data.get("rip_artists", {}).get(name, {})
        for date_str in ra.get("dates", []):
            festival_name = ra.get("festival", "")
            venue = ra.get("venue", festival_name)
            city = (ra.get("cities") or {}).get(date_str, "")
            concerts.append(Concert(
                artist_name=name,
                date=self._parse_date(date_str),
                venue=venue,
                city=city,
                festival=festival_name or None,
            ))

        return concerts

    def _to_setlist(self, artist_name: str, sd: dict) -> Setlist:
        """Baut ein Setlist-Objekt aus dem setlist_data-Block."""
        titles = sd.get("setlist_titles", [])
        play_counts = sd.get("play_counts", {})
        scores = sd.get("scores", {})
        positions_hist = sd.get("positions_hist", {})
        spotify_uris = sd.get("spotify_uris", {})
        badges = sd.get("badges", {})

        songs: list[Song] = []
        for title in titles:
            # JSON hat Positionen als String-Keys ("1", "2", ...) —
            # wir konvertieren zu Integer fuer Python.
            raw_hist = positions_hist.get(title, {})
            hist_int: dict[int, int] = {
                int(pos): count for pos, count in raw_hist.items()
            }

            songs.append(Song(
                title=title,
                spotify_uri=spotify_uris.get(title) or None,
                score=float(scores.get(title, 0.0)),
                play_count=int(play_counts.get(title, 0)),
                positions_hist=hist_int,
                badge=badges.get(title, ""),
            ))

        return Setlist(
            artist_name=artist_name,
            songs=songs,
            total_concerts_analyzed=int(sd.get("total_concerts_analyzed", 0)),
            source="",  # ist in der heutigen JSON nicht gespeichert
            set_type=sd.get("set_type", ""),
        )

    @staticmethod
    def _parse_date(date_str: str) -> date:
        """ISO-Datum 'YYYY-MM-DD' → date-Objekt.

        @staticmethod = Methode die nicht auf `self` zugreift.
        Nuetzlich fuer Helfer die zur Klasse gehoeren, aber keine
        Instanz-Daten brauchen. (Wie `static` in C# / C.)
        """
        return date.fromisoformat(date_str)
