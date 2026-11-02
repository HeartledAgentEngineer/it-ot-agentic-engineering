import json

songs = [
    "I Will Not Bow", "Until the End", "Evil Angel", "Crawl", "Red Cold River",
    "Blow Me Away", "Follow", "Angels Fall", "You", "So Cold", "Polyamorous",
    "Dear Agony", "Something Wicked", "Breath", "Awaken", "Failure",
    "Dance With the Devil", "The Diary of Jane"
]

with open('concert_data.json', 'r', encoding='utf-8') as f:
    cd = json.load(f)

bb = cd.setdefault('setlist_data', {}).setdefault('Breaking Benjamin', {})

# We inject it as the main setlist
bb["setlist_titles"] = songs
bb["scores"] = {s: 1.0 for s in songs}
bb["badges"] = {s: "setlist" for s in songs}

# clear out 'Dark' if it exists anywhere
if "Dark" in bb.get("scores", {}): del bb["scores"]["Dark"]
if "Dark" in bb.get("badges", {}): del bb["badges"]["Dark"]
if "Dark" in bb.get("spotify_uris", {}): del bb["spotify_uris"]["Dark"]

with open('concert_data.json', 'w', encoding='utf-8') as f:
    json.dump(cd, f, indent=4, ensure_ascii=False)
    
print("Successfully injected 18 songs into Breaking Benjamin's concert_data.json")
