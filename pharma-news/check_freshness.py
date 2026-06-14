#!/usr/bin/env python3
"""
Dead-man's-switch for the daily pipeline.

Exits non-zero if no digest has been archived recently, so the Heartbeat workflow fails
and GitHub emails you. This catches SILENT stalls the normal run can't report — a
disabled schedule, exhausted API quota for days, a stuck deploy — cases where there is
no failing run to email you about.

Usage:   python3 pharma-news/check_freshness.py
Tune:    MAX_AGE_DAYS (env, default 2) — alert when the newest digest is older than this.

Stdlib only — no pip installs.
"""

import os
import re
import sys
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIGESTS = ROOT / "digests"


def newest_digest_date(digests_dir: Path):
    """Most recent YYYY-MM-DD.md date in the archive, or None if there are none."""
    newest = None
    for p in digests_dir.glob("*.md"):
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})$", p.stem)
        if not m:
            continue
        try:
            d = dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            continue
        if newest is None or d > newest:
            newest = d
    return newest


def staleness(newest, today, max_age_days: int):
    """(ok, message). ok is False when there's no digest, or the newest is too old."""
    if newest is None:
        return False, "no archived digests found"
    age = (today - newest).days
    if age > max_age_days:
        return False, (f"newest digest is {newest} ({age} days old, limit {max_age_days}) — "
                       "the daily pipeline may have stalled; check the Actions tab")
    return True, f"newest digest {newest} ({age} days old)"


def main() -> int:
    max_age = int(os.environ.get("MAX_AGE_DAYS", "2"))
    ok, msg = staleness(newest_digest_date(DIGESTS), dt.date.today(), max_age)
    if ok:
        print(f"OK: {msg}")
        return 0
    print(f"ERROR: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
