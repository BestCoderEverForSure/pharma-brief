#!/usr/bin/env python3
"""
Email today's Pharma Morning Digest via Resend (send-only API).

Usage:
    python3 send_digest.py [path/to/digest.md]

If no path is given, it emails today's digest: digests/YYYY-MM-DD.md

Secrets are read (in priority order) from:
    1. Environment variables: RESEND_API_KEY, EMAIL_TO, EMAIL_FROM
    2. ~/.config/pharma-news/secrets.env   (key=value lines; chmod 600)

This script intentionally uses only the Python standard library — no pip installs.
"""

import os
import re
import sys
import json
import time
import html as _html
import datetime
import http.client
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = Path.home() / ".config" / "pharma-news" / "secrets.env"
RESEND_ENDPOINT = "https://api.resend.com/emails"
_RETRY_DELAYS = (0, 3, 8)


def _urlopen_retry(req, timeout: int = 30):
    """POST with retry on transient failures (429/5xx, dropped connection), mirroring
    run_digest.call_model. A momentary Resend/network blip must NOT fail the send — in
    the cloud a failed send aborts the whole job, costing the day's archive + publish.
    Returns (status, body); raises on a 4xx or after retries are exhausted."""
    last = None
    for delay in _RETRY_DELAYS:
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and delay != _RETRY_DELAYS[-1]:
                last = e
                continue          # transient — retry
            raise                  # 4xx (bad request/auth) — fail now
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            last = e
            if delay == _RETRY_DELAYS[-1]:
                raise
    raise last                     # exhausted retries

# Maps citation number -> source URL, so inline [n] markers become clickable links.
# Populated by prepare_digest() right before rendering; empty otherwise.
_SRCMAP: dict = {}

# --- Markets: same core tickers as the website, rendered email-safe (inline styles,
#     no JS/CSS classes) so the email carries the site's markets strip too. Mirrors
#     the lists in site/build_site.py (the two renderers are intentionally separate). ---
MARKET_TICKERS = [
    ("LLY", "Eli Lilly"), ("NVO", "Novo Nordisk"), ("PFE", "Pfizer"),
    ("AZN", "AstraZeneca"), ("MRK", "Merck"), ("NVS", "Novartis"),
    ("GSK", "GSK"), ("AMGN", "Amgen"), ("ABBV", "AbbVie"), ("JNJ", "J&J"),
]
EXTRA_TICKERS = {
    "summit": ("SMMT", "Summit Therapeutics"), "viking": ("VKTX", "Viking"),
    "biontech": ("BNTX", "BioNTech"), "moderna": ("MRNA", "Moderna"),
    "roche": ("RHHBY", "Roche"), "sanofi": ("SNY", "Sanofi"),
    "takeda": ("TAK", "Takeda"), "gilead": ("GILD", "Gilead"),
    "regeneron": ("REGN", "Regeneron"), "vertex": ("VRTX", "Vertex"),
    "bristol": ("BMY", "Bristol Myers"), "incyte": ("INCY", "Incyte"),
    "bayer": ("BAYRY", "Bayer"), "biogen": ("BIIB", "Biogen"),
}


def _fetch_market(tickers: list) -> list:
    out = []
    for t, name in tickers:
        try:
            req = urllib.request.Request(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=5d&interval=1d",
                headers={"User-Agent": "Mozilla/5.0"})
            d = json.loads(urllib.request.urlopen(req, timeout=8).read())
            closes = [c for c in d["chart"]["result"][0]["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 2:
                out.append({"t": t, "name": name,
                            "pct": (closes[-1] / closes[0] - 1) * 100, "last": closes[-1]})
        except Exception:
            continue
    return out


def render_market_email(md: str) -> str:
    """Markets section for the email: the website's core tickers plus any extra company
    named in today's digest. Inline styles only (mail clients ignore <style>/classes).
    Returns "" if no quotes come back, so a flaky/blocked endpoint never breaks the email."""
    text = md.lower()
    tickers, have = list(MARKET_TICKERS), {t for t, _ in MARKET_TICKERS}
    for kw, (tk, nm) in EXTRA_TICKERS.items():
        if kw in text and tk not in have:
            tickers.append((tk, nm)); have.add(tk)
    data = _fetch_market(tickers)
    if not data:
        return ""
    data = sorted(data, key=lambda x: x["pct"], reverse=True)
    mono = "ui-monospace,Menlo,Consolas,monospace"
    rows = []
    for x in data:
        # Green up, red down, neutral grey for ~flat (rounds to 0.0%). Grey rather than
        # literal white, which would be invisible on the email's white background.
        if round(x["pct"], 1) == 0:
            color, sign = "#8a8a8a", ""
        elif x["pct"] > 0:
            color, sign = "#2f6f4f", "+"
        else:
            color, sign = "#9c3b3b", ""
        rows.append(
            "<tr>"
            f'<td style="padding:6px 0;font-size:14px;border-bottom:1px solid #ececec">'
            f'{_html.escape(x["name"])} <span style="color:#8a8a8a;font-size:11px;font-family:{mono}">{x["t"]}</span></td>'
            f'<td style="padding:6px 0;text-align:right;font-size:13px;color:#8a8a8a;font-family:{mono};'
            f'border-bottom:1px solid #ececec">{x["last"]:.2f}</td>'
            f'<td style="padding:6px 0 6px 16px;text-align:right;font-size:13px;font-weight:600;color:{color};'
            f'font-family:{mono};border-bottom:1px solid #ececec">{sign}{x["pct"]:.1f}%</td>'
            "</tr>")
    return (
        '<hr style="border:none;border-top:1px solid #e3dfd4;margin:26px 0 0">'
        "<h2>Markets</h2>"
        '<table style="width:100%;border-collapse:collapse" cellpadding="0" cellspacing="0">'
        + "".join(rows) + "</table>"
        f'<p style="font-family:{mono};font-size:11px;color:#8a8a8a;margin:10px 0 0">'
        "Source: Yahoo Finance, end-of-day prices (5-day change). Not investment advice.</p>")


# --- Catalyst timeline: same dated events as the website, grouped the same way,
#     rendered email-safe. Read from pharma-news/catalysts.md (mirrors build_site.py). ---
CATALYSTS_PATH = PROJECT_ROOT / "pharma-news" / "catalysts.md"
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def _parse_catalysts() -> list:
    if not CATALYSTS_PATH.exists():
        return []
    events = []
    for line in CATALYSTS_PATH.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- \*\*(.+?)\*\* · (.+)$", line.strip())
        if not m:
            continue
        datestr, desc = m.group(1), m.group(2)
        # Keep the explanatory clause (up to the first ';'), not just the drug name, so a
        # reader knows WHAT the event is — capped so rows stay tidy.
        short = re.split(r";\s", desc)[0].strip()
        if len(short) > 110:
            short = short[:107].rstrip() + "…"
        when = None
        iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", datestr)
        if iso:
            try:
                when = datetime.date(int(iso[1]), int(iso[2]), int(iso[3]))
            except ValueError:
                when = None
        else:
            mon = re.search(r"([A-Za-z]{3})[a-z]*\s+(\d{4})", datestr)
            if mon and mon.group(1).lower() in _MONTHS:
                when = datetime.date(int(mon.group(2)), _MONTHS[mon.group(1).lower()], 15)
        if when:
            events.append({"date": when, "label": short})
    return sorted(events, key=lambda e: e["date"])


def render_catalysts_email() -> str:
    """Upcoming-catalysts list for the email (mirrors the website's timeline buckets),
    inline styles only. "" when there are no dated catalysts on file."""
    events = _parse_catalysts()
    if not events:
        return ""
    today = datetime.date.today()
    labels = ["Next 30 days", "1–3 months", "On the horizon"]

    def bucket(d):
        delta = (d - today).days
        return 0 if delta <= 30 else (1 if delta <= 90 else 2)

    groups: dict = {0: [], 1: [], 2: []}
    for e in events:
        groups[bucket(e["date"])].append(e)
    mono = "ui-monospace,Menlo,Consolas,monospace"
    parts = ['<hr style="border:none;border-top:1px solid #e3dfd4;margin:26px 0 0">',
             "<h2>Upcoming catalysts</h2>",
             f'<p style="font-family:{mono};font-size:12px;color:#7c7a70;margin:-2px 0 12px">'
             "Dates to watch — scheduled events that can move the sector: regulatory decisions, "
             "trial readouts, earnings, and major conferences.</p>"]
    rows_total = sum(len(groups[g]) for g in (0, 1, 2))
    rendered = 0
    for gi in (0, 1, 2):
        if not groups[gi]:
            continue
        parts.append(f'<p style="font-family:{mono};text-transform:uppercase;letter-spacing:.08em;'
                     f'font-size:11px;color:#8b635c;margin:16px 0 4px">{labels[gi]}</p>')
        parts.append('<table style="width:100%;border-collapse:collapse" cellpadding="0" cellspacing="0">')
        for e in groups[gi]:
            rendered += 1
            # No border under the very last row — otherwise it doubles up with the Markets
            # section's rule below and reads as an empty band.
            bb = "" if rendered == rows_total else "border-bottom:1px solid #ececec"
            d = e["date"].strftime("%b %d, %Y")
            parts.append(
                "<tr>"
                f'<td style="padding:5px 12px 5px 0;font-size:12px;color:#8a8a8a;font-family:{mono};'
                f'white-space:nowrap;vertical-align:top;{bb}">{d}</td>'
                f'<td style="padding:5px 0;font-size:14px;{bb}">'
                f'{_html.escape(e["label"])}</td>'
                "</tr>")
        parts.append("</table>")
    return "".join(parts)


def load_secrets() -> dict:
    """Load secrets from env vars, falling back to the secrets.env file."""
    secrets = {}
    if SECRETS_PATH.exists():
        for line in SECRETS_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip().strip('"').strip("'")
    # Env vars win over the file.
    for k in ("RESEND_API_KEY", "EMAIL_TO", "EMAIL_FROM"):
        if os.environ.get(k):
            secrets[k] = os.environ[k]
    return secrets


def find_digest(arg_path: str | None) -> Path:
    if arg_path:
        return Path(arg_path).expanduser().resolve()
    today = datetime.date.today().isoformat()
    return PROJECT_ROOT / "digests" / f"{today}.md"


def md_inline(text: str) -> str:
    """Minimal inline markdown -> HTML (links, bold, italic, clickable [n] citations)."""
    text = _html.escape(text)
    # Drop "[catalysts.md]"-style markers (internal files cited as if sources); the
    # lookahead spares real "[label.md](url)" links.
    text = re.sub(r"\s*\[[^\[\]]*\.md\](?!\()", "", text, flags=re.I)
    # Tolerate a stray space in links the model sometimes writes as "[text] (https://…)";
    # collapse it only before a URL so citations like "[1] (a note)" stay plain text.
    text = re.sub(r"\]\s+\((?=https?://)", "](", text)
    # Positively mark the minority of DIRECT publisher links with a ✓ (the rest go via the
    # Google News aggregator and can redirect) — matches the website, low-noise.
    def _emlink(m):
        label, url = m.group(1), m.group(2)
        mark = ('<span style="color:#466362;font-size:.8em" title="Direct link to the publisher"> ✓</span>'
                if "news.google.com" not in url else "")
        return f'<a href="{url}">{label}</a>{mark}'
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _emlink, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    # Make bare [n] citation markers clickable, linking to their source.
    if _SRCMAP:
        text = re.sub(r"\[(\d+)\]", lambda m: (
            f'<a href="{_SRCMAP[m.group(1)]}" style="color:#8b635c;text-decoration:none;'
            f'font-weight:600">[{m.group(1)}]</a>' if m.group(1) in _SRCMAP else m.group(0)), text)
    return text


def renumber_sources(md: str) -> str:
    """Renumber sources to 1,2,3… in the order their [n] citations first appear in the
    body, reorder the Sources list to match, and rewrite the inline citations. Sources
    that are never cited are kept and appended after the cited ones, in their original
    order. (DeepSeek cites by feed position, so raw numbers are gappy and out of order.)"""
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


def prepare_digest(md: str) -> str:
    """Renumber sources by order of appearance and arm the citation->URL map."""
    global _SRCMAP
    md = renumber_sources(md)
    _SRCMAP = parse_srcmap(md)
    return md


def published_stamp() -> str:
    """A fixed 'Published' line for email (clients can't run JS, so we can't localize
    to the reader live). Stamped in Europe/Rome — the timezone the brief is built for."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("Europe/Rome"))
        when = now.strftime("%a, %b %d, %Y · %H:%M %Z")
    except Exception:
        when = datetime.datetime.now().strftime("%a, %b %d, %Y · %H:%M")
    return (f'<p style="font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#7c7a70;'
            f'margin:2px 0 14px">Published {when} <span style="opacity:.7">'
            f'(Rome time)</span></p>')


def _md_fragment(md: str) -> str:
    """Convert the digest's markdown subset to an HTML fragment (no page wrapper)."""
    lines = md.splitlines()
    out, in_list, in_quote = [], False, False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def close_quote():
        nonlocal in_quote
        if in_quote:
            out.append("</blockquote>")
            in_quote = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_list()
            close_quote()
            continue
        if line.startswith("### "):
            close_list(); close_quote()
            h = line[4:]
            if h.rstrip().endswith("{major}"):
                h = re.sub(r"\s*\{major\}\s*$", "", h)
                out.append('<div style="font-family:ui-monospace,Menlo,monospace;text-transform:uppercase;'
                           'letter-spacing:.14em;font-size:11px;color:#8b635c;margin:16px 0 2px">Major story</div>')
                out.append(f'<h3 style="margin:.2em 0;color:#8b635c">{md_inline(h)}</h3>')
            else:
                out.append(f"<h3>{md_inline(h)}</h3>")
        elif line.startswith("## "):
            close_list(); close_quote()
            out.append(f"<h2>{md_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            close_list(); close_quote()
            out.append(f"<h1>{md_inline(line[2:])}</h1>")
        elif line.strip() in ("---", "***", "___"):
            close_list(); close_quote()
            out.append("<hr>")
        elif line.startswith("> "):
            close_list()
            if not in_quote:
                out.append('<blockquote>')
                in_quote = True
            out.append(f"<p>{md_inline(line[2:])}</p>")
        elif line.startswith("- ") or line.startswith("* "):
            close_quote()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{md_inline(line[2:])}</li>")
        else:
            close_list(); close_quote()
            out.append(f"<p>{md_inline(line)}</p>")

    close_list(); close_quote()
    return "\n".join(out)


def md_to_html(md: str, extra_html: str = "") -> str:
    """Wrap the digest body in the email page; `extra_html` is appended after the body."""
    body = _md_fragment(md)
    # Drop the 'Published' stamp in right after the H1 title.
    stamp = published_stamp()
    body = body.replace("</h1>", "</h1>\n" + stamp, 1) if "</h1>" in body else stamp + body
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f5f5f7;">
<div style="max-width:680px;margin:0 auto;padding:28px 32px;background:#ffffff;
            font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
            color:#1d1d1f;line-height:1.55;font-size:15px;">
{body}
{extra_html}
</div></body></html>"""


def email_html(md: str) -> str:
    """Assemble the full email: digest body, then Upcoming catalysts, Markets, and the
    Sources list LAST (moved out of the body to the very end, below markets)."""
    idx = md.find("\n## Sources")
    body_md, sources_md = (md[:idx], md[idx + 1:]) if idx != -1 else (md, "")
    # Drop a trailing rule so we don't get a double horizontal line before catalysts.
    body_md = re.sub(r"\n+---\s*$", "", body_md)
    extra = render_catalysts_email() + render_market_email(md)
    if sources_md.strip():
        extra += _md_fragment(sources_md)
    return md_to_html(body_md, extra)


def main() -> int:
    # --preview: render the email to an HTML file (no keys needed) so anyone can
    # see what the emailed digest looks like without sending anything.
    args = sys.argv[1:]
    if "--preview" in args:
        rest = [a for a in args if a != "--preview"]
        digest_path = find_digest(rest[0] if rest else None)
        if not digest_path.exists():
            print(f"ERROR: digest not found: {digest_path}", file=sys.stderr)
            return 3
        out = Path(rest[1]).expanduser() if len(rest) > 1 else (PROJECT_ROOT / "samples" / "email-preview.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        pmd = prepare_digest(digest_path.read_text(encoding="utf-8"))
        out.write_text(email_html(pmd), encoding="utf-8")
        print(f"Email preview written ✓ -> {out}")
        return 0

    secrets = load_secrets()
    api_key = secrets.get("RESEND_API_KEY")
    to_addr = secrets.get("EMAIL_TO", "")
    recipients = [a.strip() for a in re.split(r"[,;]+", to_addr) if a.strip()]
    from_addr = secrets.get("EMAIL_FROM", "onboarding@resend.dev")

    if not api_key or not recipients:
        print("ERROR: missing RESEND_API_KEY or EMAIL_TO.\n"
              f"Set them as env vars or in {SECRETS_PATH}", file=sys.stderr)
        return 2

    digest_path = find_digest(sys.argv[1] if len(sys.argv) > 1 else None)
    if not digest_path.exists():
        print(f"ERROR: digest not found: {digest_path}", file=sys.stderr)
        return 3

    md = prepare_digest(digest_path.read_text(encoding="utf-8"))
    # Subject = first H1 line if present, else a default.
    subject = next((l[2:].strip() for l in md.splitlines() if l.startswith("# ")),
                   f"Pharma Morning Digest — {datetime.date.today().isoformat()}")

    payload = json.dumps({
        "from": from_addr,
        "to": recipients,
        "subject": subject,
        "html": email_html(md),
        "text": md,
    }).encode("utf-8")

    req = urllib.request.Request(
        RESEND_ENDPOINT, data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 "User-Agent": "pharma-digest/1.0 (+https://resend.com)"},
    )
    try:
        status, body = _urlopen_retry(req, timeout=30)
        print(f"Sent ✓  ({status})  -> {', '.join(recipients)}\n{body}")
        return 0
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 4
    except urllib.error.URLError as e:
        print(f"ERROR: network failure: {e.reason}", file=sys.stderr)
        return 5
    except (http.client.HTTPException, OSError) as e:
        print(f"ERROR: network failure: {e}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
