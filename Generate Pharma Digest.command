#!/bin/bash
# Double-click to generate a digest (DeepSeek engine) with a few clicks — no typing.
# Pops native Mac dialogs to choose the window, edition, and whether to email it.

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

# 1) Time window
win=$(osascript -e 'choose from list {"Today (last 24h)","This week (7 days)","This month (30 days)"} with prompt "Which time window?" default items {"Today (last 24h)"}' 2>/dev/null)
[ "$win" = "false" ] || [ -z "$win" ] && exit 0
case "$win" in
  *week*)  hours=168 ;;
  *month*) hours=720 ;;
  *)       hours=24  ;;
esac

# 2) Edition
ed=$(osascript -e 'choose from list {"Morning (2-3 min)","Evening (5-8 min + deep dive)"} with prompt "Which edition?" default items {"Morning (2-3 min)"}' 2>/dev/null)
[ "$ed" = "false" ] || [ -z "$ed" ] && exit 0
case "$ed" in
  *Evening*) edition=evening ;;
  *)         edition=morning ;;
esac

# 3) Email it too?
em=$(osascript -e 'button returned of (display dialog "Also email it to you?" buttons {"No, just the website","Yes, email it"} default button "Yes, email it")' 2>/dev/null)
emailflag=""
[ "$em" = "Yes, email it" ] && emailflag="--email"

echo "Generating a $edition digest for the last ${hours}h $( [ -n "$emailflag" ] && echo '(and emailing it)')..."
echo "(this takes ~30-60 seconds)"
python3 deepseek/run_digest.py --hours "$hours" --edition "$edition" $emailflag
code=$?

if [ $code -eq 0 ]; then
  ans=$(osascript -e 'button returned of (display dialog "✅ Done — digest generated and the website updated." buttons {"Close","Open website"} default button "Open website")' 2>/dev/null)
  [ "$ans" = "Open website" ] && open "$DIR/site/public/index.html"
else
  osascript -e 'display dialog "⚠️ Something went wrong — check the Terminal text above for details." buttons {"OK"}' >/dev/null 2>&1
fi
echo ""
echo "You can close this window."
