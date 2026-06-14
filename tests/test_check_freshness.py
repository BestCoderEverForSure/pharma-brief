"""Tests for pharma-news/check_freshness.py — the dead-man's-switch (M3).

Run:  python3 -m unittest discover -s tests
"""

import datetime as dt
import tempfile
import unittest
from pathlib import Path

import fixtures as F

cf = F.load_check_freshness()


class TestNewestDigestDate(unittest.TestCase):
    def _dir(self, names):
        tmp = tempfile.TemporaryDirectory()
        for n in names:
            (Path(tmp.name) / n).write_text("x", encoding="utf-8")
        return tmp, Path(tmp.name)

    def test_picks_max_date_and_ignores_non_date_files(self):
        tmp, d = self._dir(["2026-06-10.md", "2026-06-14.md", "INDEX.md", "notes.md"])
        try:
            self.assertEqual(cf.newest_digest_date(d), dt.date(2026, 6, 14))
        finally:
            tmp.cleanup()

    def test_empty_dir_is_none(self):
        tmp, d = self._dir([])
        try:
            self.assertIsNone(cf.newest_digest_date(d))
        finally:
            tmp.cleanup()


class TestStaleness(unittest.TestCase):
    TODAY = dt.date(2026, 6, 14)

    def test_today_is_ok(self):
        ok, _ = cf.staleness(dt.date(2026, 6, 14), self.TODAY, 2)
        self.assertTrue(ok)

    def test_at_limit_is_ok(self):
        ok, _ = cf.staleness(dt.date(2026, 6, 12), self.TODAY, 2)   # age 2 == limit
        self.assertTrue(ok)

    def test_past_limit_fails(self):
        ok, msg = cf.staleness(dt.date(2026, 6, 11), self.TODAY, 2)  # age 3 > limit
        self.assertFalse(ok)
        self.assertIn("stalled", msg)

    def test_no_digests_fails(self):
        ok, msg = cf.staleness(None, self.TODAY, 2)
        self.assertFalse(ok)
        self.assertIn("no archived digests", msg)


if __name__ == "__main__":
    unittest.main()
