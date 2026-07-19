"""
Artist name matching utilities.

Normalises names before comparison to handle minor differences:
  "AC/DC"  ↔  "AC DC"
  "Motörhead"  ↔  "Motörhead"  (unicode-safe)
  "The 1975"  ↔  "1975, The"   (not handled — exact + normalised only)
"""

import re
import unicodedata


def normalise(name: str) -> str:
    """Lowercase, strip punctuation/extra whitespace, collapse spaces."""
    # Unicode normalise (NFC) so ö == ö regardless of encoding
    name = unicodedata.normalize("NFC", name)
    name = name.lower()
    # Replace common separators with space
    name = re.sub(r"[/\\|_\-–—]", " ", name)
    # Remove all remaining punctuation except letters, digits, spaces
    name = re.sub(r"[^\w\s]", "", name, flags=re.UNICODE)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def match_artists(
    followed: list[dict],
    festival_names: list[str],
) -> dict[str, str]:
    """
    Returns a mapping of {followed_artist_name: festival_artist_name}
    for every followed artist that appears in the festival lineup.

    Matching is case-insensitive and punctuation-normalised.
    """
    # Build lookup: normalised_festival_name >> original_festival_name
    festival_lookup: dict[str, str] = {}
    for fn in festival_names:
        festival_lookup[normalise(fn)] = fn

    matches: dict[str, str] = {}
    for artist in followed:
        name = artist.get("name", "")
        norm = normalise(name)
        if norm in festival_lookup:
            matches[name] = festival_lookup[norm]

    return matches
