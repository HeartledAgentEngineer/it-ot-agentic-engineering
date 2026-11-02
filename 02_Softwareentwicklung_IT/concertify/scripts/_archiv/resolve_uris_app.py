"""
resolve_uris_app.py
====================
Aufloest fehlende Spotify-URIs fuer alle Songs in setlist_data.
Nutzt App-Credentials (kein OAuth-Login noetig).

Aufruf:
    python resolve_uris_app.py                          # alle Kuenstler mit fehlenden URIs
    python resolve_uris_app.py "Alter Bridge"           # ein Kuenstler
    python resolve_uris_app.py "Loathe" "Sabaton" ...   # mehrere Kuenstler

Algorithmus pro Song:
    1. Suche "track:SONG artist:ARTIST" bei Spotify
    2. Bestes Match (erste Treffer) als URI speichern
    3. Wenn nichts gefunden: leere URI bleibt — User kann manuell suchen
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import dotenv_values
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "concert_data.json"

# Spotify-API-Limit: 180 req/min. Wir gehen bewusst langsam (2.5s = 24 req/min),
# damit die App-Token-Quota nicht erneut blockiert. Per ENV-Var ueberschreibbar.
SLEEP_BETWEEN = float(os.environ.get("RESOLVE_SLEEP", "2.5"))


class QuotaExhausted(Exception):
    pass


def _find_uri(sp: spotipy.Spotify, artist: str, song: str) -> str | None:
    """Sucht eine Track-URI fuer einen Song eines Kuenstlers."""
    try:
        # Spotify-Suche mit Filter
        q = f'track:"{song}" artist:"{artist}"'
        results = sp.search(q=q, limit=3, type="track")
        tracks = results.get("tracks", {}).get("items", [])

        if not tracks:
            # Fallback: ohne Anfuehrungszeichen
            q = f"{song} {artist}"
            results = sp.search(q=q, limit=3, type="track")
            tracks = results.get("tracks", {}).get("items", [])

        if not tracks:
            return None

        # Bestes Match: bevorzuge Track wo Artist genau matched
        for t in tracks:
            artists = [a.get("name", "").lower() for a in t.get("artists", [])]
            if artist.lower() in artists:
                return t.get("uri")

        # Sonst: erste Treffer (kann Cover sein, aber besser als nichts)
        return tracks[0].get("uri") if tracks else None

    except spotipy.exceptions.SpotifyException as e:
        if getattr(e, "http_status", None) == 429:
            raise QuotaExhausted(f"HTTP 429 bei {song!r} ({artist})") from e
        print(f"      Fehler bei {song!r}: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        print(f"      Fehler bei {song!r}: {type(e).__name__}: {e}")
        return None


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else None

    env = dotenv_values(BASE_DIR / ".env")
    client_id = env.get("SPOTIFY_CLIENT_ID", "")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("FEHLER: SPOTIFY_CLIENT_ID/SECRET fehlt in .env")
        sys.exit(1)

    auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(client_credentials_manager=auth)

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    sd = data.setdefault("setlist_data", {})

    artists = targets if targets else list(sd.keys())
    print(f"Verarbeite {len(artists)} Kuenstler (Pause {SLEEP_BETWEEN}s zwischen Calls)...\n")

    total_resolved = 0
    total_missing = 0

    for artist in artists:
        if artist not in sd:
            print(f"  {artist!r} nicht in setlist_data — uebersprungen")
            continue

        entry = sd[artist]
        titles = entry.get("setlist_titles", [])
        uris = entry.get("spotify_uris", {})

        # Nur Songs OHNE URI
        missing = [t for t in titles if not uris.get(t)]
        if not missing:
            print(f"  {artist:<22} alle {len(titles)} URIs bereits da")
            continue

        print(f"  {artist:<22} {len(missing)}/{len(titles)} Songs zu loesen...")

        resolved_here = 0
        aborted = False
        try:
            for song in missing:
                uri = _find_uri(sp, artist, song)
                if uri:
                    uris[song] = uri
                    resolved_here += 1
                    total_resolved += 1
                else:
                    total_missing += 1
                time.sleep(SLEEP_BETWEEN)
        except QuotaExhausted as e:
            print(f"     !! Spotify-Quota erschoepft: {e}")
            print(f"     !! Abbruch. Bisheriger Stand wird gespeichert.")
            aborted = True

        entry["spotify_uris"] = uris
        print(f"     -> {resolved_here}/{len(missing)} gefunden")

        # Nach jedem Kuenstler speichern (atomic)
        tmp = DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, DATA_FILE)

        if aborted:
            print(f"\nAbgebrochen wegen Quota. Versuch es in ein paar Stunden erneut.")
            print(f"Gefundene URIs bis jetzt: {total_resolved}, nicht gefunden: {total_missing}")
            sys.exit(2)

    print(f"\nFertig: {total_resolved} URIs gefunden, {total_missing} nicht gefunden")


if __name__ == "__main__":
    main()
