"""
resolve_uris_user.py
=====================
Variante von resolve_uris_app.py die den User-OAuth-Token aus .cache nutzt
statt App-Credentials. User-Token hat einen separaten Rate-Limit-Bucket —
ueberlebt also wenn der App-Token gerade dicht ist.

Aufruf:
    python resolve_uris_user.py                          # alle Kuenstler mit fehlenden URIs
    python resolve_uris_user.py "Loathe" "Sabaton" ...   # nur bestimmte Kuenstler

Sicherheit:
    1. Erst 1 Test-Call. Wenn 429 -> sofortiger Abbruch (keine Spotify-Calls verschwendet).
    2. Pause 2.5s zwischen Calls (24 req/min, weit unter Limit).
    3. Atomar speichern nach jedem Kuenstler.
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
import spotipy
from dotenv import dotenv_values

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "concert_data.json"
CACHE_FILE = BASE_DIR / ".cache"

SLEEP_BETWEEN = float(os.environ.get("RESOLVE_SLEEP", "2.5"))


class QuotaExhausted(Exception):
    pass


def _load_user_token() -> str:
    """Liest access_token aus .cache. Refresht via refresh_token falls expired.

    Refresh laeuft direkt ueber den Spotify-Token-Endpoint — kein Browser noetig,
    solange der refresh_token noch gueltig ist (i.d.R. Monate).
    """
    if not CACHE_FILE.exists():
        raise RuntimeError(
            "Keine .cache-Datei gefunden. Bitte einmal im Browser ueber http://localhost:5000 einloggen."
        )

    cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    expires_at = cache.get("expires_at", 0)
    now = int(time.time())

    if now < expires_at - 60:  # noch gueltig (60s Puffer)
        return cache["access_token"]

    # Token expired -> Refresh
    env = dotenv_values(BASE_DIR / ".env")
    client_id = env.get("SPOTIFY_CLIENT_ID", "")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET", "")

    refresh_token = cache.get("refresh_token")
    if not refresh_token:
        raise RuntimeError(
            "Kein refresh_token in .cache. Bitte einmal im Browser einloggen."
        )

    print("  Token expired, refreshe ueber refresh_token...")
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(client_id, client_secret),
        timeout=10,
    )
    r.raise_for_status()
    new_data = r.json()

    cache["access_token"] = new_data["access_token"]
    cache["expires_at"] = now + new_data.get("expires_in", 3600)
    if "refresh_token" in new_data:
        cache["refresh_token"] = new_data["refresh_token"]

    CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
    print("  Token refreshed.")
    return cache["access_token"]


def _find_uri(sp: spotipy.Spotify, artist: str, song: str) -> str | None:
    """Sucht eine Track-URI fuer einen Song eines Kuenstlers."""
    try:
        q = f'track:"{song}" artist:"{artist}"'
        results = sp.search(q=q, limit=3, type="track")
        tracks = results.get("tracks", {}).get("items", [])

        if not tracks:
            q = f"{song} {artist}"
            results = sp.search(q=q, limit=3, type="track")
            tracks = results.get("tracks", {}).get("items", [])

        if not tracks:
            return None

        for t in tracks:
            artists = [a.get("name", "").lower() for a in t.get("artists", [])]
            if artist.lower() in artists:
                return t.get("uri")

        return tracks[0].get("uri") if tracks else None

    except spotipy.exceptions.SpotifyException as e:
        if getattr(e, "http_status", None) == 429:
            retry = e.headers.get("Retry-After", "?") if hasattr(e, "headers") else "?"
            raise QuotaExhausted(f"HTTP 429 bei {song!r} (Retry-After: {retry}s)") from e
        print(f"      Fehler bei {song!r}: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        print(f"      Fehler bei {song!r}: {type(e).__name__}: {e}")
        return None


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else None

    print("Lade User-Token aus .cache...")
    try:
        token = _load_user_token()
    except Exception as e:
        print(f"FEHLER beim Token-Laden: {e}")
        sys.exit(1)

    sp = spotipy.Spotify(auth=token)

    # ─── Test-Call: 1 simple Suche um Rate-Limit-Status zu pruefen ──────────
    print("Mache Test-Call (1 Spotify-Suche)...")
    try:
        sp.search(q="test", limit=1, type="track")
        print("OK -- User-Token funktioniert!\n")
    except spotipy.exceptions.SpotifyException as e:
        if getattr(e, "http_status", None) == 429:
            retry = e.headers.get("Retry-After", "?") if hasattr(e, "headers") else "?"
            print(f"FEHLER: Auch der User-Token ist rate-limited (HTTP 429).")
            print(f"        Retry-After: {retry} Sekunden.")
            print("        Bitte spaeter erneut versuchen.")
            sys.exit(1)
        print(f"FEHLER beim Test-Call: {type(e).__name__}: {e}")
        sys.exit(1)

    # ─── Hauptlauf ─────────────────────────────────────────────────────────
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    sd = data.setdefault("setlist_data", {})

    artists = targets if targets else list(sd.keys())
    print(f"Verarbeite {len(artists)} Kuenstler (Pause {SLEEP_BETWEEN}s zwischen Calls)...\n")

    total_resolved = 0
    total_missing = 0

    for artist in artists:
        if artist not in sd:
            print(f"  {artist!r} nicht in setlist_data -- uebersprungen")
            continue

        entry = sd[artist]
        titles = entry.get("setlist_titles", [])
        uris = entry.get("spotify_uris", {})

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

        # Atomar speichern (nach jedem Kuenstler)
        tmp = DATA_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, DATA_FILE)

        if aborted:
            print(f"\nAbgebrochen wegen Quota.")
            print(f"Gefundene URIs: {total_resolved}, nicht gefunden: {total_missing}")
            sys.exit(2)

    print(f"\nFertig: {total_resolved} URIs gefunden, {total_missing} nicht gefunden")


if __name__ == "__main__":
    main()
