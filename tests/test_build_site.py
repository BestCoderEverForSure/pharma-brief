"""Tests for site/build_site.py — the pure markdown/HTML/date helpers.

No network: fetch_market()/build() are not exercised; render_market() is fed data
directly. Golden tests lock the source-renumbering and headline-linking passes.

Run:  python3 -m unittest discover -s tests
"""

import datetime as dt
import os
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

    def test_citation_url_is_html_escaped_in_href(self):
        # A source URL with a stray quote must not break out of href="" (W5).
        bs._SRCMAP = {"1": 'https://x.com/a"><script>evil'}
        try:
            out = bs.md_inline("see [1]")
            self.assertNotIn('"><script>', out)   # no attribute breakout
            self.assertIn("&quot;", out)            # quote escaped instead
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


class TestMdToHtml(unittest.TestCase):
    """The website's block renderer: TL;DR points, ledes, {major} headings, meta lines."""

    def test_bullets_become_points_with_head_and_body(self):
        out = bs.md_to_html("- **Lilly** — wins FDA nod\n- plain point\n")
        self.assertIn('<div class="points">', out)
        self.assertIn('<div class="point-h">Lilly</div>', out)
        self.assertIn('<div class="point-b">wins FDA nod</div>', out)
        self.assertIn('<div class="point-b">plain point</div>', out)   # head-less bullet

    def test_blockquote_becomes_lede(self):
        out = bs.md_to_html("> A sharp talking point.\n")
        self.assertIn('<div class="lede">', out)
        self.assertIn("A sharp talking point.", out)

    def test_major_heading_gets_tag_and_class(self):
        out = bs.md_to_html("### Big win {major}\n")
        self.assertIn('class="major"', out)
        self.assertIn("Major story", out)
        self.assertNotIn("{major}", out)                 # the marker is stripped from the text

    def test_emphasis_only_paragraph_is_meta(self):
        out = bs.md_to_html("*Window: last 24h*\n")
        self.assertIn('<p class="meta">', out)


class TestRenderTimeline(unittest.TestCase):
    EVENTS = [
        {"date": dt.date(2026, 6, 18), "label": "Tebipenem FDA", "full": "Tebipenem FDA"},
        {"date": dt.date(2026, 7, 10), "label": "Soon", "full": "Soon"},
    ]

    def test_drops_past_events_relative_to_ref_date(self):
        # As of 28 Jun, the 18 Jun catalyst has already happened — it must not appear.
        html_out = bs.render_timeline(self.EVENTS, dt.date(2026, 6, 28))
        self.assertNotIn("Tebipenem FDA", html_out)
        self.assertIn("Soon", html_out)

    def test_keeps_event_for_an_earlier_brief(self):
        # The SAME catalyst is still upcoming for a brief produced on 15 Jun.
        html_out = bs.render_timeline(self.EVENTS, dt.date(2026, 6, 15))
        self.assertIn("Tebipenem FDA", html_out)

    def test_empty_when_all_past(self):
        self.assertIn("No upcoming catalysts", bs.render_timeline(self.EVENTS, dt.date(2027, 1, 1)))


class TestRenderCatalystMix(unittest.TestCase):
    EVENTS = [
        {"date": dt.date(2026, 7, 1), "label": "PDUFA", "full": "tirzepatide PDUFA decision"},
        {"date": dt.date(2026, 7, 5), "label": "Earnings", "full": "Lilly Q2 earnings"},
        {"date": dt.date(2026, 6, 1), "label": "Past conf", "full": "ASCO congress"},
    ]

    def test_counts_only_upcoming(self):
        # As of 28 Jun the 1 Jun congress has already happened — like the timeline, the mix
        # must drop it, leaving only the regulatory + earnings bars.
        out = bs.render_catalyst_mix(self.EVENTS, dt.date(2026, 6, 28))
        self.assertIn("Regulatory", out)
        self.assertIn("Earnings", out)
        self.assertNotIn("Conference", out)   # past event dropped, same as the timeline

    def test_empty_when_all_past(self):
        self.assertEqual(bs.render_catalyst_mix(self.EVENTS, dt.date(2027, 1, 1)), "")


class TestBriefRefDate(unittest.TestCase):
    def test_plain_date_stem(self):
        self.assertEqual(bs.brief_ref_date("2026-06-28"), dt.date(2026, 6, 28))

    def test_suffixed_stem_uses_leading_date(self):
        self.assertEqual(bs.brief_ref_date("2026-06-12-deepseek"), dt.date(2026, 6, 12))

    def test_undated_stem_falls_back_to_today(self):
        self.assertEqual(bs.brief_ref_date("INDEX"), dt.date.today())


class TestRssFeed(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("SITE_URL", None)

    def tearDown(self):
        if self._saved is not None:
            os.environ["SITE_URL"] = self._saved

    def test_pages_url_derived_from_repo(self):
        self.assertEqual(bs.pages_url("https://github.com/Owner/Repo"),
                         "https://owner.github.io/Repo/")   # host lower-cased, repo kept

    def test_pages_url_env_override_wins(self):
        os.environ["SITE_URL"] = "https://example.com/site"
        self.assertEqual(bs.pages_url("https://github.com/x/y"), "https://example.com/site/")

    def test_rss_feed_structure_and_escaping(self):
        items = [{"title": 'Brief <b> & "x"', "url": "https://s/2026-06-14.html",
                  "desc": "desc & more", "dt": dt.datetime(2026, 6, 14, 5, tzinfo=dt.timezone.utc)}]
        out = bs.rss_feed(items, "https://s/", dt.datetime(2026, 6, 14, 6, tzinfo=dt.timezone.utc))
        self.assertIn('<rss version="2.0">', out)
        self.assertIn("<item>", out)
        self.assertIn("https://s/2026-06-14.html", out)
        self.assertIn("&lt;b&gt;", out)     # title HTML-escaped
        self.assertNotIn("<b>", out)         # no raw markup leaked into the XML
        self.assertIn("<pubDate>", out)


class TestIcsFeed(unittest.TestCase):
    EVENTS = [{"date": dt.date(2026, 9, 18), "label": "Zidesamtinib PDUFA",
               "full": "Zidesamtinib (Nuvalent/GSK) PDUFA; ROS1+ NSCLC, a key milestone"}]
    BUILT = dt.datetime(2026, 6, 29, 12, 0, tzinfo=dt.timezone.utc)

    def test_valid_all_day_vevent(self):
        out = bs.ics_feed(self.EVENTS, self.BUILT)
        self.assertTrue(out.startswith("BEGIN:VCALENDAR"))
        self.assertIn("END:VCALENDAR", out)
        self.assertIn("DTSTART;VALUE=DATE:20260918", out)   # all-day on the catalyst date
        self.assertIn("DTEND;VALUE=DATE:20260919", out)     # + next day (all-day convention)
        self.assertIn("SUMMARY:Zidesamtinib PDUFA", out)
        self.assertIn("DTSTAMP:20260629T120000Z", out)

    def test_escapes_rfc5545_specials(self):
        out = bs.ics_feed(self.EVENTS, self.BUILT)
        self.assertIn("\\;", out)     # ';' in the description is backslash-escaped
        self.assertIn("\\,", out)     # ',' too

    def test_stable_uid_across_rebuilds(self):
        import re as _re
        a = _re.search(r"UID:(.+)", bs.ics_feed(self.EVENTS, self.BUILT)).group(1)
        b = _re.search(r"UID:(.+)", bs.ics_feed(self.EVENTS, self.BUILT + dt.timedelta(days=1))).group(1)
        self.assertEqual(a, b)        # same event -> same UID, so a refresh updates not duplicates

    def test_empty_is_a_valid_calendar(self):
        out = bs.ics_feed([], self.BUILT)
        self.assertIn("BEGIN:VCALENDAR", out)
        self.assertNotIn("BEGIN:VEVENT", out)


class TestWatchlistTopics(unittest.TestCase):
    def _topics(self, text):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "watchlist.md"
        path.write_text(text, encoding="utf-8")
        try:
            return bs.watchlist_topics(path)
        finally:
            tmp.cleanup()

    def test_strips_notes_and_splits_alternatives(self):
        topics = self._topics(
            "## Companies\n"
            "- Eli Lilly *(primary focus - see Spotlight)*\n"
            "- Pfizer / Metsera\n"
            "## Themes\n"
            "- Drug pricing / MFN / tariffs\n"
            "- Patent cliffs & M&A\n"
            "not a bullet line\n")
        self.assertIn("Eli Lilly", topics)     # italic note + space stripped
        self.assertIn("Metsera", topics)        # ' / ' alternative split out
        self.assertIn("tariffs", topics)        # multi-slash split
        self.assertIn("M&A", topics)            # ' & ' split keeps M&A intact
        self.assertNotIn("", topics)

    def test_missing_file_is_empty(self):
        self.assertEqual(bs.watchlist_topics(Path("/no/such/watchlist.md")), [])


if __name__ == "__main__":
    unittest.main()
