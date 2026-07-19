"""
domain/concert.py
==================
Die Concert-Klasse repraesentiert ein konkretes Konzert-Ereignis
(Datum + Ort + Kuenstler).

Engineering-Konzept: "Value Object"
    Ein Objekt das durch seine Werte definiert ist (zwei Concerts sind gleich
    wenn alle Felder gleich sind). Im Gegensatz zur Entity (wie Artist) die
    eine Identitaet hat.

Brueckenwissen:
    IEC 61131-3:  Wie ein STRUCT mit DATE + STRING + STRING + ...
    C#:           Wie ein `record` — auto-generierte Equality.
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class Concert:
    """Ein einzelner Konzert-Auftritt.

    Attribute:
        artist_name:    Name des Kuenstlers (Verweis statt Objekt — vermeidet
                        zirkulaere Referenzen)
        date:           Konzert-Datum als echtes date-Objekt
                        (NICHT als String wie im JSON!)
        venue:          Konzert-Halle / Spielort, z.B. "Volksparkstadion"
        city:           Stadt, z.B. "Hamburg"
        festival:       Festival-Name oder None bei normalen Konzerten
                        Beispiele: "Rock im Park", "Wacken Open Air"
        is_support_act: True wenn dieser Kuenstler als Vorgruppe spielt
        headliner:      Bei Support-Acts: Name des Hauptkuenstlers
    """

    artist_name: str
    date: date           # WICHTIG: das ist die Python-Klasse `date`,
                         # nicht das Attribut. Beachte den import oben.
    venue: str
    city: str
    festival: str | None = None
    is_support_act: bool = False
    headliner: str | None = None

    # ─── Verhalten ──────────────────────────────────────────────────────────

    def is_upcoming(self, today: date | None = None) -> bool:
        """True wenn das Konzert heute oder spaeter ist.

        Args:
            today: Optional Vergleichsdatum (fuer Tests).
                   Default: das echte heutige Datum.

        Beispiel:
            concert = Concert(..., date=date(2026, 6, 1), ...)
            concert.is_upcoming(today=date(2026, 5, 26))  → True (Zukunft)
            concert.is_upcoming(today=date(2026, 6, 15))  → False (Vergangenheit)
        """
        # `today or date.today()` = wenn today None ist, nimm date.today().
        # `or` mit None wirkt wie ein Default-Wert.
        comparison_date = today or date.today()
        return self.date >= comparison_date

    def is_festival(self) -> bool:
        """True wenn das Konzert ein Festival-Auftritt ist."""
        return self.festival is not None

    def display_location(self) -> str:
        """Anzeige-String fuer Ort: 'Venue, Stadt' oder 'Festival, Stadt'.

        Beispiel:
            concert.display_location()  → "Volksparkstadion, Hamburg"
            festival_concert.display_location()  → "Rock im Park, Nuernberg"
        """
        if self.festival:
            return f"{self.festival}, {self.city}"
        return f"{self.venue}, {self.city}"
