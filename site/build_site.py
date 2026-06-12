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
            close_list(); close_quote(); out.append(f"<h3>{md_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            close_list(); close_quote(); out.append(f"<h2>{md_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            close_list(); close_quote(); out.append(f"<h1>{md_inline(line[2:])}</h1>")
        elif line.strip() in ("---", "***", "___"):
            close_list(); close_quote(); out.append("<hr>")
        elif line.startswith("> "):
            close_list()
            if not in_quote:
                out.append("<blockquote>"); in_quote = True
            out.append(f"<p>{md_inline(line[2:])}</p>")
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
        '<section class="panel"><h2>📈 Pharma markets — 5-day move</h2>' + market_html +
        '<p class="muted" style="font-size:11px;margin-top:10px">Source: Yahoo Finance, end-of-day prices. Not investment advice.</p></section>'
    ) if market_html else ""

    index_body = f"""
<header class="hero">
  <div class="brand">💊 Pharma Morning Brief</div>
  <p class="muted">Balanced, executive-level pharma intelligence · updated each morning</p>
  <input id="q" class="search" type="search" placeholder="🔎 Search all digests…">
</header>
<div id="results" style="display:none"></div>
<section class="panel">
  <h2>📰 Latest digest</h2>
  {latest_html}
</section>
<section class="panel">
  <h2>📅 Upcoming catalysts</h2>
  <div class="two-col"><div>{timeline}</div><div><h3>Catalyst mix</h3>{mix}</div></div>
</section>
{market_panel}
<section class="panel" id="archive">
  <h2>🗂️ Archive</h2>
  <div class="grid">{''.join(cards) if cards else '<p class="muted">No digests yet.</p>'}</div>
</section>
<script src="search-data.js"></script>
<script src="search.js"></script>"""
    (OUT / "index.html").write_text(page("Pharma Morning Brief", index_body, home_link=False), encoding="utf-8")
    (OUT / "style.css").write_text(CSS, encoding="utf-8")
    (OUT / "search-data.js").write_text("window.DIGESTS=" + json.dumps(search_index) + ";", encoding="utf-8")
    (OUT / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    print(f"Site built ✓  ({len(files)} digests)  -> {OUT / 'index.html'}")


CSS = """
:root{--bg:#f5f5f7;--card:#fff;--ink:#1d1d1f;--muted:#6e6e73;--line:#e3e3e8;
 --accent:#7c3aed;--claude:#d97706;--deepseek:#0ea5e9;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.6;font-size:16px;letter-spacing:-.011em;
 font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;}
main{max-width:820px;margin:0 auto;padding:44px 22px 16px;}
footer{max-width:820px;margin:0 auto;padding:28px 22px 56px;color:var(--muted);font-size:13px;}
h1{font-size:32px;font-weight:700;letter-spacing:-.025em;margin:.1em 0}
h2{font-size:20px;font-weight:600;letter-spacing:-.02em;margin:1.6em 0 .6em}
h3{font-size:16px;font-weight:600;margin:1.3em 0 .4em}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.muted{color:var(--muted)}
.back{display:inline-block;margin-bottom:16px;font-size:14px}
.hero{padding:12px 0 6px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:24px 26px;margin:20px 0;
 box-shadow:0 1px 2px rgba(0,0,0,.04),0 12px 32px rgba(0,0,0,.045);}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
.card{display:block;background:var(--card);border:1px solid var(--line);border-radius:14px;
 padding:15px 17px;transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease;color:var(--ink)}
.card:hover{border-color:var(--accent);transform:translateY(-3px);text-decoration:none;box-shadow:0 12px 30px rgba(0,0,0,.10)}
.card-date{font-size:12px;color:var(--muted)}
.card-title{font-weight:600;margin:4px 0 10px;font-size:15px}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;background:#eee;color:#555}
.badge.claude{background:#fef3c7;color:#92400e}
.badge.deepseek{background:#e0f2fe;color:#075985}
blockquote{margin:.6em 0;padding:.4em 1em;border-left:3px solid var(--accent);background:#faf8ff;border-radius:6px}
blockquote p{margin:.2em 0}
hr{border:none;border-top:1px solid var(--line);margin:1.4em 0}
code{background:#f0f0f3;padding:1px 5px;border-radius:5px;font-size:.9em}
ul{padding-left:1.2em}li{margin:.25em 0}
/* brand + search */
.brand{font-size:34px;font-weight:800;letter-spacing:-.03em}
.search{width:100%;margin-top:14px;padding:11px 14px;border:1px solid var(--line);
 border-radius:12px;font-size:15px;background:var(--card);color:var(--ink)}
.search:focus{outline:none;border-color:var(--accent)}
.snip{font-size:12.5px;color:var(--muted);margin-top:8px}
/* two columns for week ahead */
.two-col{display:grid;grid-template-columns:1.4fr 1fr;gap:24px;align-items:start}
@media(max-width:640px){.two-col{grid-template-columns:1fr}}
/* vertical timeline */
.vtl-group{font-size:11px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:18px 0 2px}
.vtl-wrap > .vtl-group:first-child{margin-top:4px}
.vtl{list-style:none;margin:4px 0;padding:0}
.vtl-item{position:relative;padding:9px 0 9px 28px;border-left:2px solid var(--line)}
.vtl-item:last-child{border-left-color:transparent}
.vtl-dot{position:absolute;left:-7px;top:14px;width:12px;height:12px;border-radius:50%;
 background:var(--accent);border:2px solid var(--card);box-shadow:0 0 0 1px var(--line)}
.vtl-item.reg .vtl-dot{background:#7c3aed}
.vtl-item.earn .vtl-dot{background:#16a34a}
.vtl-item.conf .vtl-dot{background:#0ea5e9}
.vtl-item.other .vtl-dot{background:#9a9aa0}
.vtl-date{display:inline-block;min-width:104px;font-weight:700;font-size:13px;margin-right:8px}
.vtl-text{font-size:14px}
.vtl-legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px;font-size:12px;color:var(--muted)}
.vtl-legend .lg{display:flex;align-items:center;gap:6px}
.vtl-legend .lg::before{content:"";width:10px;height:10px;border-radius:50%;display:inline-block}
.vtl-legend .reg::before{background:#7c3aed}.vtl-legend .earn::before{background:#16a34a}
.vtl-legend .conf::before{background:#0ea5e9}.vtl-legend .other::before{background:#9a9aa0}
@media(max-width:560px){.vtl-date{display:block;min-width:0}}
/* catalyst-mix bars */
.barchart{margin-top:6px}
.bar-row{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:13px}
.bar-name{min-width:84px;color:var(--muted)}
.bar-track{flex:1;height:10px;background:var(--line);border-radius:999px;overflow:hidden}
.bar-fill{display:block;height:100%;border-radius:999px;background:var(--accent)}
.bar-fill.reg{background:#7c3aed}.bar-fill.earn{background:#16a34a}
.bar-fill.conf{background:#0ea5e9}.bar-fill.other{background:#9a9aa0}
.bar-val{min-width:18px;text-align:right;font-weight:700}
/* markets */
.market{margin-top:4px}
.mkt-row{display:flex;align-items:center;gap:10px;margin:7px 0;font-size:13px}
.mkt-name{flex:0 0 190px}
.tkr{color:var(--muted);font-size:11px}
.mkt-bar{flex:1;height:9px;background:var(--line);border-radius:999px;overflow:hidden}
.mkt-fill{display:block;height:100%;border-radius:999px}
.mkt-fill.up{background:#16a34a}.mkt-fill.down{background:#dc2626}
.mkt-pct{flex:0 0 56px;text-align:right;font-weight:700}
.mkt-pct.up{color:#16a34a}.mkt-pct.down{color:#dc2626}
@media(max-width:560px){.mkt-name{flex-basis:120px}}
/* dark mode */
@media (prefers-color-scheme: dark){
 :root{--bg:#0f0f12;--card:#1b1b20;--ink:#ededf0;--muted:#9a9aa3;--line:#2b2b32;--accent:#a78bfa}
 blockquote{background:#1f1a2e}
 .badge{background:#2b2b32;color:#cfcfd6}
 .badge.claude{background:#3a2a10;color:#fbbf24}
 .badge.deepseek{background:#0c2c3f;color:#7dd3fc}
 code{background:#26262d}
}
@media(max-width:560px){main{padding:20px 14px}h1{font-size:24px}.brand{font-size:24px}}
"""


if __name__ == "__main__":
    build()
