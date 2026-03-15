import os
import time
import requests


class SpotifyClient:
    def __init__(self):
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.base_url = "https://api.spotify.com/v1"
        self.token_url = "https://accounts.spotify.com/api/token"

        if not self.client_id or not self.client_secret:
            raise ValueError(
                "SPOTIFY_CLIENT_ID and/or SPOTIFY_CLIENT_SECRET environment variable not set."
            )

        self._access_token = None
        self._token_expires_at = 0

    def _get_access_token(self) -> str:
        # Reuse token until shortly before expiry
        if self._access_token and time.time() < (self._token_expires_at - 30):
            return self._access_token

        response = requests.post(
            self.token_url,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=20,
        )
        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = time.time() + expires_in
        return self._access_token

    def get_new_releases(self, country="US", limit=5):
        token = self._get_access_token()
        # Use search endpoint with tag:new as fallback for browse/new-releases 403 error
        url = "https://api.spotify.com/v1/search"
        headers = {"Authorization": f"Bearer {token}"}

        # Search for new albums in the specified market
        params = {
            "q": "tag:new",
            "type": "album",
            "market": country,
            "limit": limit
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=20)
            response.raise_for_status()

            # response structure for search is { "albums": { "items": [...] } }
            albums = response.json().get("albums", {}).get("items", [])
            releases = []
            for album in albums:
                releases.append(
                    {
                        "id": album.get("id"),
                        "title": album.get("name"),
                        "artist": ", ".join(a.get("name", "") for a in album.get("artists", [])),
                        "release_date": album.get("release_date"),
                        "total_tracks": album.get("total_tracks"),
                        "external_url": album.get("external_urls", {}).get("spotify")
                    }
                )
            return releases
        except Exception as e:
            print(f"Error fetching new releases from Spotify: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return []


