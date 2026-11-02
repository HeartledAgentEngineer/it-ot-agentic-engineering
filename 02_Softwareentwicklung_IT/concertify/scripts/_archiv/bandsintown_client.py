"""
Bandsintown public API — finds ALL upcoming concerts for artists.
No API key required. Aggregates Ticketmaster, Eventim, and many more.
"""

import math
import time
from datetime import datetime, timezone

import requests

# Hamburg city center
HAMBURG_LAT = 53.5753
HAMBURG_LON = 10.0153

_BASE_URL = "https://rest.bandsintown.com/artists"
_APP_ID = "concert_playlist_generator"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class BandsintownClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def get_hamburg_artists(
        self,
        artist_names: list[str],
        radius_km: int = 50,
    ) -> dict[str, list[dict]]:
        """
        For each artist, fetch ALL future events and filter those within
        radius_km of Hamburg.

        Returns {artist_name: [event, ...]}  — only artists with matches.
        """
        results: dict[str, list[dict]] = {}
        total = len(artist_names)

        for idx, name in enumerate(artist_names, 1):
            print(f"  [{idx}/{total}] Bandsintown: {name} …", end="\r")
            events = self._get_events(name)
            nearby = [e for e in events if _within_radius(e, HAMBURG_LAT, HAMBURG_LON, radius_km)]
            if nearby:
                results[name] = nearby
            time.sleep(0.15)

        print()
        return results

    def get_all_events(self, artist_names: list[str]) -> dict[str, list[dict]]:
        """
        Return ALL upcoming events for each artist (no location filter).
        Useful for debugging or showing full tour schedules.
        """
        results: dict[str, list[dict]] = {}
        total = len(artist_names)

        for idx, name in enumerate(artist_names, 1):
            print(f"  [{idx}/{total}] Bandsintown: {name} …", end="\r")
            events = self._get_events(name)
            if events:
                results[name] = events
            time.sleep(0.15)

        print()
        return results

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _get_events(self, artist_name: str) -> list[dict]:
        """Fetch upcoming events for one artist. Returns [] on any error."""
        url = f"{_BASE_URL}/{requests.utils.quote(artist_name)}/events"
        params = {"app_id": _APP_ID, "date": "upcoming"}

        try:
            resp = self.session.get(url, params=params, timeout=10)

            # 404 = artist not found on Bandsintown — not an error
            if resp.status_code == 404:
                return []

            # Some responses return {"warn": "..."} JSON instead of a list
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return [e for e in data if _is_future(e)]
                return []

            resp.raise_for_status()

        except (requests.RequestException, ValueError):
            pass

        return []


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _within_radius(event: dict, lat: float, lon: float, radius_km: int) -> bool:
    """Return True if the event venue is within radius_km of (lat, lon)."""
    venue = event.get("venue", {})
    try:
        vlat = float(venue.get("latitude", 0) or 0)
        vlon = float(venue.get("longitude", 0) or 0)
    except (TypeError, ValueError):
        return False

    if vlat == 0 and vlon == 0:
        # Fall back to city name matching when coords are missing
        city = venue.get("city", "").lower()
        return any(
            h in city
            for h in ("hamburg", "harburg", "pinneberg", "ahrensburg", "norderstedt")
        )

    return _haversine_km(lat, lon, vlat, vlon) <= radius_km


def _is_future(event: dict) -> bool:
    """Return True if the event datetime is in the future."""
    dt_str = event.get("datetime", "")
    if not dt_str:
        return True  # keep if unknown
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt > datetime.now(timezone.utc)
    except ValueError:
        return True
