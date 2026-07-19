"""
Tavily Setlist Predictor
========================
Uses Tavily Search (free tier: 1000 searches/month) to find recent tour
setlists and predict what an artist will play next.

Strategy:
  1. Search for recent setlists from the current tour
  2. Search for new songs being tested live
  3. Rank by frequency across multiple shows
"""

import os
import re
from collections import Counter

import requests


_TAVILY_URL = "https://api.tavily.com/search"

# Songs die häufig als false positives auftauchen
_SKIP_PHRASES = {
    "setlist", "concert", "tour", "live", "show", "encore", "opening",
    "intro", "outro", "soundcheck", "tickets", "venue", "support act",
}


class TavilySetlistClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY", "")

    def get_setlist_tracks(
        self,
        artist_name: str,
        setlist_songs: int = 8,
        new_songs: int = 2,
    ) -> dict:
        """
        Returns {"setlist_titles": [...], "new_titles": []}
        Predicts the next setlist by analyzing recent tour shows.
        """
        if not self.api_key:
            print(f"      Tavily: kein API-Key gesetzt")
            return {"setlist_titles": [], "new_titles": []}

        # --- Suche 1: Aktuelle Tour-Setlists ---
        song_counter: Counter = Counter()
        results1 = self._search(
            f'"{artist_name}" setlist 2025 site:setlist.fm OR site:concertarchive.org OR site:songkick.com'
        )
        for r in results1:
            songs = _extract_songs_from_text(r.get("content", "") + "\n" + r.get("title", ""), artist_name)
            for s in songs:
                song_counter[s] += 1

        # --- Suche 2: Neue Songs die sie live testen ---
        new_counter: Counter = Counter()
        results2 = self._search(
            f'"{artist_name}" new song setlist 2025 live debut OR "first time" OR "new track"'
        )
        for r in results2:
            songs = _extract_songs_from_text(r.get("content", "") + "\n" + r.get("title", ""), artist_name)
            for s in songs:
                new_counter[s] += 1

        # Setlist: die meistgespielten Songs der aktuellen Tour
        setlist_titles = [s for s, _ in song_counter.most_common(setlist_songs * 2)]
        setlist_titles = _deduplicate(setlist_titles)[:setlist_songs]

        # New titles: Songs aus Suche 2 die noch nicht in der Haupt-Setlist sind
        setlist_set = {s.lower() for s in setlist_titles}
        new_titles = []
        for s, _ in new_counter.most_common(new_songs * 3):
            if s.lower() not in setlist_set:
                new_titles.append(s)
            if len(new_titles) >= new_songs:
                break

        if not setlist_titles:
            print(f"      Tavily: keine Songs gefunden für {artist_name}")
        else:
            print(f"      Tavily: {len(setlist_titles)} Songs gefunden für {artist_name}")

        return {"setlist_titles": setlist_titles, "new_titles": new_titles}

    def _search(self, query: str, max_results: int = 5) -> list[dict]:
        """Führt eine Tavily-Suche durch und gibt die Ergebnisse zurück."""
        try:
            resp = requests.post(
                _TAVILY_URL,
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as e:
            print(f"      Tavily search error: {e}")
            return []


def _extract_songs_from_text(text: str, artist_name: str) -> list[str]:
    """
    Extrahiert Song-Titel aus Setlist-Texten.
    Funktioniert mit setlist.fm-Format, Fließtext, Listen.
    """
    songs = []
    artist_lower = artist_name.lower()

    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 2:
            continue

        # Zeilen überspringen die offensichtlich kein Song-Titel sind
        line_lower = line.lower()
        if any(p in line_lower for p in _SKIP_PHRASES):
            continue
        if artist_lower in line_lower:
            continue
        if line.startswith(("http", "www", "#", ">")):
            continue
        if len(line) > 80:  # Zu langer Satz = Fließtext
            continue

        # Nummern/Bullets entfernen
        cleaned = re.sub(r"^\d+[.)]\s*", "", line)
        cleaned = re.sub(r"^[-*•·]\s*", "", cleaned)
        cleaned = cleaned.strip('"\'').strip()

        # Mindestlänge und kein reiner Zahlen-String
        if cleaned and len(cleaned) > 1 and not cleaned.isdigit():
            songs.append(cleaned)

    return songs


def _deduplicate(songs: list[str]) -> list[str]:
    """Entfernt Duplikate (case-insensitive) unter Beibehaltung der Reihenfolge."""
    seen = set()
    result = []
    for s in songs:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result
