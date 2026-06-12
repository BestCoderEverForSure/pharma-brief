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

## How it works - "1 recipe, 2 engines, 1 delivery"
- **Recipe (shared methodology):** `.claude/commands/pharma-news.md` (+ `pharma-news/digest-template.md`, `watchlist.md`, `catalysts.md`).
- **Two engines:**
  - **Claude** - on-demand `/pharma-news` in Claude Code; live web search, richest analysis.
  - **DeepSeek** - `deepseek/run_digest.py`; reads RSS feeds (`deepseek/feeds.txt`), cheap/per-token, runs without Claude.
- **Delivery:** `pharma-news/send_digest.py` (email via Resend) + `site/build_site.py` (static website with catalyst timeline, markets chart, search, archive).
- **Automation:** `.github/workflows/pharma-digest.yml` runs the DeepSeek engine daily in the cloud (GitHub Actions), emails it, and publishes the website (GitHub Pages).

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

## Current state & open items (session handoff)
**Live:** repo `github.com/BestCoderEverForSure/pharma-brief` (public, anonymised) · site `https://bestcodereverforsure.github.io/pharma-brief/` · GitHub Actions runs daily **07:00 Rome** (active) and emails + publishes. Secrets in `~/.config/pharma-news/secrets.env` (RESEND_API_KEY send-only, DEEPSEEK_API_KEY, EMAIL_TO=`k.valtetsiotis+resend@gmail.com`; Resend **test mode** = delivers only to that inbox).

**Built (all in `site/build_site.py` unless noted; live on local site, online site, and email where applicable):**
- Editorial magazine UI: serif masthead, custom palette (Ash Grey/Smoky Rose/Granite/Ink Black/Dusty Mauve), Avenir Next + Iowan; no sidebar/cards; centred ~760px measure.
- **⚙ Settings drawer** (gear in top bar): theme Auto/Light/Dark toggle (persists, no-flash via head script + `html.dark`), nav, search, GitHub cloud links (`SETTINGS_JS`).
- Clickable **headlines + inline `[n]` citations** (link to sources via `_SRCMAP`/`render_digest`); sources renumbered 1..N (`renumber_sources`).
- **Major-story highlight**: append ` {major}` to a heading → Smoky Rose + "MAJOR STORY" label; supported in site AND email (`send_digest.py`).
- **Semi-dynamic markets** (`render_market`): core 10 tickers + `EXTRA_TICKERS` added only when covered today; "may relate to" notes link to the specific story anchor (`#sN`/section) — correlation only, no forecasts (no-advice scope).
- Google News breadth feed in `deepseek/feeds.txt`; aggregator links get a `↗` flag; visited links grey out.

**Gotchas:**
- Cloud regenerates the digest daily → **overwrites any manual `{major}` demo tag**; DeepSeek flags major rarely (by design). To demo, re-tag a heading in today's `digests/*.md`.
- Git: cloud auto-commits digests so local diverges → sync with **`git pull origin main --no-rebase -X ours --no-edit` then push** (never force).
- macOS launchd can't read `~/Desktop` (TCC) → scheduling lives in the cloud, not local.

**Open / optional (see ROADMAP.md):** WhatsApp/Telegram delivery; Claude-API cloud version (make the *automatic* digest Claude-grade); evening edition in the cloud; verify a Resend domain to email the IMD address.
