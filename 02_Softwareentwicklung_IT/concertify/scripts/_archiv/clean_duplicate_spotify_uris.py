"""
Entfernt falsche Spotify-URIs, die mehrfach verschiedenen Songtiteln zugeordnet sind.

Hintergrund: resolve_uris_app.py hat bei Intros/Medleys oft den ersten LP-Treffer
genommen — dieselbe URI landet bei mehreren Titeln. Nur ein Titel kann richtig sein,
die anderen spielen im Player den falschen Song.

Vorgehen:
    1. Backup von concert_data.json
    2. Pro Kuenstler: URI-Duplikate finden
    3. Alle Songs in Duplikat-Gruppen: URI auf "" setzen (Titel bleiben!)
    4. Atomar speichern

Aufruf:
    python clean_duplicate_spotify_uris.py          # ausfuehren
    python clean_duplicate_spotify_uris.py --dry-run  # nur anzeigen
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "concert_data.json"


def _find_duplicate_groups(uris: dict[str, str]) -> dict[str, list[str]]:
    """uri -> [song titles] fuer URIs die von mehr als einem Titel genutzt werden."""
    by_uri: dict[str, list[str]] = defaultdict(list)
    for title, uri in uris.items():
        if uri and uri.strip():
            by_uri[uri].append(title)
    return {uri: titles for uri, titles in by_uri.items() if len(titles) > 1}


def clean_data(data: dict, *, dry_run: bool = False) -> dict:
    """Gibt Statistik zurueck."""
    sd = data.get("setlist_data", {})
    stats = {
        "artists_affected": 0,
        "groups": 0,
        "uris_cleared": 0,
        "details": [],
    }

    for artist, entry in sorted(sd.items()):
        uris = entry.get("spotify_uris", {})
        if not uris:
            continue
        groups = _find_duplicate_groups(uris)
        if not groups:
            continue

        stats["artists_affected"] += 1
        for uri, titles in groups.items():
            stats["groups"] += 1
            stats["uris_cleared"] += len(titles)
            stats["details"].append(
                {"artist": artist, "uri": uri, "titles": sorted(titles)}
            )
            if not dry_run:
                for title in titles:
                    uris[title] = ""
                entry["spotify_uris"] = uris

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Duplikat-Spotify-URIs bereinigen")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, concert_data.json nicht aendern",
    )
    args = parser.parse_args()

    if not DATA_FILE.exists():
        raise SystemExit(f"FEHLER: {DATA_FILE} nicht gefunden")

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    stats = clean_data(data, dry_run=args.dry_run)

    print(f"Kuenstler betroffen: {stats['artists_affected']}")
    print(f"Duplikat-Gruppen:    {stats['groups']}")
    print(f"URIs geleert:        {stats['uris_cleared']}")
    print()

    for row in stats["details"]:
        print(f"  {row['artist']}:")
        print(f"    {row['uri']}")
        for t in row["titles"]:
            print(f"      - {t}")
        print()

    if args.dry_run:
        print("(dry-run — keine Datei geschrieben)")
        return

    if stats["uris_cleared"] == 0:
        print("Nichts zu tun.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BASE_DIR / f"concert_data.backup_{ts}_before_uri_dedup.json"
    shutil.copy2(DATA_FILE, backup)
    print(f"Backup: {backup.name}")

    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)
    print(f"Gespeichert: {DATA_FILE.name}")


if __name__ == "__main__":
    main()
