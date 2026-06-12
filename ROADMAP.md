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
- [x] Thin-digest guard - aborts (so GitHub emails you) instead of sending a hollow brief

## Next up / your action ⬜
- [ ] **A/B DeepSeek v4-pro vs flash** - flip `DEEPSEEK_MODEL` secret, compare a few days *(you: send the exact model id; cost ~$1.50/mo on pro)*
- [ ] **Create the Telegram channel + set `TELEGRAM_CHAT_ID`** - last step to go live *(you: ~2 min — DONE if `@pharma_morning_brief` is wired)*
- [ ] **Claude-grade cloud digest** - Anthropic API + live web search (`web_search` tool), stdlib-only via raw HTTP; recommend running it for the **Sunday weekly** only (premium where it counts, pennies the rest of the week). ~$5-15/mo + web-search fee.
- [ ] *(optional)* Revoke/rotate the Telegram bot token via @BotFather (it passed through a chat)

## Optional / future 💡
- [ ] Verify a Resend domain - required to email **other people** (e.g. a pharma friend); Telegram is the free alternative
- [ ] More sources as you find them (add RSS feeds to `deepseek/feeds.txt`)
- [ ] Port the whole thing to another industry (e.g. AI news) - swap feeds/watchlist/catalysts/branding; ~half a day, no core rewrite

## Note on schedulers (resolved ✅)
Settled on **one** automatic runner: **GitHub Actions (cloud, DeepSeek)** - laptop-independent, emails + publishes the site, runs Mon-Sat morning + Sunday weekly. Local launchd is not used (macOS TCC blocks it from `~/Desktop`). Use `/pharma-news` (Claude engine) on-demand when you want the premium read.
