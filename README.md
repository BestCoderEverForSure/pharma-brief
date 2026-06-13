# Pharma Morning News Aggregator - Instruction Manual

> **New here?** Open **`OPEN ME FIRST.md`** for a 30-second orientation - or jump straight to the product: open **`site/public/index.html`**.

A balanced, high-signal briefing on the global pharmaceutical world, built to be read (or heard) in **2-3 minutes** with your morning coffee - with a deeper evening edition when you have more time.

It collects the day's pharma news (big pharma, biotech, startups, M&A, rumours, regulatory, trends - worldwide), puts each story **in context**, analyses it through eight executive **lenses**, sharpens focus on **Eli Lilly** and its rivals, flags **upcoming catalysts** and **wider-world news with pharma implications**, and runs a strict **accuracy pass** so you can repeat what you read without getting burned.

---

## 1. Quick start

Type in Claude Code:

| Command | What you get |
|---|---|
| `/pharma-news` | The **last 24 hours** - your daily 2-3 min morning read. |
| `/pharma-news evening` | A deeper **5-8 min** read with more stories + a 🔬 Deep Dive. |
| `/pharma-news catchup` | Everything **since you last ran it** (after a few days away). |
| `/pharma-news since 2026-06-01` | From a specific date until now. |
| `/pharma-news evening catchup` | Combine modes (deep read, since last run). |
| *(just ask in chat)* | Look-back questions: *"what happened with orforglipron last month?"* - searches your saved archive. |

> **First-time note:** new slash commands only appear in the menu after you **restart Claude Code**. The automatic morning run does **not** need this (see Section 6).

---

## 2. What's in each digest

1. **💡 Talking point** - one sharp, non-obvious line to sound on top of the industry in a meeting.
2. **TL;DR** - the 3-5 things that matter.
3. **Top Stories** - 2-4 items (4-6 in the evening edition), each with *What happened*, *What it means*, and 2-4 analysis lenses.
4. **🔬 Deep Dive** *(evening only)* - ~150-250 word synthesis of the day's biggest theme.
5. **🎯 Eli Lilly Spotlight** - Lilly's own news + competitor moves that affect its position, with "so what for Lilly."
6. **On the radar** - quick one-line hits (rumours labelled).
7. **🌍 Wider world → pharma** - non-pharma news with sector implications.
8. **📅 Week Ahead** - upcoming catalysts (FDA *and* EMA/CHMP, earnings, readouts, conferences).
9. **Sources** - every link, so you can verify or read deeper.

### The eight analysis lenses
Applied 2-4 per story (never all - a forced lens is noise): **Financial & capital markets · Strategic & competitive · Commercial & market access · Scientific & clinical · Regulatory & legal · Geopolitical & macro · Leadership & organizational · Technology & innovation.**

---

## 3. Accuracy (anti-hallucination)

Before saving any digest, the engine runs a mandatory accuracy pass:
- Every number, date, name, and deal value must trace to a **real source seen that run** - no filling gaps from memory.
- Market-moving facts need **two sources or a primary source** (company PR / regulator).
- **Rumours are labelled**; weak-sourced specifics are marked or dropped.
- **No invented links.** If the day is thin, it says so rather than padding.

The DeepSeek version (Section 8) is grounded *only* on the articles it fetches - the lowest-hallucination setup.

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

The morning run can email you the digest. It uses **Resend** with a **send-only** API key, stored privately at `~/.config/pharma-news/secrets.env` (chmod 600, outside this repo).

**Setup (done if you see `Sent ✓`):**
1. Sign up free at [resend.com](https://resend.com) using the address you want the digest sent to.
2. **API Keys → Create** with **Sending access** (not Full - see security note below). Copy the `re_...` key.
3. Paste it into `secrets.env` over `PASTE_YOUR_RESEND_KEY_HERE`. Save.
4. Test: `python3 pharma-news/send_digest.py` → expect `Sent ✓`.

- **Test mode** only sends to your own signup address. To send to your IMD email or a custom "from," verify a domain in Resend and update `EMAIL_FROM`.
- The send script lives at [`pharma-news/send_digest.py`](pharma-news/send_digest.py) (standard library only).

---

## 6. How the morning schedule works ⚠️ (read this)

The daily run is a **scheduled task** in the Claude app (`pharma-morning-digest`, cron `0 7 * * *`). Important realities:

- **It runs on your computer's local clock.** 7am Singapore now; automatically 7am Rome once you set your Mac to Italy time. No change needed when you relocate.
- **It uses your Claude account automatically** - you do *not* need to type anything or be present. But...
- **The Claude app must be running and your Mac must be awake.** If the computer is **asleep, shut, or the app is closed** at 7am, the task does **not** fire on time - it runs **the next time you open the app**. So you'd still get the digest, just later.
- It does **not** need the `/pharma-news` slash command to be registered - the task carries its own full instructions.

**To make the 7am run reliable:** leave the Mac plugged in, awake, and the Claude app open overnight. For a digest that arrives **even if your laptop is closed**, run the **DeepSeek version on an always-on machine** (Section 8) - that's the only setup fully independent of this laptop.

Manage/pause the task in the **"Scheduled"** sidebar. To pre-approve its tools (so the first auto-run doesn't pause for permissions), hit **"Run now"** there once.

### Which engine wrote it?
Every digest says so in its subtitle - **`Engine: Claude`** or **`Engine: DeepSeek (model)`**. Claude digests use inline linked sources; DeepSeek digests use numbered `[n]` citations resolved in a Sources list.

### Your single automatic runner: the cloud
The automatic morning digest runs in the **cloud** (GitHub Actions, DeepSeek) - reliable, laptop-independent, and it also publishes the website. Start/stop it from the repo's **Actions** tab (Disable/Enable workflow; "Run workflow" for on-demand). For a richer read any time, run `/pharma-news` (Claude) by hand. See `GUIDE.md`.

---

## 7. Audio brief (optional)

A spoken version you can listen to on the commute - free, offline, via the macOS `say` engine.

- Turn on: set `"audio": true` in [`config.json`](pharma-news/config.json) (voice via `"audio_voice"`; list voices with `say -v '?'`).
- Output: `digests/audio/YYYY-MM-DD.m4a`.
- Manual: `python3 pharma-news/make_audio.py`.

---

## 8. DeepSeek standalone version (run without Claude)

A subscription-free, **per-token** version on the DeepSeek API. Same methodology, different brain and news source. Full details in [`deepseek/README.md`](deepseek/README.md).

```bash
python3 deepseek/run_digest.py                       # morning, last 24h
python3 deepseek/run_digest.py --edition evening --hours 48
python3 deepseek/run_digest.py --email               # also email it
```

- Model is set in `secrets.env` (`DEEPSEEK_MODEL=deepseek-v4-flash` - the cheap one).
- Pulls news from [`deepseek/feeds.txt`](deepseek/feeds.txt) (edit to change breadth).
- **Trade-off:** it can only summarise what the RSS feeds supply, so discovery is narrower than Claude's live web search - the honest cost of going self-hosted.
- **This is also your answer to "runs even if my laptop is closed":** because it's plain Python, you can schedule it with `cron` on an always-on server / Raspberry Pi / cloud function.

---

## 8b. Website & cloud

**Website (local):** `python3 site/build_site.py` renders every digest into a styled, browsable site at `site/public/index.html` - with an archive grid (engine badges) and a visual **catalyst timeline**. Both engines rebuild it automatically after each run. Open `index.html` in any browser.

**Cloud (GitHub Actions + Pages):** [`.github/workflows/pharma-digest.yml`](.github/workflows/pharma-digest.yml) runs the DeepSeek digest daily at 07:00 Rome, emails it, archives it, and publishes the website to **GitHub Pages** - all without your laptop. To go live:
1. Push this project to a (private) GitHub repo.
2. Add repo **Secrets**: `DEEPSEEK_API_KEY`, `RESEND_API_KEY`, `EMAIL_TO`, `EMAIL_FROM`, `DEEPSEEK_MODEL`.
3. **Settings → Actions → Workflow permissions → Read and write**; and **Settings → Pages → Source: GitHub Actions**.
4. The workflow runs on schedule, on the **Run workflow** button on demand, and can be paused/resumed from the Actions tab ("activate when I want").

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
  run_digest.py               ← standalone DeepSeek version
  feeds.txt                   ← RSS sources
  README.md                   ← DeepSeek guide

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
| DeepSeek model error | Use a valid ID (`deepseek-v4-flash` / `deepseek-v4-pro`); check balance. |
| Morning run didn't fire at 7am | Mac was asleep/closed or app shut - see Section 6. |

---

## 12. Roadmap

- ✅ On-demand + scheduled digest · email · evening edition · audio · thread-tracking · archive search · earnings-day mode · accuracy pass · DeepSeek version
- 💡 Parked: charts/visuals (one lightweight chart in HTML email), WhatsApp/Telegram delivery, cloud-hosted always-on run.
