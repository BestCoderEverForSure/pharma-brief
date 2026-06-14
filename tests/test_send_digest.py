"""Tests for pharma-news/send_digest.py — the email rendering path.

The email is a SEPARATE code path from the website: it has its own source
renumbering, citation-linking, markdown->HTML, and "Sources last" assembly. These
tests lock that behaviour. The network bits (Yahoo markets) are patched out so the
suite stays offline and deterministic; published_stamp() is time-based so we never
assert on its exact value.

Run:  python3 -m unittest discover -s tests
"""

import datetime as dt
import tempfile
import unittest
import urllib.error
from unittest import mock
from pathlib import Path

import fixtures as F

sd = F.load_send_digest()


class _Resp:
    """Minimal stand-in for an http.client.HTTPResponse used as a context manager."""
    def __init__(self, status, body):
        self.status, self._body = status, body
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def read(self):
        return self._body.encode("utf-8")


class TestUrlopenRetry(unittest.TestCase):
    """The delivery scripts must retry a transient blip rather than fail the run (a failed
    send aborts the cloud job, costing the day's archive + publish)."""

    def test_retries_transient_then_succeeds(self):
        seq = [urllib.error.URLError("conn reset"), _Resp(200, "ok")]

        def fake_urlopen(req, timeout=30):
            r = seq.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

        with mock.patch.object(sd.time, "sleep", lambda *a: None), \
             mock.patch.object(sd.urllib.request, "urlopen", fake_urlopen):
            status, body = sd._urlopen_retry(object(), timeout=5)
        self.assertEqual((status, body), (200, "ok"))
        self.assertEqual(seq, [])   # both the failure and the success were consumed

    def test_4xx_raised_immediately_without_retry(self):
        calls = {"n": 0}

        def fake_urlopen(req, timeout=30):
            calls["n"] += 1
            raise urllib.error.HTTPError("u", 422, "Unprocessable", {}, None)

        with mock.patch.object(sd.time, "sleep", lambda *a: None), \
             mock.patch.object(sd.urllib.request, "urlopen", fake_urlopen):
            with self.assertRaises(urllib.error.HTTPError):
                sd._urlopen_retry(object())
        self.assertEqual(calls["n"], 1)   # a 4xx is not retried


class TestRenumberAndCitations(unittest.TestCase):
    def setUp(self):
        sd._SRCMAP = {}

    def test_renumber_by_first_appearance(self):
        md = ("Body [7] then [3].\n\n## Sources\n"
              "3. [B](https://b.example/x)\n7. [A](https://a.example/y)\n")
        out = sd.renumber_sources(md)
        self.assertIn("Body [1] then [2].", out)
        self.assertIn("1. [A](https://a.example/y)", out)
        self.assertIn("2. [B](https://b.example/x)", out)

    def test_prepare_digest_arms_srcmap(self):
        md = ("Body [7].\n\n## Sources\n7. [A](https://a.example/y)\n")
        sd.prepare_digest(md)
        self.assertEqual(sd._SRCMAP, {"1": "https://a.example/y"})

    def test_citation_clickable_when_srcmap_set(self):
        sd._SRCMAP = {"1": "https://a.example/y"}
        out = sd.md_inline("See [1].")
        self.assertIn('<a href="https://a.example/y"', out)
        self.assertIn(">[1]</a>", out)

    def test_direct_link_gets_check_mark(self):
        out = sd.md_inline("[Pub](https://www.statnews.com/x)")
        self.assertIn("✓", out)

    def test_google_news_link_no_check_mark(self):
        out = sd.md_inline("[Agg](https://news.google.com/x)")
        self.assertNotIn("✓", out)

    def test_strips_methodology_pseudo_citation(self):
        self.assertNotIn("catalysts.md", sd.md_inline("text [catalysts.md] more"))


class TestMdFragment(unittest.TestCase):
    def test_major_heading_gets_label(self):
        out = sd._md_fragment("### Big news {major}\nbody")
        self.assertIn("Major story", out)
        self.assertNotIn("{major}", out)

    def test_lists_and_blockquote(self):
        out = sd._md_fragment("> talking point\n\n- one\n- two")
        self.assertIn("<blockquote>", out)
        self.assertIn("<ul>", out)
        self.assertEqual(out.count("<li>"), 2)


class TestEmailAssembly(unittest.TestCase):
    """email_html must place Sources LAST — after the (appended) catalysts + markets."""

    def setUp(self):
        # Patch out the two network-touching appenders with identifiable sentinels.
        self._saved = (sd.render_catalysts_email, sd.render_market_email)
        sd.render_catalysts_email = lambda: "<!--CATALYSTS-->"
        sd.render_market_email = lambda md: "<!--MARKETS-->"

    def tearDown(self):
        sd.render_catalysts_email, sd.render_market_email = self._saved

    def test_sources_rendered_after_catalysts_and_markets(self):
        md = ("# Title\n\n> Talking point.\n\n### Story\nBody [1].\n\n"
              "## Sources\n1. [A](https://a.example/y)\n\n---\n*Footer note.*\n")
        sd.prepare_digest(md)
        html = sd.email_html(md)
        i_cat = html.index("<!--CATALYSTS-->")
        i_mkt = html.index("<!--MARKETS-->")
        i_src = html.index("Sources")
        self.assertLess(i_cat, i_mkt)
        self.assertLess(i_mkt, i_src)        # Sources come last
        self.assertIn("<h2>Sources</h2>", html)


class TestEmailOnRealFinalizedOutput(unittest.TestCase):
    """End-to-end check that the EMAIL still renders correctly on the exact output the
    refactored finalize() produces (the frozen golden). Ties the two code paths together."""

    def setUp(self):
        self._saved = (sd.render_catalysts_email, sd.render_market_email)
        sd.render_catalysts_email = lambda: ""
        sd.render_market_email = lambda md: ""

    def tearDown(self):
        sd.render_catalysts_email, sd.render_market_email = self._saved

    def test_renders_citations_sources_and_footer(self):
        finalized = F.read_golden("finalize_basic.txt")
        md = sd.prepare_digest(finalized)
        html = sd.email_html(md)
        self.assertIn('<a href="https://news.google.com/x?a=%281%29"', html)  # [1] clickable
        self.assertIn(">[1]</a>", html)
        self.assertIn("<h2>Sources</h2>", html)
        self.assertIn("grounding check", html)                                # footer survived
        self.assertIn("Major story", html)                                    # {major} label
        self.assertNotIn("## Sources", html)                                  # markdown fully converted


class TestParseCatalysts(unittest.TestCase):
    def test_iso_and_month_year(self):
        tmp = tempfile.TemporaryDirectory()
        path = Path(tmp.name) / "catalysts.md"
        path.write_text("- **2026-07-01** · tirzepatide PDUFA; clause\n"
                        "- **Aug 2026** · donanemab readout\n", encoding="utf-8")
        orig = sd.CATALYSTS_PATH
        sd.CATALYSTS_PATH = path
        try:
            events = sd._parse_catalysts()
        finally:
            sd.CATALYSTS_PATH = orig
            tmp.cleanup()
        self.assertEqual(events[0]["date"], dt.date(2026, 7, 1))
        self.assertEqual(events[0]["label"], "tirzepatide PDUFA")
        self.assertEqual(events[1]["date"], dt.date(2026, 8, 15))


if __name__ == "__main__":
    unittest.main()
