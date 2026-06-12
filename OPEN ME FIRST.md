# 👋 Open me first

**Pharma Morning Brief** — an automated, balanced pharma news aggregator that turns the day's pharmaceutical news into a fact-checked, 2–3 minute executive digest (with a focus on Eli Lilly), delivered by email and as a website.

## See it in 10 seconds (no setup, works offline)
➡️ **Open [`site/public/index.html`](site/public/index.html) in your browser.**
That's the live product: the latest digest, a catalyst timeline, a pharma markets chart, full-text search, and an archive of past digests.

## See what the morning email looks like
➡️ **Open [`samples/email-preview.html`](samples/email-preview.html)** — the exact styled digest that gets emailed each morning.
*(The email itself is sent via a private API key that is intentionally NOT in this folder, so it can't be sent from the zip — but this is precisely what it looks like.)*

## How it works (plain English)
➡️ Read [`GUIDE.md`](GUIDE.md). One idea: **1 shared recipe → 2 interchangeable AI engines (Claude + DeepSeek) → delivered by email + website.**

## Run it yourself (optional)
- **Richest version (Claude):** open this folder in Claude Code and type `/pharma-news`.
- **Cheap/automatic version (DeepSeek):** `python3 deepseek/run_digest.py` (needs a free DeepSeek API key in `~/.config/pharma-news/secrets.env`).
- **One-click control:** double-click **`Pharma Command Centre.command`** (generate, serve on localhost, edit sources, etc.).

## More docs
- [`README.md`](README.md) — full technical manual
- [`CLAUDE.md`](CLAUDE.md) — project memory / overview
- [`ROADMAP.md`](ROADMAP.md) — what's built and what's next
