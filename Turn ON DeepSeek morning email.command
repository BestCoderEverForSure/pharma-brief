#!/bin/bash
# Double-click this to ENABLE the automatic 7am DeepSeek digest email.
launchctl unload ~/Library/LaunchAgents/com.pharma-digest.morning.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.pharma-digest.morning.plist 2>/dev/null \
  && echo "✅ DeepSeek morning email ENABLED — it will run at 7am daily (Mac must be awake)." \
  || echo "⚠️ Could not enable. Is the plist at ~/Library/LaunchAgents/com.pharma-digest.morning.plist ?"
echo ""
echo "You can close this window."
