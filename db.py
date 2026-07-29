import sqlite3
import os

DB_FILE = "music_cache.sqlite"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS music_cache (
            id TEXT PRIMARY KEY,
            title TEXT,
            artist TEXT,
            duration INTEGER,
            thumbnail TEXT,
            local_path TEXT,
            telegram_file_id TEXT,
            play_count INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_song(song_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM music_cache WHERE id = ?", (song_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def save_song(song_id, title, artist, duration, thumbnail, local_path):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO music_cache 
        (id, title, artist, duration, thumbnail, local_path, telegram_file_id, play_count)
        VALUES (?, ?, ?, ?, ?, ?, NULL, COALESCE((SELECT play_count FROM music_cache WHERE id = ?), 0))
    ''', (song_id, title, artist, duration, thumbnail, local_path, song_id))
    conn.commit()
    conn.close()

def increment_play_count(song_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE music_cache SET play_count = play_count + 1 WHERE id = ?", (song_id,))
    conn.commit()
    conn.close()

init_db()
