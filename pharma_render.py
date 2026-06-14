#!/usr/bin/env python3
"""
Shared rendering helpers used by BOTH the website (site/build_site.py) and the email
(pharma-news/send_digest.py).

These two renderers are deliberately separate (the site uses CSS classes; the email uses
inline styles for mail clients), but the *data* logic underneath — renumbering citations,
mapping [n]→URL, parsing the catalyst calendar, and fetching market prices — must be
identical, or the email and site silently drift apart. That logic lives here, once.

Stdlib only — no pip installs.
"""

import re
import json
import datetime as dt
import urllib.request
import concurrent.futures

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


# --------------------------------------------------------------------------- #
#  Citations: renumber sources by order of first appearance + map [n] -> URL
# --------------------------------------------------------------------------- #
def renumber_sources(md: str) -> str:
    """Renumber sources to 1,2,3… in the order their [n] citations first appear in the
    body, reorder the Sources list to match, and rewrite the inline citations. Sources
    that are never cited are kept and appended after the cited ones, in their original
    order. (Engines cite by feed position, so raw numbers are gappy and out of order.)"""
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
        else:                       # first non-source line (e.g. the footer rule) ends the list
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


def parse_srcmap(md: str) -> dict:
    """Map each (renumbered) source number to its URL from the Sources list."""
    smap = {}
    for l in md.splitlines():
        m = re.match(r"^\s*(\d+)\.\s*\[[^\]]+\]\((https?://[^)\s]+)\)", l)
        if m:
            smap[m.group(1)] = m.group(2)
    return smap


# --------------------------------------------------------------------------- #
#  Catalyst calendar parsing (the dated "- **DATE** · desc" lines)
# --------------------------------------------------------------------------- #
def parse_catalysts(path) -> list:
    """Parse catalysts.md into sorted events: {date, label, full}. `label` is the short
    form (clause up to the first ';', capped at 110 chars) for tidy rows; `full` is the
    whole description (used for hover titles on the website)."""
    if not path or not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \*\*(.+?)\*\* · (.+)$", line.strip())
        if not m:
            continue
        datestr, desc = m.group(1), m.group(2)
        short = re.split(r";\s", desc)[0].strip()
        if len(short) > 110:
            short = short[:107].rstrip() + "…"
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


# --------------------------------------------------------------------------- #
#  Markets (free Yahoo Finance endpoint — no key, real prices only)
# --------------------------------------------------------------------------- #
MARKET_TICKERS = [
    ("LLY", "Eli Lilly"), ("NVO", "Novo Nordisk"), ("PFE", "Pfizer"),
    ("AZN", "AstraZeneca"), ("MRK", "Merck"), ("NVS", "Novartis"),
    ("GSK", "GSK"), ("AMGN", "Amgen"), ("ABBV", "AbbVie"), ("JNJ", "J&J"),
]

# Added to the markets strip ONLY when today's digest covers them (semi-dynamic).
EXTRA_TICKERS = {
    "summit": ("SMMT", "Summit Therapeutics"), "viking": ("VKTX", "Viking"),
    "biontech": ("BNTX", "BioNTech"), "moderna": ("MRNA", "Moderna"),
    "roche": ("RHHBY", "Roche"), "sanofi": ("SNY", "Sanofi"),
    "takeda": ("TAK", "Takeda"), "gilead": ("GILD", "Gilead"),
    "regeneron": ("REGN", "Regeneron"), "vertex": ("VRTX", "Vertex"),
    "bristol": ("BMY", "Bristol Myers"), "incyte": ("INCY", "Incyte"),
    "bayer": ("BAYRY", "Bayer"), "biogen": ("BIIB", "Biogen"),
}


def select_tickers(text: str) -> list:
    """Core tickers plus any EXTRA company named in today's digest text (lower-cased)."""
    tickers, have = list(MARKET_TICKERS), {t for t, _ in MARKET_TICKERS}
    for kw, (tk, nm) in EXTRA_TICKERS.items():
        if kw in text and tk not in have:
            tickers.append((tk, nm)); have.add(tk)
    return tickers


def _fetch_one(tn: tuple, timeout: int):
    t, name = tn
    try:
        req = urllib.request.Request(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5d&interval=1d",
            headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        closes = [c for c in d["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
        if len(closes) >= 2:
            return {"t": t, "name": name,
                    "pct": (closes[-1] / closes[0] - 1) * 100, "last": closes[-1]}
    except Exception:
        return None
    return None


def fetch_market(tickers: list, timeout: int = 15) -> list:
    """5-day % move + last close for each ticker via Yahoo Finance, fetched CONCURRENTLY
    (I/O-bound) so ~10-24 tickers don't run serially. Skips any ticker that errors (a flaky/
    blocked endpoint never breaks the caller); returns [] if all fail. Order is not
    significant — render_market sorts by % move."""
    if not tickers:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(tickers))) as ex:
        results = ex.map(lambda tn: _fetch_one(tn, timeout), tickers)
    return [r for r in results if r]
