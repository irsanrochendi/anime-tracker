import datetime
import os
import tempfile
import unittest

from animetracker import logic

TODAY = datetime.date(2026, 10, 17)


def show(**kw):
    base = {"title": "X", "season": 1, "episode": 10, "status": "Watching"}
    base.update(kw)
    return base


class ParseTests(unittest.TestCase):
    def test_parse_ep_num(self):
        self.assertEqual(logic.parse_ep_num("Update to EP 1174"), 1174)
        self.assertEqual(logic.parse_ep_num("EP 12"), 12)
        self.assertEqual(logic.parse_ep_num("Full"), 0)
        self.assertEqual(logic.parse_ep_num(None), 0)

    def test_finished_airing(self):
        self.assertTrue(logic.is_finished_airing("Full"))
        self.assertFalse(logic.is_finished_airing("Update to EP 3"))
        self.assertFalse(logic.is_finished_airing(""))


class BilibiliStateTests(unittest.TestCase):
    def test_new_episode(self):
        s = show(bilibili_season_id="1", latest_episode_str="Update to EP 12")
        self.assertEqual(logic.compute_state(s, TODAY).kind, logic.NEW)

    def test_up_to_date(self):
        s = show(bilibili_season_id="1", latest_episode_str="Update to EP 10")
        self.assertEqual(logic.compute_state(s, TODAY).kind, logic.UP_TO_DATE)

    def test_full_not_completed_is_orange(self):
        s = show(bilibili_season_id="1", latest_episode_str="Full")
        self.assertEqual(logic.compute_state(s, TODAY).kind, logic.FINISHED_NOT_DONE)

    def test_full_completed_is_done(self):
        s = show(bilibili_season_id="1", latest_episode_str="Full", status="Completed")
        self.assertEqual(logic.compute_state(s, TODAY).kind, logic.DONE)

    def test_unlinked(self):
        self.assertEqual(logic.compute_state(show(), TODAY).kind, logic.NONE)


class TmdbStateTests(unittest.TestCase):
    def test_tv_new_season(self):
        s = show(tmdb_id="5", tmdb_media="tv", latest_season=2, latest_ep=1, airing_ended=0)
        self.assertEqual(logic.compute_state(s, TODAY).kind, logic.NEW)

    def test_tv_same_season_behind(self):
        s = show(tmdb_id="5", tmdb_media="tv", season=2, episode=3, latest_season=2, latest_ep=5, airing_ended=0)
        self.assertEqual(logic.compute_state(s, TODAY).kind, logic.NEW)

    def test_tv_ended_caught_up_is_done(self):
        s = show(tmdb_id="5", tmdb_media="tv", season=3, episode=8, latest_season=3, latest_ep=8, airing_ended=1)
        self.assertEqual(logic.compute_state(s, TODAY).kind, logic.DONE)

    def test_tv_next_air_label(self):
        s = show(tmdb_id="5", tmdb_media="tv", season=1, episode=4, latest_season=1, latest_ep=4,
                 airing_ended=0, release_date="2026-10-20")
        st = logic.compute_state(s, TODAY)
        self.assertEqual(st.kind, logic.UP_TO_DATE)
        self.assertIn("20 Oct", st.label)

    def test_movie_unreleased_and_released(self):
        m = show(tmdb_id="9", tmdb_media="movie", status="Plan to Watch", release_date="2027-01-01")
        self.assertEqual(logic.compute_state(m, TODAY).kind, logic.UNRELEASED)
        m["release_date"] = "2025-05-01"
        self.assertEqual(logic.compute_state(m, TODAY).kind, logic.RELEASED)
        m["status"] = "Completed"
        self.assertEqual(logic.compute_state(m, TODAY).kind, logic.DONE)


class NotifyTests(unittest.TestCase):
    def test_notifies_only_when_latest_goes_up(self):
        old = show(bilibili_season_id="1", latest_episode_str="Update to EP 11")
        self.assertTrue(logic.should_notify(old, {"latest_ep": 12, "latest_season": None}, "Watching"))
        self.assertFalse(logic.should_notify(old, {"latest_ep": 11, "latest_season": None}, "Watching"))

    def test_no_notify_on_first_link_or_not_watching(self):
        first = show(bilibili_season_id="1")
        self.assertFalse(logic.should_notify(first, {"latest_ep": 12}, "Watching"))
        old = show(bilibili_season_id="1", latest_episode_str="EP 11")
        self.assertFalse(logic.should_notify(old, {"latest_ep": 12}, "Plan to Watch"))

    def test_tmdb_season_aware(self):
        old = show(tmdb_id="5", tmdb_media="tv", season=2, episode=1, latest_season=1, latest_ep=12)
        self.assertTrue(logic.should_notify(old, {"latest_season": 2, "latest_ep": 2}, "Watching"))
        self.assertFalse(logic.should_notify(old, {"latest_season": 2, "latest_ep": 1}, "Watching"))


class DbTests(unittest.TestCase):
    def test_migrates_v1_database_with_backup(self):
        import sqlite3
        from animetracker import config, db
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tracker_db.sqlite")
            conn = sqlite3.connect(path)
            conn.execute("""CREATE TABLE shows (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                            type TEXT, season INTEGER, episode INTEGER, status TEXT, notes TEXT,
                            bilibili_season_id TEXT, latest_episode_str TEXT)""")
            conn.execute("INSERT INTO shows (title, season, episode, status) VALUES ('A', 1, 3, 'Watching')")
            conn.commit()
            conn.close()

            old = config.DB_FILE
            config.DB_FILE = path
            try:
                db.init_db()
                db.init_db()  # idempoten, tidak membuat backup kedua
                backups = [f for f in os.listdir(tmp) if ".bak-" in f]
                self.assertEqual(len(backups), 1)
                row = db.list_shows()[0]
                self.assertEqual(row["title"], "A")
                self.assertIn("tmdb_id", row)
                db.adjust_number(row["id"], "episode", -10)
                self.assertEqual(db.get_show(row["id"])["episode"], 0)
            finally:
                config.DB_FILE = old


if __name__ == "__main__":
    unittest.main()
