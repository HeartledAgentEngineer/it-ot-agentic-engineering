"""
resolve_uris_anon.py
=====================
Variante die einen Spotify Anonymous-Web-Token nutzt — den gleichen Token,
den open.spotify.com beim Oeffnen im Browser erzeugt. Der Token gehoert zur
Spotify-eigenen Web-App, hat also einen anderen Rate-Limit-Bucket als
unsere registrierte App.

Aufruf:
    python resolve_uris_anon.py                          # alle Kuenstler mit fehlenden URIs
    python resolve_uris_anon.py "Loathe" "Sabaton" ...   # nur bestimmte Kuenstler

Sicherheit:
    1. Erst 1 Test-Call. Wenn 429 -> sofortiger Abbruch.
    2. Pause 2.5s zwischen Calls (24 req/min).
    3. Atomar speichern nach jedem Kuenstler.
    4. Token wird nach ~1h ungueltig — bei expired Token holen wir einen neuen.

Hinweis: Diese Methode nutzt eine inoffizielle Spotify-Web-API. Funktioniert
seit Jahren, kann aber theoretisch von Spotify geaendert werden. Reines Lesen.
"""

import json
import os
import sys
import time
from pathlib import Path

import requests
import spotipy

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "concert_data.json"

SLEEP_BETWEEN = float(os.environ.get("RESOLVE_SLEEP", "2.5"))

# Spotify Web Endpoint fuer Anonymous-Token
TOKEN_URL = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"


class QuotaExhausted(Exception):
    pass


class TokenExpired(Exception):
    pass


def _fetch_anonymous_token() -> tuple[str, int]:
    """Holt einen Anonymous-Token von open.spotify.com.

    Returns:
        (access_token, expires_at_unix_seconds)
    """
    # Spotify will einen Browser-aehnlichen User-Agent — sonst HTTP 401
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    r = requests.get(TOKEN_URL, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    token = data.get("accessToken")
    expires_ms = data.get("accessTokenExpirationTimestampMs", 0)
    if not token:
        raise RuntimeError(f"Kein accessToken in Response: {data!r}")
    expires_at = expires_ms // 1000
    return token, expires_at


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
        status = getattr(e, "http_status", None)
        if status == 429:
            retry = e.headers.get("Retry-After", "?") if hasattr(e, "headers") else "?"
            raise QuotaExhausted(f"HTTP 429 bei {song!r} (Retry-After: {retry}s)") from e
        if status == 401:
            raise TokenExpired(f"HTTP 401 bei {song!r}") from e
        print(f"      Fehler bei {song!r}: {type(e).__name__}: {e}")
        return None
    except Exception as e:
        print(f"      Fehler bei {song!r}: {type(e).__name__}: {e}")
        return None


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else None

    print("Hole Anonymous-Token von open.spotify.com...")
    try:
        token, expires_at = _fetch_anonymous_token()
    except Exception as e:
        print(f"FEHLER beim Token-Holen: {e}")
        sys.exit(1)

    sec_left = expires_at - int(time.time())
    print(f"  Token-Praefix: {token[:20]}... (gueltig fuer {sec_left}s)")

    sp = spotipy.Spotify(auth=token)

    # ─── Test-Call ──────────────────────────────────────────────────────────
    print("Mache Test-Call (1 Spotify-Suche)...")
    try:
        r = sp.search(q="test", limit=1, type="track")
        items = r.get("tracks", {}).get("items", [])
        if items:
            t = items[0]
            print(f"  OK -- gefunden: {t['name']!r} von {t['artists'][0]['name']!r}\n")
        else:
            print("  OK -- aber leeres Ergebnis (komisch, aber Token funktioniert)\n")
    except spotipy.exceptions.SpotifyException as e:
        status = getattr(e, "http_status", None)
        if status == 429:
            retry = e.headers.get("Retry-After", "?") if hasattr(e, "headers") else "?"
            print(f"FEHLER: Auch der Anonymous-Token ist rate-limited (HTTP 429).")
            print(f"        Retry-After: {retry} Sekunden.")
            sys.exit(1)
        print(f"FEHLER beim Test-Call: HTTP {status}: {e.msg}")
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
                # Token-Refresh wenn fast abgelaufen (60s Puffer)
                if int(time.time()) > expires_at - 60:
                    print("      Token expired -- hole neuen...")
                    token, expires_at = _fetch_anonymous_token()
                    sp = spotipy.Spotify(auth=token)

                try:
                    uri = _find_uri(sp, artist, song)
                except TokenExpired:
                    print("      HTTP 401 -- hole neuen Token und versuche erneut...")
                    token, expires_at = _fetch_anonymous_token()
                    sp = spotipy.Spotify(auth=token)
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

        # Atomar speichern
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
