#!/usr/bin/env bash
# Refresh all data sources (Opta, Pinnacle, Kalshi) and publish to GitHub Pages.
set -e
cd "$(dirname "$0")"
python3 refresh_opta.py              # Opta Supercomputer probabilities (SEED opta)
python3 refresh_pinnacle.py --write  # Pinnacle de-vigged odds (SEED market)
python3 refresh_kalshi.py            # live Kalshi quotes

# Only republish (and stamp the "last updated" time) when the data actually changed,
# so the timestamp reflects a real data update rather than every time this is run.
if git diff --quiet -- index.html; then
  echo "No data changes to publish."
  exit 0
fi

# Stamp the current time into the page's "Data last updated" marker.
python3 - "$(date '+%Y-%m-%d %H:%M %Z')" <<'PY'
import re, sys
ts = sys.argv[1]
with open('index.html', encoding='utf-8') as f:
    html = f.read()
html = re.sub(r'(<!--LAST_UPDATED-->).*?(<!--/LAST_UPDATED-->)',
              lambda m: m.group(1) + ts + m.group(2), html, flags=re.S)
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
PY

git add index.html
git commit -m "Refresh Opta + Pinnacle + Kalshi ($(date '+%Y-%m-%d %H:%M'))"
git push
echo "Published. Live page will update in ~1 minute."
