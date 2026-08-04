# weatherpredict

Kalshi **daily high-temperature** paper bot. Pulls an Open-Meteo **ensemble**
forecast, turns it into integer °F probabilities, compares them to live
`KXHIGH*` market mids, and papers YES when edge ≥ `MIN_EDGE`.

Moved out of [cryptodirectionpredict](https://github.com/RulzzBot-svg/cryptodirectionpredict)
so the weather stack can evolve separately from the BTC 15m bot.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py --once
```

Loop every minute:

```bash
python main.py
```

## What it does

1. Resolves `TARGET_DATE` (`today` / `tomorrow` / `YYYY-MM-DD`) per city TZ
2. Scans `CITY` — one city, a comma list, or `ALL` (`NYC`, `CHI`, `MIA`, `LAX`)
3. Pulls Open-Meteo ensemble daily max temps (°F)
4. Builds an integer °F probability mass function (ensemble + light Normal blend)
5. Loads open Kalshi contracts for each city’s series on that date
6. Scores each contract’s model P(YES) vs market mid
7. Papers YES on the best edge if `AUTO_BET=true` and edge ≥ `MIN_EDGE`

Example status:

```text
NYC Central Park | high 2026-08-05 | ensemble mean 85.6°F [81.5, 88.7] n=31
Kalshi open contracts: 6 (KXHIGHNY)
  82° to 83°       model  28.4%  mkt  44.0%  edge -15.6¢
  80° to 81°       model  18.1%  mkt  34.5%  edge -16.4¢
Advice: SKIP — best edge ...
```

## Settlement rules (important)

Kalshi city highs settle on the **NWS CLI integer high** at the listed station:

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

See `.env.example`. Useful knobs:

| Variable | Default | Meaning |
|----------|---------|---------|
| `CITY` | `ALL` | `NYC` / `CHI` / `MIA` / `LAX` / `NYC,CHI` / `ALL` |
| `KALSHI_SERIES` | city default | only applied when `CITY` is a single city |
| `TARGET_DATE` | `tomorrow` | `today` / `tomorrow` / ISO date |
| `MIN_EDGE` | `0.08` | 8¢ model − market |
| `STAKE_NOTIONAL` | `10` | paper dollars per fill |
| `AUTO_BET` | `true` | paper fills when edged |

## Sanity check

```bash
python -m py_compile main.py config.py forecast.py markets.py probability.py advisor.py paper_book.py
python main.py --once
```

## Not included yet

- Live Kalshi order placement (paper only)
- Fee / ask-aware entry
- Historical calibration / CLV tracking
- NWS CLI settlement auto-resolver
