"""
domain/artist.py
=================
Die Artist-Klasse ist die zentrale Entitaet — alles haengt an einem Kuenstler.

Engineering-Konzept: "Entity" / "Aggregate Root"
    Eine Klasse mit Identitaet (eindeutiger Name) die andere Objekte (Concerts,
    Setlist) zusammenhaelt. Die "Wurzel" eines Datenbaums.

Brueckenwissen:
    IEC 61131-3:  Ein uebergeordneter FUNCTION_BLOCK der Sub-FBs enthaelt:
                  FB_Artist enthaelt ARRAY[] OF FB_Concert + FB_Setlist
    C#:           Klasse mit Properties die andere Klassen aggregieren.
"""

from dataclasses import dataclass, field

from domain.concert import Concert
from domain.setlist import Setlist


@dataclass
class Artist:
    """Ein gefolgter Kuenstler mit Konzerten und Setlist.

    Attribute:
        name:        Anzeigename (eindeutig, gleichzeitig "Primary Key")
        spotify_id:  Spotify-Artist-ID, z.B. "6XyY86QOPPRYVxNYzbXMnZ"
                     None wenn noch nicht aufgeloest.
        is_followed: True wenn der Nutzer dem Kuenstler auf Spotify folgt.
        concerts:    Liste aller bekannten Konzerte (Hamburg + Festivals).
        setlist:     Setlist-Objekt mit den live gespielten Songs.
                     None wenn noch keine Setlist-Daten geholt wurden.
    """

    name: str
    spotify_id: str | None = None
    is_followed: bool = False
    concerts: list[Concert] = field(default_factory=list)
    # `Setlist | None` = optional. Wird bei der ersten Setlist-Abfrage gesetzt.
    setlist: Setlist | None = None

    # ─── Verhalten ──────────────────────────────────────────────────────────

    def has_upcoming_concerts(self) -> bool:
        """True wenn mindestens ein Konzert heute oder in der Zukunft ist."""
        # `any(...)` = True wenn mindestens ein Element die Bedingung erfuellt.
        # IEC-Analogie: wie eine OR-Verknuepfung ueber alle Elemente.
        return any(concert.is_upcoming() for concert in self.concerts)

    def upcoming_concerts(self) -> list[Concert]:
        """Nur die zukuenftigen Konzerte, sortiert nach Datum."""
        return sorted(
            [c for c in self.concerts if c.is_upcoming()],
            key=lambda c: c.date,
        )

    def has_setlist_data(self) -> bool:
        """True wenn echte Setlist-Daten geladen sind."""
        return self.setlist is not None and self.setlist.has_real_data()

    def festival_concerts(self) -> list[Concert]:
        """Nur die Festival-Auftritte."""
        return [c for c in self.concerts if c.is_festival()]

    def regular_concerts(self) -> list[Concert]:
        """Nur die Nicht-Festival-Konzerte."""
        return [c for c in self.concerts if not c.is_festival()]
