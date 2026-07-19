"""
Festival lineup fetcher — Tavily-based for multiple festivals.
"""

import os
import re

import requests

KNOWN_FESTIVALS: dict[str, dict] = {
    "Elbriot": {
        "date": "2026-08-28",
        "city": "Hamburg",
        "url": "https://elbriot.de/lineup/",
        "tavily_queries": [
            "Elbriot Festival 2026 lineup Hamburg Bands",
            "Elbriot 2026 lineup alle Kuenstler Hamburg",
        ],
    },
    "Impericon Festival": {
        "date": "2026-04-18",
        "city": "Leipzig / Hamburg / weitere",
        "url": "https://impericon.com/de/festival.html",
        "tavily_queries": [
            "Impericon Festival 2026 lineup bands confirmed",
            "Impericon Festival 2026 alle Kuenstler Lineup",
        ],
    },
    "Hellfest": {
        "date": "2026-06-19",
        "city": "Clisson, France",
        "url": "https://www.hellfest.fr/lineup/",
        "tavily_queries": [
            "Hellfest 2026 lineup artists complete list",
            "Hellfest Open Air 2026 bands confirmed",
        ],
    },
    "Copenhell": {
        "date": "2026-06-17",
        "city": "Copenhagen, Denmark",
        "url": "https://copenhell.dk/lineup/",
        "tavily_queries": [
            "Copenhell 2026 lineup artists complete",
            "Copenhell Festival 2026 bands confirmed",
        ],
    },
    "Rock im Park": {
        "date": "2026-06-05",
        "city": "Nürnberg",
        "url": "https://www.rock-im-park.com/lineup",
        "tavily_queries": [
            "Rock im Park 2026 lineup alle Künstler vollständig",
            "Rock im Park 2026 full lineup artists list",
        ],
    },
    "Rock am Ring": {
        "date": "2026-06-05",
        "city": "Nürburg",
        "url": "https://www.rock-am-ring.com/lineup",
        "tavily_queries": [
            "Rock am Ring 2026 lineup alle Künstler vollständig",
            "Rock am Ring 2026 full lineup artists list",
        ],
    },
    "Hurricane": {
        "date": "2026-06-19",
        "city": "Scheeßel",
        "url": "https://www.hurricane.de/lineup",
        "tavily_queries": [
            "Hurricane Festival 2026 lineup alle Künstler",
            "Hurricane Festival 2026 full lineup artists",
        ],
    },
    "Southside": {
        "date": "2026-06-19",
        "city": "Neuhausen ob Eck",
        "url": "https://www.southside.de/lineup",
        "tavily_queries": [
            "Southside Festival 2026 lineup alle Künstler",
            "Southside Festival 2026 full lineup artists",
        ],
    },
    "Wacken": {
        "date": "2026-07-30",
        "city": "Wacken",
        "url": "https://www.wacken.com/de/wacken/lineup/",
        "tavily_queries": [
            "Wacken Open Air 2026 lineup alle Bands vollständig",
            "W:O:A 2026 full lineup bands list",
        ],
    },
    "Download DE": {
        "date": "2026-06-12",
        "city": "Nürnberg",
        "url": "https://downloadfestival.de/lineup",
        "tavily_queries": [
            "Download Festival Deutschland 2026 lineup Künstler",
            "Download Festival Germany 2026 full lineup",
        ],
    },
}

_SKIP_DOMAINS = ("montreux", "jambase", "setlist.fm", "ticketmaster", "eventim")

_NOISE_EXACT = {
    "lineup", "tickets", "more", "info", "home", "menu", "stages", "festival",
    "news", "artists", "camping", "faq", "shop", "schedule", "june", "juni",
    "friday", "saturday", "sunday", "freitag", "samstag", "sonntag",
    "germany", "deutschland", "headliners", "included", "featured",
    "eventim", "jambase", "setlists", "update", "tour update",
}

_NOISE_PREFIX = (
    "tickets", "you are leaving", "endorsed", "zum festival",
    "germany", "mehr", "more",
)


def get_lineup(festival_name: str, tavily_key: str) -> list[str]:
    """
    Returns a list of artist names for the given festival via Tavily.
    Falls back to scraping the official URL if available.
    """
    info = KNOWN_FESTIVALS.get(festival_name)
    if not info:
        # Fallback fuer unbekannte Festivals: generische Tavily-Suche
        queries = [
            f"{festival_name} 2026 lineup artists list",
            f"{festival_name} 2026 bands confirmed full lineup",
        ]
        return _tavily_lineup(festival_name, queries, tavily_key)

    # Special case: Rock im Park has a dedicated scraper
    if festival_name == "Rock im Park":
        try:
            from rock_im_park import scrape_lineup
            return scrape_lineup(url=info["url"])
        except Exception:
            pass

    return _tavily_lineup(festival_name, info["tavily_queries"], tavily_key)


def _tavily_lineup(festival_name: str, queries: list[str], api_key: str) -> list[str]:
    found: list[str] = []
    for q in queries:
        try:
            resp = requests.post(
                "https://api.tavily.com/search",
                headers={"Content-Type": "application/json"},
                json={"api_key": api_key, "query": q, "search_depth": "basic", "max_results": 5},
                timeout=15,
            )
            data = resp.json()
            for result in data.get("results", []):
                url = result.get("url", "").lower()
                if any(d in url for d in _SKIP_DOMAINS):
                    continue
                text = result.get("content", "") + " " + result.get("title", "")
                # Skip results about other festivals
                other = [n for n in KNOWN_FESTIVALS if n != festival_name]
                if any(_other_festival_mentioned(o, text) for o in other):
                    continue
                found.extend(_extract_names(text))
        except Exception:
            pass
    return list(dict.fromkeys(found))


def _other_festival_mentioned(other_name: str, text: str) -> bool:
    """True if the text is clearly about a different festival."""
    key = other_name.lower().split()[0]  # "rock", "hurricane", "southside", etc.
    return key in text.lower() and other_name.lower() in text.lower()


def _extract_names(text: str) -> list[str]:
    text = re.sub(r"#{1,4}\s+", "\n", text)
    parts = re.split(r"[,\|\n•·/]", text)
    names = []
    for part in parts:
        cleaned = part.strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"[\.!?]+$", "", cleaned).strip()
        cleaned = re.sub(r"^(and|und|feat\.?|ft\.?)\s+", "", cleaned, flags=re.I).strip()
        if _plausible(cleaned):
            names.append(cleaned)
    return names


def _plausible(name: str) -> bool:
    if not name or len(name) < 2 or len(name) > 50:
        return False
    if len(name.split()) > 5:
        return False
    # Allow band names with digits (TX2, Blink-182, Sum 41) — only block years/long sequences
    if re.search(r"(19|20)\d{2}|\d{4,}", name):
        return False
    if name.lower() in _NOISE_EXACT:
        return False
    if any(name.lower().startswith(p) for p in _NOISE_PREFIX):
        return False
    return bool(re.search(r"[a-zA-ZÄÖÜäöüß]", name))
