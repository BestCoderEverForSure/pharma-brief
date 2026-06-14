# CLAUDE.md - Project memory

This file is the persistent context for this project (read it first).

## What this is
**Pharma Morning Brief** - an automated, balanced pharmaceutical-sector news aggregator. Every morning it reads the pharma world, writes a 2-3 minute executive digest (with analysis and a focus on Eli Lilly), and delivers it by **email** and a browsable **website**.

## Problem statement (the brief it was built against)
1. **Problem:** Pharma moves fast; a busy person falls behind. Existing options are either shallow headline feeds or hours of reading across many outlets. There's no single, *balanced*, analysed, 2-3 minute morning brief.
2. **User:** An incoming Eli Lilly intern / MBA - needs full-industry awareness plus sharpened intelligence on Lilly and its competitors, readable in the time it takes to drink a coffee.
3. **Why it matters:** Saves ~30-60 min/day of scanning; turns reactive headline-reading into contextual, decision-useful intelligence with forward-looking catalysts.
4. **Good solution:** A digest that (a) sweeps many reputable sources, (b) explains *what it means* via executive lenses, (c) flags upcoming catalysts, (d) is grounded/fact-checked, (e) arrives automatically each morning and is also browsable.
5. **Not in scope:** Real-time/intraday alerts; trading signals/investment advice; deep single-company research reports; non-pharma industries (though the design is portable).

## How it works - "1 recipe, swappable engines, 1 delivery"
- **Recipe (shared methodology):** `.claude/commands/pharma-news.md` (+ `pharma-news/digest-template.md`, `watchlist.md`, `catalysts.md`).
- **Engines:**
  - **Claude** - on-demand `/pharma-news` in Claude Code; live web search, richest analysis; runs on the user's Claude Code subscription (no API spend).
  - **Automatic engine** (`deepseek/run_digest.py`, cloud + Command Centre) - reads RSS feeds (`deepseek/feeds.txt`) and is engine-swappable via `PHARMA_ENGINE` (gemini|deepseek): **Gemini (primary, `gemini-2.5-flash`, free tier)** or **DeepSeek**. (Gemini 2.5 **Pro is NOT on the free tier** — free limit 0; needs billing ~$4-5/mo. Flash is free and works; tested end-to-end. Google drops the default `Python-urllib` UA, so `call_model` sets a real User-Agent.) Both use the OpenAI-compatible chat API through one `call_model()` path (`PROVIDERS` dict). Switch instantly via **Command Centre → "Choose engine"** (sets local `secrets.env` + the cloud repo Variable `PHARMA_ENGINE`), or `--engine`. Unset → Gemini when `GEMINI_API_KEY` present, else DeepSeek.
- **Delivery:** `pharma-news/send_digest.py` (email via Resend) + `site/build_site.py` (static website with catalyst timeline, markets chart, search, archive).
- **Automation:** `.github/workflows/pharma-digest.yml` runs the automatic engine daily in the cloud (GitHub Actions), emails it, posts a Telegram card, and publishes the website (GitHub Pages).

## Run it locally
- **Easiest:** double-click **`Pharma Command Centre.command`** (menu controls everything).
- **Generate (DeepSeek):** `python3 deepseek/run_digest.py [--hours 168] [--edition evening] [--email]`
- **Build the website:** `python3 site/build_site.py` → open `site/public/index.html`
- **Serve on localhost:** `cd site/public && python3 -m http.server 8765` → http://localhost:8765
- **Richest digest:** type `/pharma-news` in Claude Code (Claude engine).

## Conventions / decisions
- **Anti-hallucination first:** every fact must trace to a real source seen that run; rumours labelled; weak single sources = unconfirmed; no invented links. (`Step 4.5` in the command file.)
- **Stdlib-only Python** (no pip installs) for portability.
- **Secrets never in the repo** - they live in `~/.config/pharma-news/secrets.env` (and as encrypted GitHub Secrets). The public repo is anonymised.
- **Engine is always labelled** in each digest's subtitle (Claude vs DeepSeek + model).

## Key files
- `GUIDE.md` - plain-English (ELI5) user guide.
- `README.md` - full technical manual.
- `ROADMAP.md` - done/checklist of features.
- `digests/` - saved digests (the archive the website renders).
- `pharma_render.py` - shared render/data logic (citations, catalysts, markets) used by BOTH the site and the email; edit once, both stay in sync.
- `tests/` - stdlib `unittest` suite (run `python3 -m unittest discover -s tests -t tests`); guarded in CI by `.github/workflows/tests.yml`.

## Current state & open items (session handoff)
**Live:** repo `github.com/BestCoderEverForSure/pharma-brief` (public, anonymised) · site `https://bestcodereverforsure.github.io/pharma-brief/` · GitHub Actions runs **Mon–Fri 07:00 Rome** (24h daily brief, `--mode daily`) + **Saturday** (168h "Week in Review", `--mode review`) + **Sunday** (168h "Week Ahead" forward-look, `--mode ahead`) — all email + Telegram + publish. Schedule is three crons in `pharma-digest.yml` (`1-5`, `6`, `0`); the run step is now just `run_digest.py --email --telegram --auto` (no shell logic) — `--auto` resolves hours/edition/mode in Python (`auto_schedule`/`resolve_auto` in `run_digest.py`): from `IN_HOURS`/`IN_EDITION`/`IN_MODE` env vars for a manual run, else from the UTC weekday (Sat=review, Sun=ahead, else daily). Same picks the old `date -u +%u` bash made. **Global balance:** the breadth feed now has US + Europe (en-GB) + India (en-IN) Google News editions, and the prompt asks for proportional global coverage (de-bias at the source, not by quota). Secrets in `~/.config/pharma-news/secrets.env` (RESEND_API_KEY send-only, DEEPSEEK_API_KEY, EMAIL_TO = the private recipient inbox — kept ONLY in secrets/GitHub Secrets, never written in the repo; Resend **test mode** = delivers only to that inbox — sending to anyone else needs a verified domain, which the user does not own).

**Built (all in `site/build_site.py` unless noted; live on local site, online site, and email where applicable):**
- Editorial magazine UI: serif masthead, custom palette (Ash Grey/Smoky Rose/Granite/Ink Black/Dusty Mauve), Avenir Next + Iowan; no sidebar/cards; centred ~760px measure.
- **⚙ Settings drawer** (gear in top bar): theme Auto/Light/Dark toggle (persists, no-flash via head script + `html.dark`), nav, search, GitHub cloud links (`SETTINGS_JS`).
- Clickable **headlines + inline `[n]` citations** — link to sources via `_SRCMAP`/`render_digest`. Sources are renumbered **1,2,3… in order of first appearance in the brief** and the Sources list is reordered to match (`renumber_sources`); uncited sources kept at the end. **The email does this too now** — `send_digest.py` has its own `renumber_sources` + `parse_srcmap` + `prepare_digest`, and `md_inline` makes `[n]` clickable. Both engines benefit (both render through these two files).
- **Viewer-local publish time**: website shows a `Published <time data-utc=…>` line localized to each visitor's timezone via JS (`published_line`/`with_published` in `build_site.py`; localize snippet appended to `SETTINGS_JS`). Email **can't** localize live (no JS in mail clients) → it stamps a fixed **Europe/Rome** time (`published_stamp` in `send_digest.py`, via stdlib `zoneinfo`). Publish instant anchored at the cron hour (05:00 UTC — both the Mon–Sat morning and Sunday weekly crons fire at 05:00 UTC).
- **Major-story highlight**: append ` {major}` to a heading → Smoky Rose + "MAJOR STORY" label; supported in site AND email (`send_digest.py`).
- **Semi-dynamic markets** (`render_market`): core 10 tickers + `EXTRA_TICKERS` added only when covered today; "may relate to" notes link to the specific story anchor (`#sN`/section) — correlation only, no forecasts (no-advice scope).
- Google News breadth feed in `deepseek/feeds.txt`; aggregator links get a `↗` flag; visited links grey out.
- **Email parity** (`send_digest.py`): the email now also carries a **Markets** table (`render_market_email`) and an **Upcoming-catalysts** list (`render_catalysts_email`), inline-styled for mail clients; both fail to an empty section if data can't be fetched.
- **Source date/times**: `finalize()` appends each source's feed publish time (`_fmt_source_dt`, "· Jun 12, 2026 · 14:30 UTC") — factual only, shown only when the feed provides it. Flows to site + email (shared Sources markdown).
- **"What's new" tagging** (`recent_seen` in `run_digest.py`): articles are tagged NEW vs. previously-covered by comparing against source URLs/titles in the last 7 days of archived digests; the model leads with new and marks updates *Developing:* (only on a concrete new fact). The committed archive is the state — no separate store.
- **Grounding self-check + self-maintaining catalysts** (`review_digest` in `run_digest.py`): ONE post-generation review call both fact-checks the draft against the corpus (then `revise_for_grounding` removes unsupported claims) AND extracts explicitly-dated future catalysts, which `merge_catalysts` files into a clearly-labelled "Auto-detected" section of `catalysts.md` (deduped on drug/company tokens per date, past pruned). All defensive (failure → ship anyway). Toggles: `DIGEST_REVIEW=0`, `AUTO_CATALYSTS=0`.
- **"Last updated" footer** on the site (build time, viewer-localized). Reliability: failed email/Telegram send, empty model output, and failed git push all exit non-zero so GitHub emails the failure; one bad feed no longer aborts the run.
- **Accurate "Published" time**: `run_digest` records the real generation instant in `digests/published.json` (committed with the digest); the site localizes that to each viewer (no more fixed-anchor 05:00 UTC showing as the wrong local clock). Falls back to date-only if unknown.
- **Schedule control**: `pharma-news/set_schedule.py` (stdlib `zoneinfo`) sets the daily send time + timezone — converts local→UTC and rewrites BOTH workflow crons (keeps day-of-week). Driven from the Command Centre ("Send & schedule → Set the daily send time"), which commits/pushes so the cloud schedule changes. Command Centre was reorganised (status header showing engine + send time; engine/sources tucked under Settings).
- **Clean editorial look**: decorative emojis removed from the digest (title/headings/labels) at the source (template + command + DeepSeek prompt). The Lilly section is **"Eli Lilly Spotlight"** (was "Lilly Watch").
- **Test suite + CI (2026-06-14)**: `tests/` — stdlib `unittest` only (no pip/pytest), 62 tests, offline, <0.1s. Covers the pure helpers in `run_digest.py`, `build_site.py`, AND both delivery renderers (`send_digest.py` email + `send_telegram.py`). **Golden characterization tests** (`tests/golden/`) lock the exact output of `finalize()` + source-renumbering; regenerate them only on an intentional behaviour change with `python3 tests/_gen_golden.py`. Run all: `python3 -m unittest discover -s tests -t tests`. A **`Tests` GitHub workflow** (`.github/workflows/tests.yml`) runs them on every push/PR that touches code paths (verified green in the cloud), guarding the daily run.
- **`finalize()` refactor (2026-06-14, behaviour-preserving)**: the ~80-line `finalize()` in `run_digest.py` was split into ten small named helpers (`_strip_leaked_html`, `_label_engine`, `_append_sources`, `_apply_read_time`, …) called by a fixed-order pipeline. Proven byte-identical to the prior code by the golden tests — nothing readers see changed. (Was flagged as the one over-long function.)

**Gotchas:**
- Cloud regenerates the digest daily → **overwrites any manual `{major}` demo tag**; DeepSeek flags major rarely (by design). To demo, re-tag a heading in today's `digests/*.md`.
- Git: cloud auto-commits digests so local diverges → sync with **`git pull origin main --no-rebase -X ours --no-edit` then push** (never force).
- macOS launchd can't read `~/Desktop` (TCC) → scheduling lives in the cloud, not local.

**Open / optional (see ROADMAP.md):**
- **Telegram delivery** — **LIVE** (`pharma-news/send_telegram.py`, wired via `run_digest.py --telegram` + the workflow). Posts a summary card (title + talking point + TL;DR + "read full brief" link) to a channel; free, no domain (the chosen way to share with others, e.g. the user's pharma friend). Bot = **@pharma_morning_brief_bot**; both `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (a public `@channel`) are now set locally + as GitHub Secrets, so each run posts automatically. (To confirm end-to-end, check the channel after the next scheduled run, or trigger a manual run.) If `TELEGRAM_CHAT_ID` is ever cleared, the script skips cleanly (daily run unaffected). WhatsApp was ruled out (Business API isn't free/simple).
- **Claude-API cloud version** — make the *automatic* digest Claude-grade (currently only on-demand `/pharma-news` is Claude; the cloud daily is DeepSeek). NOTE: on-demand `/pharma-news` already gives Claude quality on the user's Claude Code subscription (no API $); this item is only about *automating* that, which needs the paid Anthropic API. User is holding off — evaluating DeepSeek-as-is first; a cheaper stepping stone is a stronger DeepSeek model on the Sunday cron only.
- Resend domain verification (only needed to email recipients other than the test inbox; user has no domain → Telegram is the chosen path for sharing).

**Done (2026-06-13 review + hardening session, PRs #2–#5):** full code-review pass (fail-loud guards, citation integrity, secret-hygiene audit); email parity (clickable links, Markets table, catalyst timeline, source date/times); "what's new" freshness tagging; grounding self-check + targeted revision; self-maintaining catalysts; site "last updated" footer; renamed Lilly Watch → **Eli Lilly Spotlight**; removed decorative emojis; merged the grounding + catalyst calls into one (cost). Verdict with user: project is feature-complete; only optional upgrade left is a Claude-grade *automatic* digest (paid API) — holding off to see DeepSeek-as-is first.

**Done (2026-06-14 — merciless audit + v2 hardening; all green in CI):** a full architectural/security audit and remediation. New since:
- **Tests + CI:** `tests/` — stdlib `unittest` only (111 tests, offline, <0.1s) over `run_digest.py`, `build_site.py`, `pharma_render.py`, and BOTH delivery renderers; golden chars lock `finalize()`/source-renumbering (regen: `python3 tests/_gen_golden.py`). `.github/workflows/tests.yml` runs them on every push/PR (path-scoped). Run: `python3 -m unittest discover -s tests -t tests`.
- **`pharma_render.py` (NEW, repo root):** single source of truth shared by the site + email renderers — `renumber_sources`, `parse_srcmap`, `parse_catalysts`, `catalyst_date`, `fetch_market`, `select_tickers`, `brief_market_days`. Killed ~229 lines of duplication so the two can't drift.
- **`finalize()` refactor:** split into ten named helpers + a pipeline (proven byte-identical by goldens).
- **Workflow de-bashed + delivery decoupled:** scheduling moved from shell into Python (`auto_schedule`/`resolve_auto`, `--auto`; Sat=review, Sun=ahead, else daily). Reordered to **generate → archive → deploy → deliver**, so a delivery outage can't cost the archive/publish; `send_digest`/`send_telegram` now retry transient failures (mirrors `call_model`).
- **Security — PII purged:** the real recipient gmail (`+resend` content) AND author identity (`+github` on every PR-merge commit) plus the "IMD" school references were rewritten out of ALL history (`git filter-repo`, force-pushed) and local copies deleted. **Treat the address as already public** (cache/forks may persist); 2FA on the account is the real mitigation, which is on.
- **Reliability/monitoring:** `pharma-news/check_freshness.py` + `.github/workflows/heartbeat.yml` (daily 08:00 UTC dead-man's-switch — emails you if no digest archived in >2 days, catching SILENT schedule stalls). `.github/workflows/retime.yml` (weekly auto-DST: re-pins the cron from `config.json` via `set_schedule.py` no-arg mode; commits only on a real DST shift). `set_schedule.py` warns on a UTC day-boundary crossing.
- **Hardening:** XML entity-guard + `MAX_FEED_BYTES` cap in `parse_feed`/`fetch`; `html.escape` on citation `href` URLs; `call_model` survives a 200-with-garbage body.
- **Features:** RSS/Atom `feed.xml` + autodiscovery (`rss_feed`/`pages_url` in `build_site`); archive pagination (index caps at 30 → `archive.html`).
- **Cost + quality:** dropped source URLs from the model corpus (~40% smaller; the ~400-char Google News links were pure cost — finalize re-attaches real URLs). Engine is **Gemini 2.5 Flash free** for ALL scheduled runs (cloud Variable `PHARMA_ENGINE=gemini` + local; Command Centre flips to DeepSeek on demand) — the 168h weekly review was run live on the free tier (298 articles read → 53 cited; ~$0). Deterministic `Window:` subtitle now shows the real date range + "N articles scanned" (`window_subtitle`). Markets %-move matches the brief window: **daily 5d, Week-in-Review 7d, Week-Ahead none** (`brief_market_days`). Catalysts: dedup curated month-only vs auto-detected ISO dates (shared `catalyst_date`), and skip generic "stocks to watch"/market-filler headlines (`_CAT_NOISE`).
- **Re-rating with user:** ~8–8.5/10 (was ~6/10 by pro standards). Remaining gap is product scope (public-data pivot for distribution), not code.
