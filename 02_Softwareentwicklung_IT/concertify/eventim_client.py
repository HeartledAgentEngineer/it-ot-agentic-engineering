"""
Eventim Hamburg concert scraper.

Strategy: Eventim.de is a Next.js app that embeds the full search result as
__NEXT_DATA__ JSON in the initial HTML response.  We parse that script tag
directly — no JavaScript execution needed, no API key required.

Falls back to the public REST API if the HTML approach returns nothing.
"""

import json
import re
import time
import requests
from bs4 import BeautifulSoup
from matcher import normalise

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

# Hamburg music search — locationIds=63, categoryId=2 (Konzerte)
_SEARCH_URL = (
    "https://www.eventim.de/eventsearch/"
    "?locationIds=63&categoryId=2&sort=DateAsc&size=48"
)

# REST API fallback (may or may not be reachable)
_API_BASE = "https://public-api.eventim.de/websearch/search/api/3.0/productGroups"


class EventimClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    def get_hamburg_concerts(self, max_pages: int = 10) -> list[dict]:
        """
        Fetch upcoming Hamburg concerts.
        Returns list of {artist, date, venue, url}.
        """
        # --- Strategy 1: __NEXT_DATA__ JSON embedded in HTML ------------ #
        concerts = self._fetch_via_next_data()
        if concerts:
            print(f"\n  >> {len(concerts)} Hamburg concerts found on Eventim")
            return concerts

        # --- Strategy 2: REST API fallback ------------------------------- #
        print("  (Eventim HTML approach empty, trying REST API…)")
        concerts = self._fetch_via_rest_api(max_pages)
        print(f"\n  >> {len(concerts)} Hamburg concerts found on Eventim")
        return concerts

    def get_hamburg_artists(
        self,
        followed_artists: list[dict],
        max_pages: int = 10,
    ) -> dict[str, list[dict]]:
        """Scrape Eventim + match against followed Spotify artists."""
        concerts = self.get_hamburg_concerts(max_pages=max_pages)
        if not concerts:
            return {}

        followed_lookup = {normalise(a["name"]): a["name"] for a in followed_artists}

        results: dict[str, list[dict]] = {}
        for concert in concerts:
            norm = normalise(concert["artist"])
            # exact match
            if norm in followed_lookup:
                original = followed_lookup[norm]
                results.setdefault(original, []).append(concert)
                continue
            # substring match ("Breaking Benjamin - Hamburg Tour")
            for artist_norm, artist_original in followed_lookup.items():
                if artist_norm and artist_norm in norm:
                    results.setdefault(artist_original, []).append(concert)
                    break

        return results

    def search_artist_hamburg(self, artist_name: str) -> list[dict]:
        """
        Searches Eventim for a specific artist in Hamburg.
        Returns list of {date, venue}.
        """
        from datetime import date as _date
        today = _date.today().isoformat()
        url = (
            "https://www.eventim.de/eventsearch/"
            f"?locationIds=63&categoryId=2&sort=DateAsc&size=20"
            f"&searchterm={requests.utils.quote(artist_name)}"
        )
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"  Eventim Suche Fehler: {e}")
            return []

        items = self._parse_next_data(resp.text)
        from matcher import normalise
        artist_norm = normalise(artist_name)
        results = []
        for c in items:
            if not c.get("date") or c["date"] < today:
                continue
            if artist_norm and artist_norm not in normalise(c.get("artist", "")):
                continue
            results.append({"date": c["date"], "venue": c.get("venue", "Hamburg")})
        return results

    def search_artist_any(self, artist_name: str, city: str = "") -> list[dict]:
        """
        Searches Eventim nationwide (no locationIds filter).
        If city is given, filters results where venue contains the city name.
        Returns list of {date, venue, city}.
        Tries HTML scrape first, falls back to REST API.
        """
        from datetime import date as _date
        today = _date.today().isoformat()
        from matcher import normalise as _norm
        artist_norm = _norm(artist_name)
        city_lower = city.lower()

        items = []

        # Strategy 1: HTML / __NEXT_DATA__ mit Pagination
        for page in range(3):  # bis zu 3 Seiten (3×48 = 144 Treffer)
            url = (
                "https://www.eventim.de/eventsearch/"
                f"?categoryId=2&sort=DateAsc&size=48&page={page}"
                f"&searchterm={requests.utils.quote(artist_name)}"
            )
            try:
                resp = self.session.get(url, timeout=15)
                resp.raise_for_status()
                page_items = self._parse_next_data(resp.text)
                if not page_items:
                    break
                items.extend(page_items)
                if len(page_items) < 48:
                    break
                time.sleep(0.3)
            except Exception as e:
                print(f"  Eventim HTML-Suche Fehler (Seite {page}): {e}")
                break

        # Strategy 2: REST API Fallback wenn HTML leer/timeout
        if not items:
            items = self._search_any_rest(artist_name)

        results = []
        for c in items:
            if not c.get("date") or c["date"] < today:
                continue
            if artist_norm and artist_norm not in _norm(c.get("artist", "")):
                continue
            venue = c.get("venue", "")
            city_field = c.get("city", "")
            # Stadtfilter: Stadt muss im Venue-Namen ODER im City-Feld stehen
            if city_lower:
                in_venue = city_lower in venue.lower()
                in_city  = city_lower in city_field.lower()
                if not in_venue and not in_city:
                    continue
            results.append({
                "date":  c["date"],
                "venue": venue,
                "city":  city_field or city or "",
                "url":   c.get("url", ""),
            })
        return results

    def _search_any_rest(self, artist_name: str) -> list[dict]:
        """REST API fallback for nationwide artist search."""
        concerts = []
        seen: set = set()
        for page in range(3):
            params = {
                "webId": "web__eventim-de",
                "searchterm": artist_name,
                "sort": "DateAsc",
                "inStock": "1",
                "genreIds": "2",
                "page": str(page),
                "size": "48",
            }
            try:
                resp = self.session.get(_API_BASE, params=params, timeout=15)
                if resp.status_code == 404:
                    break
                resp.raise_for_status()
                items = _extract_rest_events(resp.json())
                if not items:
                    break
                for c in items:
                    key = f"{normalise(c['artist'])}|{c['date']}"
                    if key not in seen:
                        seen.add(key)
                        concerts.append(c)
                if len(items) < 48:
                    break
                time.sleep(0.3)
            except Exception as e:
                print(f"  Eventim REST Fallback Fehler: {e}")
                break
        return concerts

    # ------------------------------------------------------------------ #
    # Strategy 1 — Next.js __NEXT_DATA__                                 #
    # ------------------------------------------------------------------ #

    def _fetch_via_next_data(self) -> list[dict]:
        """
        Fetch Eventim's search page, extract the embedded __NEXT_DATA__ JSON,
        and parse event data from it.
        """
        concerts: list[dict] = []
        seen: set[str] = set()

        # Fetch multiple pages by incrementing the page param
        for page in range(10):
            url = _SEARCH_URL + f"&page={page}"
            print(f"  Eventim Seite {page + 1} ...", flush=True)
            try:
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"  Eventim Fehler Seite {page + 1}: {e}", flush=True)
                break

            items = self._parse_next_data(resp.text)
            if not items:
                break

            for c in items:
                key = f"{normalise(c['artist'])}|{c['date']}"
                if key not in seen:
                    seen.add(key)
                    concerts.append(c)

            if len(items) < 20:   # fewer than a full page -> last page
                break

            time.sleep(0.5)

        return concerts

    def _parse_next_data(self, html: str) -> list[dict]:
        """Extract events from the __NEXT_DATA__ script tag."""
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if not tag or not tag.string:
            return []

        try:
            data = json.loads(tag.string)
        except json.JSONDecodeError:
            return []

        # Navigate the Next.js pageProps structure
        page_props = (
            data.get("props", {})
                .get("pageProps", {})
        )

        # Try several possible keys where product groups might live
        groups = (
            _deep_get(page_props, "searchResult", "productGroups")
            or _deep_get(page_props, "initialData", "productGroups")
            or _deep_get(page_props, "data", "productGroups")
            or _deep_get(page_props, "productGroups")
            or []
        )

        # Also try flat event lists
        if not groups:
            groups = (
                _deep_get(page_props, "searchResult", "products")
                or _deep_get(page_props, "products")
                or _deep_get(page_props, "events")
                or []
            )

        concerts: list[dict] = []
        for group in groups:
            c = _parse_group(group)
            if c:
                concerts.append(c)
        return concerts

    # ------------------------------------------------------------------ #
    # Strategy 2 — REST API                                               #
    # ------------------------------------------------------------------ #

    def _fetch_via_rest_api(self, max_pages: int) -> list[dict]:
        concerts: list[dict] = []
        seen: set[str] = set()

        for page in range(max_pages):
            print(f"  Eventim REST Seite {page + 1} ...", flush=True)
            params = {
                "webId": "web__eventim-de",
                "sort": "DateAsc",
                "inStock": "1",
                "genreIds": "2",
                "locationIds": "63",
                "page": str(page),
                "size": "48",
            }
            try:
                resp = self.session.get(_API_BASE, params=params, timeout=15)
                if resp.status_code == 404:
                    break
                resp.raise_for_status()
                raw = resp.json()
            except Exception:
                break

            items = _extract_rest_events(raw)
            if not items:
                break

            for c in items:
                key = f"{normalise(c['artist'])}|{c['date']}"
                if key not in seen:
                    seen.add(key)
                    concerts.append(c)

            if len(items) < 48:
                break
            time.sleep(0.5)

        return concerts


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _deep_get(d: dict, *keys):
    """Safely navigate nested dicts."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
        if d is None:
            return None
    return d


def _parse_group(group: dict) -> dict | None:
    """Extract concert info from one Next.js product group entry."""
    if not isinstance(group, dict):
        return None

    title = (
        group.get("name")
        or group.get("headline")
        or group.get("title")
        or group.get("artistName")
        or group.get("displayName")
        or ""
    )
    if not title:
        return None

    # Date
    date_str = ""
    for key in ("startDate", "date", "eventDate", "startTime", "minStartDate"):
        val = group.get(key, "")
        if val:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", str(val))
            if m:
                date_str = m.group(1)
                break

    # Venue / location
    venue = ""
    city_name = ""
    place = group.get("place") or group.get("venue") or group.get("location") or {}
    if isinstance(place, dict):
        venue = place.get("name") or place.get("venueName") or ""
        city_name = (
            place.get("city")
            or (place.get("address", {}) or {}).get("city", "")
            or ""
        )
        if not venue:
            venue = city_name or "Hamburg"
    elif isinstance(place, str) and place:
        venue = place

    if not city_name:
        city_name = ""

    # URL
    url = group.get("url") or group.get("ticketUrl") or group.get("link") or ""

    return {
        "artist":   title,
        "date":     date_str,
        "venue":    venue or "Hamburg",
        "city":     city_name,
        "url":      url,
        "datetime": date_str,
    }


def _extract_rest_events(data: dict) -> list[dict]:
    """Parse the legacy Eventim REST API response."""
    groups = (
        data.get("productGroups")
        or data.get("products")
        or data.get("events")
        or data.get("items")
        or []
    )
    if not isinstance(groups, list):
        return []
    return [c for g in groups if (c := _parse_group(g))]
