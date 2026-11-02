import os
from setlist_client import SetlistClient
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SETLISTFM_API_KEY")
client = SetlistClient(api_key)

tours = client.get_tour_options("Breaking Benjamin")
print("Tours:", tours)

active = tours.get("active_tour")
if active:
    print(f"Fetching ordered for active tour: {active['name']}")
    res = client.get_setlist_ordered("Breaking Benjamin", tour_name=active["name"], num_concerts=20)
    print("Ordered length:", len(res["ordered"]))
    print("Mode used:", res["mode_used"])
    print("Concerts analyzed:", res["concerts_analyzed"])

print("Done")
