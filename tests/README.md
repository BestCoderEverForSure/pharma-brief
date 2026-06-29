# Tests

Stdlib `unittest` only — no pip, no pytest (matches the project's "stdlib-only" rule).
They cover the **pure, deterministic** helpers in `engine/run_digest.py` and
`site/build_site.py` (text/markdown/date transforms). Network calls and the LLM
are **not** exercised, so the suite runs offline in well under a second.

## Run

```bash
python3 -m unittest discover -s tests -t tests
```

(or `-v` for the per-test list)

## What's here

- `test_run_digest.py` — `finalize()`, the small helpers (`_norm_title`,
  `_fmt_source_dt`, `_cat_tokens`, `parse_feed`, `merge_catalysts`), and the
  `auto_schedule`/`resolve_auto` scheduling logic that the cloud workflow's `--auto`
  flag relies on.
- `test_build_site.py` — `renumber_sources`, `link_headings`, `md_inline`,
  `parse_catalysts`, `render_market`, and the slug/date/category helpers.
- `test_send_digest.py` — the **email** path: source renumbering, clickable `[n]`
  citations, the markdown→HTML fragment, and "Sources last" assembly — including a
  test that renders the exact `finalize()` golden through the email to tie the two
  code paths together. Network (Yahoo markets) is patched out.
- `test_send_telegram.py` — the **Telegram** summary card: title / talking-point /
  TL;DR extraction and the markdown→Telegram-HTML conversion.
- `golden/` — frozen expected outputs for the multi-line transforms
  (`finalize`, source renumbering, headline linking). These are **characterization
  tests**: they lock in the current behavior so a refactor can be proven to change
  nothing.
- `fixtures.py` — loads the two modules by file path (the `site/` dir shadows a
  stdlib module name) and holds the shared sample inputs.
- `_gen_golden.py` — regenerates the `golden/` files from the current code. Run it
  **only** when you have intentionally changed behavior and want to re-freeze the
  baseline: `python3 tests/_gen_golden.py`.
