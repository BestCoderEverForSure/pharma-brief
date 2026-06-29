"""Tests for pharma_render.py — the logic SHARED by the website and the email renderers.

This module is the single source of truth for citation renumbering, the [n]->URL map,
catalyst-calendar parsing, and ticker selection, so both renderers stay in lock-step.
(The build_site / send_digest tests also exercise these via each renderer; these test the
canonical module directly, incl. select_tickers, which the per-renderer tests don't.)

Run:  python3 -m unittest discover -s tests
"""

import datetime as dt
import json
import tempfile
import unittest
from unittest import mock
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


class TestCatalystDate(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(pr.catalyst_date("2026-09-15"), dt.date(2026, 9, 15))

    def test_month_year_resolves_to_15th(self):
        self.assertEqual(pr.catalyst_date("Sep 2026"), dt.date(2026, 9, 15))
        self.assertEqual(pr.catalyst_date("September 2026"), dt.date(2026, 9, 15))
        self.assertEqual(pr.catalyst_date("Jan 2027"), dt.date(2027, 1, 15))

    def test_unparseable_is_none(self):
        self.assertIsNone(pr.catalyst_date("sometime this fall"))


class TestShortLabel(unittest.TestCase):
    def test_drops_unclosed_paren_from_semicolon_split(self):
        # ';' sits INSIDE the parenthetical, so the naive split kept '(' without ')'.
        s = pr._short_label("Q2 2026 earnings season (Lilly reports early Aug; Novo, Pfizer too).")
        self.assertEqual(s, "Q2 2026 earnings season")
        self.assertEqual(s.count("("), s.count(")"))     # balanced

    def test_word_boundary_truncation_no_midword_no_unbalanced(self):
        long = ("100% branded-pharma tariff takes effect for large firms (0% for MFN + "
                "onshoring signatories). Major supply-chain and pricing catalyst.")
        s = pr._short_label(long)
        self.assertTrue(s.endswith("…"))
        self.assertFalse(s.rstrip("…").endswith("-"))    # no mid-word hyphen cut
        self.assertEqual(s.count("("), s.count(")"))      # parens balanced
        self.assertLessEqual(len(s), 112)

    def test_short_desc_unchanged(self):
        self.assertEqual(pr._short_label("Tebipenem HBr (Spero/GSK) - FDA decision expected"),
                         "Tebipenem HBr (Spero/GSK) - FDA decision expected")


class TestParseCatalysts(unittest.TestCase):
    def test_strips_auto_detected_tag(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "catalysts.md"
        path.write_text("- **2026-06-17** · Concord Biotech analyst meet (auto-detected 2026-06-14)\n",
                        encoding="utf-8")
        try:
            events = pr.parse_catalysts(path)
        finally:
            tmp.cleanup()
        self.assertEqual(events[0]["label"], "Concord Biotech analyst meet")
        self.assertNotIn("auto-detected", events[0]["full"])

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


class TestUpcomingCatalysts(unittest.TestCase):
    REF = dt.date(2026, 6, 28)

    @staticmethod
    def _ev(d):
        return {"date": d, "label": "x", "full": "x"}

    def _events(self):
        return [self._ev(dt.date(2026, 6, 18)),   # past — must be dropped
                self._ev(dt.date(2026, 6, 28)),   # today — kept (next 30 days)
                self._ev(dt.date(2026, 7, 10)),   # +12d — next 30 days
                self._ev(dt.date(2026, 8, 20)),   # +53d — 1–3 months
                self._ev(dt.date(2026, 12, 1))]   # +156d — on the horizon

    def test_drops_events_before_ref_date(self):
        groups = pr.upcoming_catalysts(self._events(), self.REF)
        kept = [e["date"] for _, evs in groups for e in evs]
        self.assertNotIn(dt.date(2026, 6, 18), kept)        # the past event is gone
        self.assertIn(dt.date(2026, 6, 28), kept)           # ref date itself is kept

    def test_buckets_and_labels(self):
        groups = pr.upcoming_catalysts(self._events(), self.REF)
        self.assertEqual([label for label, _ in groups], list(pr.CATALYST_BUCKETS))
        by_label = {label: [e["date"] for e in evs] for label, evs in groups}
        self.assertEqual(by_label["Next 30 days"], [dt.date(2026, 6, 28), dt.date(2026, 7, 10)])
        self.assertEqual(by_label["1–3 months"], [dt.date(2026, 8, 20)])
        self.assertEqual(by_label["On the horizon"], [dt.date(2026, 12, 1)])

    def test_empty_buckets_are_omitted(self):
        # Only a far-future event -> just the horizon bucket appears, not three empty ones.
        groups = pr.upcoming_catalysts([self._ev(dt.date(2026, 12, 1))], self.REF)
        self.assertEqual([label for label, _ in groups], ["On the horizon"])

    def test_all_past_is_empty(self):
        self.assertEqual(pr.upcoming_catalysts([self._ev(dt.date(2026, 1, 1))], self.REF), [])

    def test_defaults_to_today(self):
        past, future = dt.date.today() - dt.timedelta(days=5), dt.date.today() + dt.timedelta(days=5)
        groups = pr.upcoming_catalysts([self._ev(past), self._ev(future)])
        kept = [e["date"] for _, evs in groups for e in evs]
        self.assertEqual(kept, [future])


class TestForwardCalendarText(unittest.TestCase):
    SRC = (
        "# Catalyst Calendar\n"
        "Some intro prose.\n"
        "\n"
        "## Regulatory\n"
        "- **2026-06-18** · Tebipenem FDA decision\n"      # past as of REF -> dropped
        "- **~2026-06-20** · Cytisinicline FDA decision\n"  # past (tilde tolerated) -> dropped
        "- **2026-09-18** · Zidesamtinib PDUFA\n"           # future -> kept
        "- **Monthly (~3rd week)** · EMA CHMP meeting\n"    # no parseable date -> kept
        "> Tip: keep this trimmed.\n")
    REF = dt.date(2026, 6, 28)

    def _run(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "catalysts.md"
        path.write_text(self.SRC, encoding="utf-8")
        try:
            return pr.forward_calendar_text(path, self.REF)
        finally:
            tmp.cleanup()

    def test_drops_only_past_dated_lines(self):
        out = self._run()
        self.assertNotIn("Tebipenem", out)        # past
        self.assertNotIn("Cytisinicline", out)    # past (had a ~ prefix)
        self.assertIn("Zidesamtinib", out)        # future dated entry survives

    def test_keeps_structure_and_undated_lines(self):
        out = self._run()
        for keep in ("# Catalyst Calendar", "Some intro prose.", "## Regulatory",
                     "Monthly (~3rd week)", "> Tip: keep this trimmed."):
            self.assertIn(keep, out)

    def test_missing_file_is_empty(self):
        self.assertEqual(pr.forward_calendar_text(Path("/no/such/catalysts.md"), self.REF), "")


class _R:
    """Stand-in for a Yahoo HTTP response (fetch_market calls .read() directly)."""
    def __init__(self, body):
        self._b = body
    def read(self):
        return self._b


class TestFetchMarket(unittest.TestCase):
    DAY = 86400

    def _resp(self, closes, timestamps):
        return _R(json.dumps({"chart": {"result": [
            {"timestamp": timestamps, "indicators": {"quote": [{"close": closes}]}}]}}).encode())

    def test_parses_concurrently(self):
        ts = [1_700_000_000, 1_700_000_000 + 7 * self.DAY]
        def fake(req, timeout=15):
            return self._resp([100.0, 110.0], ts)   # +10% over the 7-day span
        with mock.patch.object(pr.urllib.request, "urlopen", fake):
            out = pr.fetch_market([("LLY", "Eli Lilly"), ("PFE", "Pfizer")], days=7, timeout=1)
        self.assertEqual(len(out), 2)
        self.assertTrue(all(round(x["pct"], 1) == 10.0 and x["last"] == 110.0 for x in out))

    def test_days_selects_the_right_base_close(self):
        base = 1_700_000_000
        ts = [base + i * self.DAY for i in range(8)]        # 8 consecutive daily closes
        closes = [100, 101, 102, 103, 104, 105, 106, 107]    # latest 107 at ts[7]
        def fake(req, timeout=15):
            return self._resp(closes, ts)
        with mock.patch.object(pr.urllib.request, "urlopen", fake):
            out7 = pr.fetch_market([("X", "X")], days=7)
            out5 = pr.fetch_market([("X", "X")], days=5)
        self.assertAlmostEqual(out7[0]["pct"], 7.0, places=1)                 # vs ts[0]=100
        self.assertAlmostEqual(out5[0]["pct"], (107 / 102 - 1) * 100, places=1)  # vs ts[2]=102

    def test_skips_failures(self):
        def fake(req, timeout=15):
            raise OSError("blocked")
        with mock.patch.object(pr.urllib.request, "urlopen", fake):
            self.assertEqual(pr.fetch_market([("LLY", "Eli Lilly")]), [])

    def test_empty_is_empty(self):
        self.assertEqual(pr.fetch_market([]), [])


class TestBriefMarketDays(unittest.TestCase):
    def test_daily(self):
        self.assertEqual(pr.brief_market_days("# Pharma Morning Digest — 14/06/2026\nx"), 5)

    def test_review(self):
        self.assertEqual(pr.brief_market_days("# Pharma Week in Review — 14/06/2026\nx"), 7)

    def test_ahead_is_none(self):
        self.assertIsNone(pr.brief_market_days("# Pharma Week Ahead — 14/06/2026\nx"))

    def test_month_review(self):
        self.assertEqual(pr.brief_market_days("# Pharma Month in Review — 27/06/2026\nx"), 30)

    def test_month_ahead_is_none(self):
        self.assertIsNone(pr.brief_market_days("# Pharma Month Ahead — 28/06/2026\nx"))

    def test_year_review(self):
        self.assertEqual(pr.brief_market_days("# Pharma Year in Review — 26/12/2026\nx"), 365)

    def test_year_ahead_is_none(self):
        self.assertIsNone(pr.brief_market_days("# Pharma Year Ahead — 27/12/2026\nx"))


class TestYahooRange(unittest.TestCase):
    """The fetch window must comfortably exceed the requested lookback, or a long move
    silently collapses to whatever short span range=1mo happened to return."""

    def test_picks_a_range_that_covers_the_lookback(self):
        self.assertEqual(pr._yahoo_range(5), "1mo")     # daily
        self.assertEqual(pr._yahoo_range(7), "1mo")     # week
        self.assertEqual(pr._yahoo_range(30), "3mo")    # month
        self.assertEqual(pr._yahoo_range(365), "2y")    # year — must reach past 365 days
        self.assertEqual(pr._yahoo_range(99999), "max")


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
