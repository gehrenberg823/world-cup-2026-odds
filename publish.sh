#!/usr/bin/env bash
# Refresh Kalshi quotes and publish the updated dashboard to GitHub Pages.
set -e
cd "$(dirname "$0")"
python3 refresh_kalshi.py
git add index.html
git commit -m "Refresh Kalshi quotes ($(date '+%Y-%m-%d %H:%M'))" || { echo "No changes to publish."; exit 0; }
git push
echo "Published. Live page will update in ~1 minute."
