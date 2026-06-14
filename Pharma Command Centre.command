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

pick_kind(){ local k; k=$(menu "What kind of brief?" \
    "Daily brief (last 24h)" \
    "Evening deep-dive (last 24h)" \
    "Week in Review (last 7 days, retrospective)" \
    "Week Ahead (forward look at the coming week)" \
    "Last 30 days (daily style)")
  case "$k" in
    ""|false) return 1;;
    "Daily brief"*)       HOURS=24;  EDITION=morning; MODE=daily;;
    "Evening deep-dive"*) HOURS=24;  EDITION=evening; MODE=daily;;
    "Week in Review"*)    HOURS=168; EDITION=evening; MODE=review;;
    "Week Ahead"*)        HOURS=168; EDITION=evening; MODE=ahead;;
    "Last 30 days"*)      HOURS=720; EDITION=morning; MODE=daily;;
  esac; }
wf_state(){ gh api "repos/$REPO/actions/workflows" --jq ".workflows[]|select(.path==\".github/workflows/$WF\")|.state" 2>/dev/null; }
recips(){ grep '^EMAIL_TO=' "$S" 2>/dev/null | cut -d= -f2-; }
set_recips(){ perl -i -pe "s|^EMAIL_TO=.*|EMAIL_TO=$1|" "$S"; [ -n "$REPO" ] && gh secret set EMAIL_TO --body "$1" -R "$REPO" >/dev/null 2>&1; }
sched(){ python3 -c "import json;c=json.load(open('pharma-news/config.json'));print(c.get('delivery_time','07:00'),c.get('target_timezone','Europe/Rome'))" 2>/dev/null || echo "07:00 Europe/Rome"; }
engine_name(){ local e; e=$(grep '^PHARMA_ENGINE=' "$S" 2>/dev/null | cut -d= -f2- | sed "s/[\"' ]//g"); [ -z "$e" ] && e="gemini (default)"; echo "$e"; }
status_line(){ echo "Engine: $(engine_name)      Daily send: $(sched)"; }

# ---- actions ----
act_generate(){
  pick_kind || return
  local em; em=$(osascript -e 'button returned of (display dialog "Also email it to the subscriber list?" buttons {"No, just the website","Yes, email it"} default button "Yes, email it" with title "Pharma Command Centre")' 2>/dev/null)
  local f=""; [ "$em" = "Yes, email it" ] && f="--email"
  echo "Generating a $MODE/$EDITION digest for the last ${HOURS}h..."
  if python3 deepseek/run_digest.py --hours "$HOURS" --edition "$EDITION" --mode "$MODE" $f; then
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
  local c; c=$(menu "Send & schedule — the automatic cloud digest:" \
    "Send today's brief now (email + Telegram + website)" \
    "Set the daily send time & timezone" \
    "Daily auto-send: turn ON or OFF" \
    "Status & last run")
  case "$c" in
    "Send today"*) pick_kind || return
       gh workflow run "$WF" -f hours="$HOURS" -f edition="$EDITION" -f mode="$MODE" >/dev/null 2>&1 \
         && dlg "☁️ Cloud run started — email, Telegram, and the online website update in ~1–2 minutes." || dlg "Couldn't start the cloud run." ;;
    "Set the daily"*) act_schedule ;;
    "Daily auto-send"*) local st; st=$(wf_state); local cur="unknown"; [ "$st" = active ] && cur=ON; [ "$st" = disabled_manually ] && cur=OFF
       local p; p=$(osascript -e "button returned of (display dialog \"The daily cloud digest (currently: $cur) sends at $(sched).\" buttons {\"Turn OFF\",\"Turn ON\",\"Cancel\"} default button \"Cancel\" with title \"Pharma Command Centre\")" 2>/dev/null)
       [ "$p" = "Turn ON" ]  && gh workflow enable  "$WF" >/dev/null 2>&1 && dlg "✅ Daily cloud digest ON."
       [ "$p" = "Turn OFF" ] && gh workflow disable "$WF" >/dev/null 2>&1 && dlg "🛑 Daily cloud digest OFF." ;;
    "Status"*) local last; last=$(python3 -c "import json;print(json.load(open('pharma-news/state.json')).get('last_run') or 'never')" 2>/dev/null)
       local st; st=$(wf_state); local cl="unknown"; [ "$st" = active ] && cl="ON"; [ "$st" = disabled_manually ] && cl="OFF"
       local lr; lr=$(gh run list -R "$REPO" --workflow "$WF" --limit 1 --json conclusion,createdAt --jq '.[0]|"\(.conclusion) (\(.createdAt[0:10]))"' 2>/dev/null)
       dlg "STATUS\n\nEngine: $(engine_name)\nDaily auto-send: $cl, at $(sched)\nLast cloud run: ${lr:-none}\nEmail goes to: $(recips)" ;;
  esac
}

act_schedule(){
  local cur; cur=$(python3 -c "import json;print(json.load(open('pharma-news/config.json')).get('delivery_time','07:00'))" 2>/dev/null); [ -z "$cur" ] && cur="07:00"
  local t; t=$(ask "Send the daily brief at what time? (24-hour, e.g. 07:00)" "$cur"); [ -z "$t" ] && return
  local z; z=$(menu "…in which timezone is that time?" "Europe/Rome" "Asia/Singapore" "Europe/London" "America/New_York" "America/Los_Angeles" "Asia/Kolkata" "Other (type it)")
  case "$z" in ""|false) return;; "Other"*) z=$(ask "Type the timezone (IANA name, e.g. Europe/Paris)" "Europe/Rome"); [ -z "$z" ] && return;; esac
  local outp; outp=$(python3 pharma-news/set_schedule.py "$t" "$z" 2>&1)
  [ $? -ne 0 ] && { dlg "Couldn't set the schedule:\n\n$outp"; return; }
  local pushed="saved on this Mac (cloud not connected)"
  if [ -n "$REPO" ]; then
    git add .github/workflows/pharma-digest.yml pharma-news/config.json >/dev/null 2>&1
    if git commit -m "schedule: $t $z" >/dev/null 2>&1; then
      if git pull --rebase origin main >/dev/null 2>&1 && git push >/dev/null 2>&1; then pushed="cloud schedule updated ✓"
      else pushed="saved locally; cloud push failed — open the menu again to retry"; fi
    else pushed="no change needed"; fi
  fi
  dlg "🕖 $outp\n\nDaily cloud run: $pushed\n\nGitHub runs in UTC — re-set this after a daylight-saving change to keep the local time exact."
}

act_settings(){
  local c; c=$(menu "Settings:" "Choose engine (Gemini / DeepSeek)" "Edit watchlist, news sources, or catalysts")
  case "$c" in
    "Choose engine"*) act_engine ;;
    "Edit watchlist"*) act_customise ;;
  esac
}

act_engine(){
  local e; e=$(menu "Which AI engine writes the morning brief?" "Gemini (primary)" "DeepSeek")
  local ENG
  case "$e" in ""|false) return;; *Gemini*) ENG=gemini;; *DeepSeek*) ENG=deepseek;; *) return;; esac
  # Local runs (this Mac): set PHARMA_ENGINE in the secrets file.
  if grep -q '^PHARMA_ENGINE=' "$S" 2>/dev/null; then
    perl -i -pe "s|^PHARMA_ENGINE=.*|PHARMA_ENGINE=$ENG|" "$S"
  else
    printf 'PHARMA_ENGINE=%s\n' "$ENG" >> "$S"
  fi
  # Daily cloud run: a repo Variable (not a secret).
  local cloud="(cloud not connected)"
  [ -n "$REPO" ] && gh variable set PHARMA_ENGINE --body "$ENG" -R "$REPO" >/dev/null 2>&1 && cloud="cloud updated ✓"
  local warn=""; [ "$ENG" = gemini ] && warn="\n\nGemini needs GEMINI_API_KEY set locally and as a GitHub Secret."
  dlg "✅ Engine set to: $ENG\n\nThis Mac: updated ✓\nDaily cloud run: $cloud$warn"
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
  choice=$(menu "Pharma Morning Brief — Command Centre
$(status_line)" \
    "Read the latest brief" \
    "Make a brief now  (on this Mac only)" \
    "Send & schedule  (the automatic cloud digest)" \
    "Settings  (engine, sources, watchlist, catalysts)" \
    "Listen to the audio brief" \
    "Help — how it all works")
  case "$choice" in
    ""|false) exit 0 ;;
    "Read the latest"*) act_read ;;
    "Make a brief"*)    act_generate ;;
    "Send & schedule"*) act_cloud ;;
    "Settings"*)        act_settings ;;
    "Listen"*)          act_audio ;;
    "Help"*)            open "$DIR/GUIDE.md" ;;
  esac
done
