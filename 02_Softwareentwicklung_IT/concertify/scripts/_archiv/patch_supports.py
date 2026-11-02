import json
import os

with open('concert_data.json', 'r', encoding='utf-8') as f:
    cd = json.load(f)

sa = cd.setdefault("support_acts", {})

# Clean up any bad keys
if "Breaking Benjamin|Hamburg" in sa:
    sa["Breaking Benjamin|Hamburg"] = ["Return To Dust"]
else:
    sa["Breaking Benjamin|Hamburg"] = ["Return To Dust"]

bb = sa.setdefault("Breaking Benjamin", {})
bb["2026-06-15"] = ["Return To Dust"]

with open('concert_data.json', 'w', encoding='utf-8') as f:
    json.dump(cd, f, indent=2)

print("Added Return To Dust to support acts")
