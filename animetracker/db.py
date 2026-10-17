import os
import shutil
import sqlite3
import time
from contextlib import contextmanager

from . import config

# Kolom tambahan versi 2. Ditambahkan lewat ALTER TABLE agar DB lama tetap terbaca.
NEW_COLUMNS = {
    "bilibili_season_id": "TEXT",
    "latest_episode_str": "TEXT",
    "tmdb_id": "TEXT",
    "tmdb_media": "TEXT",       # 'movie' | 'tv'
    "poster_url": "TEXT",
    "latest_season": "INTEGER",
    "latest_ep": "INTEGER",
    "airing_ended": "INTEGER",  # 1 = tamat tayang
    "release_date": "TEXT",     # movie: tanggal rilis, tv: tanggal episode berikutnya
    "created_at": "TEXT",
    "updated_at": "TEXT",
    "last_checked": "TEXT",
}

EDITABLE_FIELDS = ("title", "type", "season", "episode", "status", "notes",
                   "bilibili_season_id", "tmdb_id", "tmdb_media", "poster_url")

REMOTE_FIELDS = ("latest_episode_str", "latest_season", "latest_ep", "airing_ended",
                 "release_date", "poster_url", "last_checked")


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def connect(path=None):
    conn = sqlite3.connect(path or config.DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _tx():
    """Koneksi per operasi (aman dipakai dari thread mana pun), commit lalu tutup."""
    conn = connect()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(path=None):
    """Buat tabel / migrasi kolom. Sebelum migrasi, DB lama dibackup sekali."""
    path = path or config.DB_FILE
    conn = connect(path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                type TEXT DEFAULT 'Anime',
                season INTEGER DEFAULT 1,
                episode INTEGER DEFAULT 1,
                status TEXT DEFAULT 'Watching',
                notes TEXT
            )
        """)
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(shows)")}
        missing = [c for c in NEW_COLUMNS if c not in existing]
        has_rows = conn.execute("SELECT COUNT(*) FROM shows").fetchone()[0] > 0
        if missing and has_rows:
            conn.close()
            backup = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.copy2(path, backup)
            conn = connect(path)
        for col in missing:
            conn.execute(f"ALTER TABLE shows ADD COLUMN {col} {NEW_COLUMNS[col]}")
        conn.commit()
    finally:
        conn.close()


def list_shows():
    with _tx() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM shows ORDER BY id DESC")]


def get_show(show_id):
    with _tx() as conn:
        row = conn.execute("SELECT * FROM shows WHERE id=?", (show_id,)).fetchone()
        return dict(row) if row else None


def insert_show(data):
    fields = [f for f in EDITABLE_FIELDS if f in data]
    now = _now()
    cols = fields + ["created_at", "updated_at"]
    vals = [data[f] for f in fields] + [now, now]
    with _tx() as conn:
        cur = conn.execute(
            f"INSERT INTO shows ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)
        return cur.lastrowid


def update_show(show_id, data):
    fields = [f for f in EDITABLE_FIELDS if f in data]
    if not fields:
        return
    sets = ", ".join(f"{f}=?" for f in fields) + ", updated_at=?"
    with _tx() as conn:
        conn.execute(f"UPDATE shows SET {sets} WHERE id=?",
                     [data[f] for f in fields] + [_now(), show_id])


def clear_remote_state(show_id):
    """Dipanggil saat sumber data (Bilibili/TMDB) diganti atau dilepas."""
    with _tx() as conn:
        conn.execute("""UPDATE shows SET latest_episode_str=NULL, latest_season=NULL, latest_ep=NULL,
                        airing_ended=NULL, release_date=NULL, last_checked=NULL WHERE id=?""", (show_id,))


def save_remote_state(show_id, values):
    fields = [f for f in REMOTE_FIELDS if f in values]
    if not fields:
        return
    with _tx() as conn:
        conn.execute(f"UPDATE shows SET {', '.join(f'{f}=?' for f in fields)} WHERE id=?",
                     [values[f] for f in fields] + [show_id])


def adjust_number(show_id, field, delta):
    if field not in ("season", "episode"):
        raise ValueError(field)
    with _tx() as conn:
        conn.execute(f"UPDATE shows SET {field}=MAX(0, COALESCE({field}, 0) + ?), updated_at=? WHERE id=?",
                     (delta, _now(), show_id))


def delete_show(show_id):
    with _tx() as conn:
        conn.execute("DELETE FROM shows WHERE id=?", (show_id,))


def db_exists():
    return os.path.exists(config.DB_FILE)
