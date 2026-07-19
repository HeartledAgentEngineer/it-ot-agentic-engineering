"""
Serper.dev — Google Search API concert finder.
Companion to TavilyConcertClient. Runs as second web-search source.
Free tier: 2500 searches/month.  No Tavily credits needed.
API docs: https://serper.dev
"""
import requests
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as _FutTimeout

# Reuse date/venue extraction from Tavily
from tavily_concert_client import (
    _extract_date_near_hamburg,
    _extract_date_near_city,
    _extract_venue,
)

_TODAY  = date.today().isoformat()
_SERPER = "https://google.serper.dev/search"


class SerperConcertClient:
    def __init__(self, api_key: str, max_workers: int = 8):
        self.api_key    = api_key
        self.max_workers = max_workers

    def get_hamburg_artists(
        self,
        followed_artists: list[dict],
        already_found: set[str] | None = None,
        max_artists: int = 300,
    ) -> dict[str, list[dict]]:
        """
        Search Hamburg concerts for followed artists via Google/Serper.
        Only checks artists NOT already found by other sources.
        Returns {artist_name: [{"datetime": "YYYY-MM-DD", "venue": "..."}]}
        """
        already_found = already_found or set()
        to_search = [
            a for a in followed_artists
            if a["name"] not in already_found
        ][:max_artists]

        if not to_search:
            return {}

        print(f"  Serper: {len(to_search)} Kuenstler werden geprueft ...", flush=True)

        results: dict[str, list[dict]] = {}
        done = 0

        _pool = ThreadPoolExecutor(max_workers=self.max_workers)
        futures = {
            _pool.submit(self._search_artist, a["name"]): a["name"]
            for a in to_search
        }
        try:
            for future in as_completed(futures, timeout=180):
                artist = futures[future]
                done += 1
                if done % 20 == 0:
                    safe = artist.encode("ascii", "replace").decode("ascii")
                    print(f"  Serper [{done}/{len(to_search)}] {safe} ...", flush=True)
                try:
                    events = future.result()
                    if events:
                        results[artist] = events
                except Exception:
                    pass
        except _FutTimeout:
            pending = sum(1 for f in futures if not f.done())
            print(f"  Serper: Timeout nach 180s — {pending} Kuenstler uebersprungen", flush=True)
        finally:
            _pool.shutdown(wait=False, cancel_futures=True)

        print(f"  >> Serper: {len(results)} Konzerte gefunden", flush=True)
        return results

    def _search_artist(self, artist: str, city: str = "Hamburg") -> list[dict]:
        """Search one artist for concerts in city via Google (Serper)."""
        year       = date.today().year
        query      = f'"{artist}" {city} Konzert {year}'
        city_lower = city.lower()
        is_hamburg = "hamburg" in city_lower

        try:
            resp = requests.post(
                _SERPER,
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                json={"q": query, "num": 5, "hl": "de", "gl": "de"},
                timeout=10,
            )
            data = resp.json()
        except Exception:
            return []

        events = []
        for result in data.get("organic", []):
            text = result.get("snippet", "") + " " + result.get("title", "")
            if city_lower not in text.lower():
                continue
            if is_hamburg:
                date_str = _extract_date_near_hamburg(text)
            else:
                date_str = _extract_date_near_city(text, city_lower)
            if not date_str or date_str < _TODAY:
                continue
            venue = _extract_venue(text) if is_hamburg else city
            events.append({
                "artist":   artist,
                "datetime": date_str,
                "venue":    venue,
                "url":      result.get("link", ""),
            })

        # Deduplicate by date
        seen, unique = set(), []
        for e in events:
            if e["datetime"] not in seen:
                seen.add(e["datetime"])
                unique.append(e)
        return unique
