"""Test Songkick for a few known Hamburg artists."""
from songkick_client import SongkickClient

test_artists = [
    {"name": "Breaking Benjamin"},
    {"name": "System Of A Down"},
    {"name": "Die Toten Hosen"},
    {"name": "Broilers"},
    {"name": "Tarja"},
    {"name": "Beyond The Black"},
]

client = SongkickClient()
results = client.get_hamburg_artists(test_artists)

print("\n=== Results ===")
if results:
    for artist, events in results.items():
        for e in events:
            print(f"  {artist}: {e['date']} @ {e['venue']}")
else:
    print("  No Hamburg shows found (or Songkick blocked requests)")
