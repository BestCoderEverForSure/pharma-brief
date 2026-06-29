# Pharma Morning News Aggregator - Instruction Manual

> **Want to just see it?** Open **`site/public/index.html`** in your browser - today's digest, catalyst timeline, markets, and the searchable archive. For plain-English how-it-works, see **`GUIDE.md`**.

A balanced, high-signal briefing on the global pharmaceutical world, built to be read (or heard) in **2-3 minutes** with your morning coffee - with a deeper evening edition when you have more time.

It collects the day's pharma news (big pharma, biotech, startups, M&A, rumours, regulatory, trends - worldwide), puts each story **in context**, analyses it through eight executive **lenses**, sharpens focus on **Eli Lilly** and its rivals, flags **upcoming catalysts** and **wider-world news with pharma implications**, and runs a strict **accuracy pass** so you can repeat what you read without getting burned.

---

## 1. Quick start

Type in Claude Code:

| Command | What you get |
|---|---|
| `/pharma-news` | The **last 24 hours** - your daily 2-3 min morning read. |
| `/pharma-news evening` | A deeper **5-8 min** read with more stories + a Deep Dive. |
| `/pharma-news catchup` | Everything **since you last ran it** (after a few days away). |
| `/pharma-news since 2026-06-01` | From a specific date until now. |
| `/pharma-news evening catchup` | Combine modes (deep read, since last run). |
| *(just ask in chat)* | Look-back questions: *"what happened with orforglipron last month?"* - searches your saved archive. |

> **First-time note:** new slash commands only appear in the menu after you **restart Claude Code**. The automatic morning run does **not** need this (see Section 6).

---

## 2. What's in each digest

1. **Talking point** - one sharp, non-obvious line to sound on top of the industry in a meeting.
2. **TL;DR** - the 3-5 things that matter.
3. **Top Stories** - 2-4 items (4-6 in the evening edition), each with *What happened*, *What it means*, and 2-4 analysis lenses. A story already covered earlier in the week only reappears (prefixed *Developing:*) if there's a concrete new fact.
4. **Deep Dive** *(evening only)* - ~150-250 word synthesis of the day's biggest theme.
5. **Eli Lilly Spotlight** - Lilly's own news + competitor moves that affect its position, with "so what for Lilly."
6. **On the radar** - quick one-line hits (rumours labelled).
7. **Wider world → pharma** - non-pharma news with sector implications.
8. **Week Ahead** - upcoming catalysts (FDA *and* EMA/CHMP, earnings, readouts, conferences).
9. **Sources** - every link (with the article's publish date/time where the feed provides it), so you can verify or read deeper.

### The eight analysis lenses
Applied 2-4 per story (never all - a forced lens is noise): **Financial & capital markets · Strategic & competitive · Commercial & market access · Scientific & clinical · Regulatory & legal · Geopolitical & macro · Leadership & organizational · Technology & innovation.**

---

## 3. Accuracy (anti-hallucination)

Before saving any digest, the engine runs a mandatory accuracy pass:
- Every number, date, name, and deal value must trace to a **real source seen that run** - no filling gaps from memory.
- Market-moving facts need **two sources or a primary source** (company PR / regulator).
- **Rumours are labelled**; weak-sourced specifics are marked or dropped.
- **No invented links.** If the day is thin, it says so rather than padding.

The DeepSeek version (Section 8) is grounded *only* on the articles it fetches - the lowest-hallucination setup. It also runs an automatic **grounding self-check**: after writing the digest, a second pass re-reads it against the fetched sources and flags any claim they don't support, then revises those out before anything is sent. (Disable with `DIGEST_REVIEW=0`.)

---

## 4. Tuning it (the files you'll actually edit)

| File | What it controls |
|---|---|
| [`pharma-news/watchlist.md`](pharma-news/watchlist.md) | Companies, therapeutic areas, themes to always check. |
| [`pharma-news/catalysts.md`](pharma-news/catalysts.md) | Known upcoming catalysts (powers Week Ahead). |
| [`pharma-news/config.json`](pharma-news/config.json) | Delivery time, timezone, audio on/off + voice. |
| [`pharma-news/digest-template.md`](pharma-news/digest-template.md) | The exact structure every digest follows. |
| [`.claude/commands/pharma-news.md`](.claude/commands/pharma-news.md) | The engine - full methodology. Edit to change behaviour. |
| [`deepseek/feeds.txt`](deepseek/feeds.txt) | News sources for the DeepSeek version. |

Want it longer/shorter, more financial, focused on different companies? Edit `watchlist.md` or just ask me to adjust the command file.

---

## 5. Email delivery (Resend)

The morning run can email you the digest. It uses **Resend** with a **send-only** API key, stored privately at `~/.config/pharma-news/secrets.env` (chmod 600, outside this repo). The email mirrors the website: clickable headlines and `[n]` citations, a **Markets** table, and an **Upcoming catalysts** list. To share with other people without verifying an email domain, the run also posts a summary card to **Telegram** (see Section 8c).

**Setup (done if you see `Sent ✓`):**
1. Sign up free at [resend.com](https://resend.com) using the address you want the digest sent to.
2. **API Keys → Create** with **Sending access** (not Full - see security note below). Copy the `re_...` key.
3. Paste it into `secrets.env` over `PASTE_YOUR_RESEND_KEY_HERE`. Save.
4. Test: `python3 pharma-news/send_digest.py` → expect `Sent ✓`.

- **Test mode** only sends to your own signup address. To send to a different address or a custom "from," verify a domain in Resend and update `EMAIL_FROM`.
- The send script lives at [`pharma-news/send_digest.py`](pharma-news/send_digest.py) (standard library only).

---

## 6. How the morning schedule works ⚠️ (read this)

The daily run is **fully in the cloud** (GitHub Actions) - laptop-independent, with nothing to keep open:

- **Mon-Fri, 07:00 Rome:** the tight daily brief (last 24h).
- **Saturday, 07:00 Rome:** **Week in Review** — a deep 7-day retrospective (the week's big picture and threads).
- **Sunday, 07:00 Rome:** **Week Ahead** — a forward-looking preview of the coming week's catalysts and what to watch.
- **Last weekend of each month:** the Saturday/Sunday editions widen to a **Month in Review** (30-day retrospective) and **Month Ahead** (coming month).
- **Last weekend of December:** they widen once more to a **Year in Review** and **Year Ahead**. (Same crons — `run_digest.py --auto` picks the edition from the date.)
- Each run generates the digest (DeepSeek), **emails it**, **posts a Telegram card**, archives it to the repo, and **publishes the website** - all without your Mac being awake.
- Start/stop it or trigger an on-demand run from the repo's **Actions** tab, or the Command Centre → **"Send & schedule."**
- **Change the send time/timezone** in the Command Centre → "Send & schedule" → "Set the daily send time & timezone." It converts your local time to a UTC cron (GitHub runs in UTC) and pushes the change. (Re-set it after a daylight-saving shift to stay exact.) Under the hood: [`pharma-news/set_schedule.py`](pharma-news/set_schedule.py) edits `config.json` + the workflow cron.
- The website footer shows a **"Last updated"** time, so a stalled run is visible at a glance. Critical failures (feeds down, thin digest, a failed send/publish) exit non-zero, so GitHub emails you the failure rather than failing silently.

### Which engine wrote it?
Every digest says so in its subtitle - **`Engine: Claude`** or **`Engine: DeepSeek (model)`**. Claude digests use inline linked sources; DeepSeek digests use numbered `[n]` citations resolved in a Sources list.

For a richer read any time, run `/pharma-news` (Claude) by hand - it uses your Claude Code subscription, so it costs nothing extra. See `GUIDE.md`.

---

## 7. Audio brief (optional)

A spoken version you can listen to on the commute - free, offline, via the macOS `say` engine.

- Produced on demand: run `python3 pharma-news/make_audio.py`, or click **Listen to the audio brief** in the Command Centre.
- Voice: set `"audio_voice"` in [`config.json`](pharma-news/config.json) (list voices with `say -v '?'`).
- Output: `digests/audio/YYYY-MM-DD.m4a`.

---

## 8. The automatic engine (Gemini or DeepSeek)

The automatic digest (cloud + local script) runs on one of two interchangeable, API-based engines - same methodology, same RSS news source, just a different brain. **Gemini is the primary engine; DeepSeek is the alternative.** Full details in [`deepseek/README.md`](deepseek/README.md).

```bash
python3 deepseek/run_digest.py                       # morning, last 24h
python3 deepseek/run_digest.py --edition evening --hours 48
python3 deepseek/run_digest.py --email               # also email it
python3 deepseek/run_digest.py --engine deepseek     # force a specific engine for one run
```

**Switching engines (easy + quick):**
- **Command Centre → "Choose engine (Gemini / DeepSeek)"** sets it for both this Mac *and* the daily cloud run in one step.
- Under the hood it's the `PHARMA_ENGINE` setting (`gemini` | `deepseek`): in `secrets.env` for local runs, and as the repo **Variable** `PHARMA_ENGINE` for the cloud. Unset → Gemini when `GEMINI_API_KEY` is present, else DeepSeek.

**Keys & models (in `secrets.env`, and as GitHub Secrets for the cloud):**
- **Gemini:** `GEMINI_API_KEY` (free key from [aistudio.google.com](https://aistudio.google.com)); model `GEMINI_MODEL` (default `gemini-2.5-flash` — free tier). Note: **`gemini-2.5-pro` is *not* on the free tier** (needs billing enabled, ~$4-5/mo at this volume); Flash is free and plenty for this digest.
- **DeepSeek:** `DEEPSEEK_API_KEY`; model `DEEPSEEK_MODEL` (e.g. the cheap `deepseek-v4-flash`).
- Pulls news from [`deepseek/feeds.txt`](deepseek/feeds.txt) (edit to change breadth).
- **Trade-off:** it can only summarise what the RSS feeds supply, so discovery is narrower than Claude's live web search - the honest cost of going self-hosted.
- **This is also your answer to "runs even if my laptop is closed":** because it's plain Python, you can schedule it with `cron` on an always-on server / Raspberry Pi / cloud function.

---

## 8b. Website & cloud

**Website (local):** `python3 site/build_site.py` renders every digest into a styled, browsable site at `site/public/index.html` - with an archive grid (engine badges), a visual **catalyst timeline**, and a markets strip whose %-move matches each brief's window (daily ~5-day, weekly ~7-day). It also emits a subscribe-able **RSS feed** (`feed.xml`, auto-discovered by feed readers); the archive index caps at the 30 most recent and links to a full `archive.html`. Both engines rebuild it automatically after each run. Open `index.html` in any browser.

**Tests:** `python3 -m unittest discover -s tests -t tests` runs the stdlib unit-test suite (offline, no keys) over the digest, website, email, and Telegram helpers. A `Tests` GitHub workflow runs them automatically on every push/PR, so a code regression is caught before it can reach the morning send. See [`tests/README.md`](tests/README.md).

**Reliability:** two small guardian workflows back the daily run - **Heartbeat** (`heartbeat.yml`, daily) fails and emails you if no digest has been archived in >2 days (catching a *silently* stalled schedule), and **Re-time** (`retime.yml`, weekly) re-pins the UTC cron to your local send time across daylight-saving changes.

**Cloud (GitHub Actions + Pages):** [`.github/workflows/pharma-digest.yml`](.github/workflows/pharma-digest.yml) runs the digest daily at 07:00 Rome (Gemini by default), emails it, archives it, and publishes the website to **GitHub Pages** - all without your laptop. To go live:
1. Push this project to a (private) GitHub repo.
2. Add repo **Secrets**: `GEMINI_API_KEY`, `RESEND_API_KEY`, `EMAIL_TO`, `EMAIL_FROM` (and, to enable each option: `DEEPSEEK_API_KEY` + `DEEPSEEK_MODEL` for the fallback engine, `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` for Telegram, `SITE_URL` for absolute RSS links). Add repo **Variables**: `PHARMA_ENGINE` (`gemini` | `deepseek`) and `GEMINI_MODEL` (default `gemini-2.5-flash`; note `DEEPSEEK_MODEL` is a Secret, not a Variable).
3. **Settings → Actions → Workflow permissions → Read and write**; and **Settings → Pages → Source: GitHub Actions**.
4. The workflow runs on schedule, on the **Run workflow** button on demand, and can be paused/resumed from the Actions tab ("activate when I want").

---

## 8c. Telegram delivery (share without a domain)

Each cloud run also posts a short summary card - title, talking point, TL;DR, and a "read the full brief" link - to a **Telegram channel**. It's free, needs no email domain, and is the simplest way to share the brief with someone else (e.g. a colleague): just send them the channel link.

- Sender: [`pharma-news/send_telegram.py`](pharma-news/send_telegram.py) (standard library only), wired via `run_digest.py --telegram`.
- Secrets: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` (a `@channel`) in `secrets.env` and as GitHub Secrets. If `TELEGRAM_CHAT_ID` is unset, the step skips cleanly - the daily run is unaffected.
- The bot must be an **admin** of the channel to post.

---

## 9. File map

```
README.md                     ← this manual
.claude/commands/
  pharma-news.md              ← the engine (methodology)
pharma-news/
  digest-template.md          ← digest structure
  watchlist.md                ← what to always track
  catalysts.md                ← catalyst calendar source
  config.json                 ← timezone, audio settings
  send_digest.py              ← email sender (Resend)
  make_audio.py               ← audio narrator (macOS say)
  state.json                  ← remembers last run (powers catchup)
digests/
  YYYY-MM-DD.md               ← your daily archive
  INDEX.md                    ← archive index (powers look-back search)
  audio/                      ← spoken briefs
deepseek/
  run_digest.py               ← standalone Gemini/DeepSeek version
  feeds.txt                   ← RSS sources
  README.md                   ← DeepSeek guide
tests/                        ← unit tests (stdlib only) + golden fixtures
  README.md                   ← how to run them

Secrets (outside the repo, private):
  ~/.config/pharma-news/secrets.env   ← Resend + DeepSeek keys (chmod 600)
```

---

## 10. Security

- Secrets live **outside** the project folder, readable only by you (`chmod 600`). Never commit them.
- The Resend key should be **send-only** - even if leaked it can only send mail, never read your inbox.
- The DeepSeek key is spend-capped by your top-up balance.

---

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| `/pharma-news` not in menu | Restart Claude Code (commands load at startup). |
| Email `403 / error code 1010` | Cloudflare blocked it - the send script sets a User-Agent to avoid this; ensure you're on the latest `send_digest.py`. |
| Email `ERROR: missing RESEND_API_KEY` | Key not pasted/saved in `secrets.env`. |
| Email sends but doesn't arrive | Check spam; confirm `EMAIL_TO` is your Resend signup address (test mode). |
| Engine model error | Use a valid model ID for the chosen engine (`gemini-2.5-pro` / `gemini-2.5-flash`, or `deepseek-v4-flash`); for Gemini, confirm the free-tier limits cover the run (3 calls/day fits) or enable billing. |
| Morning run didn't fire at 7am | Mac was asleep/closed or app shut - see Section 6. |

---

## 12. Roadmap

- ✅ On-demand + cloud-scheduled digest · email · **Telegram** · evening + Sunday weekly editions · audio · website (markets, catalyst timeline, search, dark mode, "last updated") · thread-tracking / "what's new" tagging · archive search · accuracy pass + **grounding self-check** · self-maintaining catalysts · source date/times · DeepSeek engine
- 💡 Parked: WhatsApp (Business API isn't free/simple); a Claude-grade *cloud* digest (the on-demand `/pharma-news` already gives you Claude quality on your subscription).
- See `ROADMAP.md` for the full checklist.
