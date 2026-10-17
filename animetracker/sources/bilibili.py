"""Bilibili International (Bstation) web API."""
import re

import requests

from ..config import UA
from ..logic import is_finished_airing, parse_ep_num
from . import SearchResult, SourceError

API = "https://api.bilibili.tv/intl/gateway/web/v2"
TIMEOUT = 10


def _headers(referer="https://www.bilibili.tv/"):
    return {"User-Agent": UA, "Referer": referer}


def page_url(season_id):
    return f"https://www.bilibili.tv/en/play/{season_id}"


def _raw_search(keyword, page_size=15):
    params = {"s_locale": "en_US", "platform": "web", "keyword": keyword, "pn": 1, "ps": page_size}
    res = requests.get(f"{API}/search_v2", headers=_headers(), params=params, timeout=TIMEOUT)
    if res.status_code != 200:
        raise SourceError(f"Bilibili API error {res.status_code}")
    seasons = []
    for mod in (res.json().get("data") or {}).get("modules") or []:
        # Tipe modul berubah-ubah ('ogv', 'ogv_subject', 'all'); 'ugc' = video upload user.
        mtype = mod.get("type") or ""
        if not (mtype.startswith("ogv") or mtype == "all"):
            continue
        for it in mod.get("items") or []:
            for s in (it.get("seasons") or [it]) if "seasons" in it else [it]:
                if s.get("season_id"):
                    seasons.append(s)
    return seasons


def search(keyword):
    results, seen = [], set()
    for s in _raw_search(keyword):
        sid = str(s["season_id"])
        if sid in seen:
            continue
        seen.add(sid)
        stype = s.get("season_type") or "Anime"
        results.append(SearchResult(
            source="bilibili", remote_id=sid, title=s.get("title") or "",
            subtitle=f"{s.get('index_show') or 'N/A'} · {stype}",
            poster_url=s.get("cover"),
            type_guess="Anime" if stype.lower() == "anime" else ("Movie" if "movie" in stype.lower() else "Series"),
        ))
    return results


def _remote_info(index_show, cover):
    return {
        "latest_episode_str": index_show,
        "latest_season": None,
        "latest_ep": parse_ep_num(index_show),
        "airing_ended": 1 if is_finished_airing(index_show) else 0,
        "poster_url": cover,
    }


def fetch_latest(season_id, title):
    """
    Status episode terbaru untuk season_id. Endpoint /ogv/play/series sering mengembalikan
    cards:null, jadi strategi utama pakai search API lalu cocokkan season_id-nya.
    Return dict untuk db.save_remote_state, atau None kalau gagal.
    """
    try:
        for s in _raw_search(title):
            if str(s.get("season_id")) == str(season_id) and s.get("index_show"):
                return _remote_info(s["index_show"], s.get("cover"))
    except (requests.RequestException, ValueError, SourceError):
        pass

    try:
        params = {"s_locale": "en_US", "platform": "web", "season_id": season_id}
        res = requests.get(f"{API}/ogv/play/series", params=params, timeout=TIMEOUT,
                           headers=_headers(f"https://www.bilibili.tv/play/{season_id}"))
        if res.status_code == 200:
            for c in (res.json().get("data") or {}).get("cards") or []:
                if str(c.get("season_id")) == str(season_id) and c.get("index_show"):
                    return _remote_info(c["index_show"], c.get("cover"))
    except (requests.RequestException, ValueError):
        pass
    return None


# 'E12', 'EP 12', '12' — bukan 'PV', 'PV 2', 'SP1' dsb.
_EP_LABEL = re.compile(r'^(?:EP?|Episode)?\s*(\d+)$', re.IGNORECASE)


def list_episodes(season_id):
    """
    {nomor episode: link nonton} untuk satu season, atau None kalau request gagal
    (dibedakan dari {} = request berhasil tapi tidak ada episode bernomor).
    """
    try:
        params = {"s_locale": "en_US", "platform": "web", "season_id": season_id}
        res = requests.get(f"{API}/ogv/play/episodes", params=params, timeout=TIMEOUT,
                           headers=_headers(f"https://www.bilibili.tv/play/{season_id}"))
        if res.status_code != 200:
            return None
        episodes = {}
        for sec in (res.json().get("data") or {}).get("sections") or []:
            for ep in sec.get("episodes") or []:
                m = _EP_LABEL.match((ep.get("short_title_display") or "").strip())
                if m and ep.get("episode_id"):
                    episodes.setdefault(int(m.group(1)), f"{page_url(season_id)}/{ep['episode_id']}")
        return episodes
    except (requests.RequestException, ValueError):
        return None
