# World Cup 2026 — Fair Probabilities

A single-page dashboard for building **fair probabilities** for 2026 FIFA World Cup
futures markets and comparing them to live **Kalshi** prices.

**Live page:** https://gehrenberg823.github.io/world-cup-2026-odds/

## What it does

For six markets — Outright Winner, Reach Final, Reach Semifinal, Reach Quarterfinal,
Win Group, Advance From Group — it blends two sources into a fair probability and shows
the Kalshi market alongside it:

| Column | Meaning |
|---|---|
| Opta | Opta / Stats Perform tournament-simulation probability |
| Market | Pinnacle (sharp book) price, de-vigged |
| Blended Fair % | Opta 50 / Pinnacle 50 weighted average (weights editable) |
| K Bid / K Ask / K Last | Live Kalshi YES quotes (¢) |
| Edge | Blended Fair % − Kalshi Ask (points). Green = +EV buying YES at the ask |
| Ticker | Link to the Kalshi market |

Weights are editable per market, teams sort by fair %, and there's CSV import/export
plus a sportsbook vig-removal helper. Everything is one self-contained `index.html`
(no build step, no external libraries).

## Refreshing the data

All three sources are fetched **server-side** and baked into `index.html` (CORS blocks
direct browser fetches). Each has its own script that surgically rewrites only its own
values:

```bash
pip install requests                  # one-time
python3 refresh_opta.py               # Opta probabilities    -> SEED `opta:`   (all 6 markets)
python3 refresh_pinnacle.py           # verify Pinnacle de-vig vs current values (no write)
python3 refresh_pinnacle.py --write   # Pinnacle de-vigged odds -> SEED `market:`
python3 refresh_kalshi.py             # live Kalshi quotes     -> KALSHI block
./publish.sh                          # runs all three + commit + push (updates the live page)
```

- **`refresh_opta.py`** pulls Stats Perform's `seasonandtournamentsimulations` feed via
  theanalyst.com's public outlet key and validates each market's probability sum.
- **`refresh_pinnacle.py`** pulls Pinnacle's guest API (FIFA World Cup, league 2686),
  de-vigs two-way markets Yes-vs-No and normalizes the field markets. Run without
  `--write` first to eyeball old-vs-new drift before committing.

## Data sources

- **Opta** — Stats Perform tournament-simulation feed (the data behind theanalyst.com's live predictions).
- **Pinnacle** — Pinnacle's public market data, de-vigged (two-way markets de-vigged Yes-vs-No; field markets normalized).
- **Kalshi** — public market data API.

All figures are a snapshot, not betting advice. Re-pull before trading.
