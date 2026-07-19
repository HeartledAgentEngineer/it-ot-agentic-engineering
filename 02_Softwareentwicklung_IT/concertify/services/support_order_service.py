"""
services/support_order_service.py
=================================
Reine Sortier-Logik fuer Support-Acts eines Konzerts.

Die Reihenfolge der Support-Acts steckt in der geordneten Liste
concert_data["support_acts"][artist][date]. Diese Funktion validiert eine
neue Reihenfolge (gleiche Menge an Acts!) und schreibt sie zurueck.
Kein Datei-IO -- dadurch 100% unit-testbar.
"""


def reorder_support_acts(concert_data: dict, artist: str, date: str,
                         new_order: list[str]) -> tuple[bool, str | None]:
    """Sortiert die Support-Acts eines Konzerts neu.

    Args:
        concert_data: Geladene concert_data.json-Struktur (wird mutiert).
        artist: Hauptkuenstler (Key in support_acts).
        date: Konzertdatum (Key unter dem Kuenstler).
        new_order: Gewuenschte Reihenfolge der Act-Namen.

    Returns:
        (ok, error). Bei ok=True ist concert_data neu sortiert.
        Fehler-Codes: "unknown artist/date", "order mismatch".
    """
    current = (
        concert_data.get("support_acts", {})
        .get(artist, {})
        .get(date)
    )
    if current is None:
        return False, "unknown artist/date"
    if sorted(new_order) != sorted(current):
        return False, "order mismatch"
    concert_data["support_acts"][artist][date] = list(new_order)
    return True, None
