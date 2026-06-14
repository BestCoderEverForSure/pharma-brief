"""Tests for pharma-news/set_schedule.py — the config-reading used by the DST re-time (M4).

(The local->UTC conversion + cron rewrite run in main() with file side-effects, so they're
exercised live by the workflow; here we cover the new pure config_time helper.)

Run:  python3 -m unittest discover -s tests
"""

import json
import tempfile
import unittest
from pathlib import Path

import fixtures as F

ss = F.load_set_schedule()


class TestConfigTime(unittest.TestCase):
    def _cfg(self, data):
        tmp = tempfile.TemporaryDirectory()
        p = Path(tmp.name) / "config.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return tmp, p

    def test_reads_time_and_tz(self):
        tmp, p = self._cfg({"delivery_time": "07:00", "target_timezone": "Europe/Rome"})
        try:
            self.assertEqual(ss.config_time(p), ("07:00", "Europe/Rome"))
        finally:
            tmp.cleanup()

    def test_missing_file_returns_none(self):
        self.assertEqual(ss.config_time(Path("/no/such/config.json")), (None, None))

    def test_missing_keys_returns_none(self):
        tmp, p = self._cfg({"audio": False})
        try:
            self.assertEqual(ss.config_time(p), (None, None))
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
