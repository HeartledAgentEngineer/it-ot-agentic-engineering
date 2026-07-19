"""
Claude AI Concert Finder
========================
Uses the Anthropic API with the web_search tool to find upcoming Hamburg
concerts and match them against a list of followed Spotify artists.
"""

import os
import re
import time
import anthropic
from matcher import normalise


class ClaudeConcertClient:
    def __init__(self, api_key: str | None = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_hamburg_artists(
        self,
        followed_artists: list[dict],
    ) -> dict[str, list[dict]]:
        """
        Find Hamburg concerts for followed artists via Claude + web search.
        Returns {artist_name: [concert_dict, ...]}
        """
        if not followed_artists:
            return {}

        followed_lookup = {normalise(a["name"]): a["name"] for a in followed_artists}
        artist_names = [a["name"] for a in followed_artists]

        results: dict[str, list[dict]] = {}

        # Search 1 – general Hamburg concert overview
        print("  Asking Claude about Hamburg concerts (general search) …")
        batch = self._search_general(followed_lookup)
        results.update(batch)
        print(f"    >> {len(batch)} matches so far")

        # Search 2 – look up remaining artists in batches of 25
        found = set(results.keys())
        remaining = [n for n in artist_names if n not in found]

        for i in range(0, len(remaining), 25):
            chunk = remaining[i : i + 25]
            print(
                f"  Asking Claude about specific artists ({i + 1}–{i + len(chunk)}"
                f" of {len(remaining)}) …"
            )
            batch = self._search_artists(chunk, followed_lookup)
            results.update(batch)
            print(f"    >> {len(batch)} new matches")
            if i + 25 < len(remaining):
                time.sleep(1)  # small pause between calls

        print(f"  >> {len(results)} artists with Hamburg shows found by Claude")
        return results

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _run_search(self, prompt: str) -> str:
        """Call Claude with web_search and return the full text response."""
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            tools=[{"type": "web_search_20260209", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
        text_parts = [b.text for b in response.content if b.type == "text"]
        return "\n".join(text_parts)

    def _search_general(self, followed_lookup: dict[str, str]) -> dict[str, list[dict]]:
        """Broad search for all upcoming Hamburg concerts."""
        prompt = (
            "Bitte suche im Web nach allen Konzerten und Live-Events in Hamburg "
            "(und Umgebung bis 50 km) in 2025 und 2026. "
            "Suche nach: 'Hamburg Konzerte 2025 Programm', "
            "'Hamburg concerts 2026 schedule', "
            "'Barclays Arena Hamburg 2025 2026 events', "
            "'Stadtpark Hamburg Open Air 2025', "
            "'Volksparkstadion Hamburg Konzerte', "
            "'Hamburg Trabrennbahn Konzerte'. "
            "\n\n"
            "Gib mir eine möglichst vollständige Liste aller Konzerte. "
            "Formatiere JEDES Konzert auf einer eigenen Zeile exakt so:\n"
            "KUENSTLER|DATUM|VENUE\n\n"
            "Datum-Format: YYYY-MM-DD (wenn bekannt) oder YYYY-MM oder YYYY. "
            "Schreibe NUR diese Zeilen, keinen anderen Text."
        )
        try:
            text = self._run_search(prompt)
            return self._parse_lines(text, followed_lookup)
        except Exception as e:
            print(f"  !!  General search failed: {e}")
            return {}

    def _search_artists(
        self,
        names: list[str],
        followed_lookup: dict[str, str],
    ) -> dict[str, list[dict]]:
        """Check whether specific artists have Hamburg shows."""
        names_str = ", ".join(names)
        prompt = (
            f"Bitte suche im Web, ob folgende Künstler Konzerte in Hamburg "
            f"(oder Umgebung bis 50 km) in 2025 oder 2026 haben:\n"
            f"{names_str}\n\n"
            "Formatiere jeden gefundenen Termin auf einer eigenen Zeile exakt so:\n"
            "KUENSTLER|DATUM|VENUE\n\n"
            "Datum-Format: YYYY-MM-DD (wenn bekannt) oder YYYY-MM oder YYYY. "
            "Schreibe NUR diese Zeilen für Künstler MIT Hamburg-Konzert. "
            "Wenn ein Künstler kein Hamburg-Konzert hat, schreibe nichts."
        )
        try:
            text = self._run_search(prompt)
            return self._parse_lines(text, followed_lookup)
        except Exception as e:
            print(f"  !!  Artist batch search failed: {e}")
            return {}

    def _parse_lines(
        self,
        text: str,
        followed_lookup: dict[str, str],
    ) -> dict[str, list[dict]]:
        """Parse KUENSTLER|DATUM|VENUE lines and match against followed artists."""
        results: dict[str, list[dict]] = {}

        for raw_line in text.splitlines():
            line = raw_line.strip()
            # Skip empty lines or lines that look like prose
            if not line or "|" not in line:
                continue
            # Skip lines that start with markdown / prose indicators
            if line.startswith(("#", "*", "-", ">")):
                continue

            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 2:
                continue

            artist_raw = parts[0]
            date_str = parts[1] if len(parts) > 1 else ""
            venue = parts[2] if len(parts) > 2 else "Hamburg"

            # Normalise date: extract YYYY-MM-DD or YYYY-MM or YYYY
            date_clean = ""
            m = re.search(r"(\d{4}-\d{2}-\d{2})", date_str)
            if m:
                date_clean = m.group(1)
            else:
                m2 = re.search(r"(\d{4}-\d{2})", date_str)
                if m2:
                    date_clean = m2.group(1)
                else:
                    m3 = re.search(r"(\d{4})", date_str)
                    if m3:
                        date_clean = m3.group(1)
                    else:
                        date_clean = date_str

            norm = normalise(artist_raw)
            if norm in followed_lookup:
                original = followed_lookup[norm]
                concert = {
                    "artist": original,
                    "date": date_clean,
                    "venue": venue,
                    "url": "",
                    "datetime": date_clean,
                }
                results.setdefault(original, []).append(concert)

        return results
