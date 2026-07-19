"""
external/__init__.py
======================
Adapter-Schicht zu externen APIs.

Hier wohnen alle Klassen die mit externen Diensten reden:
- setlist.fm (gesetzt-strukturierte Setlist-Daten)
- Tavily, Gemini, Claude (AI-/Web-basierte Setlist-Vorhersagen)
- Spotify, Songkick, Bandsintown (Konzert-Daten)

Die alten *_client.py Dateien im Projektroot bleiben unveraendert.
Hier sind nur duenne Wrapper die ein gemeinsames Interface herstellen
(Strategy Pattern fuer Multi-Source-Fetching).
"""

from external.setlistfm_quota import SetlistFmQuota

__all__ = ["SetlistFmQuota"]
