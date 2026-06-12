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

## To decide / your action ⬜
- [ ] **Simplify schedulers** - pick ONE automatic runner (see below) - *decide now*
- [ ] **Switch Resend key Full → Send-only** - security hardening *(you, ~2 min)*
- [ ] **Delete old private `pharma-news` repo** - tidy-up *(you, via github.com)*

## Optional / future 💡
- [ ] Send to your IMD email or a custom "from" - needs verifying a domain in Resend
- [ ] Stock / markets chart on the website - needs a price-data source (avoids made-up numbers)
- [ ] WhatsApp / Telegram delivery (instead of / alongside email)
- [ ] Higher-quality *cloud* digest via the Anthropic (Claude) API - so the automatic one is Claude-grade, not DeepSeek
- [ ] Evening edition in the cloud (a second daily run)
- [ ] More sources as you find them (add RSS feeds to `deepseek/feeds.txt`)

## Note on schedulers (the thing to simplify)
You currently have **three** ways it could run - too many:
1. **Cloud (GitHub Actions, DeepSeek)** - reliable, laptop-independent, also publishes the site. ✅ recommended as the one automatic runner.
2. **Claude app task (Claude engine)** - better quality, but only runs if the Claude app is open, and emails only (no website). Currently ON → causes a *duplicate* morning email.
3. **Local macOS launchd job (DeepSeek)** - fully redundant with the cloud. Currently OFF.

**Recommended:** keep #1 automatic, turn off #2 and remove #3, and use `/pharma-news` (Claude) on-demand when you want the premium read.
