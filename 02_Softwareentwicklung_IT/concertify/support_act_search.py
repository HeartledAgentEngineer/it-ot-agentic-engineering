"""
support_act_search.py
=====================
Support-Act-Suche via Serper (Google Search API) als Fallback, wenn
Ticketmaster und Tavily nichts liefern.

Engineering-Konzept: "Pure Extraktion getrennt von IO"
    extract_support_acts() ist reine, testbare Logik (kein Netzwerk).
    serper_support_acts() ist der duenne IO-Wrapper um die Serper-API.

Hintergrund: TM hat kaum DE-Daten, der Tavily-Heuristik-Filter ist zu schwach.
Google (Serper) nennt Support-Acts dagegen oft explizit ("Support act Chevelle",
"special guests Papa Roach", "supported by Bilmuri").
"""

import re

# Ein Name = 1-3 grossgeschriebene Tokens (Bandnamen). Die Grossschreibung filtert
# generische Phrasen wie "support act information" zuverlaessig heraus.
_NAME = r"[A-Z][A-Za-z0-9&'’]*(?:\s+[A-Z][A-Za-z0-9&'’]+){0,2}"

_PREFIX_PATTERNS = [
    re.compile(r"(?i:support act[s]?)[\s:\-–]+(" + _NAME + r")"),
    re.compile(r"(?i:special guest[s]?)[\s:\-–]+(" + _NAME + r")"),
    re.compile(r"(?i:supported by)[\s:\-–]+(" + _NAME + r")"),
]

# Generische Woerter, die nach "support act"/"special guest" stehen koennen,
# aber keine Bandnamen sind (Backup zur Grossschreibungs-Heuristik).
_STOPWORDS = {
    "information", "info", "details", "reviews", "tickets", "ticket", "lineup",
    "news", "tour", "show", "shows", "tba", "announcement", "announced", "line",
    "package", "vip", "and", "the",
}


def extract_support_acts(text: str, exclude: "set[str] | None" = None) -> "list[str]":
    """Extrahiert Support-Act-Namen aus Freitext (Titel + Snippet einer Suche).

    Liefert eine deduplizierte Liste in Fundreihenfolge. `exclude` entfernt
    z.B. den Hauptkuenstler selbst.
    """
    if not text:
        return []
    excl = {e.strip().lower() for e in (exclude or set())}
    out: list[str] = []
    seen: set[str] = set()
    for pat in _PREFIX_PATTERNS:
        for m in pat.finditer(text):
            name = m.group(1).strip(" .,-–—|:")
            low = name.lower()
            if not low or low in seen or low in excl:
                continue
            if low.split()[0] in _STOPWORDS:
                continue
            seen.add(low)
            out.append(name)
    return out


def serper_support_acts(
    api_key: str,
    artist: str,
    venue: str = "",
    year: str = "",
    num: int = 8,
    timeout: int = 15,
) -> "list[str]":
    """Fragt Serper (Google) nach Support-Acts und extrahiert Namen.

    Duenner IO-Wrapper; die eigentliche Logik steckt in extract_support_acts().
    Schluckt Netzwerkfehler bewusst (Fallback-Pfad) und liefert dann [].
    """
    if not api_key or not artist:
        return []
    import requests

    loc = venue or ""
    queries = [
        f'"{artist}" support act opener {loc} {year}'.strip(),
        f'"{artist}" {year} tour special guest supported by'.strip(),
    ]
    exclude = {artist}
    out: list[str] = []
    seen: set[str] = set()
    for q in queries:
        try:
            resp = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": q, "num": num, "hl": "en", "gl": "de"},
                timeout=timeout,
            )
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception:
            continue
        for item in data.get("organic", []):
            text = (item.get("title", "") or "") + ". " + (item.get("snippet", "") or "")
            for name in extract_support_acts(text, exclude=exclude):
                low = name.lower()
                if low not in seen:
                    seen.add(low)
                    out.append(name)
        if out:
            break  # erste Query mit Treffern reicht
    return out
