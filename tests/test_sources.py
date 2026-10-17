import unittest
from unittest import mock

from animetracker import logic
from animetracker.sources import SourceError, bilibili, tmdb


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload


BILI_SEARCH = {"data": {"modules": [
    {"type": "ogv_subject", "items": [{"title": "One Piece", "seasons": [
        {"title": "One Piece", "season_id": "37976", "index_show": "Update to EP 1180",
         "cover": "https://pic/op.png", "season_type": "Anime"},
        {"title": "One Piece: The Movie", "season_id": "37120", "index_show": "Full",
         "cover": "https://pic/m.png", "season_type": "Anime"},
    ]}]},
    {"type": "ugc", "items": [{"title": "upload video", "aid": "1"}]},
]}}


class BilibiliTests(unittest.TestCase):
    @mock.patch("animetracker.sources.bilibili.requests.get", return_value=FakeResponse(BILI_SEARCH))
    def test_search_reads_ogv_subject_module(self, _get):
        results = bilibili.search("one piece")
        self.assertEqual([r.remote_id for r in results], ["37976", "37120"])
        self.assertEqual(results[0].poster_url, "https://pic/op.png")

    @mock.patch("animetracker.sources.bilibili.requests.get", return_value=FakeResponse(BILI_SEARCH))
    def test_fetch_latest(self, _get):
        info = bilibili.fetch_latest("37976", "One Piece")
        self.assertEqual(info["latest_ep"], 1180)
        self.assertEqual(info["airing_ended"], 0)
        ended = bilibili.fetch_latest("37120", "One Piece")
        self.assertEqual(ended["airing_ended"], 1)


TMDB_TV = {"status": "Returning Series", "poster_path": "/p.jpg",
           "last_episode_to_air": {"season_number": 2, "episode_number": 7},
           "next_episode_to_air": {"air_date": "2026-10-24"}}
TMDB_MOVIE = {"status": "Released", "release_date": "2024-02-27", "poster_path": "/d.jpg"}
TMDB_SEARCH = {"results": [
    {"media_type": "movie", "id": 693134, "title": "Dune: Part Two", "release_date": "2024-02-27", "poster_path": "/d.jpg"},
    {"media_type": "tv", "id": 37854, "name": "One Piece", "first_air_date": "1999-10-20",
     "genre_ids": [16, 10759], "origin_country": ["JP"]},
    {"media_type": "person", "id": 1, "name": "Someone"},
]}


class TmdbTests(unittest.TestCase):
    def test_missing_key(self):
        with self.assertRaises(SourceError):
            tmdb.search("dune", "")

    @mock.patch("animetracker.sources.tmdb.requests.get", return_value=FakeResponse(TMDB_SEARCH))
    def test_search_and_type_guess(self, get):
        results = tmdb.search("x", "abc123")
        self.assertEqual([(r.media, r.type_guess) for r in results], [("movie", "Movie"), ("tv", "Anime")])
        self.assertEqual(get.call_args.kwargs["params"]["api_key"], "abc123")

    @mock.patch("animetracker.sources.tmdb.requests.get", return_value=FakeResponse(TMDB_SEARCH))
    def test_v4_token_uses_bearer(self, get):
        tmdb.search("x", "eyJhbGciOi.token")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer eyJhbGciOi.token")
        self.assertNotIn("api_key", get.call_args.kwargs["params"])

    @mock.patch("animetracker.sources.tmdb.requests.get", return_value=FakeResponse({}, status=401))
    def test_invalid_key(self, _get):
        with self.assertRaises(SourceError):
            tmdb.fetch_details("tv", "1", "bad")

    @mock.patch("animetracker.sources.tmdb.requests.get", return_value=FakeResponse(TMDB_TV))
    def test_tv_details_feed_state(self, _get):
        info = tmdb.fetch_details("tv", "1", "k")
        self.assertEqual((info["latest_season"], info["latest_ep"], info["airing_ended"]), (2, 7, 0))
        show = {"title": "X", "season": 2, "episode": 5, "status": "Watching", "tmdb_id": "1", "tmdb_media": "tv", **info}
        self.assertEqual(logic.compute_state(show).kind, logic.NEW)

    @mock.patch("animetracker.sources.tmdb.requests.get", return_value=FakeResponse(TMDB_MOVIE))
    def test_movie_details(self, _get):
        info = tmdb.fetch_details("movie", "693134", "k")
        self.assertEqual(info["release_date"], "2024-02-27")
        self.assertTrue(info["poster_url"].endswith("/d.jpg"))


if __name__ == "__main__":
    unittest.main()
