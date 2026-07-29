import os

# Telegram API Credentials
API_ID = int(os.environ.get("API_ID", 25461006))
API_HASH = os.environ.get("API_HASH", "be4d9b5dc42758bccb2087b071738359")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8960153668:AAFkfbBTxjrTuHdEOoOiZrMWpRroqprTqfk")
STRING_SESSION = os.environ.get("STRING_SESSION", "")  # Userbot Pyrogram String Session

# Spotify Web API (metadata/search only — https://developer.spotify.com/dashboard)
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

# Admin & System Settings
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8100453801))
CACHE_DIR = "./cache"
DEVELOPED_BY = "@Dev_Null_X"
COMMUNITY = "Node.js India Developers"
