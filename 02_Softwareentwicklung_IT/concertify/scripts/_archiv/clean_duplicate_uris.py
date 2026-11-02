#!/usr/bin/env python
"""
Einmal-Skript: bereinigt Spotify-URIs die fuer mehrere Songs verwendet werden.

Hintergrund: Der Spotify-Resolver hat fuer Live-Intros, Medleys und nicht-existente
Studio-Tracks als Fallback oft den ersten Treffer akzeptiert. Folge: dieselbe URI
ist mehreren Song-Titeln zugeordnet -> mind. einer pro Gruppe ist garantiert falsch.

Strategie: ALLE URIs einer Duplikat-Gruppe auf '' setzen (nicht riskieren den falschen
zu erwischen). Songs bleiben in setlist_titles, Frontend zeigt grauen Punkt.
"""
import json
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DATA = Path('concert_data.json')

# 1. Backup
backup = DATA.with_name(f'concert_data.backup_{datetime.now():%Y%m%d_%H%M}_pre_uri_cleanup.json')
shutil.copy(DATA, backup)
print(f'Backup: {backup.name}')

# 2. Laden
d = json.loads(DATA.read_text(encoding='utf-8'))
sd = d.get('setlist_data', {})

# 3. Bereinigen
total_cleared = 0
cleared_per_artist = {}
for artist, info in sd.items():
    uris = info.get('spotify_uris', {})
    if not uris:
        continue
    rev = defaultdict(list)
    for title, uri in uris.items():
        if uri:
            rev[uri].append(title)
    dup_groups = {u: titles for u, titles in rev.items() if len(titles) > 1}
    if not dup_groups:
        continue
    artist_count = 0
    for uri, titles in dup_groups.items():
        for title in titles:
            uris[title] = ''
            artist_count += 1
            total_cleared += 1
    cleared_per_artist[artist] = (artist_count, dup_groups)

# 4. Speichern (atomic via temp + rename)
tmp = DATA.with_suffix('.tmp')
tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding='utf-8')
tmp.replace(DATA)

# 5. Report
print(f'\n=== Bereinigt: {total_cleared} URIs in {len(cleared_per_artist)} Kuenstlern ===\n')
for artist, (cnt, groups) in sorted(cleared_per_artist.items(), key=lambda x: -x[1][0]):
    print(f'{artist} ({cnt} URIs):')
    for uri, titles in groups.items():
        short_uri = uri.split(':')[-1][:12]
        print(f'  [{short_uri}...]  ->  {titles}')
    print()
