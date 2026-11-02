import json

with open("concert_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Fix Breaking Benjamin Hamburg Venue
if "Breaking Benjamin" in data.get("hamburg_artists", {}):
    data["hamburg_artists"]["Breaking Benjamin"]["venue"] = "Inselpark Arena"
    # the 'venues' dict maps date -> venue
    if "2026-06-15" in data["hamburg_artists"]["Breaking Benjamin"].get("venues", {}):
        data["hamburg_artists"]["Breaking Benjamin"]["venues"]["2026-06-15"] = "Inselpark Arena"

# Fix Breaking Benjamin Support Act
if "Breaking Benjamin" in data.get("support_acts", {}):
    if "2026-06-15" in data["support_acts"]["Breaking Benjamin"]:
        supports = data["support_acts"]["Breaking Benjamin"]["2026-06-15"]
        if "Chevelle" in supports:
            supports.remove("Chevelle")
            print("Removed Chevelle from support acts.")

with open("concert_data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Updated concert_data.json")
