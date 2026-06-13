# Product Requirements Document - Pharma Morning Brief

**One-liner:** An automated, balanced pharma news aggregator that turns the day's
pharmaceutical news into a fact-checked, 2-3 minute executive digest - delivered by
email and as a website.

## Problem
Pharma moves extremely fast (daily approvals, trial readouts, M&A, pricing/policy
shifts across dozens of companies). Staying current today means either shallow
headline feeds with no analysis, or 45-60 minutes scanning many outlets. There is no
single, balanced, *analysed*, 2-3 minute morning brief that also says what the news
*means*.

## Target users
- **Primary:** an incoming Eli Lilly intern / MBA entering pharma - needs full-industry
  awareness plus sharpened intelligence on Lilly and its competitors, readable in the
  time it takes to drink a coffee.
- **Secondary:** any busy professional in or around pharma (strategy, BD, investing,
  comms) who needs a daily, contextual brief rather than a firehose of headlines.

## Key features
1. **Balanced multi-source sweep** - curated trade press (Endpoints, STAT, Fierce,
   BioPharma Dive, Labiotech, Pharma Technology) plus broad aggregation; "reputable
   sources only / weak single source = unconfirmed" rule.
2. **Context, not just headlines** - each story analysed through up to 8 executive
   lenses (financial, strategic, commercial, scientific, regulatory, geopolitical,
   leadership, technology).
3. **Eli Lilly Spotlight** - a dedicated block on Lilly and its rivals, with "so what for Lilly".
4. **Forward-looking** - a catalyst calendar (FDA PDUFA + EMA/CHMP, earnings,
   conferences) and a live pharma markets snapshot.
5. **Trustworthy** - a mandatory anti-hallucination pass (every fact traced to a real
   source; rumours labelled); plain-language glosses for niche terms.
6. **Two interchangeable engines** - Claude (richest, on-demand) and DeepSeek (cheap,
   runs automatically in the cloud).
7. **Delivery** - an automatic morning email (Resend) and a browsable website (timeline,
   markets, full-text search, archive), auto-published every morning via GitHub Actions
   and GitHub Pages - no laptop required.

## Out of scope
Real-time/intraday alerts; trading signals or investment advice; deep single-company
equity research; non-pharma industries (the design is portable, but not built for them).

## Success criteria
A busy reader stays genuinely current in 2-3 minutes/day instead of 45-60, with every
claim source-grounded and the most relevant catalysts flagged before they happen.

## How it works (one line)
One shared "recipe" (methodology + watchlist + template) -> two AI engines -> delivered
as email + website; see `CLAUDE.md` and `GUIDE.md` for detail.
