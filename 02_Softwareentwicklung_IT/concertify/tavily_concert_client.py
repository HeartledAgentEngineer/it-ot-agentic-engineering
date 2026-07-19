"""
Tavily-based Hamburg concert finder.

For each followed artist not already found via Ticketmaster/Songkick,
does a web search and extracts concert date + venue in Hamburg.
Uses parallel requests to stay within ~2 minutes for 200 artists.
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as _FutTimeout
from datetime import date

import requests

_TODAY = date.today().isoformat()

_VENUE_MAP: dict[str, str] = {
    "barclays": "Barclays Arena",
    "volksparkstadion": "Volksparkstadion",
    "sporthalle": "Sporthalle Hamburg",
    "inselpark": "Inselpark Arena",
    "mehr! theater": "Mehr! Theater",
    "fabrik": "Fabrik Hamburg",
    "docks": "Docks Hamburg",
    "markthalle": "Markthalle Hamburg",
    "grünspan": "Grünspan",
    "gruenspan": "Grünspan",
    "große freiheit": "Große Freiheit 36",
    "grosse freiheit": "Große Freiheit 36",
    "logo": "Logo Hamburg",
    "uebel & gefährlich": "Uebel & Gefährlich",
    "trabrennbahn": "Trabrennbahn Hamburg",
    "stadtpark": "Stadtpark Hamburg",
    "alsterdorfer": "Alsterdorfer Sporthalle",
    "hamburg": "Hamburg",
}

_HAMBURG_KEYWORDS = set(_VENUE_MAP.keys())

_MONTH_MAP = {
    "jan": "01", "january": "01", "januar": "01",
    "feb": "02", "february": "02", "februar": "02",
    "mar": "03", "march": "03", "märz": "03", "maerz": "03",
    "apr": "04", "april": "04",
    "may": "05", "mai": "05",
    "jun": "06", "june": "06", "juni": "06",
    "jul": "07", "july": "07", "juli": "07",
    "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "oct": "10", "october": "10", "oktober": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12", "dezember": "12",
}


class TavilyConcertClient:
    def __init__(self, api_key: str, max_workers: int = 8):
        self.api_key = api_key
        self.max_workers = max_workers

    def get_hamburg_artists(
        self,
        followed_artists: list[dict],
        already_found: set[str] | None = None,
        max_artists: int = 300,
    ) -> dict[str, list[dict]]:
        """
        Search Hamburg concerts for followed artists via Tavily web search.
        already_found: set of artist names already found by other sources (skip these).
        Returns {artist_name: [{"datetime": "YYYY-MM-DD", "venue": "..."}]}
        """
        already_found = already_found or set()
        to_search = [
            a for a in followed_artists
            if a["name"] not in already_found
        ][:max_artists]

        if not to_search:
            return {}

        print(f"  Tavily: {len(to_search)} Kuenstler werden geprueft ...", flush=True)

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
                if done % 10 == 0:
                    safe = artist.encode("ascii", "replace").decode("ascii")
                    print(f"  Tavily [{done}/{len(to_search)}] {safe} ...", flush=True)
                try:
                    events = future.result()
                    if events:
                        results[artist] = events
                except Exception:
                    pass
        except _FutTimeout:
            pending = sum(1 for f in futures if not f.done())
            print(f"  Tavily: Timeout nach 180s — {pending} Kuenstler uebersprungen", flush=True)
        finally:
            _pool.shutdown(wait=False, cancel_futures=True)

        print(f"  >> Tavily: {len(results)} neue Konzerte gefunden", flush=True)
        return results

    def _search_artist(self, artist: str, city: str = "Hamburg") -> list[dict]:
        """Search one artist for concerts in city. Returns list of events."""
        year = date.today().year
        query = f'"{artist}" {city} Konzert {year} Ticket'
        city_lower = city.lower()
        is_hamburg = "hamburg" in city_lower

        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                headers={"Content-Type": "application/json"},
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 3,
                },
                timeout=10,
            )
            data = resp.json()
        except Exception:
            return []

        events = []
        for result in data.get("results", []):
            text = result.get("content", "") + " " + result.get("title", "")
            # Must mention the target city
            if city_lower not in text.lower():
                continue
            if is_hamburg:
                # Proximity-based: only dates near a Hamburg keyword
                date_str = _extract_date_near_hamburg(text)
            else:
                # For other cities: take the first date near the city name
                date_str = _extract_date_near_city(text, city_lower)
            if not date_str or date_str < _TODAY:
                continue
            venue = _extract_venue(text) if is_hamburg else city
            events.append({
                "artist": artist,
                "datetime": date_str,
                "venue": venue,
                "url": result.get("url", ""),
            })

        # Deduplicate by date
        seen = set()
        unique = []
        for e in events:
            if e["datetime"] not in seen:
                seen.add(e["datetime"])
                unique.append(e)
        return unique

    def _search_nationwide(self, artist: str, date_from: str, date_to: str) -> list[dict]:
        """Sucht Konzerte eines Kuenstlers deutschlandweit via Tavily.
        Schickt drei Queries parallel: zwei allgemeine + einen Eventim-spezifischen."""
        import re as _re
        from concurrent.futures import ThreadPoolExecutor

        years = sorted(set([date_from[:4], date_to[:4]]))
        year_str = " ".join(years)

        # Drei Queries: allgemein + gezielt auf Eventim (Tavily crawlt Eventim)
        fetch_configs = [
            {"query": f'"{artist}" Tour {year_str} alle Konzerttermine Datum Ort Deutschland',
             "max_results": 10, "search_depth": "basic"},
            {"query": f'"{artist}" Konzerte {year_str} Tickets Tournee alle Spielorte',
             "max_results": 10, "search_depth": "basic"},
            {"query": f'"{artist}" {year_str} Konzert Tickets',
             "max_results": 10, "search_depth": "basic",
             "include_domains": ["eventim.de", "ticketmaster.de"]},
        ]

        def _fetch(cfg):
            try:
                payload = {
                    "api_key": self.api_key,
                    "query": cfg["query"],
                    "search_depth": cfg.get("search_depth", "basic"),
                    "max_results": cfg.get("max_results", 10),
                }
                if "include_domains" in cfg:
                    payload["include_domains"] = cfg["include_domains"]
                resp = requests.post(
                    "https://api.tavily.com/search",
                    headers={"Content-Type": "application/json"},
                    json=payload, timeout=12,
                )
                return resp.json().get("results", [])
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=3) as pool:
            all_results = []
            for r in pool.map(_fetch, fetch_configs):
                all_results.extend(r)

        # Deutsche Staedte fuer Extraktion aus Datum-Snippets
        _DE_CITIES = [
            "Berlin", "Hamburg", "Muenchen", "Koeln", "Frankfurt", "Stuttgart",
            "Duesseldorf", "Dortmund", "Essen", "Leipzig", "Bremen", "Dresden",
            "Hannover", "Nuernberg", "Nurnberg", "Duisburg", "Bochum", "Wuppertal",
            "Bielefeld", "Bonn", "Muenster", "Munster", "Karlsruhe", "Mannheim",
            "Augsburg", "Wiesbaden", "Gelsenkirchen", "Braunschweig", "Kiel",
            "Aachen", "Chemnitz", "Magdeburg", "Freiburg", "Halle", "Krefeld",
            "Oberhausen", "Luebeck", "Lubeck", "Erfurt", "Rostock", "Mainz",
            "Kassel", "Hagen", "Saarbruecken", "Saarbrucken", "Potsdam",
            "Ingolstadt", "Ulm", "Heilbronn", "Pforzheim", "Osnabrueck", "Osnabruck",
            "Wuerzburg", "Wurzburg", "Regensburg", "Wolfsburg", "Bremerhaven",
            "Muenchen", "Munchen", "Duesseldorf", "Dusseldorf",
        ]
        _city_pat = _re.compile(
            r'\b(' + '|'.join(_re.escape(c) for c in _DE_CITIES) + r')\b', _re.IGNORECASE
        )
        # Hamburg-Venue-Muster (fuer _extract_venue Fallback)
        _HAMBURG_VENUES = set(_VENUE_MAP.keys()) - {"hamburg"}

        events = []
        seen_keys: set = set()
        pat_de  = _re.compile(r'\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b')
        pat_iso = _re.compile(r'\b(20\d{2})-(\d{2})-(\d{2})\b')

        for result in all_results:
            text = result.get("content", "") + " " + result.get("title", "")

            for m in list(pat_de.finditer(text)) + list(pat_iso.finditer(text)):
                if m.re == pat_de:
                    d, mo, yr = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
                else:
                    yr, mo, d = m.group(1), m.group(2), m.group(3)
                iso = f"{yr}-{mo}-{d}"
                if iso < date_from or iso > date_to:
                    continue

                # Snippet um das Datum herum — Stadt + Venue extrahieren
                start = max(0, m.start() - 140)
                snippet = text[start: m.end() + 140]

                city_match = _city_pat.search(snippet)
                city_found = city_match.group(1) if city_match else ""

                # Venue: nur echte Hamburg-Venues (Barclays etc.) — kein "Hamburg"-Default
                snippet_lower = snippet.lower()
                real_venue = ""
                for kw in sorted(_HAMBURG_VENUES, key=len, reverse=True):
                    if kw in snippet_lower:
                        real_venue = _VENUE_MAP[kw]
                        break
                venue = real_venue or city_found or ""

                # Dedup per Datum + Stadt (gleicher Tag in anderer Stadt = kein Dup)
                key = f"{iso}|{city_found.lower()}"
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                events.append({
                    "datetime": iso,
                    "venue":    venue,
                    "city":     city_found,
                    "source":   "Tavily",
                })

        events.sort(key=lambda e: e["datetime"])
        return events


def _parse_dd_mm(d1: str, sep: str, d2: str, year: str) -> str | None:
    """
    Safely parse a numeric date with ambiguous MM/DD vs DD/MM format.
    Dot separator → always European (DD.MM.YYYY).
    Slash separator → use unambiguous number position; skip if both ≤ 12 (too ambiguous).
    """
    n1, n2 = int(d1), int(d2)
    if sep == ".":
        day, month = n1, n2          # European: DD.MM.YYYY
    elif n1 > 12:
        day, month = n1, n2          # First > 12 → must be day
    elif n2 > 12:
        day, month = n2, n1          # Second > 12 → must be day (US: MM/DD)
    else:
        return None                   # Both ≤ 12 and slash → skip to avoid swap
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{year}-{month:02d}-{day:02d}"
    return None


def _extract_date(text: str) -> str | None:
    """Extract the first plausible 202x concert date from text. Returns YYYY-MM-DD or None."""
    for m in re.finditer(r"(\d{1,2})([./])(\d{1,2})[./](202\d)", text):
        result = _parse_dd_mm(m.group(1), m.group(2), m.group(3), m.group(4))
        if result:
            return result

    # DD Month YYYY or Month DD, YYYY
    for m in re.finditer(
        r"(\d{1,2})\s+([A-Za-zäöüÄÖÜ]+)\s+(202\d)|([A-Za-zäöüÄÖÜ]+)\s+(\d{1,2})[,\s]+(202\d)",
        text,
    ):
        if m.group(1):
            day, mon_str, year = m.group(1), m.group(2).lower()[:3], m.group(3)
        else:
            mon_str, day, year = m.group(4).lower()[:3], m.group(5), m.group(6)
        month = _MONTH_MAP.get(mon_str)
        if month and 1 <= int(day) <= 31:
            return f"{year}-{month}-{day.zfill(2)}"

    return None


def _extract_date_near_city(text: str, city_lower: str) -> str | None:
    """Return the first 202x date appearing within 400 chars of the city name."""
    text_lower = text.lower()
    city_positions: list[int] = []
    idx = 0
    while True:
        pos = text_lower.find(city_lower, idx)
        if pos == -1:
            break
        city_positions.append(pos)
        idx = pos + 1
    if not city_positions:
        return None

    date_matches: list[tuple[int, str]] = []
    for m in re.finditer(r"(\d{1,2})([./])(\d{1,2})[./](202\d)", text):
        result = _parse_dd_mm(m.group(1), m.group(2), m.group(3), m.group(4))
        if result:
            date_matches.append((m.start(), result))
    for m in re.finditer(
        r"(\d{1,2})\s+([A-Za-zäöüÄÖÜ]+)\s+(202\d)|([A-Za-zäöüÄÖÜ]+)\s+(\d{1,2})[,\s]+(202\d)",
        text,
    ):
        if m.group(1):
            day, mon_str, year = m.group(1), m.group(2).lower()[:3], m.group(3)
        else:
            mon_str, day, year = m.group(4).lower()[:3], m.group(5), m.group(6)
        month = _MONTH_MAP.get(mon_str)
        if month and 1 <= int(day) <= 31:
            date_matches.append((m.start(), f"{year}-{month}-{day.zfill(2)}"))

    _WINDOW = 400
    best_date: str | None = None
    best_dist = float("inf")
    for d_pos, d_str in date_matches:
        for c_pos in city_positions:
            dist = abs(d_pos - c_pos)
            if dist < best_dist and dist <= _WINDOW:
                best_dist = dist
                best_date = d_str
    return best_date


def _extract_date_near_hamburg(text: str) -> str | None:
    """
    Return the first 202x concert date that appears within 400 chars of a Hamburg keyword.
    Prevents tour-page false positives where other cities' dates appear before Hamburg's.
    """
    text_lower = text.lower()

    # Collect all positions of Hamburg-related keywords
    hh_positions: list[int] = []
    for kw in _VENUE_MAP:
        idx = 0
        while True:
            pos = text_lower.find(kw, idx)
            if pos == -1:
                break
            hh_positions.append(pos)
            idx = pos + 1
    if not hh_positions:
        return None

    # Collect all (position, date_string) pairs
    date_matches: list[tuple[int, str]] = []

    for m in re.finditer(r"(\d{1,2})([./])(\d{1,2})[./](202\d)", text):
        result = _parse_dd_mm(m.group(1), m.group(2), m.group(3), m.group(4))
        if result:
            date_matches.append((m.start(), result))

    for m in re.finditer(
        r"(\d{1,2})\s+([A-Za-zäöüÄÖÜ]+)\s+(202\d)|([A-Za-zäöüÄÖÜ]+)\s+(\d{1,2})[,\s]+(202\d)",
        text,
    ):
        if m.group(1):
            day, mon_str, year = m.group(1), m.group(2).lower()[:3], m.group(3)
        else:
            mon_str, day, year = m.group(4).lower()[:3], m.group(5), m.group(6)
        month = _MONTH_MAP.get(mon_str)
        if month and 1 <= int(day) <= 31:
            date_matches.append((m.start(), f"{year}-{month}-{day.zfill(2)}"))


    if not date_matches:
        return None

    # Pick the date with the smallest distance to any Hamburg keyword (max 400 chars)
    _WINDOW = 400
    best_date: str | None = None
    best_dist = float("inf")
    for d_pos, d_str in date_matches:
        for h_pos in hh_positions:
            dist = abs(d_pos - h_pos)
            if dist < best_dist and dist <= _WINDOW:
                best_dist = dist
                best_date = d_str

    return best_date


def _extract_venue(text: str) -> str:
    """Extract a Hamburg venue name from text if recognisable."""
    text_lower = text.lower()
    for kw in sorted(_VENUE_MAP.keys(), key=len, reverse=True):
        if kw in text_lower:
            return _VENUE_MAP[kw]
    return "Hamburg"
