#!/usr/bin/env python3
"""
Post a short summary of today's Pharma Morning Digest to a Telegram channel/chat.

Sends a skimmable card — title, talking point, TL;DR bullets — plus a
"Read the full brief" link to the website (the full digest is too long and too
rich in citations/markets to render well inside Telegram).

Usage:
    python3 send_telegram.py [path/to/digest.md]

If no path is given, it posts today's digest: digests/YYYY-MM-DD.md

Secrets are read (in priority order) from:
    1. Environment variables
    2. ~/.config/pharma-news/secrets.env   (key=value lines; chmod 600)

Required:  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  (chat id, or @channelusername)
Optional:  SITE_URL  (base of the published site; default points at the live site)

Stdlib only — no pip installs.
"""

import os
import re
import sys
import json
import html as _html
import datetime
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = Path.home() / ".config" / "pharma-news" / "secrets.env"
DEFAULT_SITE = "https://bestcodereverforsure.github.io/pharma-brief/"
TG_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 3900  # Telegram hard limit is 4096; leave headroom.


def load_secrets() -> dict:
    secrets = {}
    if SECRETS_PATH.exists():
        for line in SECRETS_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            secrets[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SITE_URL"):
        if os.environ.get(k):
            secrets[k] = os.environ[k]
    return secrets


def find_digest(arg_path: str | None) -> Path:
    if arg_path:
        return Path(arg_path).expanduser().resolve()
    today = datetime.date.today().isoformat()
    return PROJECT_ROOT / "digests" / f"{today}.md"


def tg_inline(text: str) -> str:
    """Markdown subset -> Telegram-flavoured HTML; drop [n] citation markers."""
    text = re.sub(r"\s*\[\d+\]", "", text)                     # strip [n] citations
    text = re.sub(r"\s*\[[^\[\]]*\.md\](?!\()", "", text)      # strip "[catalysts.md]"-style markers
    text = _html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"\s*\{major\}\s*", "", text)                # not meaningful in TG
    return text.strip()


def build_message(md: str, slug: str, site_base: str) -> str:
    lines = md.splitlines()
    title = next((l[2:].strip() for l in lines if l.startswith("# ")), "Pharma Morning Brief")
    title = re.sub(r"^[^\w]+", "", title)  # drop a leading emoji for a clean bold line

    # Talking point: the lede blockquote.
    talking = ""
    for l in lines:
        if l.startswith("> "):
            talking = re.sub(r"^>\s*", "", l)
            talking = re.sub(r"^(💡\s*)?\*\*Talking point:\*\*\s*", "", talking)
            break

    # TL;DR bullets (between "## TL;DR" and the next heading/rule).
    bullets, in_tldr = [], False
    for l in lines:
        if re.match(r"^##\s+TL;DR", l, re.I):
            in_tldr = True
            continue
        if in_tldr:
            if l.startswith("## ") or l.strip() in ("---", "***"):
                break
            if re.match(r"^[-*]\s+", l):
                bullets.append(re.sub(r"^[-*]\s+", "", l).strip())

    url = site_base.rstrip("/") + "/" + slug + ".html"

    out = [f"<b>{tg_inline(title)}</b>"]
    if talking:
        out.append(f"\n💡 <i>{tg_inline(talking)}</i>")
    if bullets:
        out.append("")
        out += [f"• {tg_inline(b)}" for b in bullets]
    out.append(f'\n📖 <a href="{_html.escape(url)}">Read the full brief →</a>')
    msg = "\n".join(out)
    if len(msg) > MAX_LEN:
        msg = msg[:MAX_LEN].rsplit("\n", 1)[0] + f'\n\n📖 <a href="{_html.escape(url)}">Read the full brief →</a>'
    return msg


def main() -> int:
    args = sys.argv[1:]
    secrets = load_secrets()
    token = secrets.get("TELEGRAM_BOT_TOKEN")
    chat_id = secrets.get("TELEGRAM_CHAT_ID")
    site_base = secrets.get("SITE_URL", DEFAULT_SITE)

    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set.", file=sys.stderr)
        return 2
    if not chat_id:
        # Not an error — the channel may not be wired yet. Don't break the daily run.
        print("TELEGRAM_CHAT_ID not set — skipping Telegram post (set it to @channel or a chat id).")
        return 0

    digest_path = find_digest(args[0] if args else None)
    if not digest_path.exists():
        print(f"ERROR: digest not found: {digest_path}", file=sys.stderr)
        return 3

    md = digest_path.read_text(encoding="utf-8")
    message = build_message(md, digest_path.stem, site_base)

    def post(text: str, as_html: bool):
        body = {"chat_id": chat_id, "text": text, "disable_web_page_preview": False}
        if as_html:
            body["parse_mode"] = "HTML"
        req = urllib.request.Request(
            TG_API.format(token=token), data=json.dumps(body).encode("utf-8"),
            method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status

    try:
        status = post(message, as_html=True)
        print(f"Telegram sent ✓  ({status}) -> {chat_id}")
        return 0
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        # A malformed entity (e.g. an odd character in a headline) gives a 400.
        # Rather than drop the post, retry as plain text with the tags stripped.
        if e.code == 400:
            print(f"WARN: HTML post rejected ({detail}); retrying as plain text.", file=sys.stderr)
            # Keep link targets: "<a href=U>label</a>" -> "label U", THEN strip the
            # remaining tags (a bare strip would silently drop the read-the-brief URL),
            # and unescape all entities (&quot; included) in one go.
            plain = re.sub(r'<a href="([^"]*)">([^<]*)</a>', r"\2 \1", message)
            plain = _html.unescape(re.sub(r"<[^>]+>", "", plain))
            try:
                status = post(plain, as_html=False)
                print(f"Telegram sent ✓ (plain, {status}) -> {chat_id}")
                return 0
            except urllib.error.HTTPError as e2:
                print(f"ERROR {e2.code}: {e2.read().decode('utf-8', 'replace')}", file=sys.stderr)
                return 4
        print(f"ERROR {e.code}: {detail}", file=sys.stderr)
        return 4
    except urllib.error.URLError as e:
        print(f"ERROR: network failure: {e.reason}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
