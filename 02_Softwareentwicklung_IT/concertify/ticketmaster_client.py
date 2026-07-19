"""
Ticketmaster Discovery API client — fetches upcoming Hamburg concerts.

Free API key: https://developer.ticketmaster.com >> "GET YOUR API KEY"
(only email + password required, no credit card)
"""

import time
from datetime import date
import requests
from matcher import normalise

_TODAY = date.today().isoformat()

_BASE = "https://app.ticketmaster.com/discovery/v2/events.json"

_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class TicketmasterClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    def get_hamburg_concerts(self, max_pages: int = 5) -> list[dict]:
        """
        Fetch all upcoming Hamburg concerts from Ticketmaster.
        Returns list of {artist, date, venue, url}.
        """
        concerts: list[dict] = []

        for page in range(max_pages):
            print(f"  Ticketmaster page {page + 1} …", end="\r")

            params = {
                "apikey": self.api_key,
                "city": "Hamburg",
                "countryCode": "DE",
                "classificationName": "Music",
                "size": 200,
                "page": page,
                "sort": "date,asc",
                "locale": "*",
            }

            try:
                resp = self.session.get(_BASE, params=params, timeout=15)
                if resp.status_code == 401:
                    print(
                        "\n  XX Ticketmaster 401 — ungültiger API Key!\n"
                        "     Hole einen kostenlosen Key unter:\n"
                        "     https://developer.ticketmaster.com >> GET YOUR API KEY\n"
                        "     Den 'Consumer Key' in .env eintragen:\n"
                        "     TICKETMASTER_API_KEY=dein-consumer-key"
                    )
                    return []
                resp.raise_for_status()
                data = resp.json()
            except requests.HTTPError as e:
                print(f"\n  Ticketmaster HTTP-Fehler {e.response.status_code}")
                break
            except requests.RequestException as e:
                print(f"\n  Ticketmaster Verbindungsfehler: {e}")
                break

            events = data.get("_embedded", {}).get("events", [])
            if not events:
                break

            for event in events:
                c = _parse_event(event)
                if c:
                    concerts.append(c)

            # Check pagination
            page_info = data.get("page", {})
            total_pages = page_info.get("totalPages", 1)
            if page + 1 >= total_pages:
                break

            time.sleep(0.3)

        print(f"\n  >> {len(concerts)} Hamburg-Konzerte auf Ticketmaster gefunden")
        return concerts

    def get_hamburg_artists(
        self,
        followed_artists: list[dict],
        max_pages: int = 5,
    ) -> dict[str, list[dict]]:
        """
        Fetch Hamburg concerts and match against followed Spotify artists.
        Returns {artist_name: [concert, ...]}
        """
        concerts = self.get_hamburg_concerts(max_pages=max_pages)
        if not concerts:
            return {}

        followed_lookup = {normalise(a["name"]): a["name"] for a in followed_artists}

        results: dict[str, list[dict]] = {}
        for concert in concerts:
            norm = normalise(concert["artist"])
            # 1) exact match
            if norm in followed_lookup:
                original = followed_lookup[norm]
                results.setdefault(original, []).append(concert)
                continue
            # 2) event name contains artist name (e.g. "Breaking Benjamin - Tour 2026")
            for artist_norm, artist_original in followed_lookup.items():
                if artist_norm and artist_norm in norm:
                    results.setdefault(artist_original, []).append(concert)
                    break

        return results


def _parse_event(event: dict) -> dict | None:
    """Extract concert info from one Ticketmaster event object."""
    try:
        name = event.get("name", "").strip()
        if not name:
            return None

        # Date
        date_str = (
            event.get("dates", {})
                 .get("start", {})
                 .get("localDate", "")
        )

        # Venue
        venues = event.get("_embedded", {}).get("venues", [])
        venue_name = venues[0].get("name", "Hamburg") if venues else "Hamburg"

        # Only keep Hamburg-area events
        if venues:
            city = venues[0].get("city", {}).get("name", "").lower()
            if city and "hamburg" not in city:
                return None

        # URL
        url = event.get("url", "")

        # Skip past events
        if date_str and date_str < _TODAY:
            return None

        return {
            "artist": name,
            "date": date_str,
            "venue": venue_name,
            "url": url,
            "datetime": date_str,
        }

    except Exception:
        return None
