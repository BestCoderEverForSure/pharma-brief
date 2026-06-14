"""Tests for pharma-news/send_telegram.py — the summary-card builder.

build_message extracts the title, talking point, and TL;DR bullets and appends a
"read the full brief" link; tg_inline converts the markdown subset to Telegram HTML
and drops citations/{major}. No network is touched.

Run:  python3 -m unittest discover -s tests
"""

import unittest

import fixtures as F

tg = F.load_send_telegram()


class TestTgInline(unittest.TestCase):
    def test_strips_citations_and_major(self):
        out = tg.tg_inline("Big news [3] {major} indeed")
        self.assertNotIn("[3]", out)
        self.assertNotIn("{major}", out)

    def test_bold_italic_and_links(self):
        self.assertIn("<b>x</b>", tg.tg_inline("**x**"))
        self.assertIn("<i>y</i>", tg.tg_inline("*y*"))
        self.assertIn('<a href="https://e.com">L</a>', tg.tg_inline("[L](https://e.com)"))

    def test_strips_methodology_marker(self):
        self.assertNotIn("catalysts.md", tg.tg_inline("text [catalysts.md] more"))


class TestBuildMessage(unittest.TestCase):
    MD = (
        "# Pharma Morning Brief - 14/06/2026\n"
        "*Window: last 24h · Engine: Gemini*\n\n"
        "> **Talking point:** Lilly's lead widens.\n\n"
        "## TL;DR\n"
        "- First point [1]\n"
        "- Second point\n\n"
        "## Top Stories\n"
        "### A story\nbody\n"
    )

    def test_extracts_title_talking_point_and_bullets(self):
        msg = tg.build_message(self.MD, "2026-06-14", "https://site.example/base/")
        self.assertIn("Pharma Morning Brief", msg)
        self.assertIn("lead widens.", msg)                 # talking point (apostrophe HTML-escaped)
        self.assertNotIn("Talking point:", msg)
        self.assertIn("First point", msg)                  # TL;DR bullets
        self.assertIn("Second point", msg)
        self.assertNotIn("[1]", msg)                       # citation markers stripped

    def test_appends_full_brief_link_to_dated_page(self):
        msg = tg.build_message(self.MD, "2026-06-14", "https://site.example/base/")
        self.assertIn("https://site.example/base/2026-06-14.html", msg)
        self.assertIn("Read the full brief", msg)

    def test_tldr_stops_at_next_heading(self):
        # "A story" is under ## Top Stories, not TL;DR — it must not become a bullet.
        msg = tg.build_message(self.MD, "2026-06-14", "https://site.example/")
        self.assertNotIn("• body", msg)


if __name__ == "__main__":
    unittest.main()
