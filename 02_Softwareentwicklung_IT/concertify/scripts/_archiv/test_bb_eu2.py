import os
from setlist_client import SetlistClient
from dotenv import load_dotenv

load_dotenv()
client = SetlistClient(os.getenv("SETLISTFM_API_KEY"))
mbid = client._find_mbid_candidates("Breaking Benjamin")[0]
resp = client.session.get(f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists", params={"p": 1})
data = resp.json().get("setlist", [])

uk_stripped = 0
uk_unstripped = 0

for sl in data:
    t = sl.get("tour", {}).get("name", "")
    if "UK/ EU Tour 2026" in t:
        print(f"RAW TOUR NAME: '{t}' (Length: {len(t)})")
        if t == "UK/ EU Tour 2026":
            uk_unstripped += 1
        if t.strip() == "UK/ EU Tour 2026":
            uk_stripped += 1

print(f"Stripped: {uk_stripped}, Unstripped: {uk_unstripped}")
