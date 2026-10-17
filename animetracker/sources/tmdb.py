"""The Movie Database (TMDB) API v3 — untuk movie & series di luar Bilibili.

Butuh API key gratis dari https://www.themoviedb.org/settings/api. Bisa diisi
"API Key" (v3, 32 karakter) atau "API Read Access Token" (v4, diawali 'eyJ').
"""
import requests

from . import SearchResult, SourceError

API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w342"
KEY_URL = "https://www.themoviedb.org/settings/api"
TIMEOUT = 10
ANIMATION_GENRE = 16
ENDED_STATUSES = ("Ended", "Canceled")


def page_url(media, tmdb_id):
    return f"https://www.themoviedb.org/{media}/{tmdb_id}"


def poster(path):
    return f"{IMG}{path}" if path else None


def _get(path, api_key, params=None):
    api_key = (api_key or "").strip()
    if not api_key:
        raise SourceError("API key TMDB belum diisi. Buka ⚙ Pengaturan untuk mengisinya.")
    params = dict(params or {})
    headers = {"Accept": "application/json"}
    if api_key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {api_key}"
    else:
        params["api_key"] = api_key
    try:
        res = requests.get(f"{API}{path}", params=params, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise SourceError(f"Gagal terhubung ke TMDB: {e.__class__.__name__}") from e
    if res.status_code == 401:
        raise SourceError("API key TMDB tidak valid.")
    if res.status_code == 404:
        raise SourceError("Data tidak ditemukan di TMDB.")
    if res.status_code != 200:
        raise SourceError(f"TMDB API error {res.status_code}")
    return res.json()


def _guess_type(item, media):
    if media == "movie":
        return "Movie"
    is_anim = ANIMATION_GENRE in (item.get("genre_ids") or [])
    is_jp = "JP" in (item.get("origin_country") or []) or item.get("original_language") == "ja"
    return "Anime" if is_anim and is_jp else "Series"


def search(query, api_key, language="en-US"):
    data = _get("/search/multi", api_key, {"query": query, "language": language,
                                           "include_adult": "false", "page": 1})
    results = []
    for it in data.get("results") or []:
        media = it.get("media_type")
        if media not in ("movie", "tv"):
            continue
        title = it.get("title") or it.get("name") or ""
        date = it.get("release_date") or it.get("first_air_date") or ""
        type_guess = _guess_type(it, media)
        results.append(SearchResult(
            source="tmdb", remote_id=str(it["id"]), title=title,
            subtitle=" · ".join(x for x in (type_guess, date[:4]) if x),
            poster_url=poster(it.get("poster_path")), media=media, type_guess=type_guess,
        ))
    return results


def validate_key(api_key):
    _get("/configuration", api_key)


def fetch_details(media, tmdb_id, api_key, language="en-US"):
    """Return dict untuk db.save_remote_state. Raise SourceError kalau gagal."""
    data = _get(f"/{media}/{tmdb_id}", api_key, {"language": language})
    if media == "movie":
        return {
            "latest_episode_str": data.get("status") or "",
            "latest_season": None,
            "latest_ep": None,
            "airing_ended": 1 if data.get("status") == "Released" else 0,
            "release_date": data.get("release_date") or None,
            "poster_url": poster(data.get("poster_path")),
        }

    last = data.get("last_episode_to_air") or {}
    nxt = data.get("next_episode_to_air") or {}
    season, ep = last.get("season_number"), last.get("episode_number")
    return {
        "latest_episode_str": f"S{season} EP {ep}" if ep is not None else (data.get("status") or ""),
        "latest_season": season,
        "latest_ep": ep,
        "airing_ended": 1 if data.get("status") in ENDED_STATUSES else 0,
        "release_date": nxt.get("air_date") or None,
        "poster_url": poster(data.get("poster_path")),
    }
