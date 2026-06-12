# 🐋 DeepSeek standalone version

Runs the digest **without Claude** — on the DeepSeek API, per-token (no subscription). Same methodology and Lilly focus, just a different brain and a different news source.

## How it differs from the Claude version

| | Claude (`/pharma-news`) | DeepSeek (`run_digest.py`) |
|---|---|---|
| Research | Agentic live web search (broad, adaptive) | Fixed RSS feeds (`feeds.txt`) |
| Analysis | Claude | DeepSeek (`deepseek-chat`) |
| Cost | Your Claude plan | Per-token DeepSeek API |
| Runs without the Claude app? | No | **Yes** (plain Python) |

The trade-off: DeepSeek can only summarise the articles the RSS feeds supply — so coverage breadth depends on `feeds.txt`, not on adaptive searching. Quality of *analysis* is good; breadth of *discovery* is narrower. This is the honest cost of going subscription-free and self-hosted.

**Anti-hallucination:** DeepSeek is told to use *only* the fetched articles and never add facts from memory — grounded summarisation, which is the lowest-hallucination setup.

## Setup (one-time)

1. Get a key at [platform.deepseek.com](https://platform.deepseek.com) → API Keys.
2. Paste it into `~/.config/pharma-news/secrets.env` (replace `PASTE_YOUR_DEEPSEEK_KEY_HERE`).

## Run

```bash
python3 deepseek/run_digest.py                  # morning, last 24h
python3 deepseek/run_digest.py --edition evening --hours 48
python3 deepseek/run_digest.py --email          # also email it via Resend
```

Output saves to `digests/YYYY-MM-DD.md`, same as the Claude version.

## Tuning

- **Add/remove sources:** edit `feeds.txt`.
- **Switch model:** set `DEEPSEEK_MODEL=deepseek-reasoner` in secrets for the reasoning model.
- **OpenWebUI route:** if you'd rather drive it from OpenWebUI, you can paste the system prompt (built from this project's files) and the article corpus into a DeepSeek chat — but this script automates the whole loop for you.
