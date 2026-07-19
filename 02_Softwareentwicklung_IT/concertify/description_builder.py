"""
Build a Spotify playlist description (max 300 chars).

Format:
  RiP: Artist A, B | HH: Artist C (12.07 Stadtpark), Artist D (03.08 Barclays)
"""

from datetime import datetime


def build_description(
    hamburg_events: dict[str, list[dict]],
    rip_artists: list[str],
) -> str:
    """
    hamburg_events: {artist_name: [bandsintown_event, ...]}
    rip_artists:    list of matched artist names
    """
    parts: list[str] = []

    if rip_artists:
        parts.append("RiP 2026: " + ", ".join(sorted(rip_artists)))

    if hamburg_events:
        entries: list[str] = []
        for name in sorted(hamburg_events):
            events = sorted(hamburg_events[name], key=lambda e: e.get("date", ""))
            ev = events[0]
            date_str = ev.get("date", "")
            venue = ev.get("venue", "")
            city = ""

            location = venue or city
            if date_str and location:
                entries.append(f"{name} ({date_str} {location})")
            elif date_str:
                entries.append(f"{name} ({date_str})")
            elif location:
                entries.append(f"{name} ({location})")
            else:
                entries.append(name)

        parts.append("HH: " + ", ".join(entries))

    if not parts:
        return "Concert playlist — no upcoming shows found"

    description = " | ".join(parts)

    if len(description) <= 300:
        return description

    # Over limit — shorten venue names to city only, then truncate
    if hamburg_events:
        entries = []
        for name in sorted(hamburg_events):
            events = sorted(hamburg_events[name], key=lambda e: e.get("datetime", ""))
            ev = events[0]
            date_str = _format_date(ev.get("datetime", ""))
            venue = ev.get("venue", "")
            city = venue if isinstance(venue, str) else venue.get("city", "")
            if date_str and city:
                entries.append(f"{name} ({date_str} {city})")
            elif date_str:
                entries.append(f"{name} ({date_str})")
            else:
                entries.append(name)
        parts[-1] = "HH: " + ", ".join(entries)

    description = " | ".join(parts)
    if len(description) > 300:
        description = description[:297] + "…"

    return description


def _format_date(dt_str: str) -> str:
    """Convert ISO datetime string to DD.MM.YYYY."""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return dt_str[:10]  # fallback: YYYY-MM-DD
