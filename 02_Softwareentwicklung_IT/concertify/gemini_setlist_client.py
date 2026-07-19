"""
Gemini Setlist Finder
=====================
Uses Google Gemini with Google Search grounding to find current
tour setlists for artists not covered by setlist.fm.
Free via Google AI Studio (no payment needed).
"""

import os
import re

import requests


_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_MODEL = "gemini-2.0-flash-lite"


class GeminiSetlistClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    def get_setlist_tracks(
        self,
        artist_name: str,
        setlist_songs: int = 8,
        new_songs: int = 2,
    ) -> dict:
        """
        Returns {"setlist_titles": [...], "new_titles": []}
        Uses Gemini + Google Search to find the artist's live setlist.
        new_titles = recent charting singles not yet played live (predicted setlist additions).
        """
        import time

        url = f"{_BASE}/{_MODEL}:generateContent?key={self.api_key}"

        # --- Prompt 1: most played live songs ---
        setlist_titles = []
        prompt1 = (
            f"Search for '{artist_name} setlist 2024 2025 most played live songs'. "
            f"List the {setlist_songs} songs they play most often in concerts. "
            f"Reply ONLY with song titles, one per line, no numbering, no bullets, "
            f"no extra text. Maximum {setlist_songs} lines."
        )
        resp = self._call_gemini(url, prompt1, artist_name)
        if resp is None:
            return {"setlist_titles": [], "new_titles": []}
        try:
            text = (
                resp.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
            )
            setlist_titles = _parse_song_titles(text)[:setlist_songs]
        except Exception:
            pass

        # --- Prompt 2: recent charting singles not yet played live ---
        new_titles = []
        if new_songs > 0:
            time.sleep(2)  # kurze Pause zwischen Gemini-Calls
            prompt2 = (
                f"Search for '{artist_name} new singles 2024 2025 chart hits never played live'. "
                f"Which of their most recent and popular singles (released 2023-2025) "
                f"have they NOT yet performed live and might appear in upcoming concerts? "
                f"Only include commercially successful or well-known songs. "
                f"Reply ONLY with song titles, one per line, no numbering, no bullets, "
                f"no extra text. Maximum {new_songs} lines."
            )
            resp2 = self._call_gemini(url, prompt2, artist_name, silent=True)
            if resp2:
                try:
                    text2 = (
                        resp2.get("candidates", [{}])[0]
                             .get("content", {})
                             .get("parts", [{}])[0]
                             .get("text", "")
                    )
                    candidates = _parse_song_titles(text2)
                    # Nur Songs die nicht schon in setlist_titles sind
                    seen = {t.lower() for t in setlist_titles}
                    new_titles = [s for s in candidates if s.lower() not in seen][:new_songs]
                except Exception:
                    pass

        return {"setlist_titles": setlist_titles, "new_titles": new_titles}

    def _call_gemini(self, url: str, prompt: str, artist_name: str, silent: bool = False) -> dict | None:
        import time
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
        }
        for attempt in range(3):
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 429:
                if attempt < 2:
                    time.sleep(10 * (attempt + 1))
                    continue
                if not silent:
                    print(f"      Gemini quota exceeded for {artist_name} — using album tracks")
                return None
            try:
                resp.raise_for_status()
            except Exception as e:
                if not silent:
                    print(f"      Gemini error for {artist_name}: {e}")
                return None
            return resp.json()
        return None


def _parse_song_titles(text: str) -> list[str]:
    titles = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\d]+[.)]\s*", "", line)
        line = re.sub(r"^[-*•·]\s*", "", line)
        line = line.strip('"\'')
        if line and len(line) > 1 and not line.startswith("http"):
            titles.append(line)
    return titles
