"""
external/__init__.py
======================
Heimat fuer eigenstaendige Helfer rund um externe APIs. NICHT die API-Clients
selbst — die liegen weiterhin als *_client.py im Projektroot und werden direkt
von app.py, fetch_data.py und main.py benutzt.

Aktueller Inhalt (Ist-Zustand):
    - SetlistFmQuota (setlistfm_quota.py): zaehlt die taeglichen setlist.fm-
      Requests mit, um die 1440/Tag-Sperre zu vermeiden.

Geplant, aber NICHT umgesetzt:
    Urspruenglich war hier eine Adapter-/Wrapper-Schicht gedacht, die alle
    Konzert-/Setlist-Quellen (Spotify, Tavily, Gemini, Claude, Songkick, …)
    hinter ein gemeinsames Interface legt (Strategy Pattern fuer Multi-Source-
    Fetching). Davon existiert bisher nichts; das Fetching laeuft weiterhin
    direkt ueber die *_client.py im Root. Dieser Hinweis steht hier, damit die
    Absicht dokumentiert bleibt und nicht mit dem Ist-Zustand verwechselt wird.

Angeschlossen:
    SetlistFmQuota wird von SetlistClient (setlist_client.py im Root) genutzt:
    jeder setlist.fm-Request laeuft durch einen Kontingent-Check, der bei
    erreichtem Tageslimit stoppt, statt in die 1440/Tag-Sperre zu laufen.
"""

from external.setlistfm_quota import SetlistFmQuota

__all__ = ["SetlistFmQuota"]
