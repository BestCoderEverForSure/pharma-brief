#!/usr/bin/env python3
"""
Build a static, print-magazine-style website from the saved digests.

- Renders every digests/*.md into a styled HTML article.
- Builds an editorial archive index, a catalyst timeline, and a markets strip.

Output: site/public/  (open index.html in a browser; or push to GitHub Pages).
Stdlib only — no pip installs.

Usage:  python3 site/build_site.py
"""

import re
import os
import sys
import json
import html
import datetime as dt
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Citation/markets/catalyst data logic is shared with the email renderer so the two
# can't drift apart — see pharma_render.py.
from pharma_render import (renumber_sources, parse_srcmap, parse_catalysts,
                           upcoming_catalysts, fetch_market, select_tickers, brief_market_days,
                           strip_md_pseudo_citations, tighten_link_spaces)
DIGESTS = ROOT / "digests"
CATALYSTS = ROOT / "pharma-news" / "catalysts.md"
WATCHLIST = ROOT / "pharma-news" / "watchlist.md"
OUT = ROOT / "site" / "public"

SOURCES = [
    ("Endpoints", "https://endpoints.news"),
    ("STAT", "https://www.statnews.com/category/pharma/"),
    ("Fierce Pharma", "https://www.fiercepharma.com"),
    ("BioPharma Dive", "https://www.biopharmadive.com"),
    ("Labiotech", "https://www.labiotech.eu"),
    ("FDA", "https://www.fda.gov/news-events/fda-newsroom"),
    ("EMA", "https://www.ema.europa.eu/en/news"),
]

# ----------------------------------------------------------------------------- #
#  Markdown -> HTML (editorial subset)
# ----------------------------------------------------------------------------- #
_LEAD_EMOJI = re.compile(r"^[\U0001F000-\U0001FAFF☀-➿←-⇿⬀-⯿ℹ️⃣]+\s*")


def strip_lead(s: str) -> str:
    return _LEAD_EMOJI.sub("", s)


def _visible(t: str) -> str:
    """Heading text without markdown link syntax / {major} / emphasis marks."""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"\s*\{major\}\s*$", "", t)
    return re.sub(r"[*`]", "", t).strip()


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _visible(t).lower()).strip("-")[:60] or "sec"


_SRCMAP: dict = {}


def _mk_link(m):
    label, url = m.group(1), m.group(2)
    # Most links come via the Google News aggregator (can redirect / be region-blocked).
    # Rather than flag the ~95% majority, positively mark the minority of DIRECT publisher
    # links with a ✓ — a low-noise "this opens reliably" cue.
    direct = url.startswith(("http://", "https://")) and "news.google.com" not in url
    cls = "src direct" if direct else "src"
    title = ' title="Direct link to the publisher"' if direct else ""
    return f'<a href="{url}" target="_blank" rel="noopener" class="{cls}"{title}>{label}</a>'


def md_inline(text: str) -> str:
    text = html.escape(text)
    text = tighten_link_spaces(strip_md_pseudo_citations(text))   # shared pre-cleanups
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _mk_link, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    if _SRCMAP:
        # html.escape the URL: it comes from the Sources list (a feed link), not from the
        # already-escaped body text, so a stray quote could otherwise break out of href="".
        text = re.sub(r"\[(\d+)\]", lambda m: (
            f'<a class="cite" href="{html.escape(_SRCMAP[m.group(1)])}" target="_blank" rel="noopener">[{m.group(1)}]</a>'
            if m.group(1) in _SRCMAP else m.group(0)), text)
    return text


def md_to_html(md: str) -> str:
    out, items, in_quote, h3n = [], [], False, 0

    def flush_list():
        nonlocal items
        if not items:
            return
        pts = []
        for it in items:
            m = re.match(r"^\*\*(.+?)\*\*\s*[—–·:-]*\s*(.*)$", it)
            if m:
                head, body = md_inline(m.group(1)), md_inline(m.group(2).strip())
                pts.append(f'<div class="point"><div class="point-h">{head}</div>'
                           + (f'<div class="point-b">{body}</div>' if body else "") + "</div>")
            else:
                pts.append(f'<div class="point"><div class="point-b">{md_inline(it)}</div></div>')
        out.append('<div class="points">' + "".join(pts) + "</div>")
        items = []

    def close_quote():
        nonlocal in_quote
        if in_quote:
            out.append("</div>"); in_quote = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_list(); close_quote(); continue
        if line.startswith("### "):
            flush_list(); close_quote(); h3n += 1
            ht, cls, tag = strip_lead(line[4:]), "", ""
            if ht.rstrip().endswith("{major}"):
                cls = ' class="major"'; tag = '<div class="major-tag">Major story</div>'
                ht = re.sub(r"\s*\{major\}\s*$", "", ht)
            out.append(f'{tag}<h3 id="s{h3n}"{cls}>{md_inline(ht)}</h3>')
        elif line.startswith("## "):
            flush_list(); close_quote()
            h2t = strip_lead(line[3:])
            out.append(f'<h2 id="{_slug(h2t)}">{md_inline(h2t)}</h2>')
        elif line.startswith("# "):
            flush_list(); close_quote(); out.append(f"<h1>{md_inline(strip_lead(line[2:]))}</h1>")
        elif line.strip() in ("---", "***", "___"):
            flush_list(); close_quote(); out.append("<hr>")
        elif line.startswith("> "):
            flush_list()
            if not in_quote:
                out.append('<div class="lede">'); in_quote = True
            out.append(f"<p>{md_inline(strip_lead(line[2:]))}</p>")
        elif re.match(r"^[-*] ", line):
            close_quote(); items.append(line[2:])
        else:
            flush_list(); close_quote()
            s = line.strip()
            if s.startswith("*") and s.endswith("*") and not s.startswith("**"):
                out.append(f'<p class="meta">{md_inline(line)}</p>')
            else:
                out.append(f"<p>{md_inline(line)}</p>")
    flush_list(); close_quote()
    return "\n".join(out)


def link_headings(md: str) -> str:
    """Turn each Top Story headline into a link to its cited source.
    Uses the inline [n] citation + the numbered Sources list (DeepSeek), or leaves
    headings already written as markdown links (Claude) untouched."""
    lines = md.splitlines()
    smap = {}
    for l in lines:
        m = re.match(r"^\s*(\d+)\.\s*\[[^\]]+\]\((https?://[^)\s]+)\)", l)
        if m:
            smap[m.group(1)] = m.group(2)
    if not smap:
        return md
    out, n = [], len(lines)
    for i, l in enumerate(lines):
        hm = re.match(r"^### (.+)$", l)
        if hm and "](" not in l and "]" not in hm.group(1):
            text, suffix = hm.group(1), ""
            if text.rstrip().endswith("{major}"):
                suffix = " {major}"; text = re.sub(r"\s*\{major\}\s*$", "", text)
            url = None
            for j in range(i + 1, n):
                if re.match(r"^#{1,3} ", lines[j]):
                    break
                cm = re.search(r"\[(\d+)\]", lines[j])
                if cm and cm.group(1) in smap:
                    url = smap[cm.group(1)]
                    break
            if url:
                out.append(f"### [{text}]({url}){suffix}")
                continue
        out.append(l)
    return "\n".join(out)


def _dmy_title(md: str, stem: str) -> str:
    """Force the H1's trailing date to DD/MM/YYYY using the digest's own date (from its
    filename), so EVERY digest on the site shows d/m/y — including older archived ones whose
    title was written before that change."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", stem)
    if not m:
        return md
    dmy = f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return re.sub(r"^(#\s+\S.*?)\s+[-–—]\s+.*$", rf"\1 — {dmy}", md, count=1, flags=re.M)


def render_digest_split(md: str) -> tuple[str, str]:
    """Renumber sources, link headlines, make [n] citations clickable, then return
    (body_html_without_sources, sources_html) so the Sources list can be placed last."""
    global _SRCMAP
    md = renumber_sources(md)
    _SRCMAP = parse_srcmap(md)
    md = link_headings(md)                       # links headlines while the Sources list is present
    idx = md.find("\n## Sources")
    body, src = (md[:idx], md[idx + 1:]) if idx != -1 else (md, "")
    body_html = md_to_html(body)
    src_html = md_to_html(src) if src.strip() else ""
    _SRCMAP = {}
    return body_html, src_html


# ----------------------------------------------------------------------------- #
#  Catalyst timeline
# ----------------------------------------------------------------------------- #
def _category(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["pdufa", "chmp", "approval", "fda", "ema", "decision", "tariff", "policy", "mfn"]):
        return "reg"
    if "earnings" in t:
        return "earn"
    if any(k in t for k in ["congress", "conference", "ash", "esmo", "easd", "jpm", "morgan", "meeting", "session"]):
        return "conf"
    return "other"


_CAT_NAMES = {"reg": "Regulatory", "earn": "Earnings", "conf": "Conference", "other": "Other"}


def render_timeline(events: list[dict], ref_date: dt.date | None = None) -> str:
    """Forward-looking catalyst table as of `ref_date` (default today): events that have
    already passed are dropped, the rest grouped into next-30-days / 1–3-months / horizon
    buckets. Each digest passes its OWN date, so an archived brief looks forward from when it
    was produced rather than from the build date."""
    groups = upcoming_catalysts(events, ref_date)
    if not groups:
        return '<p class="muted">No upcoming catalysts on file.</p>'
    parts = []
    for label, evs in groups:
        parts.append(f'<div class="cat-group">{label}</div><table class="cat-table">')
        for e in evs:
            d = e["date"].strftime("%-d %b %Y")
            parts.append(
                f'<tr><td class="cat-date">{d}</td>'
                f'<td class="cat-text" title="{html.escape(e["full"])}">{html.escape(e["label"])}</td></tr>')
        parts.append("</table>")
    return '<div class="cat-wrap">' + "".join(parts) + "</div>"


def render_catalyst_mix(events: list[dict], ref_date: dt.date | None = None) -> str:
    """A compact category-mix of the UPCOMING catalysts as of `ref_date` (default today),
    rendered as a single wide row above the timeline — an at-a-glance sense of WHAT KIND of
    events are ahead (regulatory decisions, earnings, conferences, or other). Counts the exact
    same forward-looking set the timeline shows (past events dropped, same `ref_date`), so the
    cell counts and the timeline can never disagree. Returns "" when nothing is upcoming."""
    upcoming = [e for _, evs in upcoming_catalysts(events, ref_date) for e in evs]
    if not upcoming:
        return ""
    counts: dict[str, int] = {}
    for e in upcoming:
        c = _category(e["full"])
        counts[c] = counts.get(c, 0) + 1
    total = max(sum(counts.values()), 1)
    cells = []
    for k in ("reg", "earn", "conf", "other"):
        n = counts.get(k, 0)
        if not n:
            continue
        pct = round(n / total * 100)
        cells.append(
            f'<div class="catmix-cell">'
            f'<div class="catmix-top"><span class="catmix-name">{_CAT_NAMES[k]}</span>'
            f'<span class="catmix-val">{n}</span></div>'
            f'<span class="catmix-bar"><span class="catmix-fill {k}" style="width:{pct}%"></span></span>'
            "</div>")
    return ('<div class="sub-h">By category</div><div class="catmix">'
            + "".join(cells) + "</div>")


# ----------------------------------------------------------------------------- #
#  Markets (real prices, free Yahoo Finance endpoint — no key, no fake data).
#  Ticker lists + fetch live in pharma_render.py (shared with the email renderer).
# ----------------------------------------------------------------------------- #
def render_market(data: list[dict]) -> str:
    """Clean table (Name · ticker · last · 5-day %), matching the email's formatting."""
    if not data:
        return ""
    data = sorted(data, key=lambda x: x["pct"], reverse=True)
    rows = []
    for x in data:
        # Green up, red down, neutral for ~flat (rounds to 0.0%).
        if round(x["pct"], 1) == 0:
            cls, sign = "flat", ""
        elif x["pct"] > 0:
            cls, sign = "up", "+"
        else:
            cls, sign = "down", ""
        rows.append(
            "<tr>"
            f'<td class="mkt-name">{html.escape(x["name"])} <span class="tkr">{x["t"]}</span></td>'
            f'<td class="mkt-last">{x["last"]:.2f}</td>'
            f'<td class="mkt-pct {cls}">{sign}{x["pct"]:.1f}%</td>'
            "</tr>")
    return '<table class="mkt-table">' + "".join(rows) + "</table>"


# ----------------------------------------------------------------------------- #
#  Page assembly
# ----------------------------------------------------------------------------- #
def get_repo_url() -> str:
    cfg = ROOT / ".git" / "config"
    if cfg.exists():
        m = re.search(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?\s", cfg.read_text())
        if m:
            return "https://github.com/" + m.group(1)
    return ""


def pages_url(repo_url: str) -> str:
    """Absolute base URL of the published site, for the RSS feed's links. SITE_URL env wins
    (set in the workflow); otherwise derive the GitHub Pages URL from the repo
    (https://github.com/OWNER/REPO -> https://owner.github.io/REPO/). "" if unknown."""
    env = os.environ.get("SITE_URL", "").strip()
    if env:
        return env.rstrip("/") + "/"
    m = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", repo_url)
    if m:
        return f"https://{m.group(1).lower()}.github.io/{m.group(2)}/"
    return ""


def rss_feed(items: list, base_url: str, built: dt.datetime) -> str:
    """RSS 2.0 from the most recent digests, so readers can subscribe. `items` are
    {title, url, desc, dt} dicts (dt optional)."""
    def esc(s: str) -> str:
        return html.escape(s or "", quote=True)
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<rss version="2.0"><channel>',
             '<title>Pharma Morning Brief</title>',
             f'<link>{esc(base_url)}</link>',
             '<description>Balanced, fact-checked pharmaceutical-sector news — a 2–3 minute morning brief.</description>',
             f'<lastBuildDate>{format_datetime(built)}</lastBuildDate>']
    for it in items:
        parts += ['<item>',
                  f'<title>{esc(it["title"])}</title>',
                  f'<link>{esc(it["url"])}</link>',
                  f'<guid isPermaLink="true">{esc(it["url"])}</guid>']
        if it.get("dt"):
            parts.append(f'<pubDate>{format_datetime(it["dt"])}</pubDate>')
        parts.append(f'<description>{esc(it["desc"])}</description>')
        parts.append('</item>')
    parts.append('</channel></rss>')
    return "\n".join(parts)


def ics_feed(events: list, built: dt.datetime) -> str:
    """An iCalendar (.ics) feed of the catalysts so the calendar can be SUBSCRIBED to — each
    becomes an all-day event. `events` are {date, label, full} dicts (already filtered to the set
    you want published). RFC 5545: values escaped, long lines folded, and a STABLE per-event UID
    (date + slug) so a rebuild updates events in place instead of duplicating them."""
    def esc(s: str) -> str:
        return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", " ")
    def fold(line: str) -> str:        # RFC 5545 line folding (conservative, char-based)
        if len(line) <= 73:
            return line
        out, rest = [line[:73]], line[73:]
        while rest:
            out.append(" " + rest[:72]); rest = rest[72:]
        return "\r\n".join(out)
    stamp = built.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Pharma Morning Brief//Catalysts//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Pharma Catalysts",
             "X-WR-CALDESC:Upcoming pharma catalysts to watch."]
    for e in events:
        dstart = e["date"].strftime("%Y%m%d")
        dend = (e["date"] + dt.timedelta(days=1)).strftime("%Y%m%d")
        lines += ["BEGIN:VEVENT",
                  f"UID:cat-{dstart}-{_slug(e['full'])[:48]}@pharma-brief",
                  f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{dstart}",
                  f"DTEND;VALUE=DATE:{dend}",
                  fold("SUMMARY:" + esc(e["label"])),
                  fold("DESCRIPTION:" + esc(e["full"])),
                  "TRANSP:TRANSPARENT",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def watchlist_topics(path) -> list:
    """Topic chips for the Threads view, derived from watchlist.md bullets: strip the leading
    '- ', any *(italic note)* and (parenthetical), split on ' / ' and ' & ' alternatives, trim,
    dedupe, and drop over-long fragments. Best-effort — the Threads box also takes free text."""
    if not path or not path.exists():
        return []
    # Generic fragments left behind by a ' / ' or ' & ' split (e.g. "...discovery & development")
    # that would match briefs spuriously and pollute the coverage chart — drop them.
    STOP = {"development", "metabolic", "next-gen"}
    topics, seen = [], set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*-\s+(.+)$", line)
        if not m:
            continue
        t = re.sub(r"\([^)]*\)", "", m.group(1).replace("*", ""))   # drop notes/parentheticals + emphasis
        for part in re.split(r"\s+/\s+|\s+&\s+", t):
            part = part.strip(" *_-—–.")
            key = part.lower()
            if part and len(part) <= 28 and key not in STOP and key not in seen:
                topics.append(part); seen.add(key)
    return topics


def page(title: str, body: str, home_link: bool = True, repo_url: str = "") -> str:
    base = "index.html" if home_link else ""
    nav = "".join(f'<a href="{base}#{i}">{n}</a>'
                  for i, n in [("latest", "Latest"), ("upcoming", "Catalysts"),
                               ("markets", "Markets"), ("archive", "Archive")]) \
        + '<a href="threads.html">Threads</a>'
    src = ", ".join(f'<a href="{u}" target="_blank" rel="noopener">{n}</a>' for n, u in SOURCES)
    cloud = (f'<h4>Cloud</h4>'
             f'<a href="{repo_url}/actions" target="_blank" rel="noopener">Run / manage digests &rarr;</a>'
             f'<a href="{repo_url}" target="_blank" rel="noopener">Project on GitHub &rarr;</a>') if repo_url else ""
    drawer = (
        '<div class="drawer-bg" id="drawerbg"></div>'
        '<aside class="drawer" id="drawer"><button class="close" id="drawerclose" aria-label="Close">&times;</button>'
        '<div class="dtitle">Settings</div>'
        '<h4>Appearance</h4>'
        '<div class="seg" id="themeseg"><button data-theme="auto">Auto</button>'
        '<button data-theme="light">Light</button><button data-theme="dark">Dark</button></div>'
        '<h4>Go to</h4>'
        f'<a href="{base}#latest">Latest digest</a><a href="{base}#upcoming">Catalysts</a>'
        f'<a href="{base}#markets">Markets</a><a href="{base}#archive">Archive</a><a href="{base}#about">About</a>'
        '<a href="threads.html">Threads (follow a topic)</a>'
        '<h4>Find</h4><button class="opt" id="opensearch">Search the archive</button>'
        f'{cloud}</aside>')
    topbar = (f'<header class="topbar"><div class="bar">'
              f'<a class="wordmark" href="index.html">Pharma Morning Brief</a>'
              f'<button class="gear" id="gear" aria-label="Settings">&#9881;</button></div></header>')
    inner = f'<article class="doc">{body}</article>' if home_link else body
    # "Last updated" = this build's time. The build only runs after a successful digest,
    # so a stalled pipeline shows as a stale date here (localized to the viewer by the JS).
    now_utc = dt.datetime.now(dt.timezone.utc)
    built_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    built_disp = now_utc.strftime("%b %d, %Y · %H:%M UTC")
    footer = (f'<footer><div class="bar"><div class="foot-nav">{nav}</div>'
              f'<div class="foot-src">Sources monitored &mdash; {src}</div>'
              f'<div class="foot-built">Last updated <time data-utc="{built_iso}">{built_disp}</time></div>'
              f'</div></footer>')
    head_theme = ('<script>(function(){try{var t=localStorage.getItem("theme")||"auto";'
                  'if(t==="dark"||(t==="auto"&&matchMedia("(prefers-color-scheme:dark)").matches))'
                  'document.documentElement.classList.add("dark");}catch(e){}})();</script>')
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
{head_theme}
<link rel="stylesheet" href="style.css">
<link rel="alternate" type="application/rss+xml" title="Pharma Morning Brief" href="feed.xml">
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#466362">
<link rel="apple-touch-icon" href="icon.svg">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Pharma Brief">
</head><body>{drawer}{topbar}<main>{inner}</main>{footer}
<script src="settings.js"></script><script src="listen.js"></script>
<script>if('serviceWorker' in navigator)addEventListener('load',function(){{navigator.serviceWorker.register('sw.js').catch(function(){{}});}});</script></body></html>"""


def published_line(date_str: str, iso: str | None = None) -> str:
    """A 'Published' line. When the real generation instant is known (`iso`, UTC), the JS
    localizes it to each viewer's timezone; otherwise we honestly show just the date (no
    invented clock time)."""
    if iso:
        return (f'<p class="meta pub">Published '
                f'<time data-utc="{iso}">{date_str}</time> '
                f'<span class="tz-note">· your local time</span></p>')
    return f'<p class="meta pub">Published <time>{date_str}</time></p>'


def with_published(body_html: str, date_str: str, iso: str | None = None) -> str:
    """Insert the 'Published' line right after the digest's H1."""
    line = published_line(date_str, iso)
    if "</h1>" in body_html:
        return body_html.replace("</h1>", "</h1>\n" + line, 1)
    return line + body_html


def load_published() -> dict:
    """Map of digest-date -> real generation timestamp (UTC ISO), written by run_digest."""
    p = DIGESTS / "published.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
    return {}


def meta_of(md: str) -> dict:
    title = next((l[2:].strip() for l in md.splitlines() if l.startswith("# ")), "Digest")
    sub = next((l for l in md.splitlines() if l.startswith("*Window")), "")
    eng = re.search(r"Engine:\s*([^·*]+)", sub)
    engine = eng.group(1).strip() if eng else "—"
    return {"title": title, "engine": engine}


def plain_text(md: str) -> str:
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)
    t = re.sub(r"[#>*_`|]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


SEARCH_JS = """(function(){
  var input=document.getElementById('q'),
      results=document.getElementById('results'),
      archive=document.getElementById('archive');
  var toggle=document.getElementById('searchToggle'), bar=document.getElementById('searchbar');
  if(toggle&&bar){toggle.addEventListener('click',function(e){e.preventDefault();bar.hidden=!bar.hidden;if(!bar.hidden&&input)input.focus();});}
  if(!input) return;
  function row(d){return '<a class="arch-item" href="'+d.slug+'"><span class="arch-date">'+d.date+
    '</span><span class="arch-title">'+d.title+'</span><span class="arch-engine">'+d.engine+'</span></a>';}
  input.addEventListener('input',function(){
    var q=input.value.trim().toLowerCase();
    if(!q){results.innerHTML='';results.style.display='none';if(archive)archive.style.display='';return;}
    if(archive)archive.style.display='none';results.style.display='';
    var hits=(window.DIGESTS||[]).filter(function(d){return (d.title+' '+d.text).toLowerCase().indexOf(q)>=0;});
    var inner=hits.length? '<div class="arch">'+hits.map(row).join('')+'</div>'
                         : '<p class="muted">No matches.</p>';
    results.innerHTML='<section class="block"><div class="block-label">Results</div><div class="block-body">'+inner+'</div></section>';
  });
})();"""


SETTINGS_JS = """(function(){
  var g=document.getElementById('gear'),d=document.getElementById('drawer'),
      bg=document.getElementById('drawerbg'),c=document.getElementById('drawerclose');
  function open(){if(d){d.classList.add('open');bg.classList.add('open');}}
  function close(){if(d){d.classList.remove('open');bg.classList.remove('open');}}
  if(g)g.onclick=open; if(c)c.onclick=close; if(bg)bg.onclick=close;
  document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});
  var seg=document.getElementById('themeseg');
  function apply(t){
    var dark=t==='dark'||(t==='auto'&&matchMedia('(prefers-color-scheme:dark)').matches);
    document.documentElement.classList.toggle('dark',dark);
    if(seg)[].forEach.call(seg.querySelectorAll('button'),function(b){
      b.classList.toggle('sel',b.getAttribute('data-theme')===t);});
  }
  var cur='auto'; try{cur=localStorage.getItem('theme')||'auto';}catch(e){}
  apply(cur);
  if(seg)[].forEach.call(seg.querySelectorAll('button'),function(b){
    b.onclick=function(){var t=b.getAttribute('data-theme');try{localStorage.setItem('theme',t);}catch(e){}apply(t);};});
  var os=document.getElementById('opensearch'),bar=document.getElementById('searchbar'),q=document.getElementById('q');
  if(os)os.onclick=function(){close();if(bar){bar.hidden=false;if(q)q.focus();}else{location.href='index.html';}};
  // Localize any <time data-utc> to the viewer's own timezone.
  [].forEach.call(document.querySelectorAll('time[data-utc]'),function(t){
    var d=new Date(t.getAttribute('data-utc'));
    if(isNaN(d.getTime()))return;
    try{t.textContent=d.toLocaleString(undefined,{weekday:'short',day:'numeric',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});}
    catch(e){t.textContent=d.toLocaleString();}
  });
})();"""


# Read-aloud: a "Listen" button per brief using the browser's built-in speech synthesis (no
# audio files, no keys). It reads ONLY the brief prose — citations ([n] links), the Window/Engine
# subtitle, the Published line, the button itself, and the "Major story" tag are all stripped — and
# chunks into sentences so long briefs don't hit the browsers' ~15s/long-utterance cutoff.
LISTEN_JS = """(function(){
  var synth=window.speechSynthesis;
  if(!synth||typeof SpeechSynthesisUtterance==='undefined')return;   // unsupported -> no button
  function score(v){var s=0,n=v.name||'';if(/en[-_]US/i.test(v.lang))s+=2;if(/en[-_]GB/i.test(v.lang))s+=1;
    if(/Samantha|Daniel|Siri|Natural|Google/i.test(n))s+=3;if(v.localService)s+=1;return s;}
  function pickVoice(){var vs=(synth.getVoices()||[]).filter(function(v){return /^en/i.test(v.lang);});
    vs.sort(function(a,b){return score(b)-score(a);});return vs[0]||null;}
  function extract(brief){
    var c=brief.cloneNode(true);
    [].forEach.call(c.querySelectorAll('h1, a.cite, .listen-bar, .meta, .pub, .major-tag'),function(n){
      if(n.parentNode)n.parentNode.removeChild(n);});   // h1 dropped: the "DD/MM/YYYY" date reads badly aloud
    var t=c.innerText||c.textContent||'';
    t=t.replace(/\\[\\d+(?:\\s*[,\\u2013-]\\s*\\d+)*\\]/g,' ');   // any stray [n] / [1, 2] / [1-3]
    return t.replace(/\\s+/g,' ').trim();
  }
  function chunk(text){
    var parts=text.match(/[^.!?]+[.!?]+["')\\]]*|\\S[^.!?]*$/g)||[text],out=[],buf='';
    parts.forEach(function(s){s=s.trim();if(!s)return;
      if(buf&&(buf+' '+s).length>220){out.push(buf);buf=s;}else{buf=buf?buf+' '+s:s;}});
    if(buf)out.push(buf);return out;
  }
  var active=null;
  function reset(btn){btn.setAttribute('aria-pressed','false');
    btn.querySelector('.listen-i').textContent='\\u25B6';btn.querySelector('.listen-t').textContent='Listen';}
  function stop(){var b=active;active=null;synth.cancel();if(b)reset(b);}
  function play(btn,brief){
    stop();
    var text=extract(brief);if(!text)return;
    var voice=pickVoice(),parts=chunk(text),i=0;active=btn;
    btn.setAttribute('aria-pressed','true');
    btn.querySelector('.listen-i').textContent='\\u25A0';btn.querySelector('.listen-t').textContent='Stop';
    (function next(){
      if(active!==btn)return;
      if(i>=parts.length){stop();return;}
      var u=new SpeechSynthesisUtterance(parts[i++]);if(voice)u.voice=voice;u.rate=1;u.pitch=1;
      u.onend=next;u.onerror=function(){stop();};synth.speak(u);
    })();
  }
  [].forEach.call(document.querySelectorAll('.brief'),function(brief){
    if(brief.querySelector('.listen'))return;
    var bar=document.createElement('div');bar.className='listen-bar';
    var btn=document.createElement('button');btn.type='button';btn.className='listen';
    btn.setAttribute('aria-pressed','false');btn.setAttribute('aria-label','Listen to this brief');
    btn.innerHTML='<span class="listen-i" aria-hidden="true">\\u25B6</span><span class="listen-t">Listen</span>';
    btn.onclick=function(){active===btn?stop():play(btn,brief);};
    bar.appendChild(btn);
    var h1=brief.querySelector('h1');
    if(h1)h1.insertAdjacentElement('afterend',bar);else brief.insertBefore(bar,brief.firstChild);
  });
  window.addEventListener('pagehide',stop);window.addEventListener('beforeunload',stop);
})();"""


# Synonyms so a watchlist topic also matches its common short forms in the Threads/coverage view
# (e.g. "Lilly" → Eli Lilly, "merger" → M&A) instead of missing or splitting them. Deliberately
# conservative — over-broad aliases create false matches. A topic not listed matches only its own
# name; the first entry should be the canonical name. Edit freely.
TOPIC_ALIASES = {
    "Eli Lilly": ["Eli Lilly", "Lilly"],
    "Novo Nordisk": ["Novo Nordisk", "Novo"],
    "AstraZeneca": ["AstraZeneca", "Astra"],
    "Viking Therapeutics": ["Viking Therapeutics", "Viking"],
    "M&A": ["M&A", "merger", "acquisition", "takeover", "buyout"],
}


# Threads view: pick a topic (a coverage-chart bar or free text) and see every archived brief
# that mentions it, newest-first, with a snippet around the match — the archive as a storyline.
# The chart doubles as a TRENDS view: watchlist topics ranked by how many briefs mention them.
# Pure client-side over window.DIGESTS (the same index that powers search); search_index text is
# plain (unescaped), so every interpolation is HTML-escaped before it touches innerHTML.
THREADS_JS = """(function(){
  var data=window.DIGESTS||[], topics=window.THREAD_TOPICS||[], aliases=window.THREAD_ALIASES||{};
  var q=document.getElementById('threadq'),results=document.getElementById('threadresults'),
      chart=document.getElementById('threadchart');
  function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
  function rxEsc(s){return s.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&');}
  function termsFor(t){return (aliases[t]&&aliases[t].length)?aliases[t]:[t];}   // a topic's synonyms (or itself)
  function reFor(terms){return new RegExp('('+terms.map(rxEsc).join('|')+')','i');}
  function countFor(t){var re=reFor(termsFor(t));
    return data.filter(function(d){return re.test(d.title)||re.test(d.text);}).length;}
  function snippet(text,terms){
    var m=reFor(terms).exec(text);
    if(!m)return '';
    var i=m.index,start=Math.max(0,i-90),end=Math.min(text.length,i+m[0].length+150);
    var s=(start>0?'… ':'')+text.slice(start,end)+(end<text.length?' …':'');
    var hl=new RegExp('('+terms.map(function(t){return rxEsc(esc(t));}).join('|')+')','ig');
    return esc(s).replace(hl,function(m){return '<mark>'+m+'</mark>';});
  }
  function render(topic){
    topic=(topic||'').trim();
    if(!topic){results.innerHTML='';return;}
    var terms=termsFor(topic),re=reFor(terms);
    var hits=data.filter(function(d){return re.test(d.title)||re.test(d.text);})
                 .sort(function(a,b){return a.date<b.date?1:(a.date>b.date?-1:0);});
    if(!hits.length){results.innerHTML='<p class="muted">No briefs mention &ldquo;'+esc(topic)+'&rdquo; yet.</p>';return;}
    var head='<div class="thread-count">'+hits.length+' brief'+(hits.length>1?'s':'')+' mention &ldquo;'+esc(topic)+'&rdquo;</div>';
    results.innerHTML=head+hits.map(function(d){
      return '<a class="thread-item" href="'+encodeURI(d.slug)+'">'
        +'<span class="thread-date">'+esc((d.date||'').slice(0,10))+'</span>'
        +'<span class="thread-body"><span class="thread-title">'+d.title+'</span>'
        +'<span class="thread-snip">'+snippet(d.text,terms)+'</span></span></a>';
    }).join('');
  }
  function setTerm(t){q.value=t;render(t);if(history.replaceState)history.replaceState(null,'','?t='+encodeURIComponent(t));}
  function buildChart(){
    if(!chart)return;
    var rows=topics.map(function(t){return {t:t,n:countFor(t)};})
                   .filter(function(x){return x.n>0;})
                   .sort(function(a,b){return b.n-a.n;}).slice(0,16);
    if(!rows.length){chart.innerHTML='';return;}
    // Weekly buckets across the whole archive, for a per-topic trend sparkline. All client-side.
    var ds=data.map(function(d){return (d.date||'').slice(0,10);}).filter(Boolean).sort();
    var WK=604800000, t0=ds.length?Date.parse(ds[0]+'T00:00:00Z'):0;
    var nB=ds.length?Math.floor((Date.parse(ds[ds.length-1]+'T00:00:00Z')-t0)/WK)+1:0;
    function series(terms){var re=reFor(terms),a=[],i;for(i=0;i<nB;i++)a.push(0);
      data.forEach(function(d){var s=(d.date||'').slice(0,10);
        if(s&&(re.test(d.title)||re.test(d.text))){var b=Math.floor((Date.parse(s+'T00:00:00Z')-t0)/WK);if(b>=0&&b<nB)a[b]++;}});
      return a;}
    function spark(a){var mx=Math.max.apply(null,a)||1;
      var pts=a.map(function(v,i){return (i/(nB-1)*100).toFixed(1)+','+(21-(v/mx)*18).toFixed(1);}).join(' ');
      return '<svg class="spark" viewBox="0 0 100 22" preserveAspectRatio="none" aria-hidden="true"><polyline points="'+pts+'"/></svg>';}
    var max=rows[0].n;
    chart.innerHTML='<div class="trend-h">Coverage &amp; weekly trend across '+data.length+' briefs &mdash; click to follow a thread</div>'+
      rows.map(function(x){
        var mid=(nB>=2)?spark(series(termsFor(x.t)))
              :'<span class="trend-track"><span class="trend-fill" style="width:'+Math.round(x.n/max*100)+'%"></span></span>';
        return '<button class="trend-bar" type="button" data-term="'+esc(x.t)+'">'
          +'<span class="trend-name">'+esc(x.t)+'</span>'
          +'<span class="trend-mid">'+mid+'</span>'
          +'<span class="trend-val">'+x.n+'</span></button>';}).join('');
    [].forEach.call(chart.querySelectorAll('.trend-bar'),function(b){
      b.onclick=function(){setTerm(b.getAttribute('data-term'));
        results.scrollIntoView({behavior:'smooth',block:'start'});};});
  }
  buildChart();
  if(q)q.addEventListener('input',function(){render(q.value);});
  var m=location.search.match(/[?&]t=([^&]+)/);
  if(m&&q){q.value=decodeURIComponent(m[1].replace(/\\+/g,' '));render(q.value);}
})();"""


# --- PWA: installable + offline. A scalable SVG app icon (no raster tooling needed), a web app
#     manifest, and a service worker that precaches the shell + recent briefs and serves
#     cache-first so the site reads/plays offline. ---
ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Pharma Morning Brief">
<rect width="512" height="512" rx="104" fill="#17181c"/>
<g transform="rotate(40 256 256)">
<rect x="190" y="120" width="132" height="272" rx="66" fill="#f4f2ec"/>
<rect x="190" y="240" width="132" height="32" fill="#466362"/>
</g>
</svg>
"""

MANIFEST_JSON = json.dumps({
    "name": "Pharma Morning Brief",
    "short_name": "Pharma Brief",
    "description": "A balanced, fact-checked 2-3 minute pharmaceutical-sector morning brief.",
    "start_url": "index.html",
    "scope": "./",
    "display": "standalone",
    "background_color": "#f4f2ec",
    "theme_color": "#466362",
    "icons": [{"src": "icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any maskable"}],
}, indent=2)

# Cache name (__CACHE__) and precache list (__PRECACHE__) are filled in at build time.
SW_JS = """const CACHE='__CACHE__';
const PRECACHE=__PRECACHE__;
self.addEventListener('install',function(e){
  e.waitUntil(caches.open(CACHE).then(function(c){return c.addAll(PRECACHE);}).then(function(){return self.skipWaiting();}));
});
self.addEventListener('activate',function(e){
  e.waitUntil(caches.keys().then(function(ks){return Promise.all(ks.map(function(k){if(k!==CACHE)return caches.delete(k);}));}).then(function(){return self.clients.claim();}));
});
self.addEventListener('fetch',function(e){
  var req=e.request;
  if(req.method!=='GET'||new URL(req.url).origin!==self.location.origin)return;
  e.respondWith(caches.match(req).then(function(cached){
    var net=fetch(req).then(function(res){
      if(res&&res.status===200){var copy=res.clone();caches.open(CACHE).then(function(c){c.put(req,copy);});}
      return res;
    }).catch(function(){return cached;});
    return cached||net;   // cache-first for instant/offline; refresh in the background
  }));
});
"""


def brief_ref_date(stem: str) -> dt.date:
    """The date a brief looks forward FROM — the YYYY-MM-DD at the start of its filename (so
    suffixed stems like '2026-06-12-deepseek' still resolve). Catalysts before this date have
    already passed for that brief and are dropped. Falls back to today if the stem isn't dated."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", stem)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            pass
    return dt.date.today()


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    repo_url = get_repo_url()
    files = sorted([p for p in DIGESTS.glob("*.md") if p.stem != "INDEX"], reverse=True)
    pub = load_published()

    # Catalysts are rendered PER BRIEF (from each brief's own date) so a page always looks
    # forward from when it was produced — past catalysts drop off rather than lingering. Markets
    # are live prices: fetched once and shared across pages (they can't be reconstructed per day).
    events = parse_catalysts(CATALYSTS)

    def catalysts_section(ref_date: dt.date) -> str:
        # The forward-looking category-mix sits as a single wide row ABOVE the dated timeline (so
        # the timeline gets the full width, not a squeezed left column). Both count from the SAME
        # ref_date, so they always agree; when nothing is upcoming the mix is "" and the timeline
        # stands alone.
        mix, timeline = render_catalyst_mix(events, ref_date), render_timeline(events, ref_date)
        return (
            '<section class="block" id="upcoming"><div class="block-label">Catalysts</div><div class="block-body">'
            '<p class="meta">Dates to watch &mdash; scheduled events that can move the sector: regulatory decisions, '
            'trial readouts, earnings, and major conferences. '
            '<a class="cal-sub" href="catalysts.ics">Add to your calendar &#8599;</a></p>'
            + mix + timeline + "</div></section>")

    latest_md = files[0].read_text(encoding="utf-8") if files else ""
    _dt = plain_text(latest_md).lower()
    # Markets % matches the latest brief's window (daily=5d, review=7d); a forward brief on
    # the homepage has no backward window, so default the shared site strip to a week.
    mkt_days = brief_market_days(latest_md) or 7
    market_html = render_market(fetch_market(select_tickers(_dt), days=mkt_days))
    market_block = (
        '<section class="block" id="markets"><div class="block-label">Markets</div><div class="block-body">'
        + market_html + f'<p class="meta">Source: Yahoo Finance, end-of-day prices ({mkt_days}-day change). Not investment advice.</p>'
        + "</div></section>"
    ) if market_html else ""

    def sources_section(src_html):
        return (f'<section class="block"><div class="block-label">Sources</div>'
                f'<div class="block-body">{src_html}</div></section>') if src_html else ""

    base = pages_url(repo_url)
    arch_items, search_index, feed_items = [], [], []
    for p in files:
        md = _dmy_title(p.read_text(encoding="utf-8"), p.stem)   # d/m/y title for every digest
        m = meta_of(md)
        slug = p.stem + ".html"
        body_html, src_html = render_digest_split(md)
        # Order: brief → catalysts → markets → Sources (last), so you don't scroll past the
        # references to reach catalysts/markets. Catalysts look forward from THIS brief's date.
        page_extras = catalysts_section(brief_ref_date(p.stem)) + market_block
        (OUT / slug).write_text(
            page(strip_lead(m["title"]), '<div class="brief">' + with_published(body_html, p.stem, pub.get(p.stem)) + '</div>' + page_extras + sources_section(src_html), repo_url=repo_url),
            encoding="utf-8")
        engine = m["engine"]
        # Archive label: digest name only — drop the trailing date and any leading emoji (old digests).
        short_title = strip_lead(re.sub(r"\s+[-–—]\s+.*$", "", m["title"]).strip())
        arch_items.append(
            f'<a class="arch-item" href="{slug}"><span class="arch-date">{html.escape(p.stem)}</span>'
            f'<span class="arch-title">{html.escape(short_title)}</span>'
            f'<span class="arch-engine">{html.escape(engine)}</span></a>')
        search_index.append({"slug": slug, "date": p.stem, "title": html.escape(short_title),
                             "engine": html.escape(engine), "text": plain_text(md)[:4000]})
        if len(feed_items) < 20 and base:        # newest 20 (files are sorted newest-first)
            iso = pub.get(p.stem)
            try:
                when = (dt.datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso
                        else dt.datetime.strptime(p.stem, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc))
            except (ValueError, AttributeError):
                when = None
            # Feed item title keeps the date (m["title"] is "… — DD/MM/YYYY") so subscribers
            # can tell daily entries apart; the archive grid uses the date-less short_title.
            feed_items.append({"title": strip_lead(m["title"]), "url": base + slug,
                               "desc": plain_text(md)[:300], "dt": when})

    if files:
        slug0 = files[0].stem + ".html"
        body0, src0 = render_digest_split(_dmy_title(latest_md, files[0].stem))
        # On the homepage, make the latest brief's title a permalink to its own dated page.
        body0 = re.sub(r"<h1>(.*?)</h1>", rf'<h1><a href="{slug0}">\1</a></h1>', body0, count=1, flags=re.S)
        latest_html = with_published(body0, files[0].stem, pub.get(files[0].stem))
        latest_src_section = sources_section(src0)
        # Homepage catalysts match the latest brief's date, so it reads identically to that
        # brief's own page (both look forward from the day it was produced).
        index_catalysts = catalysts_section(brief_ref_date(files[0].stem))
    else:
        latest_html = '<p class="muted">No digests yet.</p>'
        latest_src_section = ""
        index_catalysts = catalysts_section(dt.date.today())
    # Archive: keep the index light — show the most recent ARCHIVE_ON_INDEX, and move the
    # complete list to its own archive.html once it grows past that (no unbounded index page).
    ARCHIVE_ON_INDEX = 30
    if not arch_items:
        index_arch = '<p class="muted">No digests yet.</p>'
    elif len(arch_items) > ARCHIVE_ON_INDEX:
        index_arch = ("".join(arch_items[:ARCHIVE_ON_INDEX])
                      + f'<a class="arch-more" href="archive.html">'
                        f'View the full archive ({len(arch_items)}) &rarr;</a>')
        full_body = (f'<section class="block"><div class="block-label">Archive</div>'
                     f'<div class="block-body"><div class="arch">{"".join(arch_items)}</div></div></section>')
        (OUT / "archive.html").write_text(
            page("Archive — Pharma Morning Brief", full_body, repo_url=repo_url), encoding="utf-8")
    else:
        index_arch = "".join(arch_items)

    index_body = f"""
<div id="searchbar" class="searchbar" hidden><input id="q" type="search" placeholder="Search the archive..." autocomplete="off"></div>
<header class="masthead">
  <div class="kicker">Daily Pharmaceutical Intelligence</div>
  <h1 class="brand">Pharma Morning Brief</h1>
  <p class="tagline">Balanced, fact-checked &mdash; in the time it takes to drink a coffee.</p>
</header>
<div id="results" style="display:none"></div>
<section class="block" id="about"><div class="block-label">About</div><div class="block-body">
  <p><strong>Pharma Morning Brief</strong> turns each day's global pharmaceutical news into a fact-checked, ~3-minute executive read &mdash; for someone entering pharma who needs to stay current without scanning 20 outlets. Weekdays: a daily brief; Saturday: a <em>Week in Review</em>; Sunday: a <em>Week Ahead</em>. On the last weekend of each month these widen to a <em>Month in Review</em> and <em>Month Ahead</em>, and at the close of December to a <em>Year in Review</em> and <em>Year Ahead</em>.</p>
  <p>Every fact is grounded in a real, linked source and passed through an automated <strong>grounding check</strong> that removes claims the sources don't support; niche terms are glossed in plain language. It runs automatically each morning on <em>Gemini</em> (free) &mdash; one click switches to <em>DeepSeek</em> &mdash; with the richest analysis available on demand via <em>Claude</em>. Each issue is labelled with the engine that wrote it.</p>
</div></section>
<section class="block" id="latest"><div class="block-label">Latest brief</div><div class="block-body brief">{latest_html}</div></section>
{index_catalysts}
{market_block}
{latest_src_section}
<section class="block" id="archive"><div class="block-label">Archive</div><div class="block-body"><div class="arch">{index_arch}</div></div></section>
<script src="search-data.js"></script><script src="search.js"></script>"""
    (OUT / "index.html").write_text(page("Pharma Morning Brief", index_body, home_link=False, repo_url=repo_url), encoding="utf-8")
    (OUT / "style.css").write_text(CSS, encoding="utf-8")
    (OUT / "search-data.js").write_text("window.DIGESTS=" + json.dumps(search_index) + ";", encoding="utf-8")
    (OUT / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    (OUT / "settings.js").write_text(SETTINGS_JS, encoding="utf-8")
    (OUT / "listen.js").write_text(LISTEN_JS, encoding="utf-8")
    # Threads: a topic-storyline view over the archive. The coverage chart (watchlist topics ranked
    # by how many briefs mention them) doubles as the trends view AND the topic picker; free text
    # covers anything else. Topics are embedded for the client to count against window.DIGESTS.
    threads_body = (
        '<section class="block"><div class="block-label">Threads</div><div class="block-body">'
        '<p class="meta">Follow a company, drug, or theme across every brief &mdash; the bars show how much '
        'each has been covered; click one (or type your own) to see every mention newest-first with a snippet.</p>'
        '<div class="thread-chart" id="threadchart"></div>'
        '<input id="threadq" class="thread-input" type="search" placeholder="e.g. orforglipron, tariffs, Novo Nordisk…" autocomplete="off">'
        '<div id="threadresults" class="thread-results"></div>'
        '</div></section>'
        f'<script>window.THREAD_TOPICS={json.dumps(watchlist_topics(WATCHLIST))};'
        f'window.THREAD_ALIASES={json.dumps(TOPIC_ALIASES)};</script>'
        '<script src="search-data.js"></script><script src="threads.js"></script>')
    (OUT / "threads.html").write_text(page("Threads — Pharma Morning Brief", threads_body, repo_url=repo_url), encoding="utf-8")
    (OUT / "threads.js").write_text(THREADS_JS, encoding="utf-8")
    # Subscribe-able catalyst calendar: the upcoming events as an .ics (regenerated each build,
    # so past events drop off and new ones appear — a subscribed calendar stays current).
    _today = dt.date.today()
    (OUT / "catalysts.ics").write_text(
        ics_feed([e for e in events if e["date"] >= _today], dt.datetime.now(dt.timezone.utc)),
        encoding="utf-8")
    # PWA: icon + manifest + service worker (precaches the shell + recent briefs for offline use).
    (OUT / "icon.svg").write_text(ICON_SVG, encoding="utf-8")
    (OUT / "manifest.webmanifest").write_text(MANIFEST_JSON, encoding="utf-8")
    precache = (["index.html", "threads.html", "style.css", "settings.js", "listen.js",
                 "search.js", "search-data.js", "threads.js", "manifest.webmanifest", "icon.svg"]
                + [p.stem + ".html" for p in files[:12]])
    swver = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    (OUT / "sw.js").write_text(
        SW_JS.replace("__CACHE__", "pharma-" + swver).replace("__PRECACHE__", json.dumps(precache)),
        encoding="utf-8")
    if base and feed_items:
        (OUT / "feed.xml").write_text(
            rss_feed(feed_items, base, dt.datetime.now(dt.timezone.utc)), encoding="utf-8")
    print(f"Site built ✓  ({len(files)} digests)  -> {OUT / 'index.html'}")


CSS = """
:root{
 --paper:#f4f2ec;--ink:#17181c;--muted:#7c7a70;--line:#e3dfd4;--accent:#466362;
 --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
 --sans:"Avenir Next","Avenir","Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
 --mono:"SF Mono",ui-monospace,Menlo,Consolas,monospace;
 --c-reg:#466362;--c-earn:#8b635c;--c-conf:#9e768f;--c-other:#9aa08c;--up:#466362;--down:#8b635c;--major:#8b635c;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
 font-size:17px;line-height:1.72;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;}
a{color:inherit;text-decoration:none}
::selection{background:var(--accent);color:#fff}

/* top bar */
.topbar{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--paper) 90%,transparent);
 backdrop-filter:saturate(140%) blur(8px);border-bottom:1px solid var(--line)}
.bar{max-width:760px;margin:0 auto;padding:12px clamp(20px,5vw,40px);display:flex;justify-content:space-between;align-items:center;gap:20px}
.wordmark{font-family:var(--serif);font-weight:700;font-size:15px;letter-spacing:-.01em}
.util-nav{display:flex;gap:22px}
.util{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:var(--muted);cursor:pointer}
.util:hover{color:var(--accent)}
.searchbar{margin:14px 0 -8px;border-bottom:1px solid var(--line)}
.searchbar input{width:100%;padding:12px 0;border:none;background:transparent;color:var(--ink);
 font-family:var(--serif);font-style:italic;font-size:21px}
.searchbar input:focus{outline:none}
.searchbar input::placeholder{color:var(--muted)}

main{max-width:760px;margin:0 auto;padding:0 clamp(20px,5vw,40px)}

/* masthead */
.masthead{padding:58px 0 30px}
.kicker{font-family:var(--mono);text-transform:uppercase;letter-spacing:.28em;font-size:11px;color:var(--accent);margin-bottom:16px}
.brand{font-family:var(--serif);font-weight:700;font-size:clamp(44px,7.5vw,72px);line-height:1;letter-spacing:-.02em;margin:0}
.tagline{font-family:var(--serif);font-style:italic;color:var(--muted);font-size:clamp(17px,2.4vw,21px);margin:.6em 0 0}

/* editorial blocks: label gutter + content + breathing right margin */
.block{padding:50px 0;border-top:1px solid var(--line)}
.block:first-of-type{border-top:none;padding-top:34px}
.block-label{font-family:var(--mono);text-transform:uppercase;letter-spacing:.2em;
 font-size:10.5px;color:var(--muted);margin-bottom:16px}
.block-body{min-width:0}
.sub-h{font-family:var(--mono);text-transform:uppercase;letter-spacing:.12em;font-size:10.5px;color:var(--muted);margin:0 0 8px}

/* typography */
h1{font-family:var(--serif);font-weight:700;font-size:clamp(30px,4.6vw,44px);line-height:1.08;letter-spacing:-.015em;margin:0 0 .35em}
h2{font-family:var(--serif);font-weight:700;font-size:26px;line-height:1.15;margin:1.7em 0 .5em}
h3{font-family:var(--serif);font-weight:700;font-size:20px;line-height:1.2;margin:1.5em 0 .35em}
p{margin:.75em 0}
.doc{padding:46px 0 24px}
.doc a,.block-body p a,.point-b a{border-bottom:1px solid color-mix(in srgb,var(--accent) 40%,transparent)}
.doc a:hover,.block-body p a:hover{border-bottom-color:var(--accent)}
h1 a,h2 a,h3 a,h1 a:visited,h2 a:visited,h3 a:visited{color:inherit !important;border-bottom:none !important}
h1 a:hover,h2 a:hover,h3 a:hover{text-decoration:underline;text-underline-offset:4px;text-decoration-thickness:1px}
/* visited source links fade; aggregator (redirect-prone) links get a marker */
a.src:visited{color:var(--muted)}
/* positively mark the minority of DIRECT publisher links (the rest go via Google News) */
a.src.direct::after{content:"✓";font-size:.7em;color:var(--accent);margin-left:2px;vertical-align:super}
h2.major a,h3.major a,h2.major,h3.major{color:var(--major) !important}
.major-tag{font-family:var(--mono);text-transform:uppercase;letter-spacing:.16em;font-size:10px;color:var(--major);margin:0 0 5px}
a.cite{border-bottom:none;color:var(--accent);font-weight:600;font-size:.82em;padding:0 1px}
a.cite:hover{text-decoration:underline;text-underline-offset:2px}
/* read-aloud "Listen" control (injected per brief by listen.js) */
.listen-bar{margin:6px 0 20px}
.listen{font-family:var(--mono);font-size:12px;letter-spacing:.04em;color:var(--accent);background:transparent;
 border:1px solid var(--line);border-radius:16px;padding:5px 14px;cursor:pointer;display:inline-flex;
 align-items:center;gap:7px;transition:background .15s,border-color .15s,color .15s}
.listen:hover{border-color:var(--accent)}
.listen[aria-pressed="true"]{background:var(--accent);color:var(--paper);border-color:var(--accent)}
.listen-i{font-size:10px;line-height:1}
.cal-sub{white-space:nowrap;color:var(--accent);border-bottom:1px solid var(--line)}
.cal-sub:hover{border-bottom-color:var(--accent)}
/* threads — coverage chart (also the trends view + topic picker) + topic-storyline results */
.thread-chart{margin:8px 0 18px}
.trend-h{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:0 0 10px}
.trend-bar{display:flex;align-items:center;gap:10px;width:100%;background:transparent;border:none;padding:5px 0;cursor:pointer;font-family:inherit;text-align:left}
.trend-name{flex:none;width:11em;font-size:13px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.trend-mid{flex:1;display:flex;align-items:center;min-width:0}
.spark{width:100%;height:22px;display:block}
.spark polyline{fill:none;stroke:var(--accent);stroke-width:1.5;vector-effect:non-scaling-stroke;stroke-linejoin:round;stroke-linecap:round}
.trend-bar:hover .spark polyline{stroke:var(--ink)}
.trend-track{flex:1;height:8px;background:var(--line);border-radius:3px;overflow:hidden}
.trend-fill{display:block;height:100%;background:var(--accent)}
.trend-val{flex:none;width:2em;text-align:right;font-family:var(--mono);font-size:12px;color:var(--muted)}
.trend-bar:hover .trend-fill{background:var(--ink)}
.trend-bar:hover .trend-name{color:var(--accent)}
.thread-input{width:100%;font-family:var(--sans);font-size:15px;padding:10px 14px;border:1px solid var(--line);border-radius:8px;background:transparent;color:var(--ink)}
.thread-input:focus{outline:none;border-color:var(--accent)}
.thread-count{font-family:var(--mono);font-size:12px;color:var(--muted);margin:20px 0 4px}
.thread-item{display:flex;gap:14px;padding:12px 0;border-bottom:1px solid var(--line)}
.thread-item:last-child{border-bottom:none}
.thread-date{font-family:var(--mono);font-size:12px;color:var(--muted);white-space:nowrap;width:6.4em;flex:none;padding-top:2px;overflow:hidden;text-overflow:ellipsis}
.thread-body{flex:1;min-width:0}
.thread-title{display:block;font-weight:600}
.thread-snip{display:block;color:var(--muted);font-size:14px;margin-top:3px;line-height:1.6}
.thread-snip mark{background:var(--accent);color:var(--paper);border-radius:2px;padding:0 2px}
.muted{color:var(--muted)}
.meta{font-family:var(--mono);font-size:11.5px;letter-spacing:.02em;color:var(--muted);text-transform:none;margin:.4em 0 1.4em}
.meta.pub{margin:.2em 0 1em}.meta.pub time{color:var(--ink)}.tz-note{opacity:.7}
strong{font-weight:700}
em{font-style:italic}
hr{border:none;border-top:1px solid var(--line);margin:2.4em 0}
code{font-family:var(--mono);font-size:.82em;color:var(--accent);background:transparent;padding:0}

/* the lead "talking point" */
.lede{margin:1.7em 0;padding:1.25em 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.lede p{margin:0;font-family:var(--serif);font-style:italic;font-size:clamp(20px,2.7vw,26px);line-height:1.4}

/* TL;DR & quick-hit points: editorial flow, no bullets */
.points{margin:1.1em 0}
.point{margin:0 0 1.4em;max-width:60ch}
.point-h{font-family:var(--sans);font-weight:700;font-size:16px;letter-spacing:-.01em;line-height:1.3}
.point-b{color:var(--ink);margin-top:.1em}

/* archive — clean ledger, no cards */
.arch{margin:.4em 0}
.arch-item{display:grid;grid-template-columns:118px 1fr auto;gap:18px;align-items:baseline;
 padding:15px 0;border-bottom:1px solid var(--line)}
.arch-item:hover .arch-title{color:var(--accent)}
.arch-more{display:inline-block;margin-top:18px;font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--accent)}
.arch-more:hover{text-decoration:underline;text-underline-offset:3px}
.arch-date{font-family:var(--mono);font-size:11px;color:var(--muted);white-space:nowrap}
.arch-title{font-family:var(--serif);font-size:19px;line-height:1.2}
.arch-engine{font-family:var(--mono);font-size:9.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);white-space:nowrap}

/* two columns (timeline + mix) */

/* bars */
/* catalyst category-mix: one wide row of cells across the full width, above the timeline */
.catmix{display:flex;gap:22px;margin:4px 0 22px}
.catmix-cell{flex:1;min-width:0}
.catmix-top{display:flex;justify-content:space-between;align-items:baseline;font-size:13.5px;margin-bottom:6px}
.catmix-name{color:var(--muted)}
.catmix-val{font-family:var(--mono);font-weight:600}
.catmix-bar{display:block;height:6px;background:var(--line);border-radius:2px;overflow:hidden}
.catmix-fill{display:block;height:100%}
.catmix-fill.reg{background:var(--c-reg)}.catmix-fill.earn{background:var(--c-earn)}
.catmix-fill.conf{background:var(--c-conf)}.catmix-fill.other{background:var(--c-other)}
@media(max-width:560px){.catmix{flex-wrap:wrap;gap:16px 22px}.catmix-cell{flex:1 1 40%}}

/* markets (clean table — matches the email) */
.mkt-table{width:100%;border-collapse:collapse;margin-top:2px}
.mkt-table td{padding:8px 0;border-bottom:1px solid var(--line);font-size:14px;vertical-align:baseline}
.mkt-name{width:60%}
.tkr{font-family:var(--mono);color:var(--muted);font-size:11px}
.mkt-last{text-align:right;font-family:var(--mono);font-size:12.5px;color:var(--muted);white-space:nowrap}
.mkt-pct{text-align:right;font-family:var(--mono);font-size:12.5px;white-space:nowrap;padding-left:16px}
.mkt-pct.up{color:var(--up)}.mkt-pct.down{color:var(--down)}.mkt-pct.flat{color:var(--muted)}

/* catalysts (clean grouped table — matches the email) */
.cat-wrap{margin-top:2px}
.cat-group{font-family:var(--mono);font-size:10.5px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:20px 0 4px}
.cat-wrap > .cat-group:first-child{margin-top:2px}
.cat-table{width:100%;border-collapse:collapse}
.cat-table td{padding:7px 0;border-bottom:1px solid var(--line);vertical-align:baseline}
.cat-table tr:last-child td{border-bottom:none}  /* avoid doubling the next section's rule */
/* td.cat-date beats the generic ".cat-table td" rule so the right padding (gap to the event) sticks */
.cat-table td.cat-date{font-family:var(--mono);font-size:12px;color:var(--muted);white-space:nowrap;padding-right:20px;width:1%}
.cat-text{font-size:14.5px}

/* footer */
footer{border-top:1px solid var(--line);margin-top:36px}
footer .bar{flex-direction:column;align-items:flex-start;gap:14px;padding:40px clamp(20px,5vw,40px) 64px}
.foot-nav{display:flex;gap:22px;flex-wrap:wrap}
.foot-nav a{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}
.foot-nav a:hover{color:var(--accent)}
.foot-src{font-size:13px;color:var(--muted)}
.foot-src a{border-bottom:1px solid var(--line)}
.foot-src a:hover{color:var(--accent);border-bottom-color:var(--accent)}
.foot-built{font-family:var(--mono);font-size:11px;color:var(--muted)}.foot-built time{color:var(--ink)}

/* responsive: drop the gutter, stack */
@media(max-width:680px){
 .block{padding:38px 0}
 .arch-item{grid-template-columns:1fr auto;gap:4px 14px}
 .arch-date{grid-column:1/-1}
}

/* dark — deep ink-black canvas, soft off-white text */
/* dark mode is toggleable via the settings gear (html.dark); "Auto" follows the OS */
html.dark{--paper:#0b0c10;--ink:#e2e8f0;--muted:#8a91a0;--line:#20232c;--accent:#86b3ad;
 --c-reg:#86b3ad;--c-earn:#c1948b;--c-conf:#bd9bb1;--c-other:#b9baa3;--up:#86b3ad;--down:#cf9087;--major:#d39b91;}
html.dark ::selection{background:var(--accent);color:#0b0c10}
/* settings gear + drawer */
.gear{width:30px;height:30px;border-radius:50%;border:1px solid var(--line);background:transparent;color:var(--ink);
 font-size:15px;cursor:pointer;display:flex;align-items:center;justify-content:center;line-height:1;padding:0}
.gear:hover{border-color:var(--accent);color:var(--accent);transform:rotate(40deg);transition:transform .2s}
.drawer-bg{position:fixed;inset:0;background:rgba(10,11,16,.4);z-index:50;opacity:0;pointer-events:none;transition:opacity .2s}
.drawer-bg.open{opacity:1;pointer-events:auto}
.drawer{position:fixed;top:0;right:0;height:100%;width:300px;max-width:86vw;background:var(--paper);
 border-left:1px solid var(--line);z-index:60;transform:translateX(100%);transition:transform .24s ease;
 padding:24px 24px 48px;overflow-y:auto;box-shadow:-12px 0 40px rgba(0,0,0,.12)}
.drawer.open{transform:none}
.drawer .dtitle{font-family:var(--serif);font-size:24px;font-weight:700;margin:0 0 2px}
.drawer h4{font-family:var(--mono);text-transform:uppercase;letter-spacing:.16em;font-size:10px;color:var(--muted);margin:24px 0 8px}
.drawer a,.drawer button.opt{display:block;width:100%;text-align:left;background:none;border:none;
 font-family:var(--sans);font-size:14.5px;color:var(--ink);padding:7px 0;cursor:pointer}
.drawer a:hover,.drawer button.opt:hover{color:var(--accent)}
.drawer .close{position:absolute;top:16px;right:18px;border:none;background:none;font-size:22px;color:var(--muted);cursor:pointer;line-height:1}
.seg{display:flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin:2px 0}
.seg button{flex:1;background:none;border:none;padding:9px 0;font-family:var(--mono);font-size:11px;
 text-transform:uppercase;letter-spacing:.06em;color:var(--muted);cursor:pointer}
.seg button.sel{background:var(--accent);color:#fff}
"""


if __name__ == "__main__":
    build()
