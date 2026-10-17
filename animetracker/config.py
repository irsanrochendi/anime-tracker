import json
import os
import sys
import threading

APP_NAME = "Anime & Show Tracker"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

TYPES = ["Anime", "Movie", "Series", "Lainnya"]
STATUSES = ["Watching", "Completed", "Plan to Watch", "Dropped"]


def _data_dir():
    # ANIME_TRACKER_DATA_DIR dipakai untuk testing agar tidak menyentuh DB asli.
    override = os.environ.get("ANIME_TRACKER_DATA_DIR")
    if override:
        os.makedirs(override, exist_ok=True)
        return override
    # Saat dibundel PyInstaller, __file__ ada di folder _MEI sementara (dihapus
    # setelah app ditutup), jadi data harus disimpan di sebelah .exe.
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DATA_DIR = _data_dir()
DB_FILE = os.path.join(DATA_DIR, "tracker_db.sqlite")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
POSTER_DIR = os.path.join(DATA_DIR, "posters")

DEFAULT_SETTINGS = {
    "tmdb_api_key": "",
    "tmdb_language": "en-US",
    "check_interval_min": 30,
    "notifications": True,
    "appearance": "Dark",
    "sort": "Update dulu",
}


class Settings:
    """settings.json di sebelah database. Thread-safe untuk get/set sederhana."""

    def __init__(self, path=SETTINGS_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._data = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                stored = json.load(f)
            if isinstance(stored, dict):
                self._data.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS})
        except (OSError, ValueError):
            pass

    def save(self):
        with self._lock:
            data = dict(self._data)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def get(self, key):
        with self._lock:
            return self._data.get(key, DEFAULT_SETTINGS.get(key))

    def update(self, **values):
        with self._lock:
            self._data.update(values)
        self.save()
