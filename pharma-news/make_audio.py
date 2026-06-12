#!/usr/bin/env python3
"""
Narrate today's Pharma Digest to an audio file using the macOS `say` engine.
Free, offline, no API. Output: digests/audio/YYYY-MM-DD.m4a

Usage:
    python3 make_audio.py [path/to/digest.md]

Voice is read from pharma-news/config.json ("audio_voice", default "Daniel").
List installed voices with:  say -v '?'
"""

import re
import sys
import json
import datetime
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "pharma-news" / "config.json"


def find_digest(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    today = datetime.date.today().isoformat()
    return PROJECT_ROOT / "digests" / f"{today}.md"


def strip_markdown(md: str) -> str:
    """Turn the digest into clean, speakable prose."""
    out = []
    for raw in md.splitlines():
        line = raw.strip()
        if not line or line in ("---", "***", "___"):
            continue
        if line.startswith("|") or line.startswith("> *Facts verified"):
            continue  # skip tables and the accuracy footer
        # Drop the Sources section — links don't read well aloud.
        if line.lower().startswith("## sources"):
            break
        line = re.sub(r"^#{1,6}\s*", "", line)          # headings
        line = re.sub(r"^[->*]\s+", "", line)            # bullets/quotes
        line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)  # links -> text
        line = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)   # bold
        line = re.sub(r"\*([^*]+)\*", r"\1", line)       # italic
        line = re.sub(r"`([^`]+)`", r"\1", line)         # code
        # Strip leading emoji/symbols for cleaner narration.
        line = re.sub(r"^[^\w\"]+", "", line).strip()
        if line:
            out.append(line)
    return "\n".join(out)


def main() -> int:
    voice = "Daniel"
    if CONFIG_PATH.exists():
        try:
            voice = json.loads(CONFIG_PATH.read_text()).get("audio_voice", voice)
        except json.JSONDecodeError:
            pass

    digest = find_digest(sys.argv[1] if len(sys.argv) > 1 else None)
    if not digest.exists():
        print(f"ERROR: digest not found: {digest}", file=sys.stderr)
        return 3

    text = strip_markdown(digest.read_text(encoding="utf-8"))
    out_dir = PROJECT_ROOT / "digests" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{digest.stem}.m4a"

    # `say` writes AIFF natively; -o with .m4a triggers AAC encoding on macOS.
    try:
        subprocess.run(
            ["say", "-v", voice, "-o", str(out_file), text],
            check=True,
        )
    except FileNotFoundError:
        print("ERROR: `say` not found — this requires macOS.", file=sys.stderr)
        return 4
    except subprocess.CalledProcessError as e:
        print(f"ERROR: say failed ({e.returncode}). Try a valid voice (say -v '?').",
              file=sys.stderr)
        return 5

    print(f"Audio brief ✓  -> {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
