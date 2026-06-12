# One-page reflection — Vibe Coding 2026

*(Draft to edit into your own voice, then type into the Microsoft Form.)*

**What did you build?**
A **Pharma Morning Brief** — an automated aggregator that reads the day's pharmaceutical news and produces a balanced, fact-checked **2–3 minute executive digest**, with a focus on Eli Lilly (where I'm interning). It puts each story *in context* through executive lenses (financial, strategic, commercial, regulatory), flags upcoming catalysts, and is delivered two ways: an automatic morning **email** and a browsable **website** (archive, search, catalyst timeline, live markets chart). It runs on **two interchangeable engines** — Claude for the richest on-demand read, and a cheaper DeepSeek pipeline that runs automatically in the cloud (GitHub Actions) so it arrives even when my laptop is off.

**Which prompt or approach worked best?**
Treating Claude as a junior developer and myself as the product manager — directing, not coding. The highest-leverage decision was making the tool **config-driven**: one shared "recipe" (methodology + watchlist + template) that both engines read, so any improvement propagates everywhere. Working in small, testable steps and asking Claude to *verify its own work* (grep the output, test the feed, run the build) caught problems fast. Being specific about the user — "an incoming Lilly intern, biomedical background but new to pharma" — produced far better output than generic prompts; it's why the digest now glosses niche terms in plain language.

**What failed, and why?**
The failures taught me the most:
- The local 7am scheduler (macOS launchd) **silently failed** — macOS blocks background jobs from reading the Desktop folder, a privacy protection I didn't know existed. I pivoted to running it in the cloud.
- A "free" stock-price source (Stooq) turned out to be **bot-blocked**; I switched to Yahoo Finance.
- The cheaper DeepSeek engine was **confidently wrong** — it emitted broken formatting and cited sources by number with no source list. I fixed it deterministically *in code* rather than trusting the model to behave.
- I briefly had **two schedulers running**, which would have sent duplicate emails — a lesson in keeping the system simple.

**What would you do differently next time?**
Decide the architecture earlier. I built a local scheduler before realising the cloud was the right home; framing "it must run when my laptop is closed" as a first principle up front would have saved a detour. I'd also adopt an "how will I *prove* this works?" mindset from the start, and cut scope faster — a few nice ideas (WhatsApp delivery, paid data) were correctly dropped, but I entertained them longer than I should have.

**How might this skill apply to your career?**
Significantly. I can now turn an idea into a *working* prototype in an afternoon instead of a slide deck, which changes how I'd pitch an initiative at Lilly. I have a sharper sense of what's easy versus hard for engineers (scraping headlines is easy; reliable scheduling and email deliverability are surprisingly fiddly), so I can scope requests realistically and recognise when an AI is confidently wrong. Most of the work was **judgment** — framing the problem, evaluating output, deciding what to leave out — which is exactly the "AI-native" capability that is fast becoming a baseline expectation rather than a differentiator.
