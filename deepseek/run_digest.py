#!/usr/bin/env python3
"""
Standalone Pharma Digest generator running on the DeepSeek API (no Claude).

Per-token, subscription-free. Pulls real pharma news from RSS feeds, then asks
DeepSeek to write the digest using THIS PROJECT'S OWN METHODOLOGY (it reads the
same command file, watchlist, and template Claude uses — one source of truth).

Anti-hallucination by design: DeepSeek cannot browse, so it is instructed to use
ONLY the supplied articles and never add facts from memory.

Usage:
    python3 deepseek/run_digest.py [--hours 24] [--edition morning|evening] [--email]

Secrets (env var or ~/.config/pharma-news/secrets.env):
    DEEPSEEK_API_KEY   (required)
    DEEPSEEK_MODEL     (optional, default "deepseek-chat")
    DEEPSEEK_BASE_URL  (optional, default "https://api.deepseek.com")

Stdlib only — no pip installs.
"""

import os
import sys
import json
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
    for k in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"):
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
            return r.read()
    except (OSError, http.client.HTTPException, ValueError) as e:
        # OSError covers URLError/timeouts/resets; HTTPException covers errors
        # raised mid-read (IncompleteRead etc.) — one bad feed must not kill the run.
        print(f"  ! skip {url}: {e}", file=sys.stderr)
        return None


def parse_feed(xml_bytes: bytes, since: dt.datetime) -> list[dict]:
    items = []
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
        import re
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


def build_system_prompt(edition: str) -> str:
    """Reuse the project's tuned methodology as the system prompt."""
    parts = ["You are generating the Pharma Digest.",
             "",
             "IMPORTANT ADAPTER NOTES (you are running on DeepSeek, not Claude Code):",
             "- You CANNOT browse the web. Use ONLY the news articles provided in the user message.",
             "- Ignore any instructions in the methodology about running web searches or saving files — those are handled outside you.",
             "- ANTI-HALLUCINATION: every fact, number, date, name, and deal value MUST come from the provided articles. If it is not in the articles, do not state it. Never use facts from your training data. Label rumours as rumours. If the day's articles are thin, say so honestly rather than inventing substance.",
             f"- Edition: {edition} (morning = tight 2-3 min; evening = deeper 5-8 min with a Deep Dive).",
             "- Output ONLY the finished digest in Markdown. No preamble.",
             "- FORMATTING: Markdown only. NEVER use raw HTML tags (no <small>, <br>, <sub>, etc.).",
             "- CITATIONS: when you use an article, cite it inline as [n] using its number from the provided article list. Do NOT write your own Sources section and do NOT invent URLs — a resolved, named Sources list is appended automatically from the article list.",
             "- NEVER cite the methodology, watchlist, or catalysts files (no [catalysts.md], [watchlist.md], etc.) — they are guidance, not sources. The upcoming-catalysts section is added automatically; just write the analysis. Cite only the numbered articles.",
             "- In the header subtitle line, set 'Engine: DeepSeek'.",
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


def call_deepseek(secrets: dict, system: str, user: str) -> str:
    base = secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
    model = secrets.get("DEEPSEEK_MODEL", "deepseek-chat")
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/chat/completions", data=payload, method="POST",
        headers={"Authorization": f"Bearer {secrets['DEEPSEEK_API_KEY']}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


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


def finalize(digest: str, items: list[dict], model: str) -> str:
    """Clean DeepSeek's output: strip stray HTML, label the engine, and append a
    real, resolved Sources list built from the actual fetched articles."""
    import re
    # 1. Strip leaked raw HTML tags (e.g. <small>) — Markdown only.
    digest = re.sub(r"</?(small|br|sub|sup|span|div|font|u|b|i)\b[^>]*>", "",
                    digest, flags=re.I)
    # 1b. Strip pseudo-citations of the internal methodology files (e.g. "[catalysts.md]")
    # the model sometimes appends — they are guidance, not sources. The negative lookahead
    # leaves any real "[label.md](url)" link untouched.
    digest = re.sub(r"\s*\[[^\[\]]*\.md\](?!\()", "", digest, flags=re.I)
    # 2. Normalise the engine label in the subtitle (or inject it after the title).
    if re.search(r"Engine:", digest):
        digest = re.sub(r"Engine:\s*[^·\n]*", f"Engine: DeepSeek ({model}) ", digest)
    else:
        lines = digest.splitlines()
        for i, l in enumerate(lines):
            if l.startswith("# "):
                lines.insert(i + 1, f"\n*Engine: DeepSeek ({model})*")
                break
        digest = "\n".join(lines)
    # 3. Drop any Sources section / footer the model wrote — we rebuild them cleanly.
    idx = digest.find("## Sources")
    if idx != -1:
        digest = digest[:idx].rstrip()
    digest = re.sub(r"\n+[*_]*Facts (verified|grounded).*$", "", digest, flags=re.S).rstrip()
    # 3b. Split grouped citations like "[3, 7]" into "[3] [7]" so every source is
    # captured — every renderer (and step 4 below) only matches single [n] markers.
    digest = re.sub(r"\[(\d+(?:\s*,\s*\d+)+)\]",
                    lambda m: " ".join(f"[{n.strip()}]" for n in m.group(1).split(",")),
                    digest)
    # 4. Build a resolved Sources list from the [n] citations actually used.
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", digest)})
    cited = [n for n in cited if 1 <= n <= len(items)]
    if cited:
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
        digest += "\n\n## Sources\n" + "\n".join(src_line(n) for n in cited)
    # 5. Standard footer.
    digest += ("\n\n---\n*Generated by DeepSeek, grounded strictly in the fetched "
               "articles above. Rumours/unconfirmed items are labelled.*\n")
    return digest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--edition", choices=["morning", "evening"], default="morning")
    ap.add_argument("--email", action="store_true", help="email the result via send_digest.py")
    ap.add_argument("--telegram", action="store_true", help="post a summary via send_telegram.py")
    args = ap.parse_args()

    secrets = load_secrets()
    if not secrets.get("DEEPSEEK_API_KEY"):
        print(f"ERROR: set DEEPSEEK_API_KEY (env or {SECRETS_PATH})", file=sys.stderr)
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

    today = dt.date.today().isoformat()
    corpus = "\n\n".join(
        f"[{i+1}] {it['title']}\n    date: {it['when']}\n    link: {it['link']}\n    {it['summary']}"
        for i, it in enumerate(items)
    )
    user = (f"Today is {today}. Window: last {args.hours} hours. Edition: {args.edition}.\n\n"
            f"Here are the ONLY articles you may use ({len(items)} total). "
            f"Write the digest grounded strictly in these:\n\n{corpus}")

    print("Calling DeepSeek...", file=sys.stderr)
    try:
        digest = call_deepseek(secrets, build_system_prompt(args.edition), user)
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code}: {e.read().decode('utf-8','replace')}", file=sys.stderr)
        return 4

    # Guard against empty/near-empty model output: don't email or publish a hollow
    # digest — abort so GitHub's failure email surfaces it (same policy as MIN_ARTICLES).
    if not digest or len(digest.strip()) < 300:
        got = 0 if not digest else len(digest.strip())
        print(f"ERROR: DeepSeek returned an empty/near-empty digest ({got} chars). "
              "Aborting so the failure is visible.", file=sys.stderr)
        return 4

    digest = finalize(digest, items, secrets.get("DEEPSEEK_MODEL", "deepseek-chat"))

    out = ROOT / "digests" / f"{today}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(digest, encoding="utf-8")
    print(f"Digest ✓  -> {out}")

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

    # Rebuild the static site so the archive + timeline stay current.
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "site" / "build_site.py")])
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
