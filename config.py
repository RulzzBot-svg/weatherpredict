"""Settings for the weather Kalshi paper bot."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


# Settlement stations used by Kalshi KXHIGH* markets (approx coords for Open-Meteo).
CITIES: dict[str, dict] = {
    "NYC": {
        "series": "KXHIGHNY",
        "lat": 40.7789,
        "lon": -73.9692,
        "timezone": "America/New_York",
        "station": "Central Park",
    },
    "CHI": {
        "series": "KXHIGHCHI",
        "lat": 41.7868,
        "lon": -87.7522,
        "timezone": "America/Chicago",
        "station": "Chicago Midway",
    },
    "MIA": {
        "series": "KXHIGHMIA",
        "lat": 25.7959,
        "lon": -80.2870,
        "timezone": "America/New_York",
        "station": "Miami Intl",
    },
    "LAX": {
        "series": "KXHIGHLAX",
        "lat": 33.9425,
        "lon": -118.4081,
        "timezone": "America/Los_Angeles",
        "station": "LAX",
    },
}


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def parse_cities(raw: str) -> tuple[str, ...]:
    """Parse CITY=NYC | CITY=NYC,CHI | CITY=ALL into known city codes."""
    text = (raw or "NYC").strip().upper()
    if text in {"ALL", "*"}:
        return tuple(sorted(CITIES))
    parts = [p.strip().upper() for p in text.split(",") if p.strip()]
    if not parts:
        parts = ["NYC"]
    unknown = [p for p in parts if p not in CITIES]
    if unknown:
        known = ", ".join(sorted(CITIES))
        raise ValueError(f"Unknown CITY={unknown!r}. Known: {known} (or ALL)")
    # Preserve order, drop dupes
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return tuple(out)


@dataclass(frozen=True)
class Settings:
    paper_bankroll: float
    stake_notional: float
    min_edge: float
    loop_interval_seconds: int
    auto_bet: bool
    cities: tuple[str, ...]
    kalshi_series_override: str | None
    target_date: str
    forecast_provider: str
    kalshi_base: str

    def city_meta(self, city: str) -> dict:
        if city not in CITIES:
            known = ", ".join(sorted(CITIES))
            raise ValueError(f"Unknown CITY={city!r}. Known: {known}")
        return CITIES[city]

    def series_for(self, city: str) -> str:
        if self.kalshi_series_override:
            return self.kalshi_series_override
        return self.city_meta(city)["series"]


def load_settings() -> Settings:
    cities = parse_cities(os.getenv("CITY", "ALL"))
    series_raw = os.getenv("KALSHI_SERIES", "").strip().upper()
    # Only honor an explicit series override when scanning a single city.
    series_override = series_raw if series_raw and len(cities) == 1 else None
    return Settings(
        paper_bankroll=_float("PAPER_BANKROLL", 1000.0),
        stake_notional=_float("STAKE_NOTIONAL", 10.0),
        min_edge=_float("MIN_EDGE", 0.08),
        loop_interval_seconds=_int("LOOP_INTERVAL_SECONDS", 60),
        auto_bet=_bool("AUTO_BET", True),
        cities=cities,
        kalshi_series_override=series_override,
        target_date=os.getenv("TARGET_DATE", "tomorrow").strip().lower(),
        forecast_provider=os.getenv("FORECAST_PROVIDER", "open_meteo_ensemble").strip(),
        kalshi_base=os.getenv(
            "KALSHI_BASE",
            "https://api.elections.kalshi.com/trade-api/v2",
        ).rstrip("/"),
    )
