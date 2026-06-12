#!/bin/bash
# Double-click this to DISABLE the automatic 7am DeepSeek digest email.
launchctl unload ~/Library/LaunchAgents/com.pharma-digest.morning.plist 2>/dev/null \
  && echo "🛑 DeepSeek morning email DISABLED." \
  || echo "ℹ️ It was already off."
echo ""
echo "You can close this window."
