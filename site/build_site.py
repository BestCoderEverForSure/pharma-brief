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


def md_inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def md_to_html(md: str) -> str:
    out, items, in_quote = [], [], False

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
            flush_list(); close_quote(); out.append(f"<h3>{md_inline(strip_lead(line[4:]))}</h3>")
        elif line.startswith("## "):
            flush_list(); close_quote(); out.append(f"<h2>{md_inline(strip_lead(line[3:]))}</h2>")
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


def render_market(data: list[dict]) -> str:
    if not data:
        return ""
    data = sorted(data, key=lambda x: x["pct"], reverse=True)
    mx = max((abs(x["pct"]) for x in data), default=1) or 1
    rows = []
    for x in data:
        cls = "up" if x["pct"] >= 0 else "down"
        sign = "+" if x["pct"] >= 0 else ""
        w = round(abs(x["pct"]) / mx * 100)
        rows.append(
            '<div class="mkt-row">'
            f'<span class="mkt-name">{html.escape(x["name"])} <span class="tkr">{x["t"]}</span></span>'
            f'<span class="mkt-bar"><span class="mkt-fill {cls}" style="width:{w}%"></span></span>'
            f'<span class="mkt-pct {cls}">{sign}{x["pct"]:.1f}%</span></div>')
    return '<div class="market">' + "".join(rows) + "</div>"


# ----------------------------------------------------------------------------- #
#  Page assembly
# ----------------------------------------------------------------------------- #
def page(title: str, body: str, home_link: bool = True) -> str:
    base = "index.html" if home_link else ""
    nav = "".join(f'<a href="{base}#{i}">{n}</a>'
                  for i, n in [("latest", "Latest"), ("upcoming", "Catalysts"),
                               ("markets", "Markets"), ("archive", "Archive")])
    src = ", ".join(f'<a href="{u}" target="_blank" rel="noopener">{n}</a>' for n, u in SOURCES)
    topbar = (f'<header class="topbar"><a class="wordmark" href="index.html">Pharma Morning Brief</a>'
              f'<nav class="topnav">{nav}</nav></header>')
    inner = f'<article class="doc">{body}</article>' if home_link else body
    footer = (f'<footer><div class="foot-nav">{nav}</div>'
              f'<div class="foot-src">Sources monitored &mdash; {src}</div></footer>')
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="style.css">
</head><body>{topbar}<main>{inner}</main>{footer}</body></html>"""


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


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in DIGESTS.glob("*.md") if p.stem != "INDEX"], reverse=True)

    arch_items, search_index = [], []
    for p in files:
        md = p.read_text(encoding="utf-8")
        m = meta_of(md)
        slug = p.stem + ".html"
        (OUT / slug).write_text(page(m["title"], md_to_html(md)), encoding="utf-8")
        engine = m["engine"]
        short_title = m["title"].split("—")[-1].strip()
        arch_items.append(
            f'<a class="arch-item" href="{slug}"><span class="arch-date">{html.escape(p.stem)}</span>'
            f'<span class="arch-title">{html.escape(short_title)}</span>'
            f'<span class="arch-engine">{html.escape(engine)}</span></a>')
        search_index.append({"slug": slug, "date": p.stem, "title": html.escape(short_title),
                             "engine": engine, "text": plain_text(md)[:4000]})

    events = parse_catalysts()
    timeline, mix = render_timeline(events), render_catalyst_mix(events)
    latest_html = md_to_html(files[0].read_text(encoding="utf-8")) if files else '<p class="muted">No digests yet.</p>'
    market_html = render_market(fetch_market(MARKET_TICKERS))
    market_block = (
        '<section class="block" id="markets"><div class="block-label">Markets</div><div class="block-body">'
        + market_html + '<p class="meta">Source: Yahoo Finance, end-of-day prices. Not investment advice.</p>'
        + "</div></section>"
    ) if market_html else ""
    arch_html = "".join(arch_items) if arch_items else '<p class="muted">No digests yet.</p>'

    index_body = f"""
<header class="masthead">
  <div class="kicker">Daily Pharmaceutical Intelligence</div>
  <h1 class="brand">Pharma Morning Brief</h1>
  <p class="tagline">Balanced, fact-checked &mdash; in the time it takes to drink a coffee.</p>
  <input id="q" class="search" type="search" placeholder="Search the archive...">
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
    (OUT / "index.html").write_text(page("Pharma Morning Brief", index_body, home_link=False), encoding="utf-8")
    (OUT / "style.css").write_text(CSS, encoding="utf-8")
    (OUT / "search-data.js").write_text("window.DIGESTS=" + json.dumps(search_index) + ";", encoding="utf-8")
    (OUT / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    print(f"Site built ✓  ({len(files)} digests)  -> {OUT / 'index.html'}")


CSS = """
:root{
 --paper:#f4f2ec;--ink:#17181c;--muted:#7c7a70;--line:#e3dfd4;--accent:#466362;
 --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
 --sans:"Avenir Next","Avenir","Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
 --mono:"SF Mono",ui-monospace,Menlo,Consolas,monospace;
 --c-reg:#466362;--c-earn:#8b635c;--c-conf:#9e768f;--c-other:#9aa08c;--up:#466362;--down:#8b635c;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
 font-size:17px;line-height:1.72;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;}
a{color:inherit;text-decoration:none}
::selection{background:var(--accent);color:#fff}

/* top bar */
.topbar{position:sticky;top:0;z-index:20;display:flex;justify-content:space-between;align-items:center;
 gap:20px;padding:13px clamp(20px,5vw,60px);background:color-mix(in srgb,var(--paper) 88%,transparent);
 backdrop-filter:saturate(140%) blur(8px);border-bottom:1px solid var(--line)}
.wordmark{font-family:var(--serif);font-weight:700;font-size:16px;letter-spacing:-.01em}
.topnav{display:flex;gap:20px}
.topnav a{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}
.topnav a:hover{color:var(--accent)}

main{max-width:1180px;margin:0 auto;padding:0 clamp(20px,5vw,60px)}

/* masthead */
.masthead{padding:64px 0 30px;border-bottom:1px solid var(--ink)}
.kicker{font-family:var(--mono);text-transform:uppercase;letter-spacing:.28em;font-size:11px;color:var(--accent);margin-bottom:18px}
.brand{font-family:var(--serif);font-weight:700;font-size:clamp(46px,8vw,82px);line-height:.98;letter-spacing:-.02em;margin:0}
.tagline{font-family:var(--serif);font-style:italic;color:var(--muted);font-size:clamp(17px,2.4vw,21px);margin:.55em 0 0;max-width:34ch}
.search{margin-top:26px;width:min(360px,100%);padding:9px 2px;border:none;border-bottom:1px solid var(--line);
 background:transparent;color:var(--ink);font-family:var(--sans);font-size:15px}
.search:focus{outline:none;border-bottom-color:var(--accent)}
.search::placeholder{color:var(--muted)}

/* editorial blocks: label gutter + content + breathing right margin */
.block{display:grid;grid-template-columns:130px minmax(0,720px) 1fr;gap:44px;
 padding:54px 0;border-top:1px solid var(--line)}
.block:first-of-type{border-top:none}
.block-label{grid-column:1;font-family:var(--mono);text-transform:uppercase;letter-spacing:.16em;
 font-size:11px;color:var(--muted);padding-top:6px}
.block-body{grid-column:2;min-width:0}
.sub-h{font-family:var(--mono);text-transform:uppercase;letter-spacing:.12em;font-size:10.5px;color:var(--muted);margin:0 0 8px}

/* typography */
h1{font-family:var(--serif);font-weight:700;font-size:clamp(30px,4.6vw,44px);line-height:1.08;letter-spacing:-.015em;margin:0 0 .35em}
h2{font-family:var(--serif);font-weight:700;font-size:26px;line-height:1.15;margin:1.7em 0 .5em}
h3{font-family:var(--serif);font-weight:700;font-size:20px;line-height:1.2;margin:1.5em 0 .35em}
p{margin:.75em 0}
.doc{max-width:720px;margin:0 auto;padding:56px 0 20px}
.doc a,.block-body p a,.point-b a{border-bottom:1px solid color-mix(in srgb,var(--accent) 40%,transparent)}
.doc a:hover,.block-body p a:hover{border-bottom-color:var(--accent)}
.muted{color:var(--muted)}
.meta{font-family:var(--mono);font-size:11.5px;letter-spacing:.02em;color:var(--muted);text-transform:none;margin:.4em 0 1.4em}
strong{font-weight:700}
em{font-style:italic}
hr{border:none;border-top:1px solid var(--line);margin:2.4em 0}
code{font-family:var(--mono);font-size:.82em;color:var(--accent);background:transparent;padding:0}

/* the lead "talking point" */
.lede{margin:1.6em 0;padding:1.15em 0;border-top:1px solid var(--ink);border-bottom:1px solid var(--ink)}
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
.mkt-row{display:flex;align-items:center;gap:12px;margin:10px 0;font-size:14px}
.mkt-name{flex:0 0 190px}
.tkr{font-family:var(--mono);color:var(--muted);font-size:11px}
.mkt-bar{flex:1;height:6px;background:var(--line);border-radius:2px;overflow:hidden}
.mkt-fill{display:block;height:100%}
.mkt-fill.up{background:var(--up)}.mkt-fill.down{background:var(--down)}
.mkt-pct{flex:0 0 56px;text-align:right;font-family:var(--mono);font-size:12.5px}
.mkt-pct.up{color:var(--up)}.mkt-pct.down{color:var(--down)}
@media(max-width:560px){.mkt-name{flex-basis:120px}}

/* footer */
footer{max-width:1180px;margin:0 auto;padding:46px clamp(20px,5vw,60px) 70px;border-top:1px solid var(--ink)}
.foot-nav{display:flex;gap:22px;flex-wrap:wrap;margin-bottom:14px}
.foot-nav a{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}
.foot-nav a:hover{color:var(--accent)}
.foot-src{font-size:13px;color:var(--muted)}
.foot-src a{border-bottom:1px solid var(--line)}
.foot-src a:hover{color:var(--accent);border-bottom-color:var(--accent)}

/* responsive: drop the gutter, stack */
@media(max-width:760px){
 .block{grid-template-columns:1fr;gap:14px;padding:38px 0}
 .block-label{grid-column:1}.block-body{grid-column:1}
 .arch-item{grid-template-columns:1fr auto;gap:4px 14px}
 .arch-date{grid-column:1/-1}
 .topnav{display:none}
}

/* dark — deep ink-black canvas, soft off-white text */
@media (prefers-color-scheme: dark){
 :root{--paper:#0b0c10;--ink:#e2e8f0;--muted:#8a91a0;--line:#20232c;--accent:#86b3ad;
  --c-reg:#86b3ad;--c-earn:#c1948b;--c-conf:#bd9bb1;--c-other:#b9baa3;--up:#86b3ad;--down:#cf9087;}
 .vtl-dot{box-shadow:0 0 0 4px var(--paper)}
 ::selection{background:var(--accent);color:#0b0c10}
}
"""


if __name__ == "__main__":
    build()
