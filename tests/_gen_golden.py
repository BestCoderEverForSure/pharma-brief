"""Regenerate the golden fixtures from the CURRENT code.

Run this ONLY to (re)capture intended behavior — e.g. right before a refactor, to
lock in the existing output. After the refactor, the tests compare against these
frozen files, so a behavior change shows up as a test failure.

    python3 tests/_gen_golden.py
"""

import fixtures as F


def main() -> None:
    rd = F.load_run_digest()
    bs = F.load_build_site()

    F.write_golden("finalize_basic.txt",
                   rd.finalize(F.FINALIZE_INPUT, F.FINALIZE_ITEMS, "Gemini", "gemini-2.5-flash"))
    F.write_golden("finalize_nosub.txt",
                   rd.finalize(F.FINALIZE_INPUT_NOSUB, F.FINALIZE_ITEMS, "DeepSeek", "deepseek-chat"))
    F.write_golden("renumber_sources.txt", bs.renumber_sources(F.RENUMBER_MD))
    F.write_golden("link_headings.txt", bs.link_headings(bs.renumber_sources(F.RENUMBER_MD)))
    print("Golden fixtures regenerated.")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
