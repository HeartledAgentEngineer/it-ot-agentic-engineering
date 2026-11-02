import json, os
from pathlib import Path

data_file = Path("concert_data.json")
cd = json.loads(data_file.read_text(encoding="utf-8"))
sd = cd.setdefault("setlist_data", {})

def make_entry(songs_ordered, scores, artist=None):
    badges = {s: "setlist" for s in scores}
    existing_uris = {}
    if artist and artist in sd:
        existing_uris = sd[artist].get("spotify_uris", {})
    return {
        "setlist_titles": songs_ordered,
        "new_titles": [],
        "spotify_uris": existing_uris,
        "scores": scores,
        "badges": badges,
        "set_type": "__festival__",
    }

# ── Three Days Grace: Sonic Temple 2025 (50 min, 12 Songs) ──────────────
# Nicht die 23-Song Alienation-Tour, sondern echtes Festival-Set
tdg_festival = [
    "Animal I Have Become",   # Immer dabei, Kernhit
    "So Called Life",
    "Break",
    "I Am Machine",
    "The Mountain",
    "Mayday",
    "I Hate Everything About You",  # Top-Hit, immer im Festival-Set
    "The Good Life",
    "Painkiller",
    "Never Too Late",
    "Riot",
    "It's All Over",          # Sonic Temple Opener
    "Home",                   # Sonic Temple
    "Pain",                   # Klassiker, oft dabei
    "Time of Dying",
    "World So Cold",
    "Just Like You",
]
# Frequenz: Core-Festival-Hits (aus Sonic Temple) = 1.0, Bonus-Klassiker = 0.75
tdg_scores = {
    "Animal I Have Become": 1.0,
    "So Called Life": 1.0,
    "Break": 1.0,
    "I Am Machine": 1.0,
    "The Mountain": 1.0,
    "Mayday": 1.0,
    "I Hate Everything About You": 1.0,
    "The Good Life": 1.0,
    "Painkiller": 1.0,
    "Never Too Late": 1.0,
    "Riot": 1.0,
    "It's All Over": 0.75,
    "Home": 0.75,
    "Pain": 0.75,
    "Time of Dying": 0.75,
    "World So Cold": 0.75,
    "Just Like You": 0.75,
}
sd["Three Days Grace"] = make_entry(tdg_festival, tdg_scores, artist="Three Days Grace")
print(f"Three Days Grace: {len(tdg_festival)} Songs (Festival-Set)")

# ── Alter Bridge: Download 2023 + Sweden Rock 2023 (10-12 Songs) ─────────
# Kein 15-Song Tour-Set, sondern echtes Festival-Format
ab_festival_scores = {
    "Silver Tongue": 1.0,        # beide Festivals
    "Addicted to Pain": 1.0,     # beide Festivals
    "Ghost of Days Gone By": 1.0,
    "Cry of Achilles": 1.0,
    "This Is War": 1.0,
    "Come to Life": 1.0,
    "Sin After Sin": 1.0,
    "Blackbird": 1.0,            # immer, der Signature-Song
    "Isolation": 1.0,
    "Metalingus": 1.0,           # Closer, immer dabei
    "Open Your Eyes": 0.5,       # nur Sweden Rock
    "Rise Today": 0.5,
    "Fortress": 0.5,             # gelegentlich im Festival-Set
    "Broken Wings": 0.5,
    "Watch Over You": 0.5,
}
ab_festival_order = [
    "Silver Tongue", "Addicted to Pain", "Ghost of Days Gone By",
    "Cry of Achilles", "This Is War", "Come to Life", "Sin After Sin",
    "Open Your Eyes", "Broken Wings", "Watch Over You",
    "Blackbird", "Isolation", "Metalingus",
    "Rise Today", "Fortress",
]
sd["Alter Bridge"] = make_entry(ab_festival_order, ab_festival_scores, artist="Alter Bridge")
print(f"Alter Bridge: {len(ab_festival_order)} Songs (Festival-Set, Download+Sweden Rock)")

# ── Limp Bizkit: Leeds Festival 2025 + Reading Festival 2025 ─────────────
# Nicht das 21-Song Headline-Konzert aus Brasilien
lb_fest_scores = {
    "Break Stuff": 1.0,          # beide Festivals, oft 2x gespielt
    "Hot Dog": 1.0,
    "My Generation": 1.0,
    "Hip Hop Hooray": 1.0,       # (Naughty by Nature cover)
    "My Way": 1.0,
    "Rollin' (Air Raid Vehicle)": 1.0,
    "Nookie": 1.0,
    "Full Nelson": 1.0,
    "Take a Look Around": 1.0,
    "Show Me What You Got": 0.75,
    "Faith": 0.75,               # George Michael cover
    "Master of Puppets": 0.5,
    "Behind Blue Eyes": 0.5,
    "Don't Stop Believin'": 0.5,
    "Drown": 0.5,
    "Walk": 0.5,
    "Eat You Alive": 0.5,
}
lb_fest_order = [
    "Break Stuff", "Hot Dog", "Show Me What You Got", "My Generation",
    "Hip Hop Hooray", "My Way", "Rollin' (Air Raid Vehicle)",
    "Master of Puppets", "Nookie", "Full Nelson",
    "Behind Blue Eyes", "Eat You Alive",
    "Faith", "Take a Look Around", "Don't Stop Believin'",
    "Drown", "Walk",
]
sd["Limp Bizkit"] = make_entry(lb_fest_order, lb_fest_scores, artist="Limp Bizkit")
print(f"Limp Bizkit: {len(lb_fest_order)} Songs (Festival-Set, Leeds+Reading)")

# Speichern
tmp = data_file.with_suffix(".tmp")
tmp.write_text(json.dumps(cd, ensure_ascii=False, indent=2), encoding="utf-8")
os.replace(tmp, data_file)
print("Gespeichert.")
