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
def catalyst_date(datestr: str):
    """A catalyst date string -> date. Accepts ISO (2026-09-15) or month+year (Sep 2026 /
    September 2026 -> the 15th, the convention used everywhere). None if unparseable. Used
    by BOTH the renderer and the auto-detect dedup, so "Sep 2026" and "2026-09-15" are
    treated as the same day and don't render as duplicates."""
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", datestr)
    if iso:
        try:
            return dt.date(int(iso[1]), int(iso[2]), int(iso[3]))
        except ValueError:
            return None
    mon = re.search(r"([A-Za-z]{3})[a-z]*\s+(\d{4})", datestr)
    if mon and mon.group(1).lower() in MONTHS:
        return dt.date(int(mon.group(2)), MONTHS[mon.group(1).lower()], 15)
    return None


def _short_label(desc: str, cap: int = 110) -> str:
    """A tidy one-line catalyst label: the first clause (up to ';'), capped at a WORD
    boundary, with any parenthesis left dangling by the split or the cap dropped — so it
    never ends mid-word or with an unclosed '(' (e.g. a ';' inside a parenthetical)."""
    short = re.split(r";\s", desc)[0].strip()
    if short.count("(") > short.count(")"):              # ')' fell after the ';' split
        short = short[:short.rfind("(")].rstrip(" ,;:-—–")
    if len(short) > cap:                                 # word-boundary length cap
        short = short[:cap].rsplit(" ", 1)[0].rstrip(" ,;:-—–") + "…"
        if short.count("(") > short.count(")"):          # cap reopened a '(' -> drop it
            short = short[:short.rfind("(")].rstrip(" ,;:-—–") + "…"
    return short


def parse_catalysts(path) -> list:
    """Parse catalysts.md into sorted events: {date, label, full}. `label` is the tidy
    one-line form for rows; `full` is the whole description (hover title on the website).
    The internal "(auto-detected …)" provenance tag is stripped from both."""
    if not path or not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \*\*(.+?)\*\* · (.+)$", line.strip())
        if not m:
            continue
        desc = re.sub(r"\s*\(auto-detected[^)]*\)\s*$", "", m.group(2)).strip()
        when = catalyst_date(m.group(1))
        if when:
            events.append({"date": when, "label": _short_label(desc), "full": desc})
    return sorted(events, key=lambda e: e["date"])


# Timeline buckets, shared so the website and the email group catalysts identically.
CATALYST_BUCKETS = ("Next 30 days", "1–3 months", "On the horizon")


def upcoming_catalysts(events: list, ref_date=None) -> list:
    """Group `events` (from parse_catalysts) into the forward-looking timeline buckets as of
    `ref_date` (default: today): next 30 days, 1–3 months, on the horizon. Events dated BEFORE
    `ref_date` are dropped — a brief always looks FORWARD from the day it was produced, so a
    catalyst that has already passed never lingers in a later (or archived) brief. Returns
    [(label, [event, …]), …] for the non-empty buckets only, in chronological order."""
    ref = ref_date or dt.date.today()
    groups = ([], [], [])
    for e in events:
        delta = (e["date"] - ref).days
        if delta < 0:                       # already happened as of this brief — drop it
            continue
        groups[0 if delta <= 30 else 1 if delta <= 90 else 2].append(e)
    return [(CATALYST_BUCKETS[i], g) for i, g in enumerate(groups) if g]


def forward_calendar_text(path, ref_date=None) -> str:
    """catalysts.md as text with PAST dated entries dropped — for feeding the LLM grounding
    check, which treats the calendar's dated lines as sources for UPCOMING events. A past event
    can't support an upcoming claim, and dropping it stops the prompt from growing as the file
    accumulates. Non-dated lines (section headers, guidance, recurring notes with no parseable
    date) are kept verbatim, so the calendar still reads as itself. "" if the file is missing."""
    if not path or not path.exists():
        return ""
    ref = ref_date or dt.date.today()
    kept = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \*\*(.+?)\*\* · ", line.strip())
        if m:
            when = catalyst_date(m.group(1))
            if when is not None and when < ref:
                continue                    # dated, and already past — leave it out of the prompt
        kept.append(line)
    return "\n".join(kept)


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


def _yahoo_range(days: int) -> str:
    """Smallest Yahoo chart `range` that comfortably spans `days`, so the 'close `days` ago'
    anchor is real data, not the oldest point we happened to fetch. (range=1mo only holds ~30
    days, so a 365-day move would silently collapse to ~1 month without this.)"""
    for limit, rng in ((7, "1mo"), (31, "3mo"), (93, "6mo"), (186, "1y"), (366, "2y")):
        if days <= limit:
            return rng
    return "max"


def _fetch_one(tn: tuple, days: int, timeout: int):
    t, name = tn
    try:
        req = urllib.request.Request(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"
            f"?range={_yahoo_range(days)}&interval=1d",
            headers={"User-Agent": "Mozilla/5.0"})
        res = json.loads(urllib.request.urlopen(req, timeout=timeout).read())["chart"]["result"][0]
        closes = res["indicators"]["quote"][0]["close"]
        ts = res.get("timestamp") or []
        pairs = [(tt, c) for tt, c in zip(ts, closes) if c is not None]
        if len(pairs) >= 2:
            last_ts, last_close = pairs[-1]
            target = last_ts - days * 86400        # `days` CALENDAR days before the latest close
            prior = [p for p in pairs if p[0] <= target]
            base = (prior[-1] if prior else pairs[0])[1]   # nearest prior trading close (handles weekends)
        else:                                       # no usable timestamps -> span of valid closes
            vc = [c for c in closes if c is not None]
            if len(vc) < 2:
                return None
            last_close, base = vc[-1], vc[0]
        return {"t": t, "name": name, "pct": (last_close / base - 1) * 100, "last": last_close}
    except Exception:
        return None


def fetch_market(tickers: list, days: int = 7, timeout: int = 15) -> list:
    """% move over the last `days` CALENDAR days (latest close vs the nearest trading close
    `days` ago) + last close, per ticker, fetched CONCURRENTLY (I/O-bound). Picks the nearest
    prior close so weekends/holidays are handled. Skips tickers that error; [] if all fail.
    Order isn't significant — render_market sorts by % move."""
    if not tickers:
        return []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(tickers))) as ex:
        results = ex.map(lambda tn: _fetch_one(tn, days, timeout), tickers)
    return [r for r in results if r]


def brief_market_days(md: str):
    """Markets %-move lookback (calendar days) matching the brief, keyed off the H1 title
    (deterministic): daily -> 5 (a smoothed trailing week), Week in Review -> 7 (the week),
    Month in Review -> 30 (the month), Year in Review -> 365 (the year); any forward 'ahead'
    edition (week/month/year) -> None (a forward-looking brief shows no backward move)."""
    title = next((l for l in md.splitlines() if l.startswith("# ")), "").lower()
    if "week ahead" in title or "month ahead" in title or "year ahead" in title:
        return None
    if "year in review" in title:
        return 365
    if "month in review" in title:
        return 30
    if "week in review" in title:
        return 7
    return 5
