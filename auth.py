#!/usr/bin/env python3
"""YouTube-kirjautuminen omalla koneella GitHub Actions -asennusta varten.

Kirjoittaa token.json:n nykyiseen hakemistoon. Tarvitsee client_secret.json:n
samasta hakemistosta ja kirjaston google-auth-oauthlib. 

Käyttö: python auth.py [--port N]
"""
import argparse

from google_auth_oauthlib.flow import InstalledAppFlow

# Sama kuin yt_chapters.py:n SCOPES. Jos muutat toista, muuta myös toinen.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8765)
args = ap.parse_args()

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(host="localhost", port=args.port, open_browser=False,
                              access_type="offline", prompt="consent")
with open("token.json", "w") as f:
    f.write(creds.to_json())
print("Token tallennettu: token.json")
