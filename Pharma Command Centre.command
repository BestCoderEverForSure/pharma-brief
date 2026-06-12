#!/bin/bash
# ════════════════════════════════════════════════════════════════════════
#  PHARMA BRIEF — COMMAND CENTRE
#  Double-click to control everything from one place (simple Mac menus).
#  Top menu groups actions; pick a group, then a specific action.
# ════════════════════════════════════════════════════════════════════════
DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$DIR" || exit 1
WF="pharma-digest.yml"
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
S="$HOME/.config/pharma-news/secrets.env"

# ---- little helpers ----
dlg(){  osascript -e "display dialog \"$1\" buttons {\"OK\"} default button \"OK\" with title \"Pharma Command Centre\"" >/dev/null 2>&1; }
ask(){  osascript -e "text returned of (display dialog \"$1\" default answer \"$2\" with title \"Pharma Command Centre\")" 2>/dev/null; }
menu(){ local p="$1"; shift; local l=""; for it in "$@"; do l="$l,\"$it\""; done; osascript -e "choose from list {${l#,}} with prompt \"$p\"" 2>/dev/null; }

pick_window(){ local w; w=$(menu "Time window?" "Today (last 24h)" "This week (7 days)" "This month (30 days)")
  case "$w" in ""|false) return 1;; *week*) HOURS=168;; *month*) HOURS=720;; *) HOURS=24;; esac; }
pick_edition(){ local e; e=$(menu "Edition?" "Morning (2-3 min)" "Evening (5-8 min + deep dive)")
  case "$e" in ""|false) return 1;; *Evening*) EDITION=evening;; *) EDITION=morning;; esac; }
wf_state(){ gh api "repos/$REPO/actions/workflows" --jq ".workflows[]|select(.path==\".github/workflows/$WF\")|.state" 2>/dev/null; }
recips(){ grep '^EMAIL_TO=' "$S" 2>/dev/null | cut -d= -f2-; }
set_recips(){ perl -i -pe "s|^EMAIL_TO=.*|EMAIL_TO=$1|" "$S"; [ -n "$REPO" ] && gh secret set EMAIL_TO --body "$1" -R "$REPO" >/dev/null 2>&1; }

# ---- actions ----
act_generate(){
  pick_window || return; pick_edition || return
  local em; em=$(osascript -e 'button returned of (display dialog "Also email it to the subscriber list?" buttons {"No, just the website","Yes, email it"} default button "Yes, email it" with title "Pharma Command Centre")' 2>/dev/null)
  local f=""; [ "$em" = "Yes, email it" ] && f="--email"
  echo "Generating a $EDITION digest for the last ${HOURS}h..."
  if python3 deepseek/run_digest.py --hours "$HOURS" --edition "$EDITION" $f; then
    local a; a=$(osascript -e 'button returned of (display dialog "✅ Done — digest generated and website updated." buttons {"Close","Open website"} default button "Open website" with title "Pharma Command Centre")' 2>/dev/null)
    [ "$a" = "Open website" ] && open "$DIR/site/public/index.html"
  else dlg "Something went wrong — see the Terminal text above."; fi
}

act_read(){
  local c; c=$(menu "How would you like to read it?" "Open in my browser" "Open on localhost (live server)" "Open the public website (online)")
  case "$c" in
    "Open in my browser") open "$DIR/site/public/index.html" ;;
    "Open on localhost"*) ( cd "$DIR/site/public" && python3 -m http.server 8765 >/dev/null 2>&1 & ); sleep 1; open "http://localhost:8765"
        dlg "🖥️ Running at http://localhost:8765 (keeps running until you quit this window)." ;;
    "Open the public"*) [ -n "$REPO" ] && open "https://$(echo "$REPO"|cut -d/ -f1|tr 'A-Z' 'a-z').github.io/$(echo "$REPO"|cut -d/ -f2)/" || dlg "No online site connected." ;;
  esac
}

act_cloud(){
  [ -z "$REPO" ] && { dlg "Cloud isn't connected (GitHub CLI not signed in)."; return; }
  local c; c=$(menu "Cloud & email:" "Run the cloud digest now" "Daily auto-send: turn ON / OFF" "Status & last run")
  case "$c" in
    "Run the cloud"*) pick_window || return; pick_edition || return
       gh workflow run "$WF" -f hours="$HOURS" -f edition="$EDITION" >/dev/null 2>&1 \
         && dlg "☁️ Cloud run started — email + website update in ~1-2 minutes." || dlg "Couldn't start the cloud run." ;;
    "Daily auto-send"*) local st; st=$(wf_state); local cur="unknown"; [ "$st" = active ] && cur=ON; [ "$st" = disabled_manually ] && cur=OFF
       local p; p=$(osascript -e "button returned of (display dialog \"Daily 7am cloud digest is currently: $cur\" buttons {\"Turn OFF\",\"Turn ON\",\"Cancel\"} default button \"Cancel\" with title \"Pharma Command Centre\")" 2>/dev/null)
       [ "$p" = "Turn ON" ]  && gh workflow enable  "$WF" >/dev/null 2>&1 && dlg "✅ Daily cloud digest ON."
       [ "$p" = "Turn OFF" ] && gh workflow disable "$WF" >/dev/null 2>&1 && dlg "🛑 Daily cloud digest OFF." ;;
    "Status"*) local last; last=$(python3 -c "import json;print(json.load(open('pharma-news/state.json')).get('last_run') or 'never')" 2>/dev/null)
       local st; st=$(wf_state); local cl="unknown"; [ "$st" = active ] && cl="ON (~7am Rome)"; [ "$st" = disabled_manually ] && cl="OFF"
       local lr; lr=$(gh run list -R "$REPO" --workflow "$WF" --limit 1 --json conclusion,createdAt --jq '.[0]|"\(.conclusion) (\(.createdAt[0:10]))"' 2>/dev/null)
       dlg "📊 STATUS\n\nLocal last run: $last\nDaily cloud digest: $cl\nLast cloud run: ${lr:-none}\nEmail goes to: $(recips)" ;;
  esac
}

act_customise(){
  local c; c=$(menu "What would you like to edit? (opens in TextEdit)" "Watchlist (companies & topics)" "News sources (feeds)" "Catalyst calendar")
  case "$c" in
    "Watchlist"*) open -e "$DIR/pharma-news/watchlist.md" ;;
    "News sources"*) open -e "$DIR/deepseek/feeds.txt" ;;
    "Catalyst"*) open -e "$DIR/pharma-news/catalysts.md" ;;
  esac
}

act_audio(){
  if python3 pharma-news/make_audio.py; then
    local a; a=$(osascript -e 'button returned of (display dialog "🔊 Audio brief created." buttons {"Close","Play"} default button "Play" with title "Pharma Command Centre")' 2>/dev/null)
    [ "$a" = "Play" ] && open "$DIR/digests/audio/$(date +%F).m4a"
  else dlg "Audio failed — generate a digest first."; fi
}

# ---- main loop ----
while true; do
  choice=$(menu "PHARMA BRIEF — COMMAND CENTRE     (pick a group)" \
    "📖  Read the brief" \
    "✍️  Make a new digest now" \
    "☁️  Cloud & email  ▸" \
    "✏️  Customise: sources, watchlist, calendar  ▸" \
    "🔊  Listen to the audio brief" \
    "❓  Help & how it works")
  case "$choice" in
    ""|false) exit 0 ;;
    *"Read the brief"*)   act_read ;;
    *"Make a new digest"*) act_generate ;;
    *"Cloud & email"*)    act_cloud ;;
    *"Customise"*)        act_customise ;;
    *"audio brief"*)      act_audio ;;
    *"Help"*)             open "$DIR/GUIDE.md" ;;
  esac
done
