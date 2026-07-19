"""
Songkick Hamburg concert finder.

Searches each followed artist individually on Songkick and checks if they
have upcoming shows in the Hamburg area.  No API key required.
"""

import re
import time
from datetime import date
import requests
from bs4 import BeautifulSoup
from matcher import normalise

_TODAY = date.today().isoformat()  # e.g. "2026-04-03"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

_HAMBURG_KEYWORDS = {
    "hamburg", "barclays", "stadtpark", "volksparkstadion",
    "trabrennbahn", "sporthalle", "mehr! theater", "fabrik",
    "docks", "markthalle", "gruenspan", "grünspan",
    "reeperbahn", "alsterdorfer", "harburg", "laeiszhalle",
    "elbphilharmonie",
}


class SongkickClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    def get_hamburg_artists(
        self,
        followed_artists: list[dict],
        max_total_seconds: int = 80,
    ) -> dict[str, list[dict]]:
        """
        Check every followed artist individually on Songkick for Hamburg shows.
        Returns {artist_name: [concert_dict, ...]}.
        Stops after max_total_seconds to avoid blocking the caller indefinitely.
        """
        results: dict[str, list[dict]] = {}
        total = len(followed_artists)
        deadline = time.time() + max_total_seconds

        for idx, artist in enumerate(followed_artists, 1):
            if time.time() > deadline:
                print(f"  Songkick: Zeitlimit ({max_total_seconds}s) nach {idx-1}/{total} Kuenstlern", flush=True)
                break

            name = artist["name"]
            safe = name.encode("ascii", "replace").decode("ascii")
            try:
                print(f"  Songkick [{idx}/{total}] {safe} ...", flush=True)
            except Exception:
                pass

            try:
                concerts = self._get_hamburg_shows(name)
            except Exception:
                concerts = []

            if concerts:
                results[name] = concerts
                try:
                    print(f"  Songkick [{idx}/{total}] {safe} -- {len(concerts)} Hamburg show(s)!     ")
                except Exception:
                    pass

            # Polite delay
            time.sleep(0.5)

        print(f"\n  >> {len(results)} artists with Hamburg shows on Songkick")
        return results

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _get_hamburg_shows(self, artist_name: str) -> list[dict]:
        """Find artist on Songkick, then return their Hamburg events."""
        artist_id, slug = self._find_artist_id(artist_name)
        if not artist_id:
            return []
        return self._fetch_hamburg_events(artist_id, slug, artist_name)

    def search_artist_any(self, artist_name: str, city: str = "") -> list[dict]:
        """Find artist on Songkick, return all upcoming German events.
        If city is given, filter to that city. Returns list of {date, venue, city}."""
        artist_id, slug = self._find_artist_id(artist_name)
        if not artist_id:
            return []
        return self._fetch_events_any_city(artist_id, slug, artist_name, city)

    def _find_artist_id(self, name: str) -> tuple[str, str]:
        """Search Songkick and return (artist_id, slug) or ('', '')."""
        try:
            resp = self.session.get(
                "https://www.songkick.com/search",
                params={"utf8": "true", "type": "artists", "query": name},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception:
            return "", ""

        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for artist links like /artists/12345-band-name
        for a in soup.select("a[href*='/artists/']"):
            href = a.get("href", "")
            m = re.search(r"/artists/(\d+)-([^/?#]+)", href)
            if not m:
                continue
            link_text = a.get_text(strip=True)
            # Accept if names are similar
            if _similar(link_text, name):
                return m.group(1), m.group(2)

        return "", ""

    def _fetch_hamburg_events(
        self, artist_id: str, slug: str, artist_name: str
    ) -> list[dict]:
        """Fetch the artist's upcoming-events page and filter to Hamburg."""
        all_events = self._fetch_events_any_city(artist_id, slug, artist_name, city="")
        return [e for e in all_events
                if any(kw in (e.get("venue", "") + e.get("city", "")).lower()
                       for kw in _HAMBURG_KEYWORDS)]

    def _fetch_events_any_city(
        self, artist_id: str, slug: str, artist_name: str, city: str = ""
    ) -> list[dict]:
        """Fetch ALL upcoming events for this artist from Songkick.
        If city is given, filter results to that city. Returns list of {date, venue, city}."""
        url = f"https://www.songkick.com/artists/{artist_id}-{slug}/calendar"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
        except Exception:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        concerts: list[dict] = []
        city_lower = city.lower()

        for event in soup.select("li.event-listings-element, li[class*='event'], article[class*='event']"):
            location_text = event.get_text(" ", strip=True)

            # Date
            date_str = ""
            time_tag = event.select_one("time[datetime]")
            if time_tag:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", time_tag.get("datetime", ""))
                if m:
                    date_str = m.group(1)
            if not date_str:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", location_text)
                if m:
                    date_str = m.group(1)
            if not date_str or date_str < _TODAY:
                continue

            # Venue
            venue_tag = (
                event.select_one(".venue-name")
                or event.select_one("[class*='venue']")
                or event.select_one(".location")
                or event.select_one("em.secondary-detail")
            )
            venue = venue_tag.get_text(strip=True).split(",")[0].strip() if venue_tag else ""

            # City — Songkick format is usually "Venue, City, Country"
            city_found = ""
            if venue_tag:
                parts = venue_tag.get_text(strip=True).split(",")
                if len(parts) >= 2:
                    city_found = parts[1].strip()
            if not city_found:
                # Try location element
                loc_tag = event.select_one(".location, [class*='location']")
                if loc_tag:
                    city_found = loc_tag.get_text(strip=True).split(",")[0].strip()

            # Filter by city if specified
            if city_lower:
                combined = (venue + " " + city_found).lower()
                if city_lower not in combined:
                    continue

            # URL
            link = event.select_one("a[href*='/concerts/']")
            event_url = ("https://www.songkick.com" + link["href"]) if link else ""

            concerts.append({
                "artist":   artist_name,
                "date":     date_str,
                "venue":    venue or city_found or city,
                "city":     city_found,
                "url":      event_url,
                "datetime": date_str,
            })

        return concerts


# ------------------------------------------------------------------ #
# Helper                                                               #
# ------------------------------------------------------------------ #

def _similar(a: str, b: str) -> bool:
    """Return True if two artist names are close enough to match."""
    na, nb = normalise(a), normalise(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na
