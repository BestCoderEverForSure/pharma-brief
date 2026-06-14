"""Tests for site/build_site.py — the pure markdown/HTML/date helpers.

No network: fetch_market()/build() are not exercised; render_market() is fed data
directly. Golden tests lock the source-renumbering and headline-linking passes.

Run:  python3 -m unittest discover -s tests
"""

import datetime as dt
import tempfile
import unittest
from pathlib import Path

import fixtures as F

bs = F.load_build_site()


class TestGolden(unittest.TestCase):
    def test_renumber_sources(self):
        self.assertEqual(bs.renumber_sources(F.RENUMBER_MD), F.read_golden("renumber_sources.txt"))

    def test_link_headings(self):
        out = bs.link_headings(bs.renumber_sources(F.RENUMBER_MD))
        self.assertEqual(out, F.read_golden("link_headings.txt"))


class TestRenumberProperties(unittest.TestCase):
    def test_citations_become_first_appearance_order(self):
        out = bs.renumber_sources(F.RENUMBER_MD)
        # [7] appears first in the body -> becomes [1]; [3] second -> [2].
        self.assertIn("Body text [1].", out)
        self.assertIn("More [2].", out)
        # Title A (originally 7) is now source 1; uncited C pushed last.
        self.assertIn("1. [Title A](https://a.example/y)", out)
        self.assertIn("3. [Uncited C](https://c.example/z)", out)

    def test_no_sources_section_is_noop(self):
        md = "# Title\nBody [1] with no sources list."
        self.assertEqual(bs.renumber_sources(md), md)


class TestInlineAndText(unittest.TestCase):
    def setUp(self):
        bs._SRCMAP = {}   # ensure a clean global between tests

    def test_bold_and_em_and_code(self):
        self.assertEqual(bs.md_inline("**b** *i* `c`"),
                         "<strong>b</strong> <em>i</em> <code>c</code>")

    def test_strips_methodology_pseudo_citation(self):
        self.assertNotIn("catalysts.md", bs.md_inline("text [catalysts.md] more"))

    def test_direct_publisher_link_marked(self):
        out = bs.md_inline("[Pub](https://www.statnews.com/x)")
        self.assertIn('class="src direct"', out)

    def test_google_news_link_not_marked_direct(self):
        out = bs.md_inline("[Agg](https://news.google.com/x)")
        self.assertIn('class="src"', out)
        self.assertNotIn("direct", out)

    def test_citation_links_when_srcmap_set(self):
        bs._SRCMAP = {"1": "https://a.example/y"}
        try:
            out = bs.md_inline("Body [1].")
            self.assertIn('class="cite"', out)
            self.assertIn("https://a.example/y", out)
        finally:
            bs._SRCMAP = {}

    def test_plain_text_strips_markdown(self):
        self.assertEqual(bs.plain_text("# H\n**x** [L](http://u) `c`"), "H x L c")


class TestSmallHelpers(unittest.TestCase):
    def test_visible_strips_link_major_emphasis(self):
        self.assertEqual(bs._visible("[Headline](http://x) {major}"), "Headline")

    def test_slug(self):
        self.assertEqual(bs._slug("Eli Lilly Spotlight {major}"), "eli-lilly-spotlight")

    def test_dmy_title_uses_filename_date(self):
        out = bs._dmy_title("# Pharma Brief - June 14, 2026\nx", "2026-06-14")
        self.assertEqual(out.splitlines()[0], "# Pharma Brief — 14/06/2026")

    def test_category(self):
        self.assertEqual(bs._category("PDUFA decision"), "reg")
        self.assertEqual(bs._category("Q2 earnings"), "earn")
        self.assertEqual(bs._category("ESMO congress"), "conf")
        self.assertEqual(bs._category("something else"), "other")

    def test_meta_of_reads_title_and_engine(self):
        md = "# Pharma Brief - 2026-06-14\n*Window: last 24h · Engine: Gemini · morning*\n"
        meta = bs.meta_of(md)
        self.assertEqual(meta["engine"], "Gemini")
        self.assertTrue(meta["title"].startswith("Pharma Brief"))


class TestRenderMarket(unittest.TestCase):
    def test_sorted_and_signed(self):
        out = bs.render_market([
            {"t": "PFE", "name": "Pfizer", "pct": -1.2, "last": 25.1},
            {"t": "LLY", "name": "Eli Lilly", "pct": 2.5, "last": 900.5},
        ])
        # Sorted by pct desc: LLY (up) before PFE (down).
        self.assertLess(out.index("Eli Lilly"), out.index("Pfizer"))
        self.assertIn('class="mkt-pct up">+2.5%', out)
        self.assertIn('class="mkt-pct down">-1.2%', out)

    def test_near_zero_is_flat(self):
        out = bs.render_market([{"t": "X", "name": "X", "pct": -0.04, "last": 10.0}])
        self.assertIn('class="mkt-pct flat">-0.0%', out)

    def test_empty_is_blank(self):
        self.assertEqual(bs.render_market([]), "")


class TestParseCatalysts(unittest.TestCase):
    def _parse(self, text):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "catalysts.md"
        path.write_text(text, encoding="utf-8")
        try:
            return bs.parse_catalysts(path)   # shared parser now takes the path explicitly
        finally:
            tmp.cleanup()

    def test_parses_iso_and_month_year(self):
        events = self._parse(
            "- **2026-07-01** · tirzepatide PDUFA; extra clause\n"
            "- **Aug 2026** · donanemab readout\n"
            "garbage line\n")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["date"], dt.date(2026, 7, 1))
        self.assertEqual(events[0]["label"], "tirzepatide PDUFA")   # clause after ';' dropped
        self.assertEqual(events[1]["date"], dt.date(2026, 8, 15))   # month-only -> 15th


if __name__ == "__main__":
    unittest.main()
