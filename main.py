#!/usr/bin/env python3
"""Weather Kalshi paper bot — multi-city daily high temperature markets."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Allow `python main.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from advisor import advise
from config import load_settings
from forecast import fetch_ensemble_high
from markets import fetch_market_settlement, fetch_open_weather_markets, resolve_target_date
from paper_book import PaperBook
from probability import build_temp_pmf, score_contracts


def _pct(x: float) -> str:
    return f"{100.0 * x:.1f}%"


def settle_open_fills(settings, book: PaperBook, *, verbose: bool = True) -> None:
    """Mark paper fills won/lost from Kalshi finalized market results."""
    for fill in list(book.open_fills()):
        try:
            settled = fetch_market_settlement(settings.kalshi_base, fill.ticker)
        except Exception as exc:
            if verbose:
                print(f"SETTLE SKIP {fill.ticker}: {exc}")
            continue
        if settled.status not in {"finalized", "settled"}:
            continue
        if settled.result not in {"yes", "no"}:
            continue
        won = settled.result == "yes"
        book.settle_fill(fill, won=won, settled_temp_f=settled.expiration_value)
        if verbose:
            print(
                f"SETTLED {'WIN' if won else 'LOSS'} {fill.ticker} "
                f"temp={settled.expiration_value} P/L ${fill.pnl:+.2f} | "
                f"{book.summary_line()}"
            )


def run_city(settings, book: PaperBook, city: str, *, verbose: bool = True) -> None:
    meta = settings.city_meta(city)
    series = settings.series_for(city)
    target = resolve_target_date(settings.target_date, meta["timezone"])

    if book.has_open_for(city, target):
        if verbose:
            print(
                f"\n{city} {meta['station']} | high {target.isoformat()} | "
                f"already holding open paper bet — skip new entries | "
                f"{book.summary_line()}"
            )
        return

    forecast = fetch_ensemble_high(
        lat=meta["lat"],
        lon=meta["lon"],
        timezone=meta["timezone"],
        target=target,
    )
    pmf = build_temp_pmf(forecast.members_f)
    contracts = fetch_open_weather_markets(
        settings.kalshi_base,
        series,
        target,
    )
    scored = score_contracts(pmf, contracts)
    decision = advise(scored, min_edge=settings.min_edge)

    if verbose:
        print(
            f"\n{city} {meta['station']} | high {target.isoformat()} | "
            f"ensemble mean {forecast.mean_f:.1f}°F "
            f"[{forecast.min_f:.1f}, {forecast.max_f:.1f}] "
            f"n={len(forecast.members_f)} | {book.summary_line()}"
        )
        print(f"Kalshi open contracts: {len(contracts)} ({series})")
        for row in scored[:8]:
            marker = "<--" if decision.pick and row.ticker == decision.pick.ticker else ""
            print(
                f"  {row.label:<16} model {_pct(row.model_yes):>6}  "
                f"mkt {_pct(row.market_yes):>6}  edge {row.edge*100:+5.1f}¢  "
                f"{row.ticker} {marker}"
            )
        print(f"Advice: {decision.action} — {decision.reason}")

    if (
        settings.auto_bet
        and decision.action == "BUY_YES"
        and decision.pick is not None
    ):
        # Prefer ask when available (conservative paper entry).
        ask = next(
            (c.yes_ask for c in contracts if c.ticker == decision.pick.ticker),
            0.0,
        )
        price = ask if ask > 0 else max(decision.pick.market_yes, 0.01)
        fill = book.buy_yes(
            ticker=decision.pick.ticker,
            label=decision.pick.label,
            price=price,
            notional=settings.stake_notional,
            model_yes=decision.pick.model_yes,
            edge=decision.pick.edge,
            city=city,
            target=target,
            series=series,
        )
        if fill and verbose:
            print(
                f"PAPER BUY YES {fill.contracts:.2f} @ {fill.price:.3f} "
                f"on {fill.ticker} ({fill.label})"
            )
        elif verbose and fill is None:
            print("PAPER BUY skipped (duplicate, bankroll, or bad price)")


def run_once(settings, book: PaperBook, *, verbose: bool = True) -> None:
    settle_open_fills(settings, book, verbose=verbose)
    for city in settings.cities:
        try:
            run_city(settings, book, city, verbose=verbose)
        except Exception as exc:
            # Keep other cities scanning if one series/forecast fails.
            print(f"\nERROR [{city}]: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Weather Kalshi paper bot")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single scan and exit",
    )
    args = parser.parse_args()

    settings = load_settings()
    book = PaperBook.load_or_create(settings.state_path, settings.paper_bankroll)
    cities = ",".join(settings.cities)

    print(
        f"Weather paper bot | cities={cities} "
        f"target={settings.target_date} min_edge={settings.min_edge:.0%} "
        f"stake=${settings.stake_notional:g} state={settings.state_path}"
    )
    print(book.summary_line())

    if args.once:
        run_once(settings, book)
        print(book.summary_line())
        return

    try:
        while True:
            try:
                run_once(settings, book)
            except Exception as exc:  # keep loop alive on transient API errors
                print(f"ERROR: {exc}")
            sys.stdout.flush()
            time.sleep(settings.loop_interval_seconds)
    except KeyboardInterrupt:
        print("\nStopped.")
        print(book.summary_line())
        for f in book.fills[-20:]:
            print(
                f"  {f.ts} {f.status.upper():4} YES {f.contracts:.2f}@${f.price:.3f} "
                f"P/L ${f.pnl:+.2f} {f.ticker}"
            )


if __name__ == "__main__":
    main()
