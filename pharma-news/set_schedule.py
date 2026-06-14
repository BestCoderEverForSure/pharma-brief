#!/usr/bin/env python3
"""
Set the automatic send time + timezone for the cloud digest.

Updates `pharma-news/config.json` and the GitHub Actions cron in
`.github/workflows/pharma-digest.yml` (GitHub cron is UTC, so the local time is
converted). Preserves each cron's day-of-week (Mon–Sat brief + Sunday weekly).

Usage:
    python3 pharma-news/set_schedule.py "07:00" "Europe/Rome"

Stdlib only — no pip installs. The caller (Command Centre) commits + pushes the
changes so the cloud schedule actually updates.
"""

import re
import sys
import json
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "pharma-news" / "config.json"
WORKFLOW = ROOT / ".github" / "workflows" / "pharma-digest.yml"


def config_time(config_path: Path):
    """(delivery_time, target_timezone) from config.json, or (None, None). Lets the weekly
    DST re-time workflow run `set_schedule.py` with no args to re-pin the configured time."""
    if not config_path.exists():
        return None, None
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
    except ValueError:
        return None, None
    return cfg.get("delivery_time"), cfg.get("target_timezone")


def main() -> int:
    if len(sys.argv) >= 3:
        tstr, tz = sys.argv[1].strip(), sys.argv[2].strip()
    else:
        # No args → re-pin from config.json (the weekly DST re-time workflow uses this).
        tstr, tz = config_time(CONFIG)
        if not tstr or not tz:
            print('Usage: set_schedule.py "HH:MM" "IANA/Timezone"  '
                  '(or set delivery_time + target_timezone in config.json)', file=sys.stderr)
            return 2
        tstr, tz = tstr.strip(), tz.strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", tstr)
    if not m:
        print(f"ERROR: bad time '{tstr}' — use 24h HH:MM (e.g. 07:00)", file=sys.stderr)
        return 2
    H, M = int(m.group(1)), int(m.group(2))
    if not (0 <= H < 24 and 0 <= M < 60):
        print("ERROR: time out of range", file=sys.stderr)
        return 2
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        print(f"ERROR: unknown timezone '{tz}' (use an IANA name, e.g. Europe/Rome)", file=sys.stderr)
        return 2

    # Convert the chosen local time to UTC using today's date, so the current DST offset
    # is applied. (GitHub cron has no timezone; re-run after a DST change to stay exact.)
    local = dt.datetime.now(zone).replace(hour=H, minute=M, second=0, microsecond=0)
    u = local.astimezone(dt.timezone.utc)
    UH, UM = u.hour, u.minute

    # If converting to UTC crosses the calendar day, the weekday the cron fires on shifts
    # too — but we only rewrite the hour/minute, not the day-of-week field. Warn loudly
    # rather than silently schedule the wrong day. (07:00 Europe/Rome never triggers this.)
    if u.date() != local.date():
        when = "the previous day" if u.date() < local.date() else "the next day"
        print(f"WARNING: {H:02d}:{M:02d} {tz} falls on {when} in UTC ({UH:02d}:{UM:02d}). "
              f"The cron weekday is NOT auto-adjusted, so the scheduled day may be off by one — "
              f"review the 'cron:' lines in {WORKFLOW.name} by hand.", file=sys.stderr)

    # Update config.json, preserving any other keys (audio, etc.).
    cfg = {}
    if CONFIG.exists():
        try:
            cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        except ValueError:
            cfg = {}
    cfg["delivery_time"] = f"{H:02d}:{M:02d}"
    cfg["target_timezone"] = tz
    cfg["cron_utc"] = f"{UH:02d}:{UM:02d} UTC (all scheduled days)"
    cfg["note"] = (f"Automatic send {H:02d}:{M:02d} {tz} = {UH:02d}:{UM:02d} UTC. "
                   "GitHub cron is UTC — re-run set_schedule.py after a daylight-saving "
                   "change to keep the local time exact.")
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    # Rewrite both cron lines' minute+hour, keeping the day-of-week field intact.
    changed = 0
    if WORKFLOW.exists():
        wf = WORKFLOW.read_text(encoding="utf-8")
        wf, changed = re.subn(
            r'(- cron: ")\d+ \d+( \* \* [0-9-]+")',
            lambda mm: f"{mm.group(1)}{UM} {UH}{mm.group(2)}", wf)
        WORKFLOW.write_text(wf, encoding="utf-8")

    print(f"Schedule set: {H:02d}:{M:02d} {tz} = {UH:02d}:{UM:02d} UTC "
          f"({changed} cron line(s) updated).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
