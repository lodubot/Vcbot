import time
import requests
import config

_token_cache = {"access_token": None, "expires_at": 0}


def _get_access_token():
    """
    Client Credentials flow — sirf metadata/search ke liye.
    Spotify full audio stream nahi deta, sirf token milta hai jo
    search + track-info endpoints access karne ke liye kaam aata hai.
    """
    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["access_token"]

    if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
        return None

    try:
        resp = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 3600)
        return _token_cache["access_token"]
    except Exception as e:
        print(f"⚠️ Spotify token error: {e}")
        return None


def _headers():
    token = _get_access_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def extract_track_id(url: str):
    # https://open.spotify.com/track/<id>?si=...
    if "open.spotify.com/track/" not in url:
        return None
    part = url.split("open.spotify.com/track/")[1]
    return part.split("?")[0].split("/")[0]


def get_track_by_id(track_id: str):
    headers = _headers()
    if not headers:
        return None
    try:
        resp = requests.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        return _format_track(resp.json())
    except Exception as e:
        print(f"⚠️ Spotify track fetch error: {e}")
        return None


def search_track(query: str):
    headers = _headers()
    if not headers:
        return None
    try:
        resp = requests.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params={"q": query, "type": "track", "limit": 1},
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("tracks", {}).get("items", [])
        if not items:
            return None
        return _format_track(items[0])
    except Exception as e:
        print(f"⚠️ Spotify search error: {e}")
        return None


def _format_track(track: dict):
    artists = ", ".join(a.get("name", "") for a in track.get("artists", []))
    images = track.get("album", {}).get("images", [])
    thumbnail = images[0]["url"] if images else ""
    return {
        "spotify_id": track.get("id"),
        "title": track.get("name", "Unknown Title"),
        "artist": artists or "Unknown Artist",
        "duration": round(track.get("duration_ms", 0) / 1000),
        "thumbnail": thumbnail,
        "preview_url": track.get("preview_url"),  # official 30s clip only
        "spotify_url": track.get("external_urls", {}).get("spotify", ""),
    }


def resolve_query(query: str):
    """
    Query ya to Spotify track link hai ya plain text search.
    Dono cases mein Spotify se accurate title/artist/thumbnail/duration
    metadata nikalta hai. Full audio stream Spotify se nahi milta —
    caller ko is metadata ke saath actual audio kahin aur se lena hoga.
    """
    track_id = extract_track_id(query)
    if track_id:
        return get_track_by_id(track_id)
    return search_track(query)
