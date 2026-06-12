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
import sys
import json
import html as _html
import datetime
import urllib.request
import urllib.error
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECRETS_PATH = Path.home() / ".config" / "pharma-news" / "secrets.env"
RESEND_ENDPOINT = "https://api.resend.com/emails"


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
    """Minimal inline markdown -> HTML (links, bold, italic)."""
    import re
    text = _html.escape(text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def md_to_html(md: str) -> str:
    """Convert the digest's markdown subset to clean HTML for email."""
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
            out.append(f"<h3>{md_inline(line[4:])}</h3>")
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
    body = "\n".join(out)
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f5f5f7;">
<div style="max-width:680px;margin:0 auto;padding:28px 32px;background:#ffffff;
            font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
            color:#1d1d1f;line-height:1.55;font-size:15px;">
{body}
</div></body></html>"""


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
        out.write_text(md_to_html(digest_path.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"Email preview written ✓ -> {out}")
        return 0

    secrets = load_secrets()
    api_key = secrets.get("RESEND_API_KEY")
    to_addr = secrets.get("EMAIL_TO")
    from_addr = secrets.get("EMAIL_FROM", "onboarding@resend.dev")

    if not api_key or not to_addr:
        print("ERROR: missing RESEND_API_KEY or EMAIL_TO.\n"
              f"Set them as env vars or in {SECRETS_PATH}", file=sys.stderr)
        return 2

    digest_path = find_digest(sys.argv[1] if len(sys.argv) > 1 else None)
    if not digest_path.exists():
        print(f"ERROR: digest not found: {digest_path}", file=sys.stderr)
        return 3

    md = digest_path.read_text(encoding="utf-8")
    # Subject = first H1 line if present, else a default.
    subject = next((l[2:].strip() for l in md.splitlines() if l.startswith("# ")),
                   f"Pharma Morning Digest — {datetime.date.today().isoformat()}")

    payload = json.dumps({
        "from": from_addr,
        "to": [to_addr],
        "subject": subject,
        "html": md_to_html(md),
        "text": md,
    }).encode("utf-8")

    req = urllib.request.Request(
        RESEND_ENDPOINT, data=payload, method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 "User-Agent": "pharma-digest/1.0 (+https://resend.com)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            print(f"Sent ✓  ({resp.status})  -> {to_addr}\n{body}")
            return 0
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
        return 4
    except urllib.error.URLError as e:
        print(f"ERROR: network failure: {e.reason}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
