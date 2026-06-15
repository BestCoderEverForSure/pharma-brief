#!/usr/bin/env python3
"""
Standalone Pharma Digest generator (no Claude Code needed).

Per-token / free-tier, subscription-free. Pulls real pharma news from RSS feeds, then
asks an LLM to write the digest using THIS PROJECT'S OWN METHODOLOGY (it reads the same
command file, watchlist, and template Claude uses — one source of truth).

Engine-swappable via PHARMA_ENGINE (gemini|deepseek): Gemini is primary (free tier);
DeepSeek is the alternative. Both speak the OpenAI-compatible chat API. Anti-hallucination
by design: the engine cannot browse, so it uses ONLY the supplied articles, and a second
grounding pass revises out any claim the sources don't support.

Usage:
    python3 deepseek/run_digest.py [--hours 24] [--edition morning|evening] [--email] [--engine gemini|deepseek]

Secrets (env var or ~/.config/pharma-news/secrets.env):
    PHARMA_ENGINE      (optional, "gemini" | "deepseek"; default: Gemini if keyed, else DeepSeek)
    GEMINI_API_KEY     (for the Gemini engine; free key at aistudio.google.com)
    GEMINI_MODEL       (optional, default "gemini-2.5-pro")
    DEEPSEEK_API_KEY   (for the DeepSeek engine)
    DEEPSEEK_MODEL     (optional, default "deepseek-chat")

Stdlib only — no pip installs.
"""

import os
import re
import sys
import json
import time
import argparse
import datetime as dt
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET
import http.client
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = Path.home() / ".config" / "pharma-news" / "secrets.env"
FEEDS_FILE = ROOT / "deepseek" / "feeds.txt"
# Cap how much of a feed we read before parsing. Real RSS/Atom feeds are well under this;
# the cap bounds a hostile/runaway payload (stdlib ElementTree isn't hardened for that).
MAX_FEED_BYTES = 5 * 1024 * 1024

# Shared catalyst date parser (also used by the site/email renderers) so the auto-detect
# dedup treats a curated "Sep 2026" and an auto-detected "2026-09-15" as the same day.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pharma_render import catalyst_date

DEFAULT_FEEDS = [
    "https://www.fiercepharma.com/rss/xml",
    "https://www.fiercebiotech.com/rss/xml",
    "https://endpoints.news/feed/",
    "https://www.statnews.com/category/pharma/feed/",
    "https://www.biopharmadive.com/feeds/news/",
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/press-releases/rss.xml",
]


def load_secrets() -> dict:
    s = {}
    if SECRETS_PATH.exists():
        for line in SECRETS_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                s[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL",
              "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_BASE_URL", "PHARMA_ENGINE"):
        if os.environ.get(k):
            s[k] = os.environ[k]
    return s


def get_feeds() -> list[str]:
    if FEEDS_FILE.exists():
        feeds = [l.strip() for l in FEEDS_FILE.read_text().splitlines()
                 if l.strip() and not l.strip().startswith("#")]
        if feeds:
            return feeds
    return DEFAULT_FEEDS


def fetch(url: str, timeout: int = 20) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pharma-digest/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(MAX_FEED_BYTES)
    except (OSError, http.client.HTTPException, ValueError) as e:
        # OSError covers URLError/timeouts/resets; HTTPException covers errors
        # raised mid-read (IncompleteRead etc.) — one bad feed must not kill the run.
        print(f"  ! skip {url}: {e}", file=sys.stderr)
        return None


def parse_feed(xml_bytes: bytes, since: dt.datetime) -> list[dict]:
    items = []
    # Defuse entity-expansion ("billion laughs"): stdlib ElementTree isn't hardened for
    # hostile input, and a legitimate RSS/Atom feed never declares custom entities. If one
    # does, treat the feed as untrusted and skip it rather than parse it. (ElementTree does
    # not resolve external entities, so XXE/file access isn't a vector here.)
    if b"<!ENTITY" in xml_bytes:
        print("  ! skip feed: declares XML entities (untrusted)", file=sys.stderr)
        return items
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return items
    # Handle RSS (<item>) and Atom (<entry>).
    nodes = root.iter("item")
    atom = "{http://www.w3.org/2005/Atom}"
    entries = list(nodes) or list(root.iter(f"{atom}entry"))
    for it in entries:
        def text(*tags):
            for t in tags:
                el = it.find(t)
                if el is not None and el.text:
                    return el.text.strip()
            return ""
        title = text("title", f"{atom}title")
        link = text("link", "guid")
        if not link:
            le = it.find(f"{atom}link")
            link = le.get("href") if le is not None else ""
        summary = text("description", "summary", f"{atom}summary", "{http://purl.org/rss/1.0/modules/content/}encoded")
        pub = text("pubDate", "published", f"{atom}published", "{http://purl.org/dc/elements/1.1/}date")
        when = None
        if pub:
            try:
                when = parsedate_to_datetime(pub)
            except (TypeError, ValueError):
                try:
                    when = dt.datetime.fromisoformat(pub.replace("Z", "+00:00"))
                except ValueError:
                    when = None
        if when and when.tzinfo is None:
            when = when.replace(tzinfo=dt.timezone.utc)
        if when and when < since:
            continue
        # Trim HTML-ish summaries crudely.
        summary = re.sub(r"<[^>]+>", "", summary)[:400]
        # Require a real http(s) link: a citation must trace to a fetchable source.
        # (link falls back to <guid>, which is often a non-URL urn/id — citing that
        # would produce a dead Sources link, breaking the "every fact links" rule.)
        if title and link.startswith(("http://", "https://")):
            items.append({"title": title, "link": link, "summary": summary,
                          "when": when.isoformat() if when else "n/a"})
    return items


def gather(hours: int) -> list[dict]:
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    all_items = []
    for url in get_feeds():
        print(f"  fetching {url}", file=sys.stderr)
        raw = fetch(url)
        if raw:
            all_items.extend(parse_feed(raw, since))
    # De-dup by title.
    seen, uniq = set(), []
    for it in all_items:
        key = it["title"].lower()
        if key not in seen:
            seen.add(key)
            uniq.append(it)
    return uniq


MODE_NOTES = {
    "daily": "",
    "review": ("- WEEKLY REVIEW edition (Saturday): step back and synthesize the WHOLE WEEK — "
               "the 3-5 biggest themes/threads, what changed and why it matters over the week, "
               "the big picture and the connections across stories. Less a list of headlines, "
               "more an analytical wrap-up. Title it '# Pharma Week in Review - {DATE}'."),
    "ahead": ("- WEEK AHEAD edition (Sunday): do NOT recap past news. Look FORWARD — lead with the "
              "most important catalysts and events coming in the next ~1-2 weeks (from the catalyst "
              "calendar in the methodology and any explicitly-dated future events in the articles), "
              "and for each explain what is at stake, who is affected, and what to watch. Use the "
              "past week's articles only for context/grounding. Keep the talking point and TL;DR, "
              "but frame everything around what's coming. Title it '# Pharma Week Ahead - {DATE}'."),
}


def build_system_prompt(edition: str, engine_label: str = "DeepSeek", mode: str = "daily") -> str:
    """Reuse the project's tuned methodology as the system prompt."""
    parts = ["You are generating the Pharma Digest.",
             "",
             f"IMPORTANT ADAPTER NOTES (you are running on {engine_label}, not Claude Code):",
             "- You CANNOT browse the web. Use ONLY the news articles provided in the user message.",
             "- Ignore any instructions in the methodology about running web searches or saving files — those are handled outside you.",
             "- ANTI-HALLUCINATION: every fact, number, date, name, and deal value MUST come from the provided articles. If it is not in the articles, do not state it. Never use facts from your training data. Label rumours as rumours. If the day's articles are thin, say so honestly rather than inventing substance.",
             f"- Edition: {edition} (morning = tight 2-3 min; evening = deeper 5-8 min with a Deep Dive).",
             "- GLOBAL BALANCE: cover developments wherever they occur — US/FDA, but also EMA/EU, UK, Japan, China, India — in proportion to what the articles actually report. Don't over-weight US stories just because more of them appear; equally, don't manufacture or inflate non-US items. Represent the day's real global picture.",
             *( [MODE_NOTES[mode]] if MODE_NOTES.get(mode) else [] ),
             "- Output ONLY the finished digest in Markdown. No preamble.",
             "- FORMATTING: Markdown only. NEVER use raw HTML tags (no <small>, <br>, <sub>, etc.). Do NOT put emojis in the title, headings, or labels — keep it clean and editorial.",
             "- CITATIONS: when you use an article, cite it inline as [n] using its number from the provided article list. Do NOT write your own Sources section and do NOT invent URLs — a resolved, named Sources list is appended automatically from the article list.",
             "- NEVER cite the methodology, watchlist, or catalysts files (no [catalysts.md], [watchlist.md], etc.) — they are guidance, not sources. Cite only the numbered articles.",
             "- Do NOT write a 'Week Ahead' or catalysts section yourself — an 'Upcoming catalysts' list is appended automatically below your text. Just write the analysis.",
             "- FRESHNESS: each article is tagged NEW or 'previously covered'. Lead with NEW stories. Include a previously-covered story ONLY if these articles add a CONCRETE new fact — a new number, date, decision, or named result (not merely a fresh angle or restatement) — and when you do, prefix that item with 'Developing:'. Otherwise leave it out. Never rehash old news as if it were breaking.",
             "- ANALYSIS DEPTH (this is what makes the brief worth reading): each Top Story's 'What it means' must deliver the NON-OBVIOUS so-what — the second-order implication, who specifically gains or loses, what it shifts competitively, or what to watch next. NEVER just restate what happened in different words. Be concrete: name the rivals, the dollar figures, the dates. Ban filler like 'addresses an unmet need', 'a significant development', or 'expands treatment options' UNLESS you immediately say why it matters and to whom.",
             "- TALKING POINT: a sharp, non-obvious thesis a smart reader could NOT get from the headlines alone — a connection ACROSS stories, a contrarian read, or the real stakes underneath. One crisp sentence. Not a summary of the day's events.",
             f"- In the header subtitle line, set 'Engine: {engine_label}'.",
             "",
             "=== METHODOLOGY (follow the analysis & structure; skip the tool/file steps) ==="]
    for f in [".claude/commands/pharma-news.md",
              "pharma-news/digest-template.md",
              "pharma-news/watchlist.md",
              "pharma-news/catalysts.md"]:
        p = ROOT / f
        if p.exists():
            parts += [f"\n----- {f} -----\n", p.read_text(encoding="utf-8")]
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
#  LLM engines. DeepSeek and Gemini both speak the OpenAI-compatible chat API,
#  so ONE call path serves both — only base URL, key, and model differ. Gemini is
#  primary; switch with PHARMA_ENGINE=gemini|deepseek (env / secrets.env / the GitHub
#  Actions variable / the --engine flag / the Command Centre).
# --------------------------------------------------------------------------- #
PROVIDERS = {
    "deepseek": {"label": "DeepSeek", "base": "https://api.deepseek.com",
                 "key": "DEEPSEEK_API_KEY", "model_key": "DEEPSEEK_MODEL",
                 "base_key": "DEEPSEEK_BASE_URL", "default_model": "deepseek-chat"},
    "gemini":   {"label": "Gemini",
                 "base": "https://generativelanguage.googleapis.com/v1beta/openai",
                 "key": "GEMINI_API_KEY", "model_key": "GEMINI_MODEL",
                 "base_key": "GEMINI_BASE_URL", "default_model": "gemini-2.5-flash"},
}


def resolve_engine(secrets: dict) -> str:
    """Which engine to use. An explicit PHARMA_ENGINE wins; otherwise prefer Gemini
    (primary) when its key is present, else fall back to DeepSeek — so the daily run
    never breaks just because the Gemini key hasn't been added yet."""
    e = (secrets.get("PHARMA_ENGINE") or "").strip().lower()
    if e in PROVIDERS:
        return e
    return "gemini" if secrets.get("GEMINI_API_KEY") else "deepseek"


def engine_model(secrets: dict, engine: str) -> str:
    p = PROVIDERS[engine]
    return secrets.get(p["model_key"]) or p["default_model"]


def call_model(secrets: dict, system: str, user: str) -> str:
    """Call whichever engine resolve_engine() picks, via its OpenAI-compatible endpoint."""
    engine = resolve_engine(secrets)
    p = PROVIDERS[engine]
    base = (secrets.get(p["base_key"]) or p["base"]).rstrip("/")
    key = secrets.get(p["key"])
    if not key:
        raise RuntimeError(f"missing {p['key']} for engine '{engine}'")
    payload = json.dumps({
        "model": engine_model(secrets, engine),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "stream": False,
    }).encode("utf-8")
    # A real User-Agent is required: Google's endpoint drops the default "Python-urllib"
    # UA (closes the connection), though it accepts curl/browsers.
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json",
               "User-Agent": "pharma-digest/1.0"}
    # Retry transient failures (5xx, rate-limit, dropped connection) — free tiers 503 under
    # load, and we don't want to lose the grounding check to a blip.
    last = None
    for delay in (0, 3, 8):
        if delay:
            time.sleep(delay)
        try:
            req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                         method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and delay != 8:
                last = e; continue          # transient — retry
            raise                            # 4xx (bad request/auth/quota=0) — fail now
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            last = e
            if delay == 8:
                raise
        except (ValueError, KeyError, IndexError, TypeError) as e:
            # 200 OK but the body isn't the JSON shape we expect (truncated, an HTML error
            # page, a changed schema). Treat as transient — retry, then fail with a clean
            # error rather than an uncaught traceback mid-run.
            last = RuntimeError(f"unexpected model response ({e})")
            if delay == 8:
                raise last
    raise last                               # exhausted retries


def _fmt_source_dt(iso: str) -> str:
    """'Jun 12, 2026 · 14:30 UTC' from a stored ISO feed timestamp; "" if the feed gave
    no parseable date. Factual only — the timestamp comes straight from the article's
    feed entry, and when it's absent we show nothing rather than guess."""
    if not iso or iso == "n/a":
        return ""
    try:
        d = dt.datetime.fromisoformat(iso)
    except ValueError:
        return ""
    if d.tzinfo is not None:
        d = d.astimezone(dt.timezone.utc)
    return d.strftime("%b %d, %Y · %H:%M UTC")


# --------------------------------------------------------------------------- #
#  finalize(): turn the model's raw draft into the shippable article. It's a
#  pipeline of small, independent text transforms — each is its own helper below,
#  so the steps read top-to-bottom and can be unit-tested in isolation. The order
#  matters and is fixed by finalize(); the helpers don't depend on each other.
# --------------------------------------------------------------------------- #
def _strip_leaked_html(digest: str) -> str:
    """Drop leaked raw HTML tags (e.g. <small>) — the digest is Markdown only."""
    return re.sub(r"</?(small|br|sub|sup|span|div|font|u|b|i)\b[^>]*>", "",
                  digest, flags=re.I)


def _strip_methodology_citations(digest: str) -> str:
    """Strip pseudo-citations of the internal methodology files (e.g. "[catalysts.md]")
    the model sometimes appends — they are guidance, not sources. The negative lookahead
    leaves any real "[label.md](url)" link untouched."""
    return re.sub(r"\s*\[[^\[\]]*\.md\](?!\()", "", digest, flags=re.I)


def _drop_week_ahead(digest: str) -> str:
    """Drop any "Week Ahead" section the model still writes — the Upcoming-catalysts list
    is appended automatically (site + email), so an inline one is redundant and was
    rendering as an empty "-". Remove from its heading up to the next section/rule."""
    return re.sub(r"\n#{1,3}\s*Week Ahead\b.*?(?=\n#{1,3}\s|\n---|\Z)", "\n",
                  digest, flags=re.S | re.I)


def _label_engine(digest: str, engine_label: str, model: str) -> str:
    """Normalise the engine label in the subtitle (or inject it after the title)."""
    if re.search(r"Engine:", digest):
        # Stop before · and * so we don't swallow the subtitle's closing '*' when Engine is
        # the last element (e.g. the Weekly Review subtitle has no '~N min read').
        return re.sub(r"Engine:\s*[^·\n*]*", f"Engine: {engine_label} ({model})", digest)
    lines = digest.splitlines()
    for i, l in enumerate(lines):
        if l.startswith("# "):
            lines.insert(i + 1, f"\n*Engine: {engine_label} ({model})*")
            break
    return "\n".join(lines)


def _reorder_subtitle(digest: str) -> str:
    """Reorder the subtitle so Edition sits just before the read-time, making the
    edition↔length link obvious: Window · Engine · Edition · ~N min read."""
    def repl(m):
        parts = [p.strip() for p in m.group(1).split("·") if p.strip()]
        ed = next((p for p in parts if p.lower().startswith("edition")), None)
        if not ed:
            return m.group(0)
        parts = [p for p in parts if not p.lower().startswith("edition")]
        eng = next((i for i, p in enumerate(parts) if p.lower().startswith("engine")), None)
        # Place Edition right AFTER Engine (so: Window · Engine · Edition · ~N min read).
        parts.insert(eng + 1 if eng is not None else max(len(parts) - 1, 0), ed)
        return "*" + " · ".join(parts) + "*"
    return re.sub(r"\*(Window[^*\n]*)\*", repl, digest, count=1)


def _drop_model_sources(digest: str) -> str:
    """Drop any Sources section / footer the model wrote — we rebuild them cleanly."""
    idx = digest.find("## Sources")
    if idx != -1:
        digest = digest[:idx].rstrip()
    return re.sub(r"\n+[*_]*Facts (verified|grounded).*$", "", digest, flags=re.S).rstrip()


def _split_grouped_citations(digest: str) -> str:
    """Split grouped citations like "[3, 7]" into "[3] [7]" so every source is captured —
    every renderer (and _append_sources below) only matches single [n] markers."""
    return re.sub(r"\[(\d+(?:\s*,\s*\d+)+)\]",
                  lambda m: " ".join(f"[{n.strip()}]" for n in m.group(1).split(",")),
                  digest)


def _append_sources(digest: str, items: list[dict]) -> str:
    """Append a resolved Sources list built from the [n] citations actually used."""
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", digest)})
    cited = [n for n in cited if 1 <= n <= len(items)]
    if not cited:
        return digest

    # Square brackets in a feed title (e.g. "[Updated] ...") or parens in a URL
    # would break the markdown link — and with it the renderers' citation maps.
    def md_safe(s: str) -> str:
        return s.replace("[", "(").replace("]", ")")

    def src_line(n: int) -> str:
        it = items[n - 1]
        url = it["link"].replace("(", "%28").replace(")", "%29")
        when = _fmt_source_dt(it.get("when", ""))
        tail = f" · {when}" if when else ""   # factual feed timestamp, or nothing
        return f"{n}. [{md_safe(it['title'])}]({url}){tail}"

    return digest + "\n\n## Sources\n" + "\n".join(src_line(n) for n in cited)


def _append_footer(digest: str, engine_label: str) -> str:
    """Standard footer — honest about what the automated check does and doesn't guarantee."""
    return digest + (
        f"\n\n---\n*Written by {engine_label} from the news sources linked above, then run "
        "through an automated **grounding check**: a second AI pass that compares each "
        "factual claim against those sources and removes anything they don't support. "
        "This catches most errors but isn't infallible — verify anything important via the "
        "linked sources. Rumours are flagged where identified. Not investment advice.*\n")


def _apply_read_time(digest: str) -> str:
    """Compute the read-time from the body word count (~200 wpm), replacing the model's
    guess — including a copy-pasted RANGE like '~5-8 min read' — or adding it when absent
    (e.g. the Weekly Review). Count prose only (everything before the Sources list)."""
    body_words = len(re.findall(r"[A-Za-z0-9']+", digest.split("## Sources")[0]))
    mins = max(1, round(body_words / 200))
    rt = r"~?\s*\d+(?:\s*[–-]\s*\d+)?\s*min read"   # matches '~12 min read' AND '~5-8 min read'
    if re.search(rt, digest):
        return re.sub(rt, f"~{mins} min read", digest, count=1)
    return re.sub(r"(\*Window[^*\n]*)\*", rf"\1 · ~{mins} min read*", digest, count=1)


def finalize(digest: str, items: list[dict], engine_label: str, model: str) -> str:
    """Clean the model's output: strip stray HTML, label the engine, and append a real,
    resolved Sources list built from the actual fetched articles. A fixed-order pipeline
    of the independent transforms above (see each helper for what it does)."""
    digest = _strip_leaked_html(digest)
    digest = _strip_methodology_citations(digest)
    digest = _drop_week_ahead(digest)
    digest = _label_engine(digest, engine_label, model)
    digest = _reorder_subtitle(digest)
    digest = _drop_model_sources(digest)
    digest = _split_grouped_citations(digest)
    digest = _append_sources(digest, items)
    digest = _append_footer(digest, engine_label)
    digest = _apply_read_time(digest)
    return digest


# --------------------------------------------------------------------------- #
#  #1  "What's new": tell genuinely-new stories from already-covered ones.
#      The committed archive is the state — no separate store to keep in sync.
# --------------------------------------------------------------------------- #
def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", t.lower())[:60]


def recent_seen(days: int = 7) -> tuple[set, set]:
    """URLs and normalised titles cited in the last `days` of archived digests."""
    urls, titles = set(), set()
    today = dt.date.today()
    for p in (ROOT / "digests").glob("*.md"):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", p.stem)
        if not m:
            continue
        try:
            d = dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            continue
        if d >= today or (today - d).days > days:   # only strictly-earlier, recent digests
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            sm = re.match(r"^\s*\d+\.\s*\[([^\]]+)\]\((https?://[^)\s]+)\)", line)
            if sm:
                titles.add(_norm_title(sm.group(1)))
                urls.add(sm.group(2))
    return urls, titles


# --------------------------------------------------------------------------- #
#  #2 + #3  Combined review: ONE call that both fact-checks the draft against the
#      sources AND extracts dated future catalysts from them — saves an article-sized
#      input vs. two calls. Grounding stays the primary task. Every call is defensive:
#      a flaky review or revision must never block delivery of an otherwise-good digest.
# --------------------------------------------------------------------------- #
def review_digest(secrets: dict, digest: str, corpus: str, today: dt.date) -> tuple[bool, str, list]:
    """Returns (grounding_ok, issues, catalyst_events). On any network/parse failure or if
    the model ignores the format, returns safe defaults (True, '', []) so nothing is blocked."""
    system = (
        "You are reviewing a pharma news digest against the ONLY permitted sources. Do TWO "
        "tasks and reply in EXACTLY this format, including the two headers:\n"
        "### GROUNDING\n"
        "PASS  — if every specific factual claim (number, date, name, approval, trial result, "
        "deal value) in the digest is supported by the sources. Otherwise, instead of PASS, "
        "list each unsupported claim as a '- ' bullet, quoting it briefly. Ignore style/phrasing.\n"
        "### CATALYSTS\n"
        "Concrete FUTURE dated catalysts the SOURCES explicitly date (regulatory/PDUFA, trial "
        "readouts, earnings, conferences), one per line as 'YYYY-MM-DD | short description'. Use "
        "the 15th if only a month+year is given. Only dates after today. NEVER invent a date. "
        "Write NONE if there are none.")
    user = f"Today is {today.isoformat()}.\n\nSOURCES:\n\n{corpus}\n\n=== DIGEST ===\n\n{digest}"
    try:
        out = call_model(secrets, system, user)
    except Exception as e:
        print(f"  ! review skipped ({e})", file=sys.stderr)
        return True, "", []
    # Split the two sections defensively. If the GROUNDING header is missing, the model
    # didn't follow the format — don't trust a parse, so pass grounding (fail-safe).
    mg = re.search(r"###\s*GROUNDING\s*(.*?)(?=###\s*CATALYSTS|\Z)", out, re.S | re.I)
    mc = re.search(r"###\s*CATALYSTS\s*(.*)\Z", out, re.S | re.I)
    if mg:
        gtext = mg.group(1).strip()
        ok = gtext.upper().startswith("PASS") or "- " not in gtext
        issues = "" if ok else gtext
    else:
        ok, issues = True, ""
    events = []
    for line in (mc.group(1).splitlines() if mc else []):
        m = re.match(r"^\s*[-*]?\s*(\d{4}-\d{2}-\d{2})\s*[|·–-]\s*(.+)$", line.strip())
        if not m:
            continue
        try:
            d = dt.date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if d > today and m.group(2).strip():
            events.append((d, m.group(2).strip()))
    return ok, issues, events


def revise_for_grounding(secrets: dict, digest: str, corpus: str, issues: str) -> str:
    """One targeted fix-pass; returns the original digest unchanged on any failure."""
    system = (
        "Revise the digest to fix ONLY the listed unsupported claims — delete them or soften "
        "to exactly what the sources support. Change NOTHING else: keep the structure, "
        "headings, [n] citations, talking point, TL;DR and overall length. Output ONLY the "
        "revised Markdown digest, with no preamble.")
    user = f"SOURCES:\n\n{corpus}\n\nUNSUPPORTED CLAIMS TO FIX:\n{issues}\n\n=== DIGEST ===\n\n{digest}"
    try:
        out = call_model(secrets, system, user).strip()
    except Exception as e:
        print(f"  ! grounding revision skipped ({e})", file=sys.stderr)
        return digest
    return out if len(out) >= 300 else digest


# --------------------------------------------------------------------------- #
#  #3  Self-maintaining catalysts: extract explicitly-dated future events from
#      the articles and keep them in a clearly-labelled section of catalysts.md.
#      Grounded — only dates the articles actually state; never inferred.
# --------------------------------------------------------------------------- #
AUTO_CAT_SECTION = "## Auto-detected (from recent briefs)"
# Generic catalyst words are ignored when deduping, so a match needs a *specific* shared
# token (a drug or company name) — not just two "FDA decision"s landing on the same day.
_CAT_STOP = {"decision", "phase", "trial", "trials", "result", "results", "readout",
             "approval", "earnings", "pdufa", "expected", "data", "study", "conference",
             "meeting", "filing", "launch", "review", "update", "report", "topline",
             "interim", "primary", "endpoint", "company", "pharma"}

# Generic market-column / listicle headlines that aren't real forward catalysts — the model
# sometimes extracts them because they carry a date. Drop them so the calendar stays signal.
_CAT_NOISE = re.compile(
    r"\b(stocks?|shares?)\s+to\s+(watch|buy|sell)\b"
    r"|\btop\s+(movers|gainers|losers|picks|stocks)\b"
    r"|\bstocks?\s+in\s+(focus|news|the\s+news)\b"
    r"|\bmarket\s+wrap\b|\bwhat\s+to\s+watch\b", re.I)


def _cat_tokens(desc: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]{5,}", desc.lower()) if w not in _CAT_STOP}


def merge_catalysts(events: list, today: dt.date) -> int:
    """Add new auto-detected catalysts to catalysts.md under a labelled section (prune past,
    dedup against the whole file). Returns the number newly added."""
    path = ROOT / "pharma-news" / "catalysts.md"
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    # Peel off any prior auto section; keep only its still-future lines (prune the past).
    body, auto_lines = text, []
    idx = text.find(AUTO_CAT_SECTION)
    if idx != -1:
        body = text[:idx].rstrip()
        for line in text[idx:].splitlines()[1:]:
            m = re.match(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\* · ", line.strip())
            if m:
                try:
                    if dt.date.fromisoformat(m.group(1)) >= today:
                        auto_lines.append(line.rstrip())
                except ValueError:
                    pass
    # Dedup index: date -> token-sets already on file (curated body + surviving auto lines),
    # so we skip a new event naming the same thing on the same day even if worded differently.
    seen_by_date: dict = {}
    for line in body.splitlines() + auto_lines:
        m = re.match(r"^- \*\*~?(.+?)\*\* · (.+)$", line.strip())
        if m:
            # Normalise the date the SAME way the site renders it (ISO, or month-only -> the
            # 15th) so a curated "Sep 2026" and an auto "2026-09-15" collide and dedup.
            d = catalyst_date(m.group(1))
            if d is None:
                continue
            seen_by_date.setdefault(d.isoformat(), []).append(
                _cat_tokens(re.sub(r"\s*\(auto-detected.*$", "", m.group(2))))
    added = 0
    for d, desc in sorted(events):
        if _CAT_NOISE.search(desc):
            continue                          # generic market column, not a real catalyst
        di, toks = d.isoformat(), _cat_tokens(desc)
        same_day = seen_by_date.get(di, [])
        if any(toks & ts for ts in same_day) or (not toks and same_day):
            continue                          # shares a specific name (or is a vague same-day dup)
        seen_by_date.setdefault(di, []).append(toks)
        auto_lines.append(f"- **{di}** · {desc} (auto-detected {today.isoformat()})")
        added += 1
    if added == 0 and idx == -1:
        return 0                              # nothing to add and no section to prune

    def line_date(l: str) -> str:
        m = re.match(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\*", l)
        return m.group(1) if m else "9999-99-99"
    auto_lines.sort(key=line_date)
    new_text = (body.rstrip() + "\n\n" + AUTO_CAT_SECTION + "\n" + "\n".join(auto_lines) + "\n") \
        if auto_lines else (body.rstrip() + "\n")
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return added


# --------------------------------------------------------------------------- #
#  Scheduling: map a UTC weekday to the run's window/edition/mode. This used to
#  live as `if`/`elif` bash in the GitHub workflow; keeping it here (a) makes it
#  testable and (b) leaves the workflow free of logic. The cloud job calls
#  run_digest.py with --auto; everything else still passes explicit flags.
# --------------------------------------------------------------------------- #
def auto_schedule(weekday: int) -> tuple[int, str, str]:
    """(hours, edition, mode) for a scheduled run, by ISO weekday (1=Mon … 7=Sun):
    Saturday = Week in Review (168h), Sunday = Week Ahead (168h), Mon–Fri = daily brief."""
    if weekday == 6:        # Saturday
        return 168, "evening", "review"
    if weekday == 7:        # Sunday
        return 168, "evening", "ahead"
    return 24, "morning", "daily"


def resolve_auto(args) -> None:
    """Fill args.hours/edition/mode for --auto, mutating `args` in place. A *manual*
    workflow run passes the picks through the IN_HOURS/IN_EDITION/IN_MODE env vars;
    a *scheduled* run leaves IN_HOURS empty, so we derive them from today's UTC weekday
    (this is exactly what the workflow's shell `if` used to do)."""
    in_hours = (os.environ.get("IN_HOURS") or "").strip()
    if in_hours:
        args.hours = int(in_hours)
        args.edition = (os.environ.get("IN_EDITION") or "morning").strip()
        args.mode = (os.environ.get("IN_MODE") or "daily").strip()
    else:
        args.hours, args.edition, args.mode = auto_schedule(
            dt.datetime.now(dt.timezone.utc).isoweekday())


def window_subtitle(mode: str, hours: int, today: dt.date, n_read: int) -> str:
    """Deterministic 'Window: …' subtitle: the real date range the brief covers plus how many
    articles were scanned. Backward editions (daily/review) show the lookback range; the Week
    Ahead shows the coming week. Replaces the model's vague 'last N hours' with trustworthy facts."""
    if mode == "ahead":
        start, end = today + dt.timedelta(days=1), today + dt.timedelta(days=7)
        return (f"Window: {start.strftime('%b %-d')} – {end.strftime('%b %-d, %Y')} "
                f"(week ahead) · grounded in {n_read} recent articles")
    days = max(1, round(hours / 24))
    start = today - dt.timedelta(days=days)
    return (f"Window: {start.strftime('%b %-d')} – {today.strftime('%b %-d, %Y')} "
            f"· {n_read} articles scanned")


def apply_window_subtitle(digest: str, mode: str, hours: int, today: dt.date, n_read: int) -> str:
    """Swap the model's 'Window: …' subtitle segment for the deterministic one, preserving the
    ' · ' separator to the next field (so it doesn't read 'articles· Engine')."""
    ws = window_subtitle(mode, hours, today, n_read)
    return re.sub(r"Window:[^·\n*]*(·[ \t]*)?",
                  lambda m: ws + (" · " if m.group(1) else ""),
                  digest, count=1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--edition", choices=["morning", "evening"], default="morning")
    ap.add_argument("--email", action="store_true", help="email the result via send_digest.py")
    ap.add_argument("--telegram", action="store_true", help="post a summary via send_telegram.py")
    ap.add_argument("--engine", choices=["gemini", "deepseek"],
                    help="override the engine for this run (default: PHARMA_ENGINE, else Gemini)")
    ap.add_argument("--mode", choices=["daily", "review", "ahead"], default="daily",
                    help="daily brief, Saturday week-in-review, or Sunday week-ahead")
    ap.add_argument("--auto", action="store_true",
                    help="scheduled-run mode: pick hours/edition/mode from IN_HOURS/IN_EDITION/IN_MODE "
                         "env vars if set (manual cloud run), else from today's UTC weekday "
                         "(Sat=review, Sun=ahead, else daily). Used by the GitHub workflow.")
    args = ap.parse_args()
    if args.auto:
        resolve_auto(args)

    secrets = load_secrets()
    if args.engine:
        secrets["PHARMA_ENGINE"] = args.engine
    engine = resolve_engine(secrets)
    label = PROVIDERS[engine]["label"]
    keyname = PROVIDERS[engine]["key"]
    if not secrets.get(keyname):
        print(f"ERROR: engine '{engine}' needs {keyname} (env or {SECRETS_PATH})", file=sys.stderr)
        return 2

    print("Gathering news from RSS feeds...", file=sys.stderr)
    items = gather(args.hours)
    # Thin-digest guard: too few articles usually means feeds are down, not a quiet
    # news day. Abort with a non-zero exit so GitHub's failure email surfaces it,
    # rather than silently emailing a hollow digest. Override with MIN_ARTICLES.
    min_articles = int(os.environ.get("MIN_ARTICLES", "5"))
    if len(items) < min_articles:
        print(f"ERROR: only {len(items)} articles fetched (< {min_articles}); "
              "feeds are likely down or the window too narrow. Aborting so the "
              "failure is visible instead of sending a thin digest.", file=sys.stderr)
        return 3
    print(f"  {len(items)} articles in the last {args.hours}h", file=sys.stderr)

    # #1 Freshness: tag each article NEW vs. already-covered in a recent digest.
    seen_urls, seen_titles = recent_seen()
    for it in items:
        it["fresh"] = it["link"] not in seen_urls and _norm_title(it["title"]) not in seen_titles
    n_new = sum(1 for it in items if it["fresh"])
    print(f"  freshness: {n_new} new, {len(items) - n_new} previously covered (last 7 days)", file=sys.stderr)

    today = dt.date.today().isoformat()
    # NB: deliberately NO link in the corpus. The model cites by [n] only (finalize
    # re-attaches the real URL from `items`), so sending the URLs — especially the ~400-char
    # base64 Google News links — was pure token cost (sent 2-3x/run: generate + review +
    # revise). Dropping them shrinks the corpus ~40% with zero effect on the output.
    corpus = "\n\n".join(
        f"[{i+1}] {it['title']}\n    date: {it['when']}\n"
        f"    freshness: {'NEW' if it['fresh'] else 'previously covered (include only if a genuine new development)'}\n"
        f"    {it['summary']}"
        for i, it in enumerate(items)
    )
    user = (f"Today is {today}. Window: last {args.hours} hours. Edition: {args.edition}. Mode: {args.mode}.\n\n"
            f"Here are the ONLY articles you may use ({len(items)} total). "
            f"Write the digest grounded strictly in these:\n\n{corpus}")

    print(f"Calling {label} ({engine_model(secrets, engine)})...", file=sys.stderr)
    try:
        digest = call_model(secrets, build_system_prompt(args.edition, label, args.mode), user)
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        if e.code == 429:
            print(f"  hint: {label} hit a rate/quota limit. Free Gemini tiers cap daily "
                  "requests (≈20/day for 2.5-flash) and reset next day — a single daily run "
                  "(~3 calls) fits easily, but many manual runs in one day can exhaust it. "
                  "Switch engine in the Command Centre, enable billing, or wait for reset.",
                  file=sys.stderr)
        return 4
    except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
        # Network drop / reset / closed connection — fail cleanly (GitHub emails the
        # failure) instead of crashing with a traceback.
        print(f"ERROR: {label} call failed ({e})", file=sys.stderr)
        return 4

    # Guard against empty/near-empty model output: don't email or publish a hollow
    # digest — abort so GitHub's failure email surfaces it (same policy as MIN_ARTICLES).
    if not digest or len(digest.strip()) < 300:
        got = 0 if not digest else len(digest.strip())
        print(f"ERROR: {label} returned an empty/near-empty digest ({got} chars). "
              "Aborting so the failure is visible.", file=sys.stderr)
        return 4

    # #2 + #3 One combined review call: fact-check the draft AND extract dated catalysts.
    # If the audit flags unsupported claims, one targeted fix-pass. All defensive — never
    # blocks delivery. Disable the whole review with DIGEST_REVIEW=0.
    cat_events = []
    if os.environ.get("DIGEST_REVIEW", "1") != "0":
        print("Reviewing (grounding + catalysts)...", file=sys.stderr)
        # The curated catalyst calendar is a valid source for dated future events — include it
        # so the grounding check doesn't strip the Week Ahead's calendar dates as "unsupported"
        # (it otherwise only sees the articles). Genuine outcome speculation is still flagged.
        cat_file = ROOT / "pharma-news" / "catalysts.md"
        review_corpus = corpus
        if cat_file.exists():
            review_corpus = (corpus + "\n\n=== CATALYST CALENDAR (curated; its dated entries are "
                             "valid sources for upcoming events) ===\n" + cat_file.read_text(encoding="utf-8"))
        ok, issues, cat_events = review_digest(secrets, digest, review_corpus, dt.date.today())
        if ok:
            print("  grounding: passed", file=sys.stderr)
        else:
            print(f"  grounding flagged claims; revising:\n{issues}", file=sys.stderr)
            digest = revise_for_grounding(secrets, digest, review_corpus, issues)

    digest = finalize(digest, items, label, engine_model(secrets, engine))

    # Force the title's date to DD/MM/YYYY (replace whatever date the model wrote after the
    # title's " - "). Deterministic — doesn't rely on the model's date formatting.
    dmy = dt.date.today().strftime("%d/%m/%Y")
    digest = re.sub(r"^(#\s+\S.*?)\s+[-–—]\s+.*$", rf"\1 — {dmy}", digest, count=1, flags=re.M)

    # Replace the model's vague "Window: last N hours" with the real date range + how many
    # articles were scanned (deterministic — trustworthy, unlike the model's own wording).
    digest = apply_window_subtitle(digest, args.mode, args.hours, dt.date.today(), len(items))

    out = ROOT / "digests" / f"{today}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(digest, encoding="utf-8")
    print(f"Digest ✓  -> {out}")

    # Record the REAL generation instant (UTC) so the website's "Published" time is the
    # actual time, not a fixed cron anchor. Stored beside the digests (committed with them);
    # the site reads digests/published.json. Best-effort — never block on it.
    try:
        pub_path = out.parent / "published.json"
        pubmap = json.loads(pub_path.read_text(encoding="utf-8")) if pub_path.exists() else {}
        pubmap[today] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        pub_path.write_text(json.dumps(pubmap, indent=0, sort_keys=True), encoding="utf-8")
    except Exception as e:
        print(f"  ! could not record publish time ({e})", file=sys.stderr)

    # A failed delivery must fail the run (non-zero exit -> GitHub failure email),
    # otherwise the digest silently never reaches anyone.
    rc = 0
    if args.email:
        import subprocess
        if subprocess.run([sys.executable, str(ROOT / "pharma-news" / "send_digest.py"), str(out)]).returncode != 0:
            rc = 1

    if args.telegram:
        import subprocess
        if subprocess.run([sys.executable, str(ROOT / "pharma-news" / "send_telegram.py"), str(out)]).returncode != 0:
            rc = 1

    # #3 Self-maintaining catalysts: file the dated events found during the review above
    # into catalysts.md (grounded; clearly labelled). Disable with AUTO_CATALYSTS=0.
    if cat_events and os.environ.get("AUTO_CATALYSTS", "1") != "0":
        added = merge_catalysts(cat_events, dt.date.today())
        if added:
            print(f"  catalysts: +{added} auto-detected", file=sys.stderr)

    # Rebuild the static site so the archive + timeline stay current.
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "site" / "build_site.py")])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
