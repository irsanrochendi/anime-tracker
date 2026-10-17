"""Logika murni (tanpa UI / network): parsing episode dan status update sebuah show."""
import datetime
import re
from dataclasses import dataclass

# Jenis status update, diurutkan dari yang paling butuh perhatian.
NEW = "new"                          # ada episode baru yang belum ditonton
FINISHED_NOT_DONE = "finished_not_done"  # tamat tayang tapi kamu belum selesai
UNRELEASED = "unreleased"            # movie belum rilis
RELEASED = "released"                # movie sudah rilis, belum ditonton
UP_TO_DATE = "up_to_date"
DONE = "done"
NONE = "none"                        # belum terhubung / belum pernah dicek

PRIORITY = {NEW: 0, FINISHED_NOT_DONE: 1, RELEASED: 2, UNRELEASED: 3, UP_TO_DATE: 4, DONE: 5, NONE: 6}


def parse_ep_num(ep_str):
    """'Update to EP 1174' -> 1174, 'EP 12' -> 12, 'Full' -> 0."""
    if not ep_str:
        return 0
    match = re.search(r'(?:EP|Ep|E)\s*(\d+)', ep_str) or re.search(r'(\d+)', ep_str)
    return int(match.group(1)) if match else 0


def is_finished_airing(ep_str):
    """
    Bilibili: kalau masih on-going index_show berisi 'Update to EP N' / 'EP N'.
    Kalau sudah tamat jadi 'Full' (tanpa angka episode).
    """
    if not ep_str:
        return False
    s = ep_str.strip().lower()
    return "full" in s and not re.search(r'\d', s)


def is_newer(a_season, a_ep, b_season, b_ep):
    """(a_season, a_ep) lebih baru dari (b_season, b_ep)? Season None = bandingkan episode saja."""
    a_ep, b_ep = a_ep or 0, b_ep or 0
    if a_season is not None and b_season is not None:
        return (a_season, a_ep) > (b_season, b_ep)
    return a_ep > b_ep


def latest_numbers(show):
    """(season, episode) terbaru yang diketahui dari sumber, atau (None, None)."""
    if show.get("tmdb_id"):
        if show.get("latest_ep") is None:
            return None, None
        return show.get("latest_season"), show.get("latest_ep")
    if show.get("bilibili_season_id") and show.get("latest_episode_str"):
        # Bilibili: tiap season punya season_id sendiri, jadi hanya episode yang dibandingkan.
        return None, parse_ep_num(show["latest_episode_str"])
    return None, None


def _is_ended(show):
    if show.get("airing_ended") is not None:
        return bool(show["airing_ended"])
    return is_finished_airing(show.get("latest_episode_str"))


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value) if value else None
    except ValueError:
        return None


@dataclass
class UpdateState:
    kind: str
    label: str


def compute_state(show, today=None):
    today = today or datetime.date.today()
    status = (show.get("status") or "").strip().lower()
    season = show.get("season") or 0
    episode = show.get("episode") or 0

    # Movie dari TMDB: tidak ada episode, yang dilacak tanggal rilis.
    if show.get("tmdb_id") and show.get("tmdb_media") == "movie":
        release = _parse_date(show.get("release_date"))
        if status == "completed":
            return UpdateState(DONE, "✔ Sudah ditonton")
        if release and release > today:
            return UpdateState(UNRELEASED, f"📅 Rilis {release.strftime('%d %b %Y')}")
        if release:
            return UpdateState(RELEASED, f"🎬 Sudah rilis ({release.year})")
        return UpdateState(NONE, "Belum ada info rilis")

    latest_season, latest_ep = latest_numbers(show)
    if latest_ep is None:
        return UpdateState(NONE, "Belum terhubung" if not (show.get("tmdb_id") or show.get("bilibili_season_id"))
                           else "Belum dicek")

    is_tmdb = bool(show.get("tmdb_id"))
    user_season = season if is_tmdb else None
    ended = _is_ended(show)
    where = f"S{latest_season} EP {latest_ep}" if latest_season is not None else f"EP {latest_ep}"

    if latest_ep and is_newer(latest_season, latest_ep, user_season, episode):
        return UpdateState(NEW, f"🔴 Baru: {where}")

    if ended:
        if status == "completed":
            return UpdateState(DONE, "🏁 Tamat — selesai ditonton")
        if is_tmdb:
            # TMDB tahu jumlah episode: kalau sudah sampai episode terakhir berarti sudah selesai.
            return UpdateState(DONE, f"🏁 Tamat — kamu sudah di {where}")
        # Bilibili 'Full' tidak menyebut angka episode, jadi belum tentu kamu sudah selesai.
        return UpdateState(FINISHED_NOT_DONE, f"🏁 Tamat tayang — kamu di EP {episode}")

    next_air = _parse_date(show.get("release_date")) if is_tmdb else None
    if next_air and next_air >= today:
        return UpdateState(UP_TO_DATE, f"✅ Up-to-date · berikutnya {next_air.strftime('%d %b')}")
    return UpdateState(UP_TO_DATE, f"✅ Up-to-date ({where})")


def should_notify(old_show, remote, user_status):
    """
    Notifikasi hanya kalau episode terbaru NAIK sejak cek terakhir dan masih lebih baru
    dari episode yang kamu tonton — supaya tidak spam tiap app dibuka.
    """
    if (user_status or "") != "Watching" or remote.get("latest_ep") is None:
        return False
    new_s, new_e = remote.get("latest_season"), remote.get("latest_ep")
    old_s, old_e = latest_numbers(old_show)
    is_tmdb = bool(old_show.get("tmdb_id"))
    user_s = old_show.get("season") if is_tmdb else None
    if not is_tmdb:
        new_s = old_s = None
    # Cek pertama setelah menautkan sumber tidak dinotifikasi: hasilnya langsung terlihat di daftar.
    went_up = old_e is not None and is_newer(new_s, new_e, old_s, old_e)
    return went_up and is_newer(new_s, new_e, user_s, old_show.get("episode") or 0)


@dataclass
class WatchPlan:
    kind: str          # 'open' | 'finished' | 'not_yet' | 'error'
    episode: int       # episode yang mau ditonton (episode terakhir + 1)
    url: str = None
    last_available: int = 0


def plan_next_episode(show, episodes):
    """
    Tentukan aksi tombol Nonton dari daftar episode Bilibili ({nomor: url}, None = gagal fetch).
    Tidak pernah membuka episode lain selain episode berikutnya.
    """
    next_ep = (show.get("episode") or 0) + 1
    if episodes is None:
        return WatchPlan("error", next_ep)
    last = max(episodes) if episodes else 0
    if next_ep in episodes:
        return WatchPlan("open", next_ep, episodes[next_ep], last)
    if _is_ended(show) and next_ep > last:
        return WatchPlan("finished", next_ep, last_available=last)
    return WatchPlan("not_yet", next_ep, last_available=last)
