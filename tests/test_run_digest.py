"""Tests for deepseek/run_digest.py — the pure, deterministic helpers.

The golden tests lock in finalize()'s exact output so the refactor that splits it
into named steps can be proven to change nothing. The rest are ordinary unit tests
for the small text/date helpers. Network and model calls are not exercised.

Run:  python3 -m unittest discover -s tests
"""

import datetime as dt
import json
import os
import tempfile
import types
import unittest
import urllib.error
from unittest import mock
from pathlib import Path

import fixtures as F

rd = F.load_run_digest()


class _JsonResp:
    """Stand-in for the OpenAI-compatible chat response, usable as a context manager."""
    def __init__(self, payload):
        self._b = json.dumps(payload).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def read(self):
        return self._b


class TestFinalizeGolden(unittest.TestCase):
    def test_basic_matches_golden(self):
        out = rd.finalize(F.FINALIZE_INPUT, F.FINALIZE_ITEMS, "Gemini", "gemini-2.5-flash")
        self.assertEqual(out, F.read_golden("finalize_basic.txt"))

    def test_nosub_matches_golden(self):
        out = rd.finalize(F.FINALIZE_INPUT_NOSUB, F.FINALIZE_ITEMS, "DeepSeek", "deepseek-chat")
        self.assertEqual(out, F.read_golden("finalize_nosub.txt"))


class TestFinalizeProperties(unittest.TestCase):
    """Behavioural invariants — readable guarantees independent of exact wording."""

    def setUp(self):
        self.out = rd.finalize(F.FINALIZE_INPUT, F.FINALIZE_ITEMS, "Gemini", "gemini-2.5-flash")

    def test_strips_leaked_html(self):
        self.assertNotIn("<small>", self.out)

    def test_strips_methodology_pseudo_citation(self):
        self.assertNotIn("[catalysts.md]", self.out)

    def test_drops_model_week_ahead_section(self):
        self.assertNotIn("Week Ahead", self.out)

    def test_drops_model_written_sources(self):
        self.assertNotIn("garbage", self.out)

    def test_engine_label_normalised_once(self):
        self.assertEqual(self.out.count("Engine: Gemini (gemini-2.5-flash)"), 1)
        self.assertNotIn("OldLabel", self.out)

    def test_grouped_citations_split(self):
        self.assertIn("[2] [3]", self.out)
        self.assertNotIn("[2, 3]", self.out)

    def test_sources_rebuilt_and_renumbered_from_items(self):
        self.assertIn("## Sources", self.out)
        self.assertIn("1. [Lilly's tirzepatide wins (Updated) FDA nod]", self.out)  # ] -> ) made md-safe
        self.assertIn("%281%29", self.out)  # parens in the URL percent-escaped

    def test_source_feed_timestamp_only_when_present(self):
        self.assertIn("Jun 12, 2026 · 14:30 UTC", self.out)   # item 1 had a date
        self.assertIn("2. [Novo readout disappoints](https://www.statnews.com/y)\n", self.out)  # item 2 "n/a" -> no tail

    def test_footer_present(self):
        self.assertIn("grounding check", self.out)
        self.assertIn("Not investment advice.", self.out)

    def test_read_time_recomputed_from_body(self):
        self.assertIn("min read", self.out)
        self.assertNotIn("~9 min read", self.out)  # the model's guess was replaced


class TestSmallHelpers(unittest.TestCase):
    def test_norm_title(self):
        self.assertEqual(rd._norm_title("Lilly's Tirzepatide: A Win!"), "lillystirzepatideawin")

    def test_fmt_source_dt_utc(self):
        self.assertEqual(rd._fmt_source_dt("2026-06-12T14:30:00+00:00"), "Jun 12, 2026 · 14:30 UTC")

    def test_fmt_source_dt_converts_to_utc(self):
        # +02:00 14:30 -> 12:30 UTC
        self.assertEqual(rd._fmt_source_dt("2026-06-12T14:30:00+02:00"), "Jun 12, 2026 · 12:30 UTC")

    def test_fmt_source_dt_blank_for_na_or_garbage(self):
        self.assertEqual(rd._fmt_source_dt("n/a"), "")
        self.assertEqual(rd._fmt_source_dt(""), "")
        self.assertEqual(rd._fmt_source_dt("not-a-date"), "")

    def test_cat_tokens_drops_generic_words(self):
        toks = rd._cat_tokens("Phase 3 readout for tirzepatide in obesity")
        self.assertIn("tirzepatide", toks)
        self.assertIn("obesity", toks)
        self.assertNotIn("phase", toks)     # generic catalyst word, ignored
        self.assertNotIn("readout", toks)


class TestParseFeed(unittest.TestCase):
    def test_parses_rss_and_filters_old_and_nonhttp(self):
        since = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc)
        xml = b"""<rss><channel>
          <item><title>Fresh story</title><link>https://ex.com/a</link>
            <description>&lt;p&gt;hi&lt;/p&gt; body</description>
            <pubDate>Fri, 12 Jun 2026 14:30:00 +0000</pubDate></item>
          <item><title>Too old</title><link>https://ex.com/old</link>
            <pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate></item>
          <item><title>No real link</title><guid>urn:uuid:1234</guid></item>
        </channel></rss>"""
        items = rd.parse_feed(xml, since)
        titles = [i["title"] for i in items]
        self.assertIn("Fresh story", titles)
        self.assertNotIn("Too old", titles)        # before `since`
        self.assertNotIn("No real link", titles)    # guid isn't an http link
        self.assertNotIn("<p>", items[0]["summary"])  # HTML stripped from summary

    def test_bad_xml_returns_empty(self):
        self.assertEqual(rd.parse_feed(b"not xml at all", dt.datetime.now(dt.timezone.utc)), [])


class TestMergeCatalysts(unittest.TestCase):
    """merge_catalysts writes to pharma-news/catalysts.md, so run it against a
    temporary ROOT to avoid touching the real file."""

    def _run_with_temp_catalysts(self, initial: str, events, today):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "pharma-news").mkdir(parents=True)
        (root / "pharma-news" / "catalysts.md").write_text(initial, encoding="utf-8")
        orig = rd.ROOT
        rd.ROOT = root
        try:
            added = rd.merge_catalysts(events, today)
            text = (root / "pharma-news" / "catalysts.md").read_text(encoding="utf-8")
        finally:
            rd.ROOT = orig
            tmp.cleanup()
        return added, text

    def test_adds_new_event_under_labelled_section(self):
        today = dt.date(2026, 6, 14)
        added, text = self._run_with_temp_catalysts(
            "# Catalysts\n\n- **2026-07-01** · Existing curated event\n",
            [(dt.date(2026, 8, 1), "tirzepatide PDUFA decision")], today)
        self.assertEqual(added, 1)
        self.assertIn("## Auto-detected (from recent briefs)", text)
        self.assertIn("tirzepatide PDUFA decision (auto-detected 2026-06-14)", text)

    def test_dedups_same_day_same_drug(self):
        today = dt.date(2026, 6, 14)
        added, _ = self._run_with_temp_catalysts(
            "# Catalysts\n\n- **2026-08-01** · tirzepatide approval decision\n",
            [(dt.date(2026, 8, 1), "tirzepatide PDUFA")], today)
        self.assertEqual(added, 0)   # shares the specific token "tirzepatide" on the same day

    def test_dedups_curated_month_only_against_auto_iso(self):
        # Regression: a curated month-only "Sep 2026" conference and an auto-detected
        # "2026-09-15" both resolve to the 15th — they must not both appear.
        today = dt.date(2026, 6, 14)
        added, _ = self._run_with_temp_catalysts(
            "# Catalysts\n\n## Conferences\n- **Sep 2026** · EASD (European diabetes) - GLP-1 data\n",
            [(dt.date(2026, 9, 15), "EASD (European diabetes) conference")], today)
        self.assertEqual(added, 0)

    def test_skips_generic_market_columns(self):
        today = dt.date(2026, 6, 14)
        added, _ = self._run_with_temp_catalysts(
            "# Catalysts\n",
            [(dt.date(2026, 6, 20), "Stocks to Watch: Vedanta, Aurobindo Pharma, Dr Reddy's"),
             (dt.date(2026, 6, 21), "Top movers in pharma today")], today)
        self.assertEqual(added, 0)   # generic market filler, not real catalysts

    def test_prunes_past_auto_events(self):
        today = dt.date(2026, 6, 14)
        initial = ("# Catalysts\n\n## Auto-detected (from recent briefs)\n"
                   "- **2026-01-01** · old donanemab readout (auto-detected 2025-12-01)\n")
        added, text = self._run_with_temp_catalysts(initial, [], today)
        self.assertNotIn("donanemab", text)   # past auto event pruned


class TestWindowSubtitle(unittest.TestCase):
    TODAY = dt.date(2026, 6, 14)

    def test_review_shows_lookback_range_and_count(self):
        s = rd.window_subtitle("review", 168, self.TODAY, 298)
        self.assertIn("Jun 7", s)                 # 168h = 7 days back
        self.assertIn("Jun 14, 2026", s)
        self.assertIn("298 articles scanned", s)

    def test_daily_24h_range(self):
        s = rd.window_subtitle("daily", 24, self.TODAY, 40)
        self.assertIn("Jun 13", s)
        self.assertIn("40 articles scanned", s)

    def test_ahead_shows_coming_week(self):
        s = rd.window_subtitle("ahead", 168, self.TODAY, 250)
        self.assertIn("Jun 15", s)
        self.assertIn("Jun 21, 2026", s)
        self.assertIn("week ahead", s)
        self.assertIn("250", s)

    def test_month_review_shows_30day_lookback(self):
        s = rd.window_subtitle("month_review", 720, self.TODAY, 612)
        self.assertIn("May 15", s)                # 720h ≈ 30 days back from Jun 14
        self.assertIn("Jun 14, 2026", s)
        self.assertIn("612 articles scanned", s)

    def test_month_ahead_shows_coming_month(self):
        s = rd.window_subtitle("month_ahead", 720, self.TODAY, 400)
        self.assertIn("Jun 15", s)                # day after today
        self.assertIn("Jul 14, 2026", s)          # +30 days
        self.assertIn("month ahead", s)
        self.assertIn("400", s)

    def test_year_review_shows_trailing_year_with_start_year(self):
        s = rd.window_subtitle("year_review", 8760, self.TODAY, 900)
        self.assertIn("Jun 14, 2025", s)          # ~365 days back — start carries its year
        self.assertIn("Jun 14, 2026", s)
        self.assertIn("900 articles scanned", s)

    def test_year_ahead_shows_coming_year(self):
        s = rd.window_subtitle("year_ahead", 8760, self.TODAY, 700)
        self.assertIn("Jun 15, 2026", s)          # start carries its year (span crosses into 2027)
        self.assertIn("Jun 14, 2027", s)
        self.assertIn("year ahead", s)
        self.assertIn("700", s)

    def test_archive_review_labels_count_as_sources(self):
        # Archive-sourced reviews say "sources across the period's briefs", not "articles scanned".
        s = rd.window_subtitle("month_review", 720, self.TODAY, 133, from_archive=True)
        self.assertIn("133 sources across the period's briefs", s)
        self.assertNotIn("scanned", s)
        # RSS-sourced (default) keeps the original wording.
        self.assertIn("articles scanned", rd.window_subtitle("month_review", 720, self.TODAY, 133))


class TestAutoSchedule(unittest.TestCase):
    """Locks the date->(hours, edition, mode) table that used to be shell `if`s in the
    workflow. Mon-Fri = daily brief; Saturday = Week in Review, but the LAST Saturday of the
    month = Month in Review; Sunday = Week Ahead, but the LAST Sunday = Month Ahead."""

    def test_weekdays_are_daily(self):
        for day in (15, 16, 17, 18, 19):    # Mon-Fri, Jun 2026
            self.assertEqual(rd.auto_schedule(dt.date(2026, 6, day)), (24, "morning", "daily"))

    def test_ordinary_saturday_is_week_review(self):
        self.assertEqual(rd.auto_schedule(dt.date(2026, 6, 6)), (168, "evening", "review"))

    def test_ordinary_sunday_is_week_ahead(self):
        self.assertEqual(rd.auto_schedule(dt.date(2026, 6, 14)), (168, "evening", "ahead"))

    def test_last_saturday_is_month_review(self):
        # Jun 27, 2026 is the last Saturday of June.
        self.assertEqual(rd.auto_schedule(dt.date(2026, 6, 27)), (720, "evening", "month_review"))

    def test_last_sunday_is_month_ahead(self):
        # Jun 28, 2026 is the last Sunday of June.
        self.assertEqual(rd.auto_schedule(dt.date(2026, 6, 28)), (720, "evening", "month_ahead"))

    def test_last_sat_and_sun_resolved_independently(self):
        # Feb 2026: last Saturday (28th) and last Sunday (22nd) fall in DIFFERENT weekends.
        self.assertEqual(rd.auto_schedule(dt.date(2026, 2, 28)), (720, "evening", "month_review"))
        self.assertEqual(rd.auto_schedule(dt.date(2026, 2, 22)), (720, "evening", "month_ahead"))
        self.assertEqual(rd.auto_schedule(dt.date(2026, 2, 21)), (168, "evening", "review"))

    def test_last_weekend_of_december_is_year_not_month(self):
        # Dec 2026: last Sat = 26th, last Sun = 27th. Year-end beats the monthly upgrade.
        self.assertEqual(rd.auto_schedule(dt.date(2026, 12, 26)), (8760, "evening", "year_review"))
        self.assertEqual(rd.auto_schedule(dt.date(2026, 12, 27)), (8760, "evening", "year_ahead"))

    def test_ordinary_december_weekend_is_still_weekly(self):
        # An earlier-December Saturday/Sunday is just a normal week edition.
        self.assertEqual(rd.auto_schedule(dt.date(2026, 12, 19)), (168, "evening", "review"))
        self.assertEqual(rd.auto_schedule(dt.date(2026, 12, 20)), (168, "evening", "ahead"))

    def test_full_year_distribution(self):
        # Walk every day of a year: never raises, and exactly one last-Saturday per month is
        # upgraded (December's to year_review, the other 11 to month_review) — same for Sundays.
        sat, sun = {}, {}
        d = dt.date(2027, 1, 1)
        while d.year == 2027:
            _, _, mode = rd.auto_schedule(d)              # must not raise on any date
            if d.isoweekday() == 6:
                sat[mode] = sat.get(mode, 0) + 1
            elif d.isoweekday() == 7:
                sun[mode] = sun.get(mode, 0) + 1
            d += dt.timedelta(days=1)
        self.assertEqual(sat.get("year_review"), 1)       # only December's last Saturday
        self.assertEqual(sat.get("month_review"), 11)     # the other eleven months
        self.assertEqual(sun.get("year_ahead"), 1)
        self.assertEqual(sun.get("month_ahead"), 11)


class TestResolveAuto(unittest.TestCase):
    """resolve_auto mutates args from env (manual cloud run) or the weekday (scheduled)."""

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("IN_HOURS", "IN_EDITION", "IN_MODE")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _args(self):
        return types.SimpleNamespace(hours=24, edition="morning", mode="daily")

    def test_manual_inputs_from_env(self):
        os.environ["IN_HOURS"] = "168"
        os.environ["IN_EDITION"] = "evening"
        os.environ["IN_MODE"] = "review"
        a = self._args()
        rd.resolve_auto(a)
        self.assertEqual((a.hours, a.edition, a.mode), (168, "evening", "review"))

    def test_manual_month_review_from_env(self):
        # A workflow_dispatch can request the new editions explicitly.
        os.environ["IN_HOURS"] = "720"
        os.environ["IN_EDITION"] = "evening"
        os.environ["IN_MODE"] = "month_review"
        a = self._args()
        rd.resolve_auto(a)
        self.assertEqual((a.hours, a.edition, a.mode), (720, "evening", "month_review"))

    def test_manual_inputs_default_edition_mode_when_blank(self):
        os.environ["IN_HOURS"] = "48"   # hours given, edition/mode left empty
        a = self._args()
        rd.resolve_auto(a)
        self.assertEqual((a.hours, a.edition, a.mode), (48, "morning", "daily"))

    def test_scheduled_falls_back_to_weekday(self):
        # No IN_HOURS -> derive from today's UTC date (same call resolve_auto makes).
        a = self._args()
        rd.resolve_auto(a)
        expected = rd.auto_schedule(dt.datetime.now(dt.timezone.utc).date())
        self.assertEqual((a.hours, a.edition, a.mode), expected)

    def test_non_numeric_hours_falls_back_to_schedule(self):
        # A typo'd manual input ("24h") must not crash the run — fall back to the schedule.
        os.environ["IN_HOURS"] = "24h"
        a = self._args()
        rd.resolve_auto(a)
        self.assertEqual((a.hours, a.edition, a.mode),
                         rd.auto_schedule(dt.datetime.now(dt.timezone.utc).date()))


class TestWindowFeedUrl(unittest.TestCase):
    """The Google News breadth feed's 'when:Nd' recency cap must widen to match the run's
    window, so reviews aren't grounded in only the hardcoded 2 days."""

    GN = "https://news.google.com/rss/search?q=x%20when%3A2d&hl=en-US"

    def test_daily_is_byte_identical(self):
        self.assertEqual(rd._window_feed_url(self.GN, 24), self.GN)   # 24h -> when:2d, unchanged

    def test_widens_for_week_month_year(self):
        self.assertIn("when%3A8d", rd._window_feed_url(self.GN, 168))     # week
        self.assertIn("when%3A31d", rd._window_feed_url(self.GN, 720))    # month
        self.assertIn("when%3A366d", rd._window_feed_url(self.GN, 8760))  # year

    def test_non_google_url_untouched(self):
        u = "https://www.fiercepharma.com/rss/xml"
        self.assertEqual(rd._window_feed_url(u, 720), u)

    def test_handles_raw_colon_form(self):
        self.assertIn("when:31d", rd._window_feed_url("https://x.test/?q=a%20when:2d", 720))


class TestForceTitle(unittest.TestCase):
    """force_title normalises the H1: date always, and the whole canonical title for the
    special editions (so market scale / edition detection don't depend on the model)."""

    D = dt.date(2026, 6, 27)

    def test_special_edition_title_is_forced_regardless_of_model_wording(self):
        out = rd.force_title("# Pharma Monthly Wrap-Up - whenever\n\nbody", "month_review", self.D)
        self.assertTrue(out.startswith("# Pharma Month in Review — 27/06/2026"))

    def test_year_edition_title_forced(self):
        out = rd.force_title("# some creative heading the model invented\n", "year_review", self.D)
        self.assertTrue(out.startswith("# Pharma Year in Review — 27/06/2026"))

    def test_daily_keeps_model_prefix_and_only_fixes_date(self):
        out = rd.force_title("# Pharma Evening Digest - 1 Jan 1999\nx", "daily", dt.date(2026, 6, 16))
        self.assertTrue(out.startswith("# Pharma Evening Digest — 16/06/2026"))


class TestArchiveCorpus(unittest.TestCase):
    """The backward review editions synthesise from the archived briefs covering the window
    instead of live RSS, falling back to RSS when the archive is too thin."""

    DAILY = ("# Pharma Morning Digest — {date}\n\n"
             "> **Talking point:** Thesis for {date}.\n\n"
             "## TL;DR\n- First point [1]\n- Second point [2]\n\n"
             "## Top Stories\nbody\n\n"
             "## Sources\n"
             "1. [Headline A {date}](https://ex.com/a-{n}) · {date} · 10:00 UTC\n"
             "2. [Headline B {date}](https://ex.com/b-{n}) · {date} · 11:00 UTC\n")

    def _make_archive(self, dates):
        d = Path(tempfile.mkdtemp())
        for i, day in enumerate(dates):
            (d / f"{day}.md").write_text(
                self.DAILY.format(date=day.isoformat(), n=i), encoding="utf-8")
        (d / "published.json").write_text("{}", encoding="utf-8")   # must be ignored
        return d

    def _brief(self, title, date, n=0):
        """A minimal valid brief with an arbitrary title (for review/ahead/daily mixes)."""
        return (f"# {title} — {date}\n\n> **Talking point:** Thesis for {title}.\n\n"
                f"## TL;DR\n- A point [1]\n\n## Sources\n"
                f"1. [Headline {date}](https://ex.com/x-{n}) · {date}\n")

    def test_filename_date_parsing(self):
        self.assertEqual(rd._brief_date("2026-06-15.md"), dt.date(2026, 6, 15))
        self.assertIsNone(rd._brief_date("published.json"))
        self.assertIsNone(rd._brief_date("notes.md"))

    def test_brief_window_days_and_forward_detection(self):
        self.assertEqual(rd._brief_window_days("# Pharma Year in Review — x\n"), 365)
        self.assertEqual(rd._brief_window_days("# Pharma Month in Review — x\n"), 30)
        self.assertEqual(rd._brief_window_days("# Pharma Week in Review — x\n"), 7)
        self.assertEqual(rd._brief_window_days("# Pharma Morning Digest — x\n"), 0)
        self.assertTrue(rd._brief_is_forward("# Pharma Month Ahead — x\n"))
        self.assertFalse(rd._brief_is_forward("# Pharma Month in Review — x\n"))

    def test_sources_parse_into_items(self):
        items = rd._brief_sources(self.DAILY.format(date="2026-06-10", n=0))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["link"], "https://ex.com/a-0")
        self.assertTrue(items[0]["title"].startswith("Headline A"))

    def test_timeline_entry_has_thesis_and_points(self):
        entry = rd._brief_timeline_entry(self.DAILY.format(date="2026-06-10", n=0))
        self.assertIn("Thesis: Thesis for 2026-06-10", entry)
        self.assertIn("First point", entry)
        self.assertNotIn("[1]", entry)             # citation markers stripped from the timeline

    def test_gather_from_archive_builds_items_and_timeline(self):
        today = dt.date(2026, 6, 30)
        dates = [today - dt.timedelta(days=k) for k in range(1, 11)]   # 10 briefs in-window
        d = self._make_archive(dates)
        items, timeline = rd.gather_from_archive(today, 30, archive_dir=d)
        self.assertEqual(len(items), 20)            # 10 briefs × 2 unique sources
        self.assertTrue(all(it["link"].startswith("https://") for it in items))
        self.assertEqual(timeline.count("Thesis:"), 10)

    def test_gather_from_archive_respects_window(self):
        today = dt.date(2026, 6, 30)
        dates = [today - dt.timedelta(days=k) for k in (1, 2, 3, 100, 200)]  # 2 are out of window
        d = self._make_archive(dates)
        items, timeline = rd.gather_from_archive(today, 30, archive_dir=d)
        self.assertEqual(timeline.count("Thesis:"), 3)   # only the 3 within 30 days

    def test_thin_archive_falls_back(self):
        today = dt.date(2026, 6, 30)
        d = self._make_archive([today - dt.timedelta(days=1)])   # 1 brief < MIN_ARCHIVE_BRIEFS
        items, timeline = rd.gather_from_archive(today, 30, archive_dir=d)
        self.assertEqual((items, timeline), ([], ""))

    def test_malformed_brief_degrades_quietly(self):
        # A junk brief (no title/sources) and a bad-date filename must not break the run: the
        # good briefs still contribute, the junk contributes nothing, nothing raises.
        today = dt.date(2026, 6, 30)
        d = self._make_archive([today - dt.timedelta(days=k) for k in (1, 2, 3)])
        (d / f"{(today - dt.timedelta(days=4)).isoformat()}.md").write_text("garbage, no title or sources")
        (d / "2026-06-99.md").write_text("invalid date in filename")
        items, timeline = rd.gather_from_archive(today, 30, archive_dir=d)
        self.assertEqual(len(items), 6)              # 3 good briefs × 2 sources; junk adds none
        self.assertEqual(timeline.count("Thesis:"), 3)

    def test_rollup_subsumes_finer_briefs_and_excludes_forward(self):
        # A Month in Review subsumes that month's weekly + daily briefs (no double-counting), a
        # forward 'Ahead' brief is excluded from a retrospective, and the uncovered tail is kept.
        today = dt.date(2026, 7, 20)
        d = Path(tempfile.mkdtemp())
        (d / "2026-06-30.md").write_text(self._brief("Pharma Month in Review", "2026-06-30", 1))
        (d / "2026-06-18.md").write_text(self._brief("Pharma Week in Review", "2026-06-18", 2))
        (d / "2026-06-10.md").write_text(self._brief("Pharma Morning Digest", "2026-06-10", 3))
        (d / "2026-07-05.md").write_text(self._brief("Pharma Month Ahead", "2026-07-05", 4))
        (d / "2026-07-08.md").write_text(self._brief("Pharma Morning Digest", "2026-07-08", 5))
        (d / "2026-07-15.md").write_text(self._brief("Pharma Morning Digest", "2026-07-15", 6))
        items, timeline = rd.gather_from_archive(today, 365, archive_dir=d)
        self.assertIn("Month in Review", timeline)
        self.assertNotIn("Week in Review", timeline)    # subsumed by the month rollup
        self.assertNotIn("Ahead", timeline)             # forward-looking brief excluded
        self.assertNotIn("2026-06-10", timeline)        # daily inside the month, subsumed
        self.assertIn("2026-07-15", timeline)           # uncovered tail daily kept
        self.assertEqual(timeline.count("###"), 3)      # month review + 2 tail dailies


class TestCallModelRetry(unittest.TestCase):
    """call_model is the one network call the whole pipeline depends on — its retry/backoff
    and fail-fast-on-4xx behaviour were previously untested."""

    SECRETS = {"GEMINI_API_KEY": "k"}   # makes resolve_engine pick a keyed engine

    @staticmethod
    def _ok(content):
        return _JsonResp({"choices": [{"message": {"content": content}}]})

    def test_retries_transient_then_succeeds(self):
        seq = [urllib.error.URLError("conn reset"), self._ok("the digest")]

        def fake(req, timeout=180):
            r = seq.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(rd.time, "sleep", lambda *a: None), \
             mock.patch.object(rd.urllib.request, "urlopen", fake):
            out = rd.call_model(self.SECRETS, "system", "user")
        self.assertEqual(out, "the digest")
        self.assertEqual(seq, [])   # both the failure and success were consumed

    def test_4xx_fails_fast_without_retry(self):
        calls = {"n": 0}

        def fake(req, timeout=180):
            calls["n"] += 1
            raise urllib.error.HTTPError("u", 400, "Bad Request", {}, None)

        with mock.patch.object(rd.time, "sleep", lambda *a: None), \
             mock.patch.object(rd.urllib.request, "urlopen", fake):
            with self.assertRaises(urllib.error.HTTPError):
                rd.call_model(self.SECRETS, "s", "u")
        self.assertEqual(calls["n"], 1)

    def test_missing_key_raises(self):
        with self.assertRaises(RuntimeError):
            rd.call_model({}, "s", "u")   # no engine key configured


class TestReviewDigest(unittest.TestCase):
    """The grounding self-check is the product's anti-hallucination guarantee, and its
    PASS/issue parsing + catalyst extraction is fragile — now covered. call_model is mocked."""

    TODAY = dt.date(2026, 6, 14)

    def _review(self, model_output):
        with mock.patch.object(rd, "call_model", lambda *a, **k: model_output):
            return rd.review_digest({}, "digest", "corpus", self.TODAY)

    def test_pass_extracts_only_future_catalysts(self):
        out = ("### GROUNDING\nPASS\n\n### CATALYSTS\n"
               "2026-08-01 | tirzepatide PDUFA decision\n"
               "2020-01-01 | ancient event (past, must be dropped)\n")
        ok, issues, events = self._review(out)
        self.assertTrue(ok)
        self.assertEqual(issues, "")
        self.assertEqual(events, [(dt.date(2026, 8, 1), "tirzepatide PDUFA decision")])

    def test_flags_unsupported_claims(self):
        out = '### GROUNDING\n- "Lilly cured cancer" — not in the sources\n\n### CATALYSTS\nNONE\n'
        ok, issues, events = self._review(out)
        self.assertFalse(ok)
        self.assertIn("Lilly cured cancer", issues)
        self.assertEqual(events, [])

    def test_malformed_output_is_failsafe_pass(self):
        # Model ignored the format → don't trust a parse; pass grounding (fail-safe).
        ok, issues, events = self._review("Sure! Overall the digest looks great.")
        self.assertEqual((ok, issues, events), (True, "", []))

    def test_call_failure_is_failsafe(self):
        def boom(*a, **k):
            raise RuntimeError("network down")
        with mock.patch.object(rd, "call_model", boom):
            result = rd.review_digest({}, "d", "c", self.TODAY)
        self.assertEqual(result, (True, "", []))

    def test_revision_keeps_original_when_result_is_thin(self):
        # A revision that comes back hollow must NOT ship — fall back to the (already-guarded)
        # original, since the empty-output guard runs before this step and won't re-check it.
        original = "x" * 500
        with mock.patch.object(rd, "call_model", lambda *a, **k: "too short"):
            self.assertEqual(rd.revise_for_grounding({}, original, "corpus", "issues"), original)

    def test_revision_failure_keeps_original(self):
        def boom(*a, **k):
            raise RuntimeError("down")
        with mock.patch.object(rd, "call_model", boom):
            self.assertEqual(rd.revise_for_grounding({}, "y" * 500, "c", "i"), "y" * 500)


class TestFinalizeReadTime(unittest.TestCase):
    def test_replaces_ranged_read_time_without_duplicating(self):
        # The evening template writes a RANGE ('~5-8 min read'); finalize must replace it
        # with the computed value, not append a second read-time next to it.
        md = ("# Pharma Week Ahead - 2026-06-14\n"
              "*Window: last 168 hours · Engine: X · Edition: evening · ~5-8 min read*\n\n"
              "> point.\n\n### Story\nBody [1].\n")
        out = rd.finalize(md, F.FINALIZE_ITEMS, "Gemini", "gemini-2.5-flash")
        self.assertNotIn("5-8 min read", out)        # the range was replaced
        self.assertEqual(out.count("min read"), 1)    # exactly one read-time


class TestApplyWindowSubtitle(unittest.TestCase):
    TODAY = dt.date(2026, 6, 14)

    def test_replaces_window_and_preserves_separator(self):
        sub = ("# Pharma Week Ahead — 14/06/2026\n"
               "*Window: last 168 hours · Engine: Gemini · Edition: evening · ~12 min read*\n")
        out = rd.apply_window_subtitle(sub, "ahead", 168, self.TODAY, 304)
        self.assertIn("recent articles · Engine", out)   # ' · ' separator kept (no 'articles· Engine')
        self.assertNotIn("articles· Engine", out)
        self.assertNotIn("last 168 hours", out)          # model's vague text gone

    def test_inserts_subtitle_when_window_missing(self):
        # Model omitted the 'Window:' line entirely — the deterministic subtitle must still be
        # injected (after the H1) rather than silently dropped.
        sub = "# Pharma Week Ahead — 14/06/2026\n\nSome body text.\n"
        out = rd.apply_window_subtitle(sub, "ahead", 168, self.TODAY, 304)
        self.assertIn(rd.window_subtitle("ahead", 168, self.TODAY, 304), out)
        self.assertTrue(out.startswith("# Pharma Week Ahead"))   # H1 still leads


class TestParseFeedEntityGuard(unittest.TestCase):
    def test_feed_declaring_entities_is_skipped(self):
        # "billion laughs" style payload — must be refused, not parsed.
        bomb = (b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]>'
                b'<rss><channel><item><title>&lol;</title>'
                b'<link>https://x.com/a</link></channel></rss>')
        self.assertEqual(rd.parse_feed(bomb, dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)), [])


if __name__ == "__main__":
    unittest.main()
