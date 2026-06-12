#!/usr/bin/env python3
"""
Build a static website from the saved digests.

- Renders every digests/*.md into a styled HTML page.
- Builds an archive index (newest first) with engine badges.
- Draws a visual "Week Ahead" catalyst timeline (SVG) from pharma-news/catalysts.md
  — using only real, dated catalysts (no invented data).

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

# ----------------------------------------------------------------------------- #
#  Markdown -> HTML (the subset our digests use)
# ----------------------------------------------------------------------------- #
_LEAD_EMOJI = re.compile(r"^[\U0001F000-\U0001FAFF☀-➿←-⇿⬀-⯿ℹ️⃣]+\s*")


def strip_lead(s: str) -> str:
    """Remove a leading emoji/icon from heading or quote text (less 'AI-generated' look)."""
    return _LEAD_EMOJI.sub("", s)


def md_inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def md_to_html(md: str) -> str:
    out, in_list, in_quote = [], False, False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>"); in_list = False

    def close_quote():
        nonlocal in_quote
        if in_quote:
            out.append("</blockquote>"); in_quote = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            close_list(); close_quote(); continue
        if line.startswith("### "):
            close_list(); close_quote(); out.append(f"<h3>{md_inline(strip_lead(line[4:]))}</h3>")
        elif line.startswith("## "):
            close_list(); close_quote(); out.append(f"<h2>{md_inline(strip_lead(line[3:]))}</h2>")
        elif line.startswith("# "):
            close_list(); close_quote(); out.append(f"<h1>{md_inline(strip_lead(line[2:]))}</h1>")
        elif line.strip() in ("---", "***", "___"):
            close_list(); close_quote(); out.append("<hr>")
        elif line.startswith("> "):
            close_list()
            if not in_quote:
                out.append("<blockquote>"); in_quote = True
            out.append(f"<p>{md_inline(strip_lead(line[2:]))}</p>")
        elif re.match(r"^[-*] ", line):
            close_quote()
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{md_inline(line[2:])}</li>")
        else:
            close_list(); close_quote(); out.append(f"<p>{md_inline(line)}</p>")
    close_list(); close_quote()
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
        short = re.split(r" — ", desc)[0].strip()  # split only on em-dash, not periods (keeps "J.P.")
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
    """Vertical, fully readable timeline (HTML) — no label overlap, color-coded."""
    if not events:
        return '<p class="muted">No dated catalysts on file yet.</p>'
    # One continuous timeline: near-term detail flowing into the longer horizon,
    # grouped by period so it reads cleanly without a hard cut-off.
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
    """Second graphic: a simple bar chart of upcoming catalysts by type."""
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
#  Markets chart (real prices, free Yahoo Finance endpoint — no key, no fake data)
# ----------------------------------------------------------------------------- #
MARKET_TICKERS = [
    ("LLY", "Eli Lilly"), ("NVO", "Novo Nordisk"), ("PFE", "Pfizer"),
    ("AZN", "AstraZeneca"), ("MRK", "Merck"), ("NVS", "Novartis"),
    ("GSK", "GSK"), ("AMGN", "Amgen"), ("ABBV", "AbbVie"), ("JNJ", "J&J"),
]


def fetch_market(tickers: list) -> list[dict]:
    """5-day % move per ticker from Yahoo Finance. Skips any that fail — never invents data."""
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
    nav = '<a class="back" href="index.html">← All digests</a>' if home_link else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="style.css">
</head><body><main>{nav}{body}</main>
<footer>💊 Pharma Morning News Aggregator · auto-generated archive</footer>
</body></html>"""


def meta_of(md: str) -> dict:
    title = next((l[2:].strip() for l in md.splitlines() if l.startswith("# ")), "Digest")
    sub = next((l for l in md.splitlines() if l.startswith("*Window")), "")
    eng = re.search(r"Engine:\s*([^·*]+)", sub)
    engine = eng.group(1).strip() if eng else "—"
    return {"title": title, "engine": engine}


def plain_text(md: str) -> str:
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)   # links -> their text
    t = re.sub(r"[#>*_`|]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


SEARCH_JS = """(function(){
  var input=document.getElementById('q'),
      results=document.getElementById('results'),
      archive=document.getElementById('archive');
  if(!input) return;
  input.addEventListener('input',function(){
    var q=input.value.trim().toLowerCase();
    if(!q){results.innerHTML='';results.style.display='none';if(archive)archive.style.display='';return;}
    if(archive)archive.style.display='none';results.style.display='';
    var hits=(window.DIGESTS||[]).filter(function(d){return (d.title+' '+d.text).toLowerCase().indexOf(q)>=0;});
    if(!hits.length){results.innerHTML='<section class="panel"><p class="muted">No matches.</p></section>';return;}
    results.innerHTML='<section class="panel"><h2>Search results</h2><div class="grid">'+hits.map(function(d){
      var i=d.text.toLowerCase().indexOf(q),
          s=i>=0?d.text.substr(Math.max(0,i-45),130):d.text.substr(0,130);
      return '<a class="card" href="'+d.slug+'"><div class="card-date">'+d.date+'</div>'+
        '<div class="card-title">'+d.title+'</div><div class="snip">…'+
        s.replace(/[<>]/g,' ')+'…</div></a>';}).join('')+'</div></section>';
  });
})();"""


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted([p for p in DIGESTS.glob("*.md") if p.stem != "INDEX"], reverse=True)

    cards, search_index = [], []
    for p in files:
        md = p.read_text(encoding="utf-8")
        m = meta_of(md)
        slug = p.stem + ".html"
        (OUT / slug).write_text(page(m["title"], md_to_html(md)), encoding="utf-8")
        engine = m["engine"]
        badge = "claude" if "claude" in engine.lower() else ("deepseek" if "deepseek" in engine.lower() else "other")
        short_title = m["title"].split("—")[-1].strip()
        cards.append(
            f'<a class="card" href="{slug}"><div class="card-date">{html.escape(p.stem)}</div>'
            f'<div class="card-title">{html.escape(short_title)}</div>'
            f'<span class="badge {badge}">{html.escape(engine)}</span></a>')
        search_index.append({"slug": slug, "date": p.stem, "title": html.escape(short_title),
                             "engine": engine, "text": plain_text(md)[:4000]})

    events = parse_catalysts()
    timeline, mix = render_timeline(events), render_catalyst_mix(events)
    latest_html = md_to_html(files[0].read_text(encoding="utf-8")) if files else '<p class="muted">No digests yet.</p>'
    market_html = render_market(fetch_market(MARKET_TICKERS))
    market_panel = (
        '<section class="panel" id="markets"><h2>Pharma markets &mdash; 5-day move</h2>' + market_html +
        '<p class="muted" style="font-size:11px;margin-top:10px">Source: Yahoo Finance, end-of-day prices. Not investment advice.</p></section>'
    ) if market_html else ""

    index_body = f"""
<header class="hero">
  <div class="kicker">Daily Pharmaceutical Intelligence</div>
  <div class="brand">Pharma Morning Brief</div>
  <p class="tagline">Balanced, fact-checked &mdash; in the time it takes to drink a coffee.</p>
  <input id="q" class="search" type="search" placeholder="Search all digests...">
</header>
<div id="results" style="display:none"></div>
<div class="shell">
<aside class="rail">
  <div class="rail-h">On this page</div>
  <a href="#latest">Latest digest</a>
  <a href="#upcoming">Upcoming catalysts</a>
  <a href="#markets">Markets</a>
  <a href="#archive">Archive</a>
  <a href="#about">About</a>
  <div class="rail-h">Sources monitored</div>
  <a href="https://endpoints.news" target="_blank" rel="noopener">Endpoints News</a>
  <a href="https://www.statnews.com/category/pharma/" target="_blank" rel="noopener">STAT Pharma</a>
  <a href="https://www.fiercepharma.com" target="_blank" rel="noopener">Fierce Pharma</a>
  <a href="https://www.biopharmadive.com" target="_blank" rel="noopener">BioPharma Dive</a>
  <a href="https://www.labiotech.eu" target="_blank" rel="noopener">Labiotech</a>
  <a href="https://www.fda.gov/news-events/fda-newsroom" target="_blank" rel="noopener">FDA Newsroom</a>
  <a href="https://www.ema.europa.eu/en/news" target="_blank" rel="noopener">EMA News</a>
</aside>
<div class="content">
<section class="panel" id="latest">
  <h2>Latest digest</h2>
  {latest_html}
</section>
<section class="panel" id="upcoming">
  <h2>Upcoming catalysts</h2>
  <div class="two-col"><div>{timeline}</div><div><h3>Catalyst mix</h3>{mix}</div></div>
</section>
{market_panel}
<section class="panel" id="archive">
  <h2>Archive</h2>
  <div class="grid">{''.join(cards) if cards else '<p class="muted">No digests yet.</p>'}</div>
</section>
<section class="panel" id="about">
  <h2>About this project</h2>
  <p><strong>Pharma Morning Brief</strong> turns the day's pharmaceutical news into a fact-checked, 2-3 minute executive digest &mdash; built for someone entering pharma who needs to stay current without reading 20 outlets every morning.</p>
  <p><strong>How it works:</strong> one shared "recipe" runs through <strong>two interchangeable AI engines</strong> &mdash; <em>Claude</em> (richest analysis, on-demand) and <em>DeepSeek</em> (cheap, runs automatically in the cloud every morning). The result is emailed <em>and</em> published here. Every fact is grounded in a real, linked source; niche terms are glossed in plain language; each digest is labelled with the engine that wrote it.</p>
</section>
</div>
</div>
<script src="search-data.js"></script>
<script src="search.js"></script>"""
    (OUT / "index.html").write_text(page("Pharma Morning Brief", index_body, home_link=False), encoding="utf-8")
    (OUT / "style.css").write_text(CSS, encoding="utf-8")
    (OUT / "search-data.js").write_text("window.DIGESTS=" + json.dumps(search_index) + ";", encoding="utf-8")
    (OUT / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    print(f"Site built ✓  ({len(files)} digests)  -> {OUT / 'index.html'}")


CSS = """
:root{
 --paper:#e8e9e0;--card:#fbfbf6;--ink:#0f1020;--muted:#5e6a65;--line:#cdcebf;--accent:#466362;
 --serif:Georgia,"Iowan Old Style","Palatino Linotype",Palatino,"Times New Roman",serif;
 --sans:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 --mono:"SF Mono",ui-monospace,Menlo,Consolas,monospace;
 --c-reg:#466362;--c-earn:#8b635c;--c-conf:#9e768f;--c-other:#9aa08c;--up:#466362;--down:#8b635c;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);line-height:1.62;font-size:16.5px;
 font-family:var(--sans);-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;}
main{max-width:1060px;margin:0 auto;padding:40px 22px 16px;}
footer{max-width:1060px;margin:0 auto;padding:22px 0 56px;color:var(--muted);font-size:11.5px;
 border-top:1px solid var(--line);font-family:var(--mono);letter-spacing:.04em;text-transform:uppercase;}
h1{font-family:var(--serif);font-weight:700;font-size:30px;line-height:1.15;margin:.2em 0 .3em}
h2{font-family:var(--serif);font-weight:700;font-size:21px;margin:1.7em 0 .7em;padding-bottom:.3em;border-bottom:1px solid var(--line)}
h3{font-family:var(--sans);font-weight:700;font-size:16px;letter-spacing:-.01em;margin:1.4em 0 .4em}
p{margin:.6em 0}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid rgba(70,99,98,.35)}
a:hover{border-bottom-color:var(--accent)}
.muted{color:var(--muted)}
.back{display:inline-block;margin-bottom:18px;font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.07em;border:none}
/* masthead */
.hero{padding:4px 0 18px;border-bottom:2px solid var(--ink);margin-bottom:8px}
.kicker{font-family:var(--mono);text-transform:uppercase;letter-spacing:.22em;font-size:10.5px;color:var(--accent);margin-bottom:10px}
.brand{font-family:var(--serif);font-weight:700;font-size:44px;line-height:1.02;letter-spacing:-.015em}
.tagline{font-family:var(--serif);font-style:italic;color:var(--muted);font-size:16px;margin:.5em 0 0}
.search{width:100%;margin-top:16px;padding:11px 14px;border:1px solid var(--line);border-radius:8px;
 font-size:15px;font-family:var(--sans);background:var(--card);color:var(--ink)}
.search:focus{outline:none;border-color:var(--accent)}
.snip{font-size:12.5px;color:var(--muted);margin-top:8px}
/* layout shell + side rail */
.shell{display:grid;grid-template-columns:180px 1fr;gap:36px;align-items:start}
.content{min-width:0}
.rail{position:sticky;top:22px;font-size:13px;line-height:1.45;border-right:1px solid var(--line);padding-right:16px}
.rail-h{font-family:var(--mono);text-transform:uppercase;letter-spacing:.1em;font-size:9.5px;color:var(--muted);margin:18px 0 6px}
.rail-h:first-child{margin-top:0}
.rail a{display:block;color:var(--ink);border-bottom:none;padding:3px 0}
.rail a:hover{color:var(--accent)}
@media(max-width:760px){.shell{grid-template-columns:1fr}.rail{position:static;border-right:none;border-bottom:1px solid var(--line);padding:0 0 10px;margin-bottom:6px;display:flex;flex-wrap:wrap;gap:6px 14px}.rail-h{width:100%;margin:6px 0 0}}
/* panels & cards */
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px 26px;margin:18px 0}
.panel h2:first-child{margin-top:.1em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
.card{display:block;background:var(--paper);border:1px solid var(--line);border-top:3px solid var(--accent);
 border-radius:5px;padding:14px 16px;transition:transform .15s ease,box-shadow .15s ease;color:var(--ink)}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(0,0,0,.08)}
.card-date{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:.03em}
.card-title{font-family:var(--serif);font-weight:700;margin:5px 0 10px;font-size:16px;line-height:1.25}
.badge{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.04em;padding:2px 7px;border-radius:4px;background:#d8dac9;color:#4d5249}
.badge.claude{background:#ece0db;color:#6e463f}
.badge.deepseek{background:#dde7e5;color:#33514f}
/* pull-quote */
blockquote{margin:1.1em 0;padding:.1em 0 .1em 1.1em;border-left:3px solid var(--accent);
 font-family:var(--serif);font-style:italic;font-size:18px;line-height:1.4;color:var(--ink)}
blockquote p{margin:.2em 0}
hr{border:none;border-top:1px solid var(--line);margin:1.6em 0}
code{font-family:var(--mono);background:#dcdccf;padding:1px 5px;border-radius:4px;font-size:.85em}
ul{padding-left:1.15em}li{margin:.3em 0}
/* two columns */
.two-col{display:grid;grid-template-columns:1.4fr 1fr;gap:26px;align-items:start}
@media(max-width:640px){.two-col{grid-template-columns:1fr}}
/* timeline */
.vtl-group{font-family:var(--mono);font-size:10.5px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin:18px 0 4px}
.vtl-wrap > .vtl-group:first-child{margin-top:2px}
.vtl{list-style:none;margin:4px 0;padding:0}
.vtl-item{position:relative;padding:8px 0 8px 26px;border-left:1px solid var(--line)}
.vtl-item:last-child{border-left-color:transparent}
.vtl-dot{position:absolute;left:-5px;top:13px;width:9px;height:9px;border-radius:50%;background:var(--accent);border:2px solid var(--card);box-shadow:0 0 0 1px var(--line)}
.vtl-item.reg .vtl-dot{background:var(--c-reg)}.vtl-item.earn .vtl-dot{background:var(--c-earn)}
.vtl-item.conf .vtl-dot{background:var(--c-conf)}.vtl-item.other .vtl-dot{background:var(--c-other)}
.vtl-date{display:inline-block;min-width:104px;font-family:var(--mono);font-size:12px;margin-right:8px}
.vtl-text{font-size:14px}
.vtl-legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px;font-size:11.5px;color:var(--muted)}
.vtl-legend .lg{display:flex;align-items:center;gap:6px}
.vtl-legend .lg::before{content:"";width:9px;height:9px;border-radius:50%;display:inline-block}
.vtl-legend .reg::before{background:var(--c-reg)}.vtl-legend .earn::before{background:var(--c-earn)}
.vtl-legend .conf::before{background:var(--c-conf)}.vtl-legend .other::before{background:var(--c-other)}
@media(max-width:560px){.vtl-date{display:block;min-width:0}}
/* bars */
.barchart{margin-top:6px}
.bar-row{display:flex;align-items:center;gap:10px;margin:9px 0;font-size:13px}
.bar-name{min-width:84px;color:var(--muted)}
.bar-track{flex:1;height:8px;background:var(--line);border-radius:2px;overflow:hidden}
.bar-fill{display:block;height:100%;border-radius:2px;background:var(--accent)}
.bar-fill.reg{background:var(--c-reg)}.bar-fill.earn{background:var(--c-earn)}
.bar-fill.conf{background:var(--c-conf)}.bar-fill.other{background:var(--c-other)}
.bar-val{min-width:18px;text-align:right;font-family:var(--mono);font-size:12px}
/* markets */
.market{margin-top:4px}
.mkt-row{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:13px}
.mkt-name{flex:0 0 190px}
.tkr{font-family:var(--mono);color:var(--muted);font-size:11px}
.mkt-bar{flex:1;height:8px;background:var(--line);border-radius:2px;overflow:hidden}
.mkt-fill{display:block;height:100%;border-radius:2px}
.mkt-fill.up{background:var(--up)}.mkt-fill.down{background:var(--down)}
.mkt-pct{flex:0 0 56px;text-align:right;font-family:var(--mono);font-size:12.5px}
.mkt-pct.up{color:var(--up)}.mkt-pct.down{color:var(--down)}
@media(max-width:560px){.mkt-name{flex-basis:120px}}
/* dark mode */
@media (prefers-color-scheme: dark){
 :root{--paper:#0f1020;--card:#191b2c;--ink:#e8e9e0;--muted:#9aa0a0;--line:#2b2d40;--accent:#7ba6a3;
  --c-reg:#7ba6a3;--c-earn:#b88a82;--c-conf:#b894ab;--c-other:#b9baa3;--up:#7ba6a3;--down:#c08a82;}
 .card{background:#191b2c}
 blockquote{color:#e2e3da}
 code{background:#23253a}
 .badge{background:#23253a;color:#c7c8bb}
 .badge.claude{background:#2f2421;color:#caa49b}
 .badge.deepseek{background:#1d2c2b;color:#9cc3bf}
 a{border-bottom-color:rgba(123,166,163,.45)}
}
@media(max-width:560px){main{padding:22px 16px}.brand{font-size:32px}h1{font-size:25px}}
"""


if __name__ == "__main__":
    build()
