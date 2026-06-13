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
import json
import html
import datetime as dt
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGESTS = ROOT / "digests"
CATALYSTS = ROOT / "pharma-news" / "catalysts.md"
OUT = ROOT / "site" / "public"

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}

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
    gnews = "news.google.com" in url
    cls = "src gnews" if gnews else "src"
    title = ' title="Opens via the Google News aggregator — may redirect or be region-blocked"' if gnews else ""
    return f'<a href="{url}" target="_blank" rel="noopener" class="{cls}"{title}>{label}</a>'


def md_inline(text: str) -> str:
    text = html.escape(text)
    # Drop "[catalysts.md]"-style markers (internal files cited as if sources); the
    # lookahead spares real "[label.md](url)" links.
    text = re.sub(r"\s*\[[^\[\]]*\.md\](?!\()", "", text, flags=re.I)
    # Tolerate a stray space in links the model sometimes writes as "[text] (https://…)";
    # collapse it only before a URL so citations like "[1] (a note)" stay plain text.
    text = re.sub(r"\]\s+\((?=https?://)", "](", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _mk_link, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    if _SRCMAP:
        text = re.sub(r"\[(\d+)\]", lambda m: (
            f'<a class="cite" href="{_SRCMAP[m.group(1)]}" target="_blank" rel="noopener">[{m.group(1)}]</a>'
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


def renumber_sources(md: str) -> str:
    """DeepSeek cites sources by their position in the fetched feed (gappy, out of order).
    Renumber to 1,2,3… in the order the [n] citations first appear in the body, reorder the
    Sources list to match, and rewrite the inline citations. Uncited sources are appended
    after the cited ones, in their original order."""
    lines = md.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip().lower().startswith("## sources")), None)
    if start is None:
        return md
    end, src, list_order = len(lines), {}, []
    for i in range(start + 1, len(lines)):
        m = re.match(r"^(\d+)\.(\s.*)$", lines[i])
        if m:
            src[m.group(1)] = m.group(2)
            list_order.append(m.group(1))
        elif lines[i].strip() == "":
            continue
        else:                       # first non-source line (e.g. footer rule) ends the list
            end = i
            break
    if not src:
        return md
    body = "\n".join(lines[:start])
    order, seen = [], set()
    for n in re.findall(r"\[(\d+)\]", body):        # citation order of first appearance
        if n in src and n not in seen:
            order.append(n); seen.add(n)
    for n in list_order:                            # then any uncited sources
        if n not in seen:
            order.append(n); seen.add(n)
    mapping = {old: str(i + 1) for i, old in enumerate(order)}
    body = re.sub(r"\[(\d+)\]", lambda mm: "[" + mapping.get(mm.group(1), mm.group(1)) + "]", body)
    rebuilt = [lines[start]] + [f"{mapping[old]}.{src[old]}" for old in order]
    tail = lines[end:]
    if tail:
        rebuilt += [""] + tail
    return body + "\n" + "\n".join(rebuilt)


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


def _parse_srcmap(md: str) -> dict:
    smap = {}
    for l in md.splitlines():
        m = re.match(r"^\s*(\d+)\.\s*\[[^\]]+\]\((https?://[^)\s]+)\)", l)
        if m:
            smap[m.group(1)] = m.group(2)
    return smap


def render_digest(md: str) -> str:
    """Full digest -> HTML: renumber sources, link headlines, and make inline [n] citations clickable."""
    global _SRCMAP
    md = renumber_sources(md)
    _SRCMAP = _parse_srcmap(md)
    out = md_to_html(link_headings(md))
    _SRCMAP = {}
    return out


def company_anchors(md: str, keymap: dict) -> dict:
    """Map each ticker to the anchor of the digest section that mentions it — a Top Story
    (#sN) if possible, else a ## section — so a markets note jumps straight to it."""
    stories, sections, cur, h3n = [], [], None, 0
    for l in md.splitlines():
        if l.startswith("### "):
            h3n += 1; stories.append([f"s{h3n}", strip_lead(l[4:])]); cur = ("S", len(stories) - 1)
        elif l.startswith("## "):
            t = strip_lead(l[3:]); sections.append([_slug(t), t]); cur = ("H", len(sections) - 1)
        elif l.startswith("# "):
            cur = None
        elif cur:
            (stories if cur[0] == "S" else sections)[cur[1]][1] += " " + l
    out = {}
    for tk, kw in keymap.items():
        kw = kw.lower()
        out[tk] = next((s[0] for s in stories if kw in s[1].lower()),
                       next((s[0] for s in sections if kw in s[1].lower()), None))
    return out


# ----------------------------------------------------------------------------- #
#  Catalyst timeline
# ----------------------------------------------------------------------------- #
def parse_catalysts() -> list[dict]:
    if not CATALYSTS.exists():
        return []
    events = []
    for line in CATALYSTS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \*\*(.+?)\*\* · (.+)$", line.strip())
        if not m:
            continue
        datestr, desc = m.group(1), m.group(2)
        short = re.split(r" — ", desc)[0].strip()
        when = None
        iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", datestr)
        if iso:
            try:
                when = dt.date(int(iso[1]), int(iso[2]), int(iso[3]))
            except ValueError:
                when = None
        else:
            mon = re.search(r"([A-Za-z]{3})[a-z]*\s+(\d{4})", datestr)
            if mon and mon.group(1).lower() in MONTHS:
                when = dt.date(int(mon.group(2)), MONTHS[mon.group(1).lower()], 15)
        if when:
            events.append({"date": when, "label": short, "full": desc})
    return sorted(events, key=lambda e: e["date"])


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


def render_timeline(events: list[dict]) -> str:
    if not events:
        return '<p class="muted">No dated catalysts on file yet.</p>'
    today = dt.date.today()
    labels = ["Next 30 days", "1–3 months", "On the horizon"]

    def bucket(d):
        delta = (d - today).days
        return 0 if delta <= 30 else (1 if delta <= 90 else 2)

    groups = {0: [], 1: [], 2: []}
    for e in events:
        groups[bucket(e["date"])].append(e)

    parts = []
    for gi in (0, 1, 2):
        if not groups[gi]:
            continue
        parts.append(f'<div class="vtl-group">{labels[gi]}</div><ol class="vtl">')
        for e in groups[gi]:
            cat = _category(e["full"])
            d = e["date"].strftime("%-d %b %Y")
            parts.append(
                f'<li class="vtl-item {cat}"><span class="vtl-dot"></span>'
                f'<span class="vtl-date">{d}</span>'
                f'<span class="vtl-text" title="{html.escape(e["full"])}">{html.escape(e["label"])}</span></li>')
        parts.append("</ol>")
    legend = ('<div class="vtl-legend">'
              + "".join(f'<span class="lg {k}">{v}</span>' for k, v in _CAT_NAMES.items())
              + "</div>")
    return '<div class="vtl-wrap">' + "".join(parts) + "</div>" + legend


def render_catalyst_mix(events: list[dict]) -> str:
    if not events:
        return ""
    counts: dict[str, int] = {}
    for e in events:
        c = _category(e["full"])
        counts[c] = counts.get(c, 0) + 1
    total = max(sum(counts.values()), 1)
    bars = []
    for k in ("reg", "earn", "conf", "other"):
        n = counts.get(k, 0)
        if not n:
            continue
        pct = round(n / total * 100)
        bars.append(
            f'<div class="bar-row"><span class="bar-name">{_CAT_NAMES[k]}</span>'
            f'<span class="bar-track"><span class="bar-fill {k}" style="width:{pct}%"></span></span>'
            f'<span class="bar-val">{n}</span></div>')
    return '<div class="barchart">' + "".join(bars) + "</div>"


# ----------------------------------------------------------------------------- #
#  Markets (real prices, free Yahoo Finance endpoint — no key, no fake data)
# ----------------------------------------------------------------------------- #
MARKET_TICKERS = [
    ("LLY", "Eli Lilly"), ("NVO", "Novo Nordisk"), ("PFE", "Pfizer"),
    ("AZN", "AstraZeneca"), ("MRK", "Merck"), ("NVS", "Novartis"),
    ("GSK", "GSK"), ("AMGN", "Amgen"), ("ABBV", "AbbVie"), ("JNJ", "J&J"),
]

# Companies added to the markets strip ONLY when today's digest covers them (semi-dynamic).
EXTRA_TICKERS = {
    "summit": ("SMMT", "Summit Therapeutics"), "viking": ("VKTX", "Viking"),
    "biontech": ("BNTX", "BioNTech"), "moderna": ("MRNA", "Moderna"),
    "roche": ("RHHBY", "Roche"), "sanofi": ("SNY", "Sanofi"),
    "takeda": ("TAK", "Takeda"), "gilead": ("GILD", "Gilead"),
    "regeneron": ("REGN", "Regeneron"), "vertex": ("VRTX", "Vertex"),
    "bristol": ("BMY", "Bristol Myers"), "incyte": ("INCY", "Incyte"),
    "bayer": ("BAYRY", "Bayer"), "biogen": ("BIIB", "Biogen"),
}


def fetch_market(tickers: list) -> list[dict]:
    out = []
    for t, name in tickers:
        try:
            req = urllib.request.Request(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5d&interval=1d",
                headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=15).read())
            closes = [c for c in d["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 2:
                out.append({"t": t, "name": name,
                            "pct": (closes[-1] / closes[0] - 1) * 100, "last": closes[-1]})
        except Exception:
            continue
    return out


def render_market(data: list[dict], anchors: dict | None = None) -> str:
    if not data:
        return ""
    anchors = anchors or {}
    data = sorted(data, key=lambda x: x["pct"], reverse=True)
    mx = max((abs(x["pct"]) for x in data), default=1) or 1
    rows = []
    for x in data:
        cls = "up" if x["pct"] >= 0 else "down"
        sign = "+" if x["pct"] >= 0 else ""
        w = round(abs(x["pct"]) / mx * 100)
        # Only a hedged, sourced CORRELATION note (links to the specific story) — never causation, never a forecast.
        a = anchors.get(x["t"])
        note = (f'<div class="mkt-note">· may relate to '
                f'<a href="#{a}">today&rsquo;s coverage of {html.escape(x["name"])}</a></div>'
                if a else "")
        rows.append(
            '<div class="mkt-item"><div class="mkt-row">'
            f'<span class="mkt-name">{html.escape(x["name"])} <span class="tkr">{x["t"]}</span></span>'
            f'<span class="mkt-bar"><span class="mkt-fill {cls}" style="width:{w}%"></span></span>'
            f'<span class="mkt-pct {cls}">{sign}{x["pct"]:.1f}%</span></div>' + note + "</div>")
    return '<div class="market">' + "".join(rows) + "</div>"


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


def page(title: str, body: str, home_link: bool = True, repo_url: str = "") -> str:
    base = "index.html" if home_link else ""
    nav = "".join(f'<a href="{base}#{i}">{n}</a>'
                  for i, n in [("latest", "Latest"), ("upcoming", "Catalysts"),
                               ("markets", "Markets"), ("archive", "Archive")])
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
</head><body>{drawer}{topbar}<main>{inner}</main>{footer}
<script src="settings.js"></script></body></html>"""


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
    try{t.textContent=d.toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short'});}
    catch(e){t.textContent=d.toLocaleString();}
  });
})();"""


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    repo_url = get_repo_url()
    files = sorted([p for p in DIGESTS.glob("*.md") if p.stem != "INDEX"], reverse=True)
    pub = load_published()

    arch_items, search_index = [], []
    for p in files:
        md = p.read_text(encoding="utf-8")
        m = meta_of(md)
        slug = p.stem + ".html"
        (OUT / slug).write_text(
            page(m["title"], with_published(render_digest(md), p.stem, pub.get(p.stem)), repo_url=repo_url),
            encoding="utf-8")
        engine = m["engine"]
        short_title = m["title"].split("—")[-1].strip()
        arch_items.append(
            f'<a class="arch-item" href="{slug}"><span class="arch-date">{html.escape(p.stem)}</span>'
            f'<span class="arch-title">{html.escape(short_title)}</span>'
            f'<span class="arch-engine">{html.escape(engine)}</span></a>')
        search_index.append({"slug": slug, "date": p.stem, "title": html.escape(short_title),
                             "engine": html.escape(engine), "text": plain_text(md)[:4000]})

    events = parse_catalysts()
    timeline, mix = render_timeline(events), render_catalyst_mix(events)
    latest_md = files[0].read_text(encoding="utf-8") if files else ""
    latest_html = (with_published(render_digest(latest_md), files[0].stem, pub.get(files[0].stem))
                   if files else '<p class="muted">No digests yet.</p>')
    _key = {"LLY": "lilly", "NVO": "novo", "PFE": "pfizer", "AZN": "astrazeneca", "MRK": "merck",
            "NVS": "novartis", "GSK": "gsk", "AMGN": "amgen", "ABBV": "abbvie", "JNJ": "j&j"}
    _dt = plain_text(latest_md).lower()
    tickers, have, full_key = list(MARKET_TICKERS), {t for t, _ in MARKET_TICKERS}, dict(_key)
    for kw, (tk, nm) in EXTRA_TICKERS.items():
        if kw in _dt and tk not in have:
            tickers.append((tk, nm)); have.add(tk); full_key[tk] = kw
    anchors = company_anchors(renumber_sources(latest_md), full_key)
    market_html = render_market(fetch_market(tickers), anchors)
    market_block = (
        '<section class="block" id="markets"><div class="block-label">Markets</div><div class="block-body">'
        + market_html + '<p class="meta">Source: Yahoo Finance, end-of-day prices. Not investment advice.</p>'
        + "</div></section>"
    ) if market_html else ""
    arch_html = "".join(arch_items) if arch_items else '<p class="muted">No digests yet.</p>'

    index_body = f"""
<div id="searchbar" class="searchbar" hidden><input id="q" type="search" placeholder="Search the archive..." autocomplete="off"></div>
<header class="masthead">
  <div class="kicker">Daily Pharmaceutical Intelligence</div>
  <h1 class="brand">Pharma Morning Brief</h1>
  <p class="tagline">Balanced, fact-checked &mdash; in the time it takes to drink a coffee.</p>
</header>
<div id="results" style="display:none"></div>
<section class="block" id="latest"><div class="block-label">Latest</div><div class="block-body">{latest_html}</div></section>
<section class="block" id="upcoming"><div class="block-label">Catalysts</div><div class="block-body">
  <div class="two-col"><div>{timeline}</div><div><div class="sub-h">Catalyst mix</div>{mix}</div></div>
</div></section>
{market_block}
<section class="block" id="archive"><div class="block-label">Archive</div><div class="block-body"><div class="arch">{arch_html}</div></div></section>
<section class="block" id="about"><div class="block-label">About</div><div class="block-body">
  <p><strong>Pharma Morning Brief</strong> turns the day's pharmaceutical news into a fact-checked, 2-3 minute executive digest &mdash; for someone entering pharma who needs to stay current without reading 20 outlets every morning.</p>
  <p>One shared editorial standard runs through two interchangeable engines &mdash; <em>Claude</em> (richest analysis, on demand) and <em>DeepSeek</em> (lean, automatic in the cloud each morning). Every fact is grounded in a real, linked source; niche terms are glossed in plain language; each issue is labelled with the engine that wrote it.</p>
</div></section>
<script src="search-data.js"></script><script src="search.js"></script>"""
    (OUT / "index.html").write_text(page("Pharma Morning Brief", index_body, home_link=False, repo_url=repo_url), encoding="utf-8")
    (OUT / "style.css").write_text(CSS, encoding="utf-8")
    (OUT / "search-data.js").write_text("window.DIGESTS=" + json.dumps(search_index) + ";", encoding="utf-8")
    (OUT / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    (OUT / "settings.js").write_text(SETTINGS_JS, encoding="utf-8")
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
a.gnews::after{content:"↗";font-size:.72em;color:var(--muted);margin-left:1px;vertical-align:super}
h2.major a,h3.major a,h2.major,h3.major{color:var(--major) !important}
.major-tag{font-family:var(--mono);text-transform:uppercase;letter-spacing:.16em;font-size:10px;color:var(--major);margin:0 0 5px}
a.cite{border-bottom:none;color:var(--accent);font-weight:600;font-size:.82em;padding:0 1px}
a.cite:hover{text-decoration:underline;text-underline-offset:2px}
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
.arch-date{font-family:var(--mono);font-size:11px;color:var(--muted);white-space:nowrap}
.arch-title{font-family:var(--serif);font-size:19px;line-height:1.2}
.arch-engine{font-family:var(--mono);font-size:9.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);white-space:nowrap}

/* two columns (timeline + mix) */
.two-col{display:grid;grid-template-columns:1.5fr 1fr;gap:40px;align-items:start}
@media(max-width:640px){.two-col{grid-template-columns:1fr;gap:24px}}

/* timeline */
.vtl-group{font-family:var(--mono);font-size:10.5px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:18px 0 4px}
.vtl-wrap > .vtl-group:first-child{margin-top:2px}
.vtl{list-style:none;margin:4px 0;padding:0}
.vtl-item{position:relative;padding:8px 0 8px 24px;border-left:1px solid var(--line)}
.vtl-item:last-child{border-left-color:transparent}
.vtl-dot{position:absolute;left:-5px;top:13px;width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px var(--paper)}
.vtl-item.reg .vtl-dot{background:var(--c-reg)}.vtl-item.earn .vtl-dot{background:var(--c-earn)}
.vtl-item.conf .vtl-dot{background:var(--c-conf)}.vtl-item.other .vtl-dot{background:var(--c-other)}
.vtl-date{display:inline-block;min-width:104px;font-family:var(--mono);font-size:12px;margin-right:8px}
.vtl-text{font-size:14.5px}
.vtl-legend{display:flex;gap:16px;flex-wrap:wrap;margin-top:14px;font-size:11.5px;color:var(--muted)}
.vtl-legend .lg{display:flex;align-items:center;gap:6px}
.vtl-legend .lg::before{content:"";width:9px;height:9px;border-radius:50%;display:inline-block}
.vtl-legend .reg::before{background:var(--c-reg)}.vtl-legend .earn::before{background:var(--c-earn)}
.vtl-legend .conf::before{background:var(--c-conf)}.vtl-legend .other::before{background:var(--c-other)}
@media(max-width:560px){.vtl-date{display:block;min-width:0}}

/* bars */
.barchart{margin-top:2px}
.bar-row{display:flex;align-items:center;gap:10px;margin:10px 0;font-size:13px}
.bar-name{min-width:84px;color:var(--muted)}
.bar-track{flex:1;height:6px;background:var(--line);border-radius:2px;overflow:hidden}
.bar-fill{display:block;height:100%}
.bar-fill.reg{background:var(--c-reg)}.bar-fill.earn{background:var(--c-earn)}
.bar-fill.conf{background:var(--c-conf)}.bar-fill.other{background:var(--c-other)}
.bar-val{min-width:18px;text-align:right;font-family:var(--mono);font-size:12px}

/* markets */
.market{margin-top:2px}
.mkt-item{margin:11px 0}
.mkt-row{display:flex;align-items:center;gap:12px;margin:0;font-size:14px}
.mkt-note{font-size:12px;color:var(--muted);margin:3px 0 0;padding-left:2px}
.mkt-note a{border-bottom:1px solid var(--line)}
.mkt-note a:hover{color:var(--accent);border-bottom-color:var(--accent)}
.mkt-name{flex:0 0 190px}
.tkr{font-family:var(--mono);color:var(--muted);font-size:11px}
.mkt-bar{flex:1;height:6px;background:var(--line);border-radius:2px;overflow:hidden}
.mkt-fill{display:block;height:100%}
.mkt-fill.up{background:var(--up)}.mkt-fill.down{background:var(--down)}
.mkt-pct{flex:0 0 56px;text-align:right;font-family:var(--mono);font-size:12.5px}
.mkt-pct.up{color:var(--up)}.mkt-pct.down{color:var(--down)}
@media(max-width:560px){.mkt-name{flex-basis:120px}}

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
html.dark .vtl-dot{box-shadow:0 0 0 4px var(--paper)}
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
