# CLAUDE.md — project memory

Persistent context for this project. Read it first.

## What this is
**Pharma Morning Brief** — an automated, balanced pharmaceutical-sector news digest. Each morning it reads the pharma world, writes a tight **2–3 minute** executive brief (analysis + an Eli Lilly focus), fact-checks it, and delivers it by **email**, **Telegram**, and a browsable **website** (also RSS + audio). Saturday brings a deeper *Week in Review*, Sunday a forward-looking *Week Ahead* — widening to Month/Year editions on the last weekend of each month and December.

## Problem & scope
- **User:** an incoming Eli Lilly intern / MBA — wants full-industry awareness plus sharpened intelligence on Lilly and its rivals, in the time it takes to drink a coffee.
- **Why:** turns ~30–60 min/day of reactive headline-scanning into contextual, decision-useful intelligence with forward-looking catalysts.
- **In scope:** broad sweep of reputable sources → "what it means" via executive lenses → catalysts → grounded/fact-checked → automatic + browsable.
- **Not in scope:** intraday alerts, trading/investment advice, deep single-company reports, non-pharma industries (the design is portable).

## How it works — one recipe, swappable engines, multi-channel delivery
- **Recipe (shared methodology):** `.claude/commands/pharma-news.md` + `pharma-news/{digest-template,watchlist,catalysts}.md`.
- **Engines** — one `call_model()` path (`PROVIDERS` dict) in `engine/run_digest.py`:
  - **Automatic:** Gemini (primary, `gemini-2.5-flash`, free tier) or DeepSeek — pick via `PHARMA_ENGINE` (gemini|deepseek) or `--engine`; unset → Gemini if `GEMINI_API_KEY` present, else DeepSeek. (Gemini **Pro is not free** — Flash is. Gemini needs a real `User-Agent`, set in `call_model`.) Reads RSS from `engine/feeds.txt`.
  - **Claude:** on-demand `/pharma-news` in Claude Code — live web search, richest analysis, runs on the Claude subscription (no API spend).
- **Delivery:** `pharma-news/send_digest.py` (email via Resend), `pharma-news/send_telegram.py` (Telegram card), `site/build_site.py` (static site → GitHub Pages).
- **Automation:** `.github/workflows/pharma-digest.yml` runs `engine/run_digest.py --auto` daily in the cloud → ground-check → archive → build + deploy site → email + Telegram. `--auto` derives window/edition/mode from the UTC date (`auto_schedule`/`resolve_auto`).

## Editions (cadence)
- **Mon–Fri morning:** the tight ~3-min daily — Talking point, TL;DR, ≤3 Top Stories, a brief Eli Lilly Spotlight (hard ~550-word cap). Omits Deep Dive / On the radar / Wider world.
- **Saturday:** Week in Review (last Sat of a month → Month in Review; last Sat of Dec → Year in Review) — analytical synthesis that explicitly includes macro/wider-world forces.
- **Sunday:** Week Ahead (→ Month/Year Ahead) — forward-looking catalysts.
- Review/ahead editions run as the deeper **evening** edition. Review editions synthesize from the project's **own fact-checked archive** (`gather_from_archive`), falling back to live RSS when the archive is young.

## Run it locally
- **Easiest:** double-click **`Pharma Command Centre.command`** (menu: run, choose engine, schedule, status).
- **Generate:** `python3 engine/run_digest.py [--hours 24] [--edition morning|evening] [--mode daily|review|ahead|month_review|...] [--email] [--telegram] [--engine gemini|deepseek]`
- **Build the site:** `python3 site/build_site.py` → open `site/public/index.html` (or `cd site/public && python3 -m http.server 8765`).
- **Richest (Claude):** type `/pharma-news` in Claude Code.
- **Tests:** `python3 -m unittest discover -s tests -t tests` (stdlib only, offline, ~190 tests).

## Conventions / decisions
- **Anti-hallucination first:** every fact traces to a source seen that run; rumours labelled; weak single sources flagged; no invented links. A post-generation pass (`review_digest` → `revise_for_grounding`) strips unsupported claims. (`Step 4.5` in the command file; toggle `DIGEST_REVIEW=0`.)
- **Stdlib-only Python** (no pip) for portability.
- **Shared logic in `pharma_render.py`** — used by BOTH the site and the email so they can't drift (citation renumbering, `[n]`→URL, catalyst parsing/buckets, markets, inline-markdown cleanups). Edit once.
- **Catalysts look forward from each brief's own date** (`upcoming_catalysts`) at every boundary — site, email, and the LLM prompt (`forward_calendar_text`). `catalysts.md` is a forward-looking working file; `merge_catalysts` self-maintains its auto-detected section (toggle `AUTO_CATALYSTS=0`).
- **"What's new" tagging** (`recent_seen`): articles are NEW vs. previously-covered by comparing the last 7 days of archived briefs; the committed archive *is* the state.
- **Secrets never in the repo** — `~/.config/pharma-news/secrets.env` + encrypted GitHub Secrets (`GEMINI_API_KEY`, `RESEND_API_KEY`, `EMAIL_TO`, `EMAIL_FROM`, `DEEPSEEK_*`, `TELEGRAM_*`, `SITE_URL`; `PHARMA_ENGINE`/`GEMINI_MODEL` are repo **Variables**). The public repo is anonymised.
- **Engine is labelled** in every digest subtitle.

## Key files
- `engine/run_digest.py` — the multi-engine generator (gather → prompt → ground-check → finalize → archive → build).
- `pharma_render.py` — shared render/data logic (site + email).
- `site/build_site.py` — the static site: archive, catalyst timeline + category mix, markets, **Threads** (topic storyline) + coverage/weekly-trend, subscribe-able catalyst **`.ics`**, **Listen** read-aloud (play/pause/resume + restart), search, dark mode, installable **PWA**/offline.
- `pharma-news/` — `send_digest.py`, `send_telegram.py`, `make_audio.py`, `check_freshness.py`, `set_schedule.py`, `{watchlist,catalysts,digest-template}.md`, `config.json`, `state.json`.
- `digests/` — saved digests (the archive the site renders) + `published.json`.
- `tests/` — stdlib `unittest` + golden fixtures (regen: `python3 tests/_gen_golden.py`); guarded by `.github/workflows/tests.yml`.
- `.github/workflows/` — `pharma-digest.yml` (daily run + deploy), `tests.yml`, `heartbeat.yml` (dead-man's-switch, emails if no digest in >2 days), `retime.yml` (weekly DST re-pin).
- `README.md` (full manual) · `GUIDE.md` (plain-English) · `ROADMAP.md` (feature checklist).

## Current state
- **Live:** repo `github.com/BestCoderEverForSure/pharma-brief` (public, anonymised) · site `https://bestcodereverforsure.github.io/pharma-brief/`.
- **Schedule:** three crons in `pharma-digest.yml` (`1-5`, `6`, `0` at 05:00 UTC = 07:00 Rome). Generate (`--auto`) → archive → deploy → deliver, in that order, so a delivery outage can't cost the archive/publish; senders retry transient failures.
- **Engine:** Gemini Flash (free) for scheduled runs; DeepSeek on demand; Claude via `/pharma-news`.
- **Feature-complete.** It's run almost entirely on **autorun** (weekday mornings + Saturday review + Sunday ahead). ~191 stdlib tests green.

## Gotchas
- Cloud regenerates the digest daily → **overwrites a manual `{major}` demo tag**; the model flags "major" rarely by design. Re-tag a heading in today's `digests/*.md` to demo.
- Cloud auto-commits digests, so local diverges → the workflow does `git pull --rebase` then push; locally, pull before pushing (never force).
- macOS launchd can't read `~/Desktop` (TCC) → scheduling lives in the cloud, not local.
- The site registers a **service worker** (PWA) — after a *local* rebuild, hard-refresh to bypass the cache.
- **Security:** PII (the recipient email, the author's identity) was purged from git history with `git filter-repo` and force-pushed. Treat the recipient address as *already public* (caches/forks may persist); account 2FA is the real mitigation. Resend is in **test mode** → delivers only to `EMAIL_TO`; emailing anyone else needs a verified domain (not owned) — Telegram is the sharing path.

## Open / optional (see ROADMAP.md)
- **Claude-grade *automatic* digest** (paid Anthropic API) — today only on-demand `/pharma-news` is Claude; the cloud daily is Gemini. Holding off (evaluating Gemini/DeepSeek first).
- **Resend domain verification** — only to email recipients beyond the test inbox (Telegram covers sharing).
- **Time-based trend depth** — the per-topic weekly sparkline gets richer as the archive grows; "rising/cooling" deltas are worth revisiting once there are months of data.
