# ✅ Roadmap & Feature Checklist

Where the project stands, and everything we discussed adding.

## Done ✅
- [x] On-demand digest - `/pharma-news` (Claude engine)
- [x] Evening edition - deeper 5-8 min read + Deep Dive
- [x] DeepSeek engine - cheap, runs without Claude
- [x] Email delivery - via Resend
- [x] Audio brief - spoken `.m4a` (macOS `say`), local & optional
- [x] Catalyst calendar + Week Ahead - FDA **and** EMA/CHMP
- [x] Configurable watchlist - companies / therapeutic areas / themes
- [x] Thread-tracking, archive search, earnings-day mode
- [x] Anti-hallucination accuracy pass (ground every fact in a real source)
- [x] Engine labels - every digest says Claude or DeepSeek (+ model)
- [x] Website - latest digest, catalyst timeline, catalyst-mix chart, search, dark mode, archive
- [x] Cloud automation - GitHub Actions: daily email + auto-publish website
- [x] Anonymised public repo (no name/email exposed)
- [x] Sourcing upgrade - added Labiotech.eu; quality-source rule
- [x] Editorial magazine UI + ⚙ settings drawer (theme/nav/search/cloud links)
- [x] Clickable headlines + `[n]` citations; sources renumbered by order of appearance (site **and** email)
- [x] Semi-dynamic markets table (core tickers + covered tickers; correlation-only)
- [x] Viewer-local publish time on the website; fixed Rome stamp in email
- [x] **Telegram delivery** - summary card + "read full brief" link to a public channel (free, no domain)
- [x] **Sunday "Week in Review"** - deeper evening edition over 7 days, in the cloud
- [x] **Monthly + yearly editions** - the last Saturday/Sunday of each month widen to a **Month in Review / Month Ahead** (30-day), and the last weekend of December to a **Year in Review / Year Ahead** (12-month); same crons, the edition is chosen from the date in `auto_schedule`
- [x] Thin-digest guard - aborts (so GitHub emails you) instead of sending a hollow brief
- [x] **Reliability hardening** - fail-loud on failed email/Telegram send, empty model output, or a failed git push (no more silent losses); one flaky feed no longer kills the run
- [x] **Email parity with the site** - clickable links + `[n]` citations, a Markets table, and an Upcoming-catalysts list in the email
- [x] **Source date/times** - each source shows its publish time where the feed provides one (factual only, never guessed)
- [x] **"What's new" tagging** - stories already covered in the last 7 days only reappear as *Developing:* with a concrete new fact
- [x] **Grounding self-check** - a second pass fact-checks the draft against the sources and revises out unsupported claims
- [x] **Self-maintaining catalysts** - explicitly-dated future events from the day's news are auto-filed into `catalysts.md` (clearly labelled, deduped, pruned)
- [x] **"Last updated" footer** on the site; renamed the Lilly section to **Eli Lilly Spotlight**; removed decorative emojis for a cleaner editorial look
- [x] Cost: grounding + catalyst extraction share **one** review call (~3 model calls/run)
- [x] **Gemini engine + instant switch** - automatic digest can run on **Gemini** (primary, `gemini-2.5-flash`, free tier) or **DeepSeek**, via one OpenAI-compatible `call_model()` path (with a retry on transient 5xx); switch in the Command Centre ("Choose engine") or `PHARMA_ENGINE` (local `secrets.env` + cloud repo Variable). Free Gemini key from aistudio.google.com → $0 tokens. (Gemini 2.5 **Pro** isn't free — needs billing, ~$4-5/mo.)
- [x] **Test suite + CI (code-quality hardening)** - `tests/` (stdlib `unittest`, 111 offline tests) covers the digest, website, email, and Telegram helpers; **golden tests** lock `finalize()`/source-renumbering output; a `Tests` GitHub workflow runs them on every push/PR (green in the cloud). Also: split the long `finalize()` into a readable pipeline (proven byte-identical) and moved the workflow's day-of-week scheduling out of shell into Python (`--auto`).
- [x] **Audit v2 (2026-06-14) — security/reliability/cost** - PII purged from public git history (`filter-repo`); shared `pharma_render.py` (no more site/email drift); delivery reordered after archive+publish + send retries; XML entity-guard; citation-`href` escaping; **RSS feed** + autodiscovery; archive pagination; **Heartbeat** dead-man's-switch + **auto-DST re-time** workflows; corpus trimmed (~40% cheaper); deterministic `Window:` subtitle (date range + articles-scanned); **markets %-move matched to the brief** (daily 5d / review 7d / ahead none); catalyst dedup (month-only vs ISO) + market-filler filter.

## Next up / your action ⬜
- [ ] **A/B DeepSeek v4-pro vs flash** - flip `DEEPSEEK_MODEL` secret, compare a few days *(you: send the exact model id; cost ~$1.50/mo on pro)*
- [x] **Create the Telegram channel + set `TELEGRAM_CHAT_ID`** - done; the `@channel` handle is set locally + as a GitHub Secret, so the daily run posts automatically (confirm by checking the channel after the next run)
- [ ] **Claude-grade cloud digest** - Anthropic API + live web search (`web_search` tool), stdlib-only via raw HTTP; recommend running it for the **Sunday weekly** only (premium where it counts, pennies the rest of the week). ~$5-15/mo + web-search fee.
- [x] *(optional)* Revoke/rotate the Telegram bot token via @BotFather - done; fresh token issued and updated in both places, no longer exposed in any chat

## Optional / future 💡
- [ ] Verify a Resend domain - required to email **other people** (e.g. a pharma friend); Telegram is the free alternative
- [ ] More sources as you find them (add RSS feeds to `deepseek/feeds.txt`)
- [ ] Port the whole thing to another industry (e.g. AI news) - swap feeds/watchlist/catalysts/branding; ~half a day, no core rewrite

## Note on schedulers (resolved ✅)
Settled on **one** automatic runner: **GitHub Actions (cloud, DeepSeek)** - laptop-independent, emails + publishes the site, runs Mon-Sat morning + Sunday weekly. Local launchd is not used (macOS TCC blocks it from `~/Desktop`). Use `/pharma-news` (Claude engine) on-demand when you want the premium read.
