# Open me first

Pharma Morning Brief - an automated, balanced pharma news aggregator. It turns the
day's pharmaceutical news into a fact-checked, 2-3 minute executive digest (with a
focus on Eli Lilly), delivered by email and as a website.

## Just want to see it? (10 seconds, no setup, works offline)
Open  **site/public/index.html**  in your browser.
That is the product: today's digest, a catalyst timeline, a pharma markets chart,
full-text search, and an archive of past digests.

## Reading order - you only need the first two
1. This file (what to open).
2. site/public/index.html (the product).

Everything else is reference, in rough order of usefulness:
- GUIDE.md         - how it works, in plain English (1 recipe, 2 AI engines, email + website)
- samples/email-preview.html  - exactly what the morning email looks like (opens in a browser)
- EVIDENCE.md      - proof the email + cloud automation really run (not a mock-up)
- CLAUDE.md        - project overview + the problem statement it was built against
- README.md        - the full technical manual
- ROADMAP.md       - features built, and ideas considered or parked
- DEMO.md          - a 60-second demo script

## Folders
- site/         - the generated website
- digests/      - saved digests (the data the website shows)
- pharma-news/  - the engine's config (watchlist, catalysts, template) and scripts
- deepseek/     - the DeepSeek engine and its news feeds
- samples/      - the email preview
- .github/      - the cloud automation (GitHub Actions)
- .claude/commands/  - the /pharma-news command for Claude Code

## Run it yourself (optional)
- Richest version (Claude): open this folder in Claude Code and type  /pharma-news
- Automatic version (DeepSeek): double-click  "Pharma Command Centre.command"  for a
  simple menu (generate a digest, open the site, check status, edit sources).
