"""Durable paper ledger for weather YES contracts."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class PaperFill:
    ticker: str
    label: str
    side: str  # YES
    contracts: float
    price: float
    model_yes: float
    edge: float
    city: str = ""
    target_date: str = ""  # ISO date
    series: str = ""
    status: str = "open"  # open | won | lost
    settled_temp_f: Optional[float] = None
    pnl: float = 0.0
    ts: str = field(default_factory=_utc_now)
    settled_ts: Optional[str] = None


@dataclass
class PaperBook:
    bankroll: float
    fills: list[PaperFill] = field(default_factory=list)
    path: Optional[Path] = None
    realized_pnl: float = 0.0
    wins: int = 0
    losses: int = 0

    def can_buy(self, notional: float) -> bool:
        return notional > 0 and self.bankroll >= notional

    def open_fills(self) -> list[PaperFill]:
        return [f for f in self.fills if f.status == "open"]

    def has_open_for(self, city: str, target: date) -> bool:
        key = target.isoformat()
        return any(
            f.status == "open" and f.city == city and f.target_date == key
            for f in self.fills
        )

    def has_ticker(self, ticker: str) -> bool:
        return any(f.ticker == ticker for f in self.fills)

    def buy_yes(
        self,
        *,
        ticker: str,
        label: str,
        price: float,
        notional: float,
        model_yes: float,
        edge: float,
        city: str,
        target: date,
        series: str,
    ) -> PaperFill | None:
        if price <= 0 or price >= 1:
            return None
        if self.has_ticker(ticker) or self.has_open_for(city, target):
            return None
        if not self.can_buy(notional):
            return None
        contracts = notional / price
        self.bankroll -= notional
        fill = PaperFill(
            ticker=ticker,
            label=label,
            side="YES",
            contracts=contracts,
            price=price,
            model_yes=model_yes,
            edge=edge,
            city=city,
            target_date=target.isoformat(),
            series=series,
        )
        self.fills.append(fill)
        self.save()
        return fill

    def settle_fill(
        self,
        fill: PaperFill,
        *,
        won: bool,
        settled_temp_f: Optional[float] = None,
    ) -> None:
        if fill.status != "open":
            return
        # YES settles to $1 if won, $0 if lost. Cost basis already deducted.
        payout = fill.contracts * (1.0 if won else 0.0)
        fill.pnl = payout - (fill.contracts * fill.price)
        fill.status = "won" if won else "lost"
        fill.settled_temp_f = settled_temp_f
        fill.settled_ts = _utc_now()
        self.bankroll += payout
        self.realized_pnl += fill.pnl
        if won:
            self.wins += 1
        else:
            self.losses += 1
        self.save()

    def summary_line(self) -> str:
        settled = self.wins + self.losses
        wr = (100.0 * self.wins / settled) if settled else 0.0
        return (
            f"bank ${self.bankroll:,.2f} | open {len(self.open_fills())} | "
            f"W/L {self.wins}/{self.losses} ({wr:.0f}%) | "
            f"realized P/L ${self.realized_pnl:+,.2f}"
        )

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "bankroll": self.bankroll,
            "realized_pnl": self.realized_pnl,
            "wins": self.wins,
            "losses": self.losses,
            "fills": [asdict(f) for f in self.fills],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @classmethod
    def load_or_create(cls, path: Path, starting_bankroll: float) -> "PaperBook":
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            fills = [PaperFill(**row) for row in data.get("fills") or []]
            book = cls(
                bankroll=float(data.get("bankroll", starting_bankroll)),
                fills=fills,
                path=path,
                realized_pnl=float(data.get("realized_pnl", 0.0)),
                wins=int(data.get("wins", 0)),
                losses=int(data.get("losses", 0)),
            )
            return book
        book = cls(bankroll=starting_bankroll, path=path)
        book.save()
        return book
