"""Cek update episode ke Bilibili / TMDB di background dan kirim notifikasi Windows."""
import threading
import time

from . import db, logic
from .sources import SourceError, bilibili, tmdb

try:
    from win11toast import notify as _toast
    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False

CHECK_STATUSES = ("Watching", "Plan to Watch")


def send_toast(title, body, url=None):
    if not HAS_TOAST:
        return
    try:
        _toast(title, body, on_click=url or (lambda *_: None), app_id="Anime & Show Tracker")
    except Exception:
        # Notifikasi gagal tidak boleh menghentikan pengecekan.
        pass


class UpdateChecker:
    def __init__(self, settings, on_changed):
        self.settings = settings
        self.on_changed = on_changed   # dipanggil (dari thread worker) setelah DB berubah
        self._lock = threading.Lock()  # satu pengecekan penuh dalam satu waktu
        self._stop = threading.Event()
        self._wake = threading.Event()
        self.last_check = None

    # ── satu show ────────────────────────────────────────────────────────────
    def fetch_remote(self, show):
        if show.get("tmdb_id") and show.get("tmdb_media"):
            return tmdb.fetch_details(show["tmdb_media"], show["tmdb_id"],
                                      self.settings.get("tmdb_api_key"), self.settings.get("tmdb_language"))
        if show.get("bilibili_season_id"):
            return bilibili.fetch_latest(show["bilibili_season_id"], show["title"])
        return None

    def check_show(self, show, notify=True):
        """Return True kalau show ini punya episode baru yang dinotifikasi."""
        try:
            remote = self.fetch_remote(show)
        except SourceError:
            return False
        if not remote:
            return False
        remote = dict(remote, last_checked=time.strftime("%Y-%m-%d %H:%M:%S"))
        if not remote.get("poster_url"):
            remote.pop("poster_url", None)   # jangan hapus poster lama kalau sumber tidak kirim cover
        db.save_remote_state(show["id"], remote)

        if notify and self.settings.get("notifications") and logic.should_notify(show, remote, show.get("status")):
            if show.get("tmdb_id"):
                url = tmdb.page_url(show["tmdb_media"], show["tmdb_id"])
            else:
                url = bilibili.page_url(show["bilibili_season_id"])
            send_toast("Episode baru!",
                       f"{show['title']}: {remote['latest_episode_str']}\n(Kamu di S{show.get('season')} EP {show.get('episode')})",
                       url)
            return True
        return False

    def check_show_async(self, show_id):
        def run():
            show = db.get_show(show_id)
            if show:
                self.check_show(show, notify=False)
                self.on_changed()
        threading.Thread(target=run, daemon=True).start()

    # ── semua show ───────────────────────────────────────────────────────────
    def check_all(self):
        """Return ringkasan: dict(checked, new=[judul], finished=[(judul, ep)])."""
        with self._lock:
            shows = [s for s in db.list_shows()
                     if s.get("status") in CHECK_STATUSES and (s.get("bilibili_season_id") or s.get("tmdb_id"))]
            for show in shows:
                try:
                    self.check_show(show)
                except Exception:
                    # Satu show bermasalah tidak boleh menghentikan pengecekan yang lain.
                    continue
            self.last_check = time.strftime("%H:%M")
            self.on_changed()

            new, finished = [], []
            for s in db.list_shows():
                state = logic.compute_state(s)
                if s.get("status") == "Watching" and state.kind == logic.NEW:
                    new.append(s["title"])
                elif state.kind == logic.FINISHED_NOT_DONE:
                    finished.append((s["title"], s.get("episode") or 0))
            return {"checked": len(shows), "new": new, "finished": finished}

    def start_periodic(self):
        def loop():
            while not self._stop.is_set():
                try:
                    self.check_all()
                except Exception:
                    pass
                minutes = max(5, int(self.settings.get("check_interval_min") or 30))
                self._wake.wait(minutes * 60)
                self._wake.clear()
        threading.Thread(target=loop, daemon=True, name="update-checker").start()

    def reschedule(self):
        """Interval diubah di pengaturan: jalankan siklus berikutnya sekarang."""
        self._wake.set()

    def stop(self):
        self._stop.set()
        self._wake.set()
