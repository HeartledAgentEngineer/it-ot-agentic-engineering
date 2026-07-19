import os
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import dotenv_values

env = dotenv_values('.env')
sp = Spotify(auth_manager=SpotifyClientCredentials(
    client_id=env.get('SPOTIFY_CLIENT_ID', ''),
    client_secret=env.get('SPOTIFY_CLIENT_SECRET', '')
))

print(sp.artist_top_tracks("53Hm23U3dtaHeB5Oy6GbaS", country="DE"))
