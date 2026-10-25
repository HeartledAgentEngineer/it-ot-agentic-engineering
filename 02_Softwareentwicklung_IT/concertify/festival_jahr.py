"""
festival_jahr.py
================
Leitet das Festival-Zieljahr aus dem vom Nutzer gewaehlten Zeitraum ab und
baut daraus volle Festival-Daten. Zweck: Festival-Suchen (Rock im Park &Co.)
folgen dem Zeitraum statt einer hartkodierten Jahreszahl — damit findet die
App z. B. "Rock im Park 2027", sobald der Zeitraum 2027 abdeckt.

Reine Logik, kein IO, keine Abhaengigkeiten — bewusst klein und testbar.
"""

from datetime import date

_OFFENES_ENDE = "9999"


def ziel_jahr(date_from: str, date_to: str) -> int:
    """
    Zieljahr fuer Festival-Suchen aus dem Zeitraum (ISO "YYYY-MM-DD").

    Regel:
      - Das "bis"-Jahr hat Vorrang (es markiert das Ende des Zielfensters).
      - Ist "bis" offen (9999) oder leer, zaehlt das "von"-Jahr.
      - Sind beide leer/unlesbar, gilt das aktuelle Jahr.
    """
    bis = _jahr_aus(date_to)
    if bis is not None and not date_to.strip().startswith(_OFFENES_ENDE):
        return bis
    von = _jahr_aus(date_from)
    if von is not None:
        return von
    return date.today().year


def festival_datum(md_oder_datum: str, jahr: int) -> str:
    """
    Baut ein volles ISO-Datum fuer das Zieljahr.

    Akzeptiert sowohl ein Monat-Tag-Kuerzel ("06-05") als auch ein volles
    Alt-Datum ("2026-06-05") — in beiden Faellen wird das Zieljahr gesetzt.
    """
    md = md_oder_datum.strip()
    # Volles Datum "YYYY-MM-DD" -> nur Monat-Tag uebernehmen
    if len(md) == 10 and md[4] == "-" and md[7] == "-":
        md = md[5:]
    return f"{jahr:04d}-{md}"


def jahr_aus_daten(artist_map: dict) -> int:
    """
    Zieljahr aus bereits gespeicherten Festival-Eintraegen ableiten.

    Nimmt das Jahr des ersten gefundenen Datums (``info["dates"]``);
    ist nichts vorhanden, gilt das aktuelle Jahr. Zweck: Endpunkte, die auf
    gespeicherten rip_artists arbeiten, brauchen kein hartes 2026.
    """
    for info in (artist_map or {}).values():
        for d in (info or {}).get("dates", []):
            jahr = _jahr_aus(d)
            if jahr is not None:
                return jahr
    return date.today().year


def _jahr_aus(iso: str) -> int | None:
    """Liest das Jahr aus einem ISO-Datum; None bei leer/unlesbar."""
    iso = (iso or "").strip()
    if len(iso) >= 4 and iso[:4].isdigit():
        return int(iso[:4])
    return None
