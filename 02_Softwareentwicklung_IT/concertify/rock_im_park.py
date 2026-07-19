"""
Rock im Park 2026 lineup fetcher.

Strategy:
  1. Scrape rock-im-park.com (gets ~64 artists visible in initial HTML)
  2. Supplement via Tavily web search (catches artists missing from JS-rendered page)
  3. scrape_timetable(): tries /spielplan page + Tavily for day/stage/time per artist
"""

import os
import re

import requests
from bs4 import BeautifulSoup

_DAY_MAP = {
    "freitag": "Freitag", "friday": "Freitag",
    "samstag": "Samstag", "saturday": "Samstag",
    "sonntag": "Sonntag", "sunday": "Sonntag",
}

_STAGE_RE = re.compile(
    r"\b(Utopia Stage|Mandora Stage|Orbit Stage|"
    r"Mainstage|Alternastage|Parkstage|Park Stage|Rock Stage|Metal Stage|"
    r"Infield Stage|Festival Stage|Zeltbuehne|Zeltbühne|Hang Stage|"
    r"Main Stage|Haupt.?b.hne|Neben.?b.hne)\b",
    re.I,
)
_TIME_RANGE_RE = re.compile(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})")
_TIME_RE       = re.compile(r"\b(\d{1,2}:\d{2})\b")

_DEFAULT_URL = "https://www.rock-im-park.com/lineup"

_ARTIST_SELECTORS = [
    "[class*='artist'] [class*='name']",
    "[class*='artist'] h1",
    "[class*='artist'] h2",
    "[class*='artist'] h3",
    "[class*='artist'] h4",
    "[class*='lineup'] [class*='name']",
    "[class*='lineup'] h2",
    "[class*='lineup'] h3",
    ".act-name",
    ".band-name",
    "h2.name",
    "h3.name",
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def scrape_lineup(url: str | None = None) -> list[str]:
    """
    Returns the Rock im Park 2026 lineup.
    Scrapes the official website first, then supplements via Tavily if available.
    """
    target = url or os.getenv("ROCK_IM_PARK_LINEUP_URL", _DEFAULT_URL)
    print(f"  Scraping Rock im Park lineup from: {target}")

    scraped: list[str] = []
    try:
        resp = requests.get(target, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        for selector in _ARTIST_SELECTORS:
            elements = soup.select(selector)
            if not elements:
                continue
            candidates = [_clean(el.get_text()) for el in elements]
            candidates = [c for c in candidates if _plausible_artist_name(c)]
            if candidates:
                scraped = candidates
                print(f"  >> {len(scraped)} artists via CSS scrape")
                break

        if not scraped:
            scraped = _fallback_extract(soup)
    except requests.RequestException as exc:
        print(f"  Scrape request failed: {exc}")

    # Supplement 1: Tavily (often quota-limited; we tolerate failure silently)
    tavily_key = _load_api_key("TAVILY_API_KEY")
    tavily_extra: list[str] = []
    if tavily_key:
        tavily_extra = _tavily_lineup(tavily_key)
        new_count = sum(1 for a in tavily_extra if a not in scraped)
        if new_count:
            print(f"  >> {new_count} additional artists via Tavily web search")

    # Supplement 2: Serper (Google Search API, 2500/month free) - fallback when Tavily quota hits
    serper_key = _load_api_key("SERPER_API_KEY")
    serper_extra: list[str] = []
    if serper_key:
        serper_extra = _serper_lineup(serper_key)
        already = set(scraped) | set(tavily_extra)
        new_count = sum(1 for a in serper_extra if a not in already)
        if new_count:
            print(f"  >> {new_count} additional artists via Serper (Google) search")

    merged = list(dict.fromkeys(scraped + tavily_extra + serper_extra))
    print(f"  >> {len(merged)} Rock im Park artists total")
    return merged


def _load_api_key(name: str) -> str:
    """Read an API key from environment or .env file."""
    key = os.getenv(name, "")
    if key:
        return key
    try:
        from dotenv import dotenv_values as _dv
        return _dv(os.path.join(os.path.dirname(__file__), ".env")).get(name, "") or ""
    except Exception:
        return ""


def _serper_lineup(api_key: str) -> list[str]:
    """Search Serper (Google) for Rock im Park 2026 artists. Drop-in alternative to Tavily."""
    queries = [
        "Rock im Park 2026 lineup all artists complete",
        "Rock im Park 2026 lineup alle Kuenstler",
        "Rock im Park 2026 Freitag Samstag Sonntag lineup",
        "Rock im Park 2026 Linkin Park Volbeat Sabaton Iron Maiden lineup",
    ]
    _skip_domains = ("setlist.fm",)  # jambase kept - actually gives good day-breakdowns for RiP
    found: list[str] = []
    for q in queries:
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": q, "num": 8, "hl": "de", "gl": "de"},
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
            for result in data.get("organic", []):
                url = result.get("link", "").lower()
                if any(d in url for d in _skip_domains):
                    continue
                text = result.get("snippet", "") + " " + result.get("title", "")
                if re.search(r"montreux jazz|reeperbahn festival", text, re.I):
                    continue
                found.extend(_extract_names_from_text(text))
        except Exception:
            pass
    return list(dict.fromkeys(found))


def _tavily_lineup(api_key: str) -> list[str]:
    """Search Tavily for Rock im Park 2026 artists not found by scraping."""
    queries = [
        "Rock im Park 2026 lineup alle Kuenstler vollstaendig",
        "Rock im Park 2026 full lineup artists list",
        "Rock im Park 2026 Bands Nuernberg Zeppelinfeld complete",
        "Rock im Park 2026 Hollywood Undead Limp Bizkit h-blockx lineup",
    ]
    _skip_domains = ("montreux", "jambase", "setlist.fm")
    found: list[str] = []
    for q in queries:
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                headers={"Content-Type": "application/json"},
                json={"api_key": api_key, "query": q, "search_depth": "basic", "max_results": 8},
                timeout=15,
            )
            data = resp.json()
            for result in data.get("results", []):
                url = result.get("url", "").lower()
                if any(d in url for d in _skip_domains):
                    continue
                text = result.get("content", "") + " " + result.get("title", "")
                # Skip if result is primarily about an unrelated festival (not Rock im Park)
                if re.search(r"montreux jazz|reeperbahn festival", text, re.I):
                    continue
                # Rock am Ring shares the lineup — keep those results but they're fine
                found.extend(_extract_names_from_text(text))
        except Exception:
            pass
    return list(dict.fromkeys(found))


def _extract_names_from_text(text: str) -> list[str]:
    """Extract potential artist names from a comma/bullet/markdown separated text."""
    # Handle markdown headers: "## Artist Name." → "Artist Name"
    text = re.sub(r"#{1,4}\s+", "\n", text)
    # Split on common separators
    parts = re.split(r"[,\|\n•·/]", text)
    names = []
    for part in parts:
        cleaned = _clean(part)
        # Strip trailing punctuation and filler
        cleaned = re.sub(r"[\.!?]+$", "", cleaned).strip()
        cleaned = re.sub(r"^(and|und|feat\.?|ft\.?)\s+", "", cleaned, flags=re.I).strip()
        if _plausible_artist_name(cleaned):
            names.append(cleaned)
    return names


def _fallback_extract(soup: BeautifulSoup) -> list[str]:
    """Last-resort: look for data-artist / data-name / aria-label attributes."""
    names: list[str] = []
    for tag in soup.find_all(True):
        for attr in ("data-artist", "data-name", "data-title", "aria-label"):
            val = tag.get(attr, "")
            cleaned = _clean(val)
            if _plausible_artist_name(cleaned):
                names.append(cleaned)
    return list(dict.fromkeys(names))


def scrape_timetable(artists: list[str], api_key: str = "") -> dict[str, dict]:
    """
    Returns {artist_name: {day, stage, start, end}} for matched artists.
    Tries /spielplan scrape first, then Tavily general timetable,
    then per-artist targeted queries for any still-missing artists.
    """
    text = _get_timetable_text(api_key)
    result = _extract_schedule(text, artists) if text else {}

    # Per-artist fallback for any still-missing artists
    if api_key:
        missing = [a for a in artists if a not in result]
        for artist in missing:
            slot = _tavily_artist_slot(artist, api_key)
            if slot:
                result[artist] = slot

    print(f"  >> Timetable: {len(result)}/{len(artists)} Kuenstler mit Slot-Daten", flush=True)
    return result


def _tavily_artist_slot(artist: str, api_key: str) -> dict | None:
    """Targeted Tavily search for a single artist's Rock im Park slot."""
    queries = [
        f'"{artist}" "Rock im Park" 2026 Freitag Samstag Sonntag Spielplan Buehne',
        f'"{artist}" "Rock im Park" 2026 Utopia Mandora Orbit timetable day stage',
    ]
    for q in queries:
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                headers={"Content-Type": "application/json"},
                json={"api_key": api_key, "query": q, "search_depth": "basic", "max_results": 5},
                timeout=12,
            )
            results = resp.json().get("results", [])
        except Exception:
            continue

        for result in results:
            text = result.get("content", "")
            # Künstlernamen im Text suchen
            idx = text.lower().find(artist.lower())
            if idx == -1:
                plain = re.sub(r'["\(\)]', '', artist).lower().strip()
                idx   = text.lower().find(plain)
            if idx == -1:
                continue
            # Kontext-Fenster um den Künstler-Namen
            window = text[max(0, idx - 200): idx + 300]

            sm = _STAGE_RE.search(window)
            stage = sm.group(1) if sm else ""
            m = _TIME_RANGE_RE.search(window)
            start = m.group(1) if m else ""
            end   = m.group(2) if m else ""
            if not start:
                m2 = _TIME_RE.search(window)
                start = m2.group(1) if m2 else ""
            day = ""
            for marker, d in _DAY_MAP.items():
                if marker in window.lower():
                    day = d
                    break

            if stage or start or day:
                return {"day": day, "stage": stage, "start": start, "end": end}
    return None


def _get_timetable_text(api_key: str) -> str:
    """Fetch timetable text: official page first, then tagesweise Tavily-Suchen."""
    for url in [
        "https://www.rock-im-park.com/spielplan",
        "https://www.rock-im-park.com/timetable",
        "https://www.rock-im-park.com/lineup/timetable",
    ]:
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, "lxml")
                for tag in soup(["script", "style", "noscript"]):
                    tag.decompose()
                text = soup.get_text("\n", strip=True)
                if len(text) > 1000:
                    return text
        except Exception:
            pass

    if not api_key:
        return ""

    # Tagesweise Suchen — Tages-Header einbetten damit _extract_schedule korrekt propagiert
    combined = ""
    for day_de in ["Freitag", "Samstag", "Sonntag"]:
        combined += f"\n\n{day_de}\n\n"
        day_queries = [
            f"Rock im Park 2026 {day_de} Spielplan Timetable Zeiten Lineup Buehne",
            f"Rock im Park 2026 {day_de} schedule lineup artists stages time",
        ]
        for q in day_queries:
            try:
                resp = requests.post(
                    "https://api.tavily.com/search",
                    headers={"Content-Type": "application/json"},
                    json={"api_key": api_key, "query": q, "search_depth": "basic", "max_results": 5},
                    timeout=15,
                )
                for r in resp.json().get("results", []):
                    combined += r.get("content", "") + "\n"
            except Exception:
                pass
    return combined


def _extract_schedule(text: str, artists: list[str]) -> dict[str, dict]:
    """
    Find {day, stage, start, end} for each artist in the schedule text.
    Searches for the artist name and reads surrounding context.
    """
    from matcher import normalise as _norm

    result: dict[str, dict] = {}
    lines = text.split("\n")

    # Build per-line day index: propagate day context downward
    line_day: list[str] = []
    current_day = ""
    for line in lines:
        ll = line.lower()
        for marker, day in _DAY_MAP.items():
            if marker in ll:
                current_day = day
                break
        line_day.append(current_day)

    for artist in artists:
        artist_norm = _norm(artist)
        for i, line in enumerate(lines):
            if artist_norm not in _norm(line):
                continue
            # Artist found — collect context window (this + next 4 lines)
            ctx = "\n".join(lines[i : i + 5])

            day = line_day[i]
            # Also check context for day marker if not yet set
            if not day:
                for marker, d in _DAY_MAP.items():
                    if marker in ctx.lower():
                        day = d
                        break

            m = _TIME_RANGE_RE.search(ctx)
            start = m.group(1) if m else ""
            end   = m.group(2) if m else ""
            if not start:
                m2 = _TIME_RE.search(ctx)
                start = m2.group(1) if m2 else ""

            sm = _STAGE_RE.search(ctx)
            stage = sm.group(1) if sm else ""

            if day or stage or start:
                result[artist] = {"day": day, "stage": stage, "start": start, "end": end}
                break

    return result


def _clean(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _plausible_artist_name(name: str) -> bool:
    """Heuristic: artist names are short and mostly alphabetic."""
    if not name or len(name) < 2 or len(name) > 50:
        return False
    # Too many words = sentence, not an artist name
    if len(name.split()) > 5:
        return False
    # Contains year or long digit sequence → likely a date/URL, not a band name
    # Allow: TX2, Blink-182, Sum 41, 30 Seconds to Mars
    if re.search(r"(19|20)\d{2}|\d{4,}", name):
        return False
    noise_exact = {
        "lineup", "tickets", "more", "info", "home", "menu", "stages",
        "festival", "news", "artists", "camping", "faq", "shop", "schedule",
        "rock im park", "rock am ring", "june", "juni", "freitag", "samstag",
        "friday", "saturday", "sunday", "sonntag",
        "nuremberg", "nuernberg", "nurnberg", "germany", "deutschland",
        "headliners", "included", "featured", "grooveist", "songkick",
        "eventim", "jambase", "setlists", "zeppelinfeld", "update",
        "wechsle", "montreux", "tour update",
    }
    if name.lower() in noise_exact:
        return False
    # Starts with known non-artist patterns
    noise_prefix = ("rock im park", "rock am ring", "tickets", "montreux",
                    "you are leaving", "grooveist", "com and", "endorsed",
                    "zum festival", "wechsle zu", "nuremberg", "nürnberg",
                    "germany", "more…")
    if any(name.lower().startswith(p.lower()) for p in noise_prefix):
        return False
    # Ends with city/country names typical of venue descriptions
    if re.search(r",\s*(Germany|Deutschland|Nuremberg|N.rnberg)$", name, re.I):
        return False
    return bool(re.search(r"[a-zA-ZÄÖÜäöüß]", name))
