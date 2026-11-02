import urllib.request, json
from dotenv import dotenv_values

env = dotenv_values('.env')
req = urllib.request.Request('https://api.setlist.fm/rest/1.0/search/setlists?artistName=Breaking%20Benjamin&cityName=Leipzig', headers={'x-api-key': env.get('SETLISTFM_API_KEY', ''), 'Accept': 'application/json'})
try:
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode('utf-8'))
        for sl in data.get('setlist', []):
            print(f"Date: {sl.get('eventDate')} Venue: {sl.get('venue', {}).get('name')}")
            for st in sl.get('sets', {}).get('set', []):
                for song in st.get('song', []):
                    if song.get('name'):
                        print(song.get('name'))
except Exception as e:
    print('ERROR:', e)
