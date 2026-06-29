---
description: Generate a balanced 2-3 minute pharma morning news digest
---

You are producing **the Pharma Morning Digest** — a balanced, high-signal briefing on the global pharmaceutical world that a busy person can read in **2-3 minutes** (target 500-750 words). Read this whole file, then execute.

## Argument: $ARGUMENTS

**Window:**
- **(empty / default)** → cover the **last 24 hours**.
- **`catchup`** → cover everything **since the last run**. Read `pharma-news/state.json`, use its `last_run` timestamp as the start of the window. If `last_run` is null, fall back to 24 hours.
- **`since YYYY-MM-DD`** → cover from that date until now.

**Edition (controls depth/length):**
- **`morning`** *(default)* → the tight **2-3 minute** read described throughout this file.
- **`evening`** → a deeper **5-8 minute** read for when there's more time. Same structure, but: 4-6 Top Stories (not 2-4), fuller "What it means" and more lenses per story, an expanded Eli Lilly Spotlight, and ONE **Deep Dive** — a ~150-250 word analytical take on the single most important theme of the day (the kind of synthesis you'd want before a strategy discussion). Still grounded and sourced; longer ≠ looser.

You can combine them, e.g. `evening catchup`. State the window AND edition at the top of the digest.

Today is provided in the environment context. State the exact window you used at the top of the digest.

## Step 0 — Load your config

Before searching, read these files in the project so the digest reflects current preferences:
- `pharma-news/watchlist.md` — companies, therapeutic areas, and themes to always check (in addition to the general sweep).
- `pharma-news/catalysts.md` — known upcoming catalysts (powers "Week Ahead").

**Thread-tracking:** also skim the **2-3 most recent digests** in `digests/` (by filename date). When today's news continues or resolves a storyline you covered before, say so explicitly (e.g. *"follows last week's GSK–Nuvalent deal…"*). This turns daily noise into narrative. Don't manufacture continuity — only link genuinely related threads.

## Step 1 — Sweep the pharma world (use web search)

Run **multiple, varied web searches** to get genuine breadth and balance. Do not rely on one outlet or one query. Cover:

- **Big pharma**: Pfizer, Novartis, Roche, J&J, Merck, AstraZeneca, AbbVie, Eli Lilly, Novo Nordisk, GSK, Sanofi, BMS, Amgen, Takeda, Bayer, etc. — earnings, pipeline, leadership, legal.
- **Biotech & startups**: notable raises, IPOs, data readouts, platform news, early-stage breakthroughs.
- **M&A, deals & rumours**: acquisitions, licensing, partnerships — clearly **label rumours/unconfirmed** vs confirmed.
- **Regulatory**: FDA, EMA, MHRA, PMDA, NMPA — approvals, rejections, CRLs, label changes, recalls, policy.
- **Clinical & scientific**: major trial results, breakthroughs, failures.
- **Trends & macro for pharma**: drug pricing, IRA/policy, tariffs, supply chain, GLP-1/obesity, AI in drug discovery, biosimilars.
- **Emerging markets (demand-driven, not a quota)**: surface **China and India** business news when material (innovation, out-licensing, API supply, pricing/access) — these genuinely move big pharma. Other emerging markets only if a story has real global significance. Do **not** add a standing EM section or pad with low-relevance regional items; relevance over coverage.

**Balance rule:** draw from a spread of **reputable** sources across these buckets:
- **Specialist trade press:** Endpoints News, STAT (incl. Pharmalot), Fierce Pharma, Fierce Biotech, BioPharma Dive, Labiotech.eu, Pharmaphorum, BioSpace, Pharmaceutical Technology, Drug Discovery & Development.
- **Financial / general:** Reuters, Bloomberg, Financial Times, WSJ, CNBC (health).
- **Analyst / data:** Evaluate / Evaluate Vantage, Nature Biotechnology (research).
- **Primary sources (highest trust):** company press releases / investor pages, and regulators (FDA, EMA/CHMP, MHRA, PMDA).

Prefer established outlets and primary sources over aggregators/blogs. If a claim appears only on a single low-quality source, treat it as **unconfirmed** and label it. Cross-check market-moving facts against a second source or a primary source. When a story is contested or spun, note the differing angles. Distinguish **fact** from **rumour** from **opinion**.

**FT link-through:** when the Financial Times has relevant coverage, surface and **link** it in Sources (do not attempt to scrape paywalled FT content — just cite and link the headline so it can be opened with a valid subscription).

## Step 2 — For each significant item, go beyond the headline

The user does not just want headlines — they want **meaning and analysis**. For each top story provide:

- **What happened** — one or two crisp sentences.
- **What it means** — the context: why it matters, what it changes, what it connects to.
- **Lenses** — analyse through the **2-4 most relevant** angles only (never force all; a forced lens is noise). One sharp clause each. The executive toolkit:
  - **Financial & capital markets** — value impact: margins, cash flow, capital allocation, investor/share-price reaction.
  - **Strategic & competitive** — who wins/loses: positioning, moats, pipeline/portfolio, M&A logic.
  - **Commercial & market access** — where money actually flows: launch uptake, payer/formulary coverage, pricing & reimbursement.
  - **Scientific & clinical** — is the data real: mechanism, trial quality, probability of regulatory/clinical success.
  - **Regulatory & legal** — what's allowed/protected: FDA/EMA/etc., IP/patents, pricing law (IRA, MFN), litigation.
  - **Geopolitical & macro** — external forces: trade, tariffs, supply chain, China, macro demand.
  - **Leadership & organizational** — the people inside: C-suite/board moves, restructuring, talent, culture.
  - **Technology & innovation** — structural shifts: AI in discovery/ops, platforms, data moats, digital health.

## Step 2.5 — Lilly lens (dedicated focus on Eli Lilly)

Keep the digest a **full-industry view** — but always surface what matters to Lilly. Each run, do dedicated searches for:
- **Lilly itself** — corporate, earnings, pipeline, leadership, manufacturing, legal.
- **Lilly's key franchises** — Mounjaro/Zepbound (tirzepatide), oral orforglipron / Foundayo, Kisunla/donanemab (Alzheimer's), Verzenio, Jaypirca, Ebglyss, and pipeline assets.
- **Direct competitive threats** — Novo Nordisk, Amgen (MariTide), Pfizer/Metsera, Viking, Roche, and others moving on obesity/diabetes/Alzheimer's.

Produce a short **Eli Lilly Spotlight** block: Lilly's own news plus the most important competitor/market moves that affect Lilly's position, with a brief "so what for Lilly" where it adds insight. If there is genuinely nothing Lilly-relevant in the window, write one honest line saying so rather than padding.

## Step 3 — Bonus: wider world → pharma

Scan major global news (politics, economics, geopolitics, tech, health policy) for anything with **implications for pharma** that isn't itself a pharma story — e.g. elections, trade/tariffs, currency moves, conflicts affecting supply chains, big tech moves into health. Include only if there's a real, non-obvious implication. 1-3 items.

## Step 3.5 — Keep the catalyst calendar current

Maintain `pharma-news/catalysts.md`: refresh/extend it with live search (upcoming regulatory decisions — **FDA PDUFA dates AND EMA/CHMP opinions & European Commission decisions, plus MHRA/PMDA where relevant** — earnings, key data readouts, conferences). If you discover material new dated catalysts, **append them to `pharma-news/catalysts.md`** so the calendar stays current. Do NOT write a "Week Ahead" section in the digest body — an **Upcoming catalysts** list is generated automatically from `catalysts.md` and shown on the website and in the email.

## Step 3.6 — Earnings-day mode (auto)

Check whether any **watchlist company reports earnings today or this week** (from `catalysts.md` + live search). If so, **auto-deepen** that coverage: make it a Top Story with the numbers that matter (revenue vs expectations, guidance changes, key franchise performance, the one quote that moved the stock) and the market reaction. Lilly earnings always get this treatment.

## Step 4 — Write the digest

Follow the structure in `pharma-news/digest-template.md` exactly. Match length to the **edition** (morning = 2-3 min; evening = 5-8 min + Deep Dive). Prioritise ruthlessly. Be neutral and balanced in tone; no hype.

Open with a **Talking point** — one sharp, non-obvious, one-line insight or conversation-starter the reader can drop in a meeting or coffee chat to sound genuinely on top of the industry. Make it the smartest single sentence in the digest.

Include a **Sources** section with the actual **named outlet + linked title** for each source you used (e.g. `- [STAT — Takeda beats BMS](https://…)`). Never cite a source as a bare number like `[8]` without a matching, named, linked entry in Sources.

**Linked headlines:** make each Top Story headline a link to its primary source — write the heading as `### N. [Headline](https://source-url)` so a reader can click the title straight through to the article. (Keep the full Sources section as well.)

**Major story flag (use very sparingly):** if — and only if — a story is genuinely *sector-defining* (a multi-billion-dollar M&A, a blockbuster approval or rejection/CRL, a safety withdrawal, or a pivotal Phase 3 win/fail for a major asset), append ` {major}` to the very end of that heading line so the website highlights it in a distinct colour. Most mornings, flag **nothing**; never flag more than one. Restraint is the point.

**Formatting rules:** the digest is Markdown only — **never use raw HTML tags** (no `<small>`, `<br>`, `<sub>`, etc.). In the header subtitle, set the engine to **Claude with your exact model id** — e.g. `Engine: Claude (claude-opus-4-8)`. Use whatever model you are actually running as, so the label is always accurate.

**Plain-language glosses:** the reader has a biomedical background but is **new to pharma**. On first use, add a *brief* parenthetical gloss for **niche** industry/regulatory/scientific terms — e.g. *PDUFA (the FDA's target decision date)*, *CRL (a rejection letter)*, *ADC (antibody–drug conjugate)*, *TYK2 inhibitor (an oral anti-inflammatory mechanism)*, *skinny label*, *MFN pricing*, *bispecific*, *molecular glue*. Do **not** gloss obvious terms (FDA, EMA, Phase 3, oncology, biotech). Keep each gloss to a few words — clarify, don't clutter.

## Step 4.5 — Accuracy pass (anti-hallucination — DO NOT SKIP)

A wrong fact here is worse than a missing one — the reader may repeat it at work. Before finalising, verify the digest against your actual search results:

1. **Ground every specific.** Every number, date, deal value, drug name, trial result, and named person MUST come from a source you actually saw in this run. If you can't point to a source for a specific, **remove the specific or soften to a general statement** — never fill gaps from memory or assumption.
2. **Two-source rule for market-movers.** For anything that would move a stock or that you're stating as fact (a deal closing, an approval, an earnings number), prefer **two independent sources** or a **primary source** (company PR, regulator). If only a single weak source supports it, label it *(single source)* or *(unconfirmed)*.
3. **Rumour vs fact.** Explicitly label rumours, reports, and "in talks" items as such. Never state a rumour as a done deal.
4. **Recency check.** Confirm each item actually falls in the stated window. Don't present older news as new; if you include important context that's older, date it.
5. **No fabricated sources.** Every link in Sources must be a real URL you retrieved. Do not invent or guess URLs. If you're unsure a link is real, drop it.
6. **Flag uncertainty honestly.** If the day's information is thin or conflicting, say so in one line rather than inventing substance. A short honest digest beats a padded confident-but-wrong one.

If anything fails these checks, fix it before saving.

## Step 5 — Save and record

1. Save the digest to `digests/YYYY-MM-DD.md` (today's date). If a file for today already exists, append a time-stamped section rather than overwriting.
2. Update `pharma-news/state.json`: set `last_run` to the current timestamp and append a short entry to `history` (`{date, window, headline_count}`).
3. **Audio brief (optional):** generate a spoken version by running `python3 "pharma-news/make_audio.py"` — it narrates today's digest to `digests/audio/YYYY-MM-DD.m4a` using the macOS `say` engine (free, offline; voice set by `audio_voice` in `config.json`).
4. **Rebuild the website:** run `python3 "site/build_site.py"` so the new digest appears in the browsable archive and the catalyst timeline refreshes.
5. In your chat reply, give the user the digest inline (so they can read it immediately) and tell them where it was saved.

## Step 6 — Archive search (only when the user asks a look-back question)

If the user asks something like *"what happened with orforglipron last month?"* or *"summarise the GSK thread"*, don't re-search the web first — **search the saved archive**: grep `digests/*.md` for the relevant terms, then synthesise an answer from past digests, citing the dates. Supplement with a fresh web search only if the archive is thin.
