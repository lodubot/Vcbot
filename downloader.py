import os
import yt_dlp
from config import CACHE_DIR
import db
import spotify

def clean_text(text: str) -> str:
    if not text:
        return "Unknown"
    return str(text).replace("`", "").replace("*", "").replace("_", "").replace("<", "").replace(">", "").strip()


def _find_audio_stream(search_target: str):
    """yt-dlp se sirf audio-stream URL nikalta hai, video download nahi karta."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'cookiefile': 'cookies.txt',
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'mweb', 'android']
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_target, download=False)
        if 'entries' in info and len(info['entries']) > 0:
            info = info['entries'][0]

        audio_url = None
        for f in info.get('formats', []):
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                audio_url = f.get('url')
                break
        if not audio_url:
            audio_url = info.get('url')

        return info, audio_url


def resolve_track(query: str, is_video: bool = False):
    """
    Flow:
      1) Spotify (link ya search) se accurate title/artist/thumbnail/duration lo.
      2) Us exact "title artist" se actual audio/video stream resolve karo.
         (Spotify khud full-length audio nahi deta, sirf metadata + 30s preview.)
      3) Agar Spotify match na mile ya /vplay ho, purana YouTube-direct flow chalta hai.
    """
    print(f"📡 Resolving track for: {query}")

    spotify_meta = None if is_video else spotify.resolve_query(query)

    try:
        if spotify_meta:
            search_target = f"ytsearch1:{spotify_meta['title']} {spotify_meta['artist']} audio"
        elif "youtube.com" in query or "youtu.be" in query:
            search_target = query
        else:
            search_target = f"ytsearch1:{query}"

        info, audio_url = _find_audio_stream(search_target)
        vid_id = info.get('id')

        if spotify_meta:
            song_data = {
                "id": spotify_meta["spotify_id"] or vid_id,
                "title": clean_text(spotify_meta["title"]),
                "artist": clean_text(spotify_meta["artist"]),
                "duration": spotify_meta["duration"] or info.get('duration', 0),
                "thumbnail": spotify_meta["thumbnail"] or info.get('thumbnail', ''),
                "local_path": audio_url,
                "is_video": False,
                "source": "spotify",
            }
        else:
            song_data = {
                "id": vid_id,
                "title": clean_text(info.get('title', 'Unknown Title')),
                "artist": clean_text(info.get('uploader', 'YouTube Artist')),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "local_path": audio_url,
                "is_video": is_video,
                "source": "youtube",
            }

        db.save_song(
            song_data["id"], song_data["title"], song_data["artist"],
            song_data["duration"], song_data["thumbnail"], song_data["local_path"]
        )
        return song_data

    except Exception as err:
        raise Exception(f"All Downloaders Failed: {err}")
