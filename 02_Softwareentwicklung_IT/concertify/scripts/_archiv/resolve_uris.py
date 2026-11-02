"""
Einmalig: Spotify-URIs fuer alle Songs in setlist_data vorauflösen.
Nutzt den OAuth-Token aus .cache (kein ClientCredentials noetig).
Speichert Ergebnisse direkt in concert_data.json.

Aufruf: python resolve_uris.py
"""
import json, os, time
from pathlib import Path
from dotenv import dotenv_values

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "concert_data.json"

env = dotenv_values(BASE_DIR / ".env")

# OAuth-Token aus .cache laden (selbe Methode wie app.py)
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

auth = SpotifyOAuth(
    client_id=env.get("SPOTIFY_CLIENT_ID", ""),
    client_secret=env.get("SPOTIFY_CLIENT_SECRET", ""),
    redirect_uri=env.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
    scope="user-follow-read playlist-read-private playlist-modify-public playlist-modify-private",
    cache_path=str(BASE_DIR / ".cache"),
)
token_info = auth.get_cached_token()
if not token_info:
    print("FEHLER: Kein gueltiger Token in .cache — bitte zuerst die App oeffnen und einloggen.")
    exit(1)
if auth.is_token_expired(token_info):
    token_info = auth.refresh_access_token(token_info["refresh_token"])

sp = Spotify(auth=token_info["access_token"], requests_timeout=10)


class RateLimitError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate Limit — Retry nach {retry_after}s")


def search_uri(artist: str, song: str) -> str | None:
    """Sucht exakte URI fuer artist + song. Wirft RateLimitError wenn gesperrt."""
    import re as _re
    try:
        r = sp.search(q=f'track:"{song}" artist:"{artist}"', type="track", limit=5)
        items = r.get("tracks", {}).get("items", [])
        if not items:
            r2 = sp.search(q=f"{song} {artist}", type="track", limit=5)
            items = r2.get("tracks", {}).get("items", [])
        if items:
            return items[0]["uri"]
    except Exception as e:
        err = str(e)
        m = _re.search(r'[Rr]etry.*?(\d+)\s*s', err)
        if m or "rate" in err.lower() or "limit" in err.lower() or "429" in err:
            retry = int(m.group(1)) if m else 0
            raise RateLimitError(retry)
        print(f"  Fehler bei '{song}' / '{artist}': {err}")
    return None


def _save(cd):
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cd, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, DATA_FILE)


cd = json.loads(DATA_FILE.read_text(encoding="utf-8"))
sd = cd.get("setlist_data", {})

total_songs = sum(len(d.get("setlist_titles", [])) for d in sd.values())
found = 0
skipped = 0
artist_count = 0

print(f"Starte URI-Aufloesung: {len(sd)} Kuenstler, {total_songs} Songs gesamt\n")

rate_limited = False

for artist, d in sd.items():
    if rate_limited:
        break

    songs = d.get("setlist_titles", [])
    if not songs:
        print(f"  {artist}: keine Songs — uebersprungen")
        continue

    existing_uris = d.get("spotify_uris", {})
    to_resolve = [s for s in songs if s not in existing_uris]

    if not to_resolve:
        print(f"  {artist}: alle {len(songs)} Songs haben schon URIs")
        artist_count += 1
        continue

    print(f"  {artist}: {len(to_resolve)} Songs aufloesen ...", end="", flush=True)
    new_uris = dict(existing_uris)
    ok = 0
    for song in to_resolve:
        try:
            uri = search_uri(artist, song)
        except RateLimitError as rl:
            mins = rl.retry_after // 60
            print(f"\n\nRATE LIMIT erreicht! Spotify sperrt Suchanfragen fuer ~{mins} Minuten.")
            print(f"Bereits aufgeloest: {found} Songs fuer {artist_count} Kuenstler.")
            print(f"Bisher geloeste URIs wurden gespeichert. Bitte in ~{mins}min neu starten.")
            d["spotify_uris"] = new_uris
            _save(cd)
            rate_limited = True
            break
        if uri:
            new_uris[song] = uri
            ok += 1
        else:
            skipped += 1
        time.sleep(0.12)

    if rate_limited:
        break

    d["spotify_uris"] = new_uris
    found += ok
    artist_count += 1
    print(f" {ok}/{len(to_resolve)} gefunden")
    _save(cd)

if not rate_limited:
    print(f"\nFertig: {found} URIs gefunden, {skipped} nicht gefunden")
    print(f"Ergebnis in concert_data.json gespeichert.")
