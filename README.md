# weatherpredict

Kalshi **daily high-temperature** paper bot. Pulls an Open-Meteo **ensemble**
forecast, turns it into integer °F probabilities, compares them to live
`KXHIGH*` market mids, and papers YES when edge ≥ `MIN_EDGE`.

Hands-off mode: persists the paper book, skips cities that already have an
open bet, and auto-settles fills when Kalshi marks the market finalized.

Moved out of [cryptodirectionpredict](https://github.com/RulzzBot-svg/cryptodirectionpredict)
so the weather stack can evolve separately from the BTC 15m bot.

## Quick start (local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py --once
```

Loop forever (same as Render):

```bash
python main.py
```

## Set-and-forget on Render (do once)

You need a **new** Background Worker for this repo (don’t reuse the BTC one).

### Option A — Blueprint (easiest)

1. Push/merge to `main`
2. Render → **New → Blueprint** → select `weatherpredict`
3. Confirm `render.yaml` (`weatherpredict-paper` worker + 1GB disk)
4. Deploy

Auto-deploys on every push to `main` after that.

### Option B — Manual worker

1. Render → **New → Background Worker** → `RulzzBot-svg/weatherpredict`
2. **Build:** `pip install -r requirements.txt`
3. **Start:** `python main.py`
4. Add a **persistent disk** mounted at `/var/data` (keeps bankroll/fills across restarts)
5. Env vars:

| Key | Value |
|-----|-------|
| `PYTHONUNBUFFERED` | `1` |
| `STATE_PATH` | `/var/data/paper_book.json` |
| `CITY` | `ALL` |
| `TARGET_DATE` | `tomorrow` |
| `MIN_EDGE` | `0.08` |
| `STAKE_NOTIONAL` | `10` |
| `PAPER_BANKROLL` | `1000` |
| `AUTO_BET` | `true` |
| `LOOP_INTERVAL_SECONDS` | `300` |

Leave it running. Check logs occasionally; no daily babysitting required.

## What it does each loop

1. Settles any open paper fills whose Kalshi markets are `finalized`
2. For each city in `CITY` (`ALL` = NYC/CHI/MIA/LAX):
   - Skips if that city already has an open bet for the target date
   - Forecast → integer °F PMF → score open `KXHIGH*` contracts
   - Papers YES on best edge if `AUTO_BET=true` and edge ≥ `MIN_EDGE`
3. Sleeps `LOOP_INTERVAL_SECONDS` (default 5 minutes)

State file: `STATE_PATH` (default `data/paper_book.json`).

## Settlement rules (important)

Kalshi city highs settle on the **NWS CLI integer high** at the listed station.
This bot reads Kalshi’s own finalized `result` / `expiration_value` so paper
P/L matches the exchange.

| strike_type | YES if |
|-------------|--------|
| `between`   | floor ≤ temp ≤ cap |
| `greater`   | temp > floor (ticker T87 ⇒ 88°+) |
| `less`      | temp < cap (ticker T80 ⇒ 79°−) |

| City | Series | Station |
|------|--------|---------|
| NYC | `KXHIGHNY` | Central Park |
| CHI | `KXHIGHCHI` | Chicago Midway |
| MIA | `KXHIGHMIA` | Miami Intl |
| LAX | `KXHIGHLAX` | LAX |

## Config

See `.env.example`.

## Sanity check

```bash
python -m py_compile main.py config.py forecast.py markets.py probability.py advisor.py paper_book.py
python main.py --once
```

## Not included yet

- Live Kalshi order placement (paper only)
- Fee-aware sizing / liquidity filters beyond ask entry
- Telegram / email alerts
- Historical calibration / CLV tracking
