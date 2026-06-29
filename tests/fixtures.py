"""Shared test fixtures: module loaders, sample inputs, and golden-file helpers.

The two modules under test live in non-package dirs (`engine/`, `site/`) and one
of them (`site`) shadows a stdlib module name, so we load them by file path under
unique names rather than via the import system. Stdlib only — no pip, no pytest.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_run_digest():
    return _load(ROOT / "engine" / "run_digest.py", "rd_under_test")


def load_build_site():
    # NB: unique name — "site" would shadow the stdlib `site` module.
    return _load(ROOT / "site" / "build_site.py", "build_site_under_test")


def load_send_digest():
    return _load(ROOT / "pharma-news" / "send_digest.py", "send_digest_under_test")


def load_send_telegram():
    return _load(ROOT / "pharma-news" / "send_telegram.py", "send_telegram_under_test")


def load_pharma_render():
    return _load(ROOT / "pharma_render.py", "pharma_render_under_test")


def load_check_freshness():
    return _load(ROOT / "pharma-news" / "check_freshness.py", "check_freshness_under_test")


def load_set_schedule():
    return _load(ROOT / "pharma-news" / "set_schedule.py", "set_schedule_under_test")


def load_make_audio():
    return _load(ROOT / "pharma-news" / "make_audio.py", "make_audio_under_test")


def read_golden(name: str) -> str:
    return (GOLDEN_DIR / name).read_text(encoding="utf-8")


def write_golden(name: str, content: str) -> None:
    (GOLDEN_DIR / name).write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------- #
#  Shared sample inputs (used by both the golden generator and the tests, so
#  the frozen output always corresponds to exactly this input).
# --------------------------------------------------------------------------- #

# finalize(): exercises every cleanup step — leaked <small>, a [catalysts.md]
# pseudo-citation, a stray "Week Ahead" section, an old Engine label to rewrite,
# grouped "[2, 3]" citations, a bogus model-written Sources list, a "[Updated]"
# bracket and parens in a URL (markdown-link hazards), and a feed timestamp.
FINALIZE_ITEMS = [
    {"title": "Lilly's tirzepatide wins [Updated] FDA nod",
     "link": "https://news.google.com/x?a=(1)", "summary": "s",
     "when": "2026-06-12T14:30:00+00:00"},
    {"title": "Novo readout disappoints",
     "link": "https://www.statnews.com/y", "summary": "s", "when": "n/a"},
    {"title": "Pfizer deal",
     "link": "https://endpoints.news/z", "summary": "s",
     "when": "2026-06-11T09:00:00+00:00"},
]

FINALIZE_INPUT = """# Pharma Morning Brief - 2026-06-14
*Window: last 24h · Engine: OldLabel · morning · ~9 min read*

> A sharp talking point [catalysts.md].

### Lilly scores a win {major}
What it means: big deal [1] and also [2, 3]. <small>note</small>

### Week Ahead
- something the model wrongly wrote

## Sources
9. [garbage](https://bad)

---
*Facts verified against sources.*
"""

# finalize() second case: no existing "Engine:" subtitle and no "*Window…*" line,
# so the label is injected after the H1 and the read-time is appended fresh.
FINALIZE_INPUT_NOSUB = """# Pharma Week in Review - 2026-06-14

> Weekly synthesis.

### Theme one
Analysis here [1].
"""

# build_site.renumber_sources / link_headings: gappy, out-of-order source numbers
# plus an uncited source that must be pushed to the end.
RENUMBER_MD = """# Pharma Brief - 2026-06-14
*Window: last 24h · Engine: Gemini*

### First story
Body text [7].

### Second story
More [3].

## Sources
3. [Title B](https://b.example/x)
7. [Title A](https://a.example/y)
9. [Uncited C](https://c.example/z)
"""
