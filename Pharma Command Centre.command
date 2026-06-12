#!/bin/bash
# ════════════════════════════════════════════════════════════════════════
#  PHARMA BRIEF — COMMAND CENTRE
#  Double-click this to control everything from one menu (Mac dialogs).
#  Controls: local digests, the cloud (run / 7am on-off), website, sources,
#  status, and audio. No commands to type.
# ════════════════════════════════════════════════════════════════════════
DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$DIR" || exit 1
WF="pharma-digest.yml"
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)

dlg(){ osascript -e "display dialog \"$1\" buttons {\"OK\"} default button \"OK\"" >/dev/null 2>&1; }

pick_window(){  # -> HOURS
  local w; w=$(osascript -e 'choose from list {"Today (last 24h)","This week (7 days)","This month (30 days)"} with prompt "Time window?" default items {"Today (last 24h)"}' 2>/dev/null)
  case "$w" in ""|false) return 1;; *week*) HOURS=168;; *month*) HOURS=720;; *) HOURS=24;; esac
}
pick_edition(){  # -> EDITION
  local e; e=$(osascript -e 'choose from list {"Morning (2-3 min)","Evening (5-8 min + deep dive)"} with prompt "Edition?" default items {"Morning (2-3 min)"}' 2>/dev/null)
  case "$e" in ""|false) return 1;; *Evening*) EDITION=evening;; *) EDITION=morning;; esac
}
workflow_state(){ gh api "repos/$REPO/actions/workflows" --jq ".workflows[]|select(.path==\".github/workflows/$WF\")|.state" 2>/dev/null; }

while true; do
  choice=$(osascript -e 'choose from list {"📰 Generate a digest now (this Mac)","🌐 Open the website","☁️ Run the cloud digest now (emails + website)","⏰ Daily 7am cloud digest: turn ON / OFF","📊 Status","✏️ Edit watchlist / sources / calendar","🔊 Make an audio brief","❓ Help / guide"} with prompt "PHARMA BRIEF — COMMAND CENTRE

What would you like to do?" default items {"📰 Generate a digest now (this Mac)"}' 2>/dev/null)
  [ "$choice" = "false" ] || [ -z "$choice" ] && exit 0

  case "$choice" in
    "📰 Generate"*)
      pick_window || continue; pick_edition || continue
      em=$(osascript -e 'button returned of (display dialog "Also email it to you?" buttons {"No","Yes"} default button "Yes")' 2>/dev/null)
      EM=""; [ "$em" = "Yes" ] && EM="--email"
      echo "Generating a $EDITION digest for the last ${HOURS}h..."
      if python3 deepseek/run_digest.py --hours "$HOURS" --edition "$EDITION" $EM; then
        a=$(osascript -e 'button returned of (display dialog "✅ Done — digest generated and website updated." buttons {"Close","Open website"} default button "Open website")' 2>/dev/null)
        [ "$a" = "Open website" ] && open "$DIR/site/public/index.html"
      else dlg "Something went wrong — see the Terminal text above."; fi ;;

    "☁️ Run the cloud"*)
      [ -z "$REPO" ] && { dlg "Cloud isn't connected (GitHub CLI not signed in)."; continue; }
      pick_window || continue; pick_edition || continue
      if gh workflow run "$WF" -f hours="$HOURS" -f edition="$EDITION" >/dev/null 2>&1; then
        dlg "☁️ Cloud run started. You'll get the email and the website will update in ~1-2 minutes."
      else dlg "Couldn't start the cloud run."; fi ;;

    "⏰ Daily"*)
      [ -z "$REPO" ] && { dlg "Cloud isn't connected (GitHub CLI not signed in)."; continue; }
      st=$(workflow_state); cur="unknown"
      [ "$st" = "active" ] && cur="ON"; [ "$st" = "disabled_manually" ] && cur="OFF"
      pick=$(osascript -e "button returned of (display dialog \"The daily 7am cloud digest is currently: $cur\" buttons {\"Turn OFF\",\"Turn ON\",\"Cancel\"} default button \"Cancel\")" 2>/dev/null)
      case "$pick" in
        "Turn ON")  gh workflow enable  "$WF" >/dev/null 2>&1 && dlg "✅ Daily 7am cloud digest is now ON." ;;
        "Turn OFF") gh workflow disable "$WF" >/dev/null 2>&1 && dlg "🛑 Daily 7am cloud digest is now OFF." ;;
      esac ;;

    "🌐 Open"*)
      [ -f "$DIR/site/public/index.html" ] && open "$DIR/site/public/index.html"
      [ -n "$REPO" ] && open "https://$(echo "$REPO" | cut -d/ -f1 | tr 'A-Z' 'a-z').github.io/$(echo "$REPO" | cut -d/ -f2)/" ;;

    "📊 Status"*)
      last=$(python3 -c "import json;print(json.load(open('pharma-news/state.json')).get('last_run') or 'never')" 2>/dev/null)
      st=$(workflow_state); cloud="unknown"
      [ "$st" = "active" ] && cloud="ON (auto ~7am Rome)"; [ "$st" = "disabled_manually" ] && cloud="OFF"
      lastrun=$(gh run list -R "$REPO" --workflow "$WF" --limit 1 --json conclusion,createdAt --jq '.[0]|"\(.conclusion // "?") (\(.createdAt[0:10]))"' 2>/dev/null)
      dlg "📊 STATUS

Local last run: $last
Daily cloud digest: $cloud
Last cloud run: ${lastrun:-none}" ;;

    "✏️ Edit"*)
      f=$(osascript -e 'choose from list {"Watchlist (companies & topics)","News sources (feeds)","Catalyst calendar"} with prompt "Edit which file? (opens in TextEdit)"' 2>/dev/null)
      case "$f" in
        *Watchlist*) open -e "$DIR/pharma-news/watchlist.md" ;;
        *sources*)   open -e "$DIR/deepseek/feeds.txt" ;;
        *Catalyst*)  open -e "$DIR/pharma-news/catalysts.md" ;;
      esac ;;

    "🔊 Make"*)
      if python3 pharma-news/make_audio.py; then
        a=$(osascript -e 'button returned of (display dialog "🔊 Audio brief created." buttons {"Close","Play"} default button "Play")' 2>/dev/null)
        [ "$a" = "Play" ] && open "$DIR/digests/audio/$(date +%F).m4a"
      else dlg "Audio failed — generate a digest first."; fi ;;

    "❓ Help"*) open "$DIR/GUIDE.md" ;;
  esac
done
