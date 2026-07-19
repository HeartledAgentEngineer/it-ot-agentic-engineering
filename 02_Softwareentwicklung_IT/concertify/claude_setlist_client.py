"""
Claude AI Setlist Finder
========================
Uses Claude + web search to find current tour setlists for artists
not covered by setlist.fm.
"""

import os
import re

import anthropic


class ClaudeSetlistClient:
    def __init__(self, api_key: str | None = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )

    def get_setlist_tracks(
        self,
        artist_name: str,
        setlist_songs: int = 8,
        new_songs: int = 2,
    ) -> dict:
        """
        Returns {"setlist_titles": [...], "new_titles": []}
        Uses web search to find the artist's current live setlist.
        """
        prompt = (
            f"Search the web for '{artist_name} setlist 2024 2025 most played songs' "
            f"and '{artist_name} live concert setlist'. "
            f"Find the {setlist_songs} songs they play most often in their live shows. "
            f"Reply ONLY with song titles, one per line, no numbering, no bullets, "
            f"no extra text, no explanations. Maximum {setlist_songs} lines."
        )

        try:
            response = self.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=1024,
                tools=[{"type": "web_search_20260209", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}],
            )
            text = "\n".join(b.text for b in response.content if b.type == "text")
            titles = _parse_song_titles(text)
            return {
                "setlist_titles": titles[:setlist_songs],
                "new_titles": [],
            }
        except Exception as e:
            print(f"      Claude setlist error for {artist_name}: {e}")
            return {"setlist_titles": [], "new_titles": []}


def _parse_song_titles(text: str) -> list[str]:
    titles = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^[\d]+[.)]\s*", "", line)   # remove "1. " or "1) "
        line = re.sub(r"^[-*•·]\s*", "", line)       # remove "- " or "* "
        line = line.strip('"\'')
        if line and len(line) > 1 and not line.startswith("http"):
            titles.append(line)
    return titles
