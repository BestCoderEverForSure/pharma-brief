"""Tests for pharma-news/make_audio.py — strip_markdown(), the digest→spoken-text
transform. Pure/offline (no `say`, no audio): we only check the text it produces.

Run:  python3 -m unittest discover -s tests
"""

import unittest

import fixtures as F

ma = F.load_make_audio()


class TestStripMarkdown(unittest.TestCase):
    def test_drops_sources_section(self):
        out = ma.strip_markdown("# Brief\nBody line.\n\n## Sources\n1. [A](https://x.example/a)\n")
        self.assertIn("Body line.", out)
        self.assertNotIn("Sources", out)                 # everything from Sources on is cut
        self.assertNotIn("x.example", out)

    def test_flattens_links_emphasis_and_leading_emoji(self):
        out = ma.strip_markdown("## 📊 Markets\nThe **drug** *won* a [big nod](https://e.example/a) today.\n")
        self.assertIn("Markets", out)                    # heading text kept; '##' + emoji gone
        self.assertNotIn("📊", out)
        self.assertIn("The drug won a big nod today.", out)
        self.assertNotIn("e.example", out)               # link URL spoken as its text only

    def test_skips_tables_rules_and_accuracy_footer(self):
        out = ma.strip_markdown("Intro.\n\n| col | col |\n| --- | --- |\n\n---\n> *Facts verified against sources.*\n")
        self.assertIn("Intro.", out)
        self.assertNotIn("col", out)                     # table rows skipped
        self.assertNotIn("Facts verified", out)          # accuracy footer skipped
        self.assertNotIn("---", out)
