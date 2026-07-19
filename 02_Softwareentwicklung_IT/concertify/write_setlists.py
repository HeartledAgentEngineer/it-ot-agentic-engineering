import json, os
from pathlib import Path

data_file = Path("concert_data.json")
cd = json.loads(data_file.read_text(encoding="utf-8"))
sd = cd.setdefault("setlist_data", {})

def make_entry(songs_ordered, scores, artist=None, set_type="__festival__",
               play_counts=None, positions=None, total_concerts=0,
               positions_hist=None):
    badges = {s: "setlist" for s in scores}
    existing_uris = {}
    if artist and artist in sd:
        existing_uris = sd[artist].get("spotify_uris", {})
    pos_hist = positions_hist or {}
    # positions (avg) aus hist ableiten wenn vorhanden, sonst Fallback
    if pos_hist:
        pos = {s: sum(int(k) * v for k, v in d.items()) / sum(d.values())
               for s, d in pos_hist.items()}
    elif positions:
        pos = positions
    else:
        pos = {s: float(i + 1) for i, s in enumerate(songs_ordered)}
    return {
        "setlist_titles": songs_ordered,
        "new_titles": [],
        "spotify_uris": existing_uris,
        "scores": scores,
        "badges": badges,
        "set_type": set_type,
        "play_counts": play_counts or {},
        "positions": pos,
        "positions_hist": pos_hist,
        "total_concerts_analyzed": total_concerts,
    }


# ── Linkin Park — From Zero World Tour (83 Konzerte) ─────────────────────────
# Quelle: setlist.fm stats, tour=33dc2cf1
lp_total = 83
lp_order = [
    "Somewhere I Belong", "Lying From You", "Up From the Bottom",
    "Points of Authority", "New Divide", "The Emptiness Machine",
    "Over Each Other", "The Catalyst", "Burn It Down",
    "Castle of Glass", "Where'd You Go", "Waiting for the End",
    "From the Inside", "Two Faced", "Empty Spaces",
    "When They Come for Me", "One Step Closer", "Break/Collapse",
    "Lost", "Leave Out All the Rest", "What I've Done",
    "Kintsugi", "Overflow", "Numb", "In the End",
    "Faint", "Papercut", "Heavy Is the Crown", "Bleed It Out",
    "Crawling", "A Place for My Head", "Keys to the Kingdom", "Good Things Go",
]
lp_play_counts = {
    # Fixe Songs (jeden Abend gespielt)
    "Somewhere I Belong": 83, "Up From the Bottom": 83,
    "The Emptiness Machine": 83, "The Catalyst": 83, "Burn It Down": 83,
    "Where'd You Go": 83, "Waiting for the End": 83, "From the Inside": 83,
    "Two Faced": 83, "Empty Spaces": 83, "When They Come for Me": 83,
    "One Step Closer": 83, "Break/Collapse": 83, "Lost": 83,
    "What I've Done": 83, "Kintsugi": 83, "Overflow": 83,
    "Numb": 83, "In the End": 83,
    # Häufig
    "Lying From You": 75, "Over Each Other": 70,
    "Heavy Is the Crown": 65, "Points of Authority": 65,
    "Papercut": 70, "Bleed It Out": 62, "Faint": 60,
    # Wechselnd
    "Castle of Glass": 60, "New Divide": 55,
    "Leave Out All the Rest": 50,
    # Selten
    "Crawling": 25, "A Place for My Head": 20,
    "Keys to the Kingdom": 20, "Good Things Go": 20,
}
lp_scores = {s: round(lp_play_counts[s] / lp_total, 2) for s in lp_order}
sd["Linkin Park"] = make_entry(
    lp_order, lp_scores, artist="Linkin Park",
    set_type="From Zero Tour",
    play_counts=lp_play_counts, total_concerts=lp_total,
)


# ── Papa Roach — Rise of the Roach Tour 2025 (76 Konzerte) ───────────────────
# Quelle: setlist.fm stats 2025
pr_total = 76
pr_order = [
    "Even If It Kills Me", "Blood Brothers", "Dead Cell",
    "...To Be Loved", "Kill the Noise", "Getting Away With Murder",
    "California Love", "Liar", "Falling Apart",
    "Leave a Light On (Talk Away the Dark)", "Scars", "Help",
    "BRAINDEAD", "Between Angels and Insects",
    "Nu-Metal Time Machine Medley", "Born for Greatness", "Last Resort",
]
pr_play_counts = {
    "Even If It Kills Me": 76, "Blood Brothers": 76, "Dead Cell": 76,
    "...To Be Loved": 76, "Kill the Noise": 76, "Getting Away With Murder": 76,
    "California Love": 76, "Liar": 76, "Falling Apart": 76,
    "Leave a Light On (Talk Away the Dark)": 76, "Scars": 76, "Help": 76,
    "BRAINDEAD": 76, "Between Angels and Insects": 76,
    "Nu-Metal Time Machine Medley": 72, "Born for Greatness": 65, "Last Resort": 76,
}
pr_scores = {s: round(pr_play_counts[s] / pr_total, 2) for s in pr_order}
sd["Papa Roach"] = make_entry(
    pr_order, pr_scores, artist="Papa Roach",
    set_type="2026 Tour",
    play_counts=pr_play_counts, total_concerts=pr_total,
)


# ── Limp Bizkit — Festival-Set (1 Konzert, Hauptdaten aus Tour-Archiv) ────────
lb_order = [
    "Drown", "Break Stuff", "Master of Puppets", "Hot Dog",
    "Show Me What You Got", "My Generation", "Livin' It Up",
    "Walk", "My Way", "Rollin' (Air Raid Vehicle)",
    "Proud Mary", "Re-Arranged", "Behind Blue Eyes", "Eat You Alive",
    "Nookie", "Full Nelson", "Boiler",
    "Careless Whisper", "Faith", "Take a Look Around",
    "Don't Stop Believin'",
]
sd["Limp Bizkit"] = make_entry(
    lb_order, {s: 1.0 for s in lb_order},
    artist="Limp Bizkit", set_type="__festival__",
)


# ── Three Days Grace — RiP Festival-Set ~75 min (~15 Songs) ──────────────────
# Alienation Tour hat 23 Songs, Festival-Slot ~75 min = ca. 15 Kernhits
tdg_order = [
    "Dominate", "Animal I Have Become", "So Called Life", "Break",
    "Home", "The Mountain", "Pain", "Kill Me Fast",
    "I Hate Everything About You", "I Am Machine", "Time of Dying",
    "Mayday", "The Good Life", "Never Too Late", "Riot",
]
tdg_scores = {s: 1.0 for s in tdg_order}
sd["Three Days Grace"] = make_entry(
    tdg_order, tdg_scores, artist="Three Days Grace",
    set_type="__festival__",
)


# ── Hollywood Undead — (2 Konzerte, Best-of) ─────────────────────────────────
hu_order = [
    "CHAOS", "Riot", "Comin' in Hot", "SAVIOR", "Day of the Dead",
    "Another Way Out", "Bullet", "Undead", "Everywhere I Go", "Sweet Caroline",
]
hu_scores = {s: 1.0 for s in hu_order[:-1]}
hu_scores["Sweet Caroline"] = 0.5
sd["Hollywood Undead"] = make_entry(
    hu_order, hu_scores, artist="Hollywood Undead", set_type="__festival__",
)


# ── Breaking Benjamin — Awaken the Fallen Tour 2025 (44 Konzerte) ────────────
# Quelle: setlist.fm stats year=2025 — ALLE Songs 44/44, konsistente Setlist
bb_total = 44
bb_order = [
    "Awaken", "Follow", "Blow Me Away", "Failure",
    "Evil Angel", "You", "So Cold", "Red Cold River",
    "Until the End", "Dance With the Devil", "Blood",
    "Dear Agony", "Polyamorous", "Without You",
    "Breath", "I Will Not Bow", "The Diary of Jane",
]
bb_scores = {s: 1.0 for s in bb_order}
bb_play_counts = {s: 44 for s in bb_order}
sd["Breaking Benjamin"] = make_entry(
    bb_order, bb_scores, artist="Breaking Benjamin",
    set_type="Awaken the Fallen Tour",
    play_counts=bb_play_counts, total_concerts=bb_total,
)


# ── Within Temptation — Bleed Out Tour 2024 (2 Konzerte für uns) ─────────────
wt_scores = {
    "We Go to War": 1.0, "Faster": 1.0, "In the Middle of the Night": 1.0,
    "Stand My Ground": 1.0, "Bleed Out": 1.0, "Wireless": 1.0,
    "Lost": 1.0, "Paradise (What About Us?)": 1.0,
    "Ice Queen": 1.0, "Mother Earth": 1.0,
    "The Reckoning": 0.5, "What Have You Done": 0.5,
    "The Howling": 0.5, "Ritual": 0.5,
    "The Heart of Everything": 0.5, "Forsaken": 0.5,
    "Don't Pray for Me": 0.5,
}
wt_order = [
    "We Go to War", "Faster", "In the Middle of the Night",
    "Stand My Ground", "Bleed Out", "Wireless", "Lost",
    "The Reckoning", "Paradise (What About Us?)", "What Have You Done",
    "Ice Queen", "Mother Earth",
    "The Howling", "Ritual", "The Heart of Everything",
    "Forsaken", "Don't Pray for Me",
]
sd["Within Temptation"] = make_entry(
    wt_order, wt_scores, artist="Within Temptation", set_type="__festival__",
)


# ── Alter Bridge — What Lies Within Tour 2025 (2 Konzerte für uns) ───────────
ab_scores = {
    "Silent Divide": 1.0, "Addicted to Pain": 1.0, "Cry of Achilles": 1.0,
    "Fortress": 1.0, "Playing Aces": 1.0, "Burn It Down": 1.0,
    "Open Your Eyes": 1.0, "Broken Wings": 1.0, "Watch Over You": 1.0,
    "Tested and Able": 1.0, "Rise Today": 1.0, "Metalingus": 1.0,
    "Blackbird": 1.0, "Isolation": 1.0,
    "Silver Tongue": 0.5, "Ghost of Days Gone By": 0.5,
}
ab_order = [
    "Silent Divide", "Addicted to Pain", "Cry of Achilles", "Fortress",
    "Playing Aces", "Burn It Down", "Open Your Eyes", "Broken Wings",
    "Watch Over You", "Silver Tongue", "Tested and Able", "Rise Today",
    "Metalingus", "Blackbird", "Isolation", "Ghost of Days Gone By",
]
sd["Alter Bridge"] = make_entry(
    ab_order, ab_scores, artist="Alter Bridge",
    set_type="__festival__",
)


# ── H-Blockx — (2 Konzerte, Best-of) ─────────────────────────────────────────
hb_scores = {
    "Straight Outta Nowhere": 1.0, "How Do You Feel?": 1.0,
    "Countdown to Insanity": 1.0, "Can't Get Enough": 1.0,
    "Move": 1.0, "Desperado": 1.0, "Revolution": 1.0,
    "Leave Me Alone!": 1.0, "Lights Out": 1.0, "Pour Me a Glass": 1.0,
    "The Power": 1.0, "Little Girl": 1.0, "Risin' High": 1.0,
    "Corns About 2 Pop": 1.0, "Ring of Fire": 1.0,
    "Timeless": 0.5, "Me and My Horse": 0.5,
    "Licky Licky": 0.5, "Last Summer": 0.5,
}
hb_order = [
    "Straight Outta Nowhere", "How Do You Feel?", "Countdown to Insanity",
    "Timeless", "Me and My Horse", "Can't Get Enough", "Move",
    "Licky Licky", "Desperado", "Revolution", "Leave Me Alone!",
    "Lights Out", "Last Summer", "Pour Me a Glass", "Little Girl",
    "The Power", "Risin' High", "Corns About 2 Pop", "Ring of Fire",
]
sd["H-Blockx"] = make_entry(
    hb_order, hb_scores, artist="H-Blockx", set_type="__festival__",
)


# ── Bloodywood — (1 Konzert, unvollständig) ───────────────────────────────────
bw_order = ["Gaddaar", "Aaj", "Dana Dan", "Bekhauf", "Nu Delhi"]
sd["Bloodywood"] = make_entry(
    bw_order, {s: 1.0 for s in bw_order},
    artist="Bloodywood", set_type="__festival__",
)


# ── Bury Tomorrow — (2 Konzerte) ─────────────────────────────────────────────
bt_scores = {
    "Choke": 1.0, "Abandon Us": 1.0, "Let Go": 1.0,
    "Villain Arc": 1.0, "What If I Burn": 1.0,
    "Boltcutter": 1.0, "Black Flame": 1.0,
    "DEATH (Ever Colder)": 0.5, "Cannibal": 0.5,
}
bt_order = [
    "Choke", "DEATH (Ever Colder)", "Cannibal", "Boltcutter",
    "Let Go", "Villain Arc", "What If I Burn", "Black Flame", "Abandon Us",
]
sd["Bury Tomorrow"] = make_entry(
    bt_order, bt_scores, artist="Bury Tomorrow", set_type="__festival__",
)


# ── Social Distortion — (2 Konzerte) ─────────────────────────────────────────
socdi_scores = {
    "Born to Kill": 1.0, "Ring of Fire": 1.0, "Tonight": 1.0,
    "No Way Out": 1.0, "The Way Things Were": 1.0,
    "Reach for the Sky": 1.0, "Dear Lover": 1.0,
    "Bad Luck": 0.5, "Ball and Chain": 0.5, "Rebel Rebel": 0.5,
}
socdi_order = [
    "Born to Kill", "Ring of Fire", "Tonight", "No Way Out",
    "The Way Things Were", "Reach for the Sky", "Dear Lover",
    "Bad Luck", "Ball and Chain", "Rebel Rebel",
]
sd["Social Distortion"] = make_entry(
    socdi_order, socdi_scores, artist="Social Distortion", set_type="__festival__",
)


# ── The Story So Far — (1 Konzert) ───────────────────────────────────────────
tssf_order = [
    "Big Blind", "Roam", "Out of It", "Nothing to Say",
    "High Regard", "All This Time", "Watch You Go",
    "Things I Can't Change", "The Glass", "Letterman",
    "Proper Dose", "Keep This Up", "Empty Space", "Quicksand",
]
sd["The Story So Far"] = make_entry(
    tssf_order, {s: 1.0 for s in tssf_order},
    artist="The Story So Far", set_type="__festival__",
)


# ── Black Veil Brides — (1 Konzert, Madison WI Mai 2026) ─────────────────────
bvb_order = [
    "Knives and Pens", "Bleeders", "Coffin", "Rebel Love Song",
    "Hallelujah", "Faithless", "Wake Up", "Vindicate",
    "Certainty", "Beautiful Remains", "Carolyn", "Revenger",
    "Sweet Blasphemy", "The Legacy", "Perfect Weapon",
    "Lost It All", "Fallen Angels", "In the End",
]
sd["Black Veil Brides"] = make_entry(
    bvb_order, {s: 1.0 for s in bvb_order},
    artist="Black Veil Brides", set_type="__festival__",
)


# ── Bush — (1 Konzert, BottleRock Napa 2026) ──────────────────────────────────
bush_order = [
    "Machinehead", "60 Ways to Forget People", "More Than Machines",
    "Everything Zen", "Swallowed", "The Land of Milk and Honey",
    "Flowers on a Grave", "Little Things", "Glycerine", "Comedown",
]
sd["Bush"] = make_entry(
    bush_order, {s: 1.0 for s in bush_order},
    artist="Bush", set_type="__concert__",
)


# ── Ankor — Rock im Park Festival-Set (~7 Songs) ──────────────────────────────
ankor_order = [
    "Darkbeat", "Embers", "Venom", "Stereo",
    "MADARA · endless dream", "Danzo · Lying Ghost", "Prisoner",
]
sd["Ankor"] = make_entry(
    ankor_order, {s: 1.0 for s in ankor_order},
    artist="Ankor", set_type="__festival__",
)


# ── TX2 — Rock im Park Festival-Set (~8 Songs) ────────────────────────────────
tx2_order = [
    "Feed", "Vendetta", "HOSTAGE (they will not erase us)",
    "So Numb", "The End of Us", "Confession", "MAD", "I Would Hate Me Too",
]
sd["TX2"] = make_entry(
    tx2_order, {s: 1.0 for s in tx2_order},
    artist="TX2", set_type="__festival__",
)


# Speichern
tmp = data_file.with_suffix(".tmp")
tmp.write_text(json.dumps(cd, ensure_ascii=False, indent=2), encoding="utf-8")
os.replace(tmp, data_file)

print(f"OK - {len(sd)} Kuenstler in setlist_data:")
for a in sorted(sd.keys()):
    n   = len(sd[a]["setlist_titles"])
    tot = sd[a].get("total_concerts_analyzed", 0)
    st  = sd[a].get("set_type", "?")
    src = f"{tot} Konzerte" if tot else "geschaetzt"
    print(f"  {a}: {n} Songs | {st} | {src}")
