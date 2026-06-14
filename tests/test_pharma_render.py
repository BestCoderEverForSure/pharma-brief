"""Tests for pharma_render.py — the logic SHARED by the website and the email renderers.

This module is the single source of truth for citation renumbering, the [n]->URL map,
catalyst-calendar parsing, and ticker selection, so both renderers stay in lock-step.
(The build_site / send_digest tests also exercise these via each renderer; these test the
canonical module directly, incl. select_tickers, which the per-renderer tests don't.)

Run:  python3 -m unittest discover -s tests
"""

import datetime as dt
import tempfile
import unittest
from pathlib import Path

import fixtures as F

pr = F.load_pharma_render()


class TestRenumberSources(unittest.TestCase):
    def test_first_appearance_order_and_uncited_last(self):
        md = ("Body [7] then [3].\n\n## Sources\n"
              "3. [B](https://b.example/x)\n7. [A](https://a.example/y)\n"
              "9. [C uncited](https://c.example/z)\n")
        out = pr.renumber_sources(md)
        self.assertIn("Body [1] then [2].", out)
        self.assertIn("1. [A](https://a.example/y)", out)
        self.assertIn("2. [B](https://b.example/x)", out)
        self.assertIn("3. [C uncited](https://c.example/z)", out)   # uncited -> end

    def test_no_sources_section_is_noop(self):
        md = "# T\nBody [1] with no list."
        self.assertEqual(pr.renumber_sources(md), md)


class TestParseSrcmap(unittest.TestCase):
    def test_maps_number_to_url(self):
        md = "## Sources\n1. [A](https://a.example/y)\n2. [B](https://b.example/x)\n"
        self.assertEqual(pr.parse_srcmap(md),
                         {"1": "https://a.example/y", "2": "https://b.example/x"})


class TestParseCatalysts(unittest.TestCase):
    def test_iso_month_year_and_fields(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "catalysts.md"
        path.write_text("- **2026-07-01** · tirzepatide PDUFA; long extra clause\n"
                        "- **Aug 2026** · donanemab readout\n"
                        "not a catalyst line\n", encoding="utf-8")
        try:
            events = pr.parse_catalysts(path)
        finally:
            tmp.cleanup()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["date"], dt.date(2026, 7, 1))
        self.assertEqual(events[0]["label"], "tirzepatide PDUFA")     # clause after ';' trimmed
        self.assertEqual(events[0]["full"], "tirzepatide PDUFA; long extra clause")
        self.assertEqual(events[1]["date"], dt.date(2026, 8, 15))     # month-only -> 15th

    def test_missing_file_is_empty(self):
        self.assertEqual(pr.parse_catalysts(Path("/no/such/catalysts.md")), [])


class TestSelectTickers(unittest.TestCase):
    def test_core_always_present(self):
        sel = pr.select_tickers("nothing relevant here")
        self.assertEqual(sel, pr.MARKET_TICKERS)          # just the core 10, in order

    def test_extra_added_when_named(self):
        sel = dict((t, n) for t, n in pr.select_tickers("today novo and viking and roche moved"))
        self.assertIn("VKTX", sel)    # viking
        self.assertIn("RHHBY", sel)   # roche
        self.assertIn("LLY", sel)     # core still there

    def test_no_duplicate_when_extra_overlaps(self):
        sel = pr.select_tickers("summit summit summit")
        self.assertEqual([t for t, _ in sel].count("SMMT"), 1)


if __name__ == "__main__":
    unittest.main()
