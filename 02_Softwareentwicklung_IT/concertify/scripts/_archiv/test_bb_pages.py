import os
from setlist_client import SetlistClient
from dotenv import load_dotenv

load_dotenv()
client = SetlistClient(os.getenv("SETLISTFM_API_KEY"))
mbid = client._find_mbid_candidates("Breaking Benjamin")[0]

for page in range(1, 6):
    resp = client.session.get(f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists", params={"p": page})
    data = resp.json().get("setlist", [])
    uk = 0
    awaken = 0
    for sl in data:
        t = sl.get("tour", {}).get("name", "")
        if t == "UK/ EU Tour 2026":
            uk += 1
        elif t == "Awaken The Fallen Tour":
            awaken += 1
    print(f"Page {page}: UK/EU={uk}, Awaken={awaken}")
