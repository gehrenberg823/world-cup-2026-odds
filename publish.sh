#!/usr/bin/env bash
# Refresh all data sources (Opta, Pinnacle, Kalshi) and publish to GitHub Pages.
set -e
cd "$(dirname "$0")"
python3 refresh_opta.py              # Opta Supercomputer probabilities (SEED opta)
python3 refresh_pinnacle.py --write  # Pinnacle de-vigged odds (SEED market)
python3 refresh_kalshi.py            # live Kalshi quotes
git add index.html
git commit -m "Refresh Opta + Pinnacle + Kalshi ($(date '+%Y-%m-%d %H:%M'))" || { echo "No changes to publish."; exit 0; }
git push
echo "Published. Live page will update in ~1 minute."
