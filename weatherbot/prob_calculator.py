"""
prob_calculator.py — convert ensemble forecast + market threshold into p(YES).

Given a `WeatherMarket` (city, agg=high/low, op, threshold_c) and a
`CityForecast` (143 ensemble members, hourly Celsius) for the resolution day,
compute:

    p_yes  = P(market resolves YES | ensemble truth)
    spread = stdev across the 143 model means at the relevant hour
             — used by edge_filter (Patch P16 model-agreement check)

For "exact" bin markets ("be N°C") we assume the resolution rounds the
recorded temperature to the nearest integer Celsius — i.e. YES iff the
actual reading falls in [N-0.5, N+0.5). For Fahrenheit-quoted markets the
question text already guarantees an integer °F bin, but we operate in
Celsius after `market_scanner._f_to_c` conversion. The bin width therefore
shrinks to 5/9 °C for °F-quoted exact markets — handled by `bin_half_c`.

This is an INTENTIONAL simplification (Round 3 P10 — temp range markets only,
Bayesian shrinkage / per-city calibration arrives in W2).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from weatherbot.forecast_fetcher import CityForecast
from weatherbot.market_scanner import WeatherMarket


@dataclass
class Probability:
    p_yes: float                  # raw ensemble probability of YES
    member_count: int             # how many ensemble members were used
    member_agreement_sd: float    # stdev of the daily agg across all members (°C)
    daily_min_c: float            # observed range across members for sanity logging
    daily_max_c: float
    bin_half_c: float             # half-width of the resolution bin (in °C)
    insufficient_data: bool       # true if too few members to trust


def _resolution_day_window_utc(end_date: datetime) -> tuple[datetime, datetime]:
    """The day the market resolves over, expressed as a [start, end) UTC window.

    Polymarket weather markets phrase the question as "on April 30" but settle
    against the daily max/min recorded at the resolution station. The market
    typically closes near noon UTC the day after the observed date — so we
    subtract 12 h and take that date's full UTC calendar day as the window.

    Caveat (Patch P6): airport stations report in local time, not UTC. Sao
    Paulo's local "April 30 max" spans roughly 03:00 UTC Apr 30 → 03:00 UTC
    May 1. Using UTC-day approximation introduces a few-hour shift; this is
    acceptable for a daily max because the diurnal peak is mid-afternoon
    local. Calibration in W2 will absorb residual bias per city.
    """
    from datetime import timedelta
    anchor = end_date.astimezone(timezone.utc) - timedelta(hours=12)
    day_start = datetime(anchor.year, anchor.month, anchor.day, 0, 0, tzinfo=timezone.utc)
    day_end = day_start + timedelta(hours=24)
    return day_start, day_end


def _hour_indices_for_window(
    hours_iso: list[str], start: datetime, end: datetime
) -> list[int]:
    """Return indices into the ensemble hourly array that fall in [start, end)."""
    out: list[int] = []
    for i, ts in enumerate(hours_iso):
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if start <= t < end:
            out.append(i)
    return out


def _member_daily_agg(member_series: list[float], idxs: list[int], agg: str) -> Optional[float]:
    """Daily max or min across the relevant hourly indices for ONE member."""
    vals = [member_series[i] for i in idxs if 0 <= i < len(member_series)]
    if not vals:
        return None
    return max(vals) if agg == "high" else min(vals)


def compute_probability(market: WeatherMarket, forecast: CityForecast) -> Probability:
    """Compute p(YES) for the market using the city's ensemble forecast.

    Returns Probability(insufficient_data=True) if ensemble doesn't cover the
    resolution day or if too few members (Patch P19 — fail safe).
    """
    start, end = _resolution_day_window_utc(market.end_date)
    idxs = _hour_indices_for_window(forecast.hours_utc, start, end)

    # Bin width depends on the unit the market was QUOTED in (Patch B1 fix).
    # The earlier reverse-conversion heuristic mis-classified °C thresholds
    # whose °F equivalent happened to be integer (5°C, 10°C, 25°C, 30°C, ...),
    # using the wrong (5/18°C) bin and inflating apparent edges.
    if market.original_unit == "F":
        bin_half_c = 0.5 * (5.0 / 9.0)   # 1°F bin → ±5/18 °C
    else:
        bin_half_c = 0.5                  # 1°C bin → ±0.5 °C

    daily_aggs: list[float] = []
    for series in forecast.all_members_flat():
        v = _member_daily_agg(series, idxs, market.agg)
        if v is not None:
            daily_aggs.append(v)

    if len(daily_aggs) < 30 or not idxs:
        return Probability(
            p_yes=0.0,
            member_count=len(daily_aggs),
            member_agreement_sd=0.0,
            daily_min_c=0.0,
            daily_max_c=0.0,
            bin_half_c=bin_half_c,
            insufficient_data=True,
        )

    n = len(daily_aggs)
    if market.op == "le":
        p = sum(1 for v in daily_aggs if v <= market.threshold_c) / n
    elif market.op == "ge":
        p = sum(1 for v in daily_aggs if v >= market.threshold_c) / n
    elif market.op == "range":
        lo = market.threshold_c
        hi = market.threshold_hi_c if market.threshold_hi_c is not None else lo
        # Inclusive on both ends — the published bin uses two integer endpoints.
        # The resolution bin actually spans [lo - bin_half, hi + bin_half).
        p = sum(1 for v in daily_aggs if lo - bin_half_c <= v < hi + bin_half_c) / n
    elif market.op == "exact":
        lo = market.threshold_c - bin_half_c
        hi = market.threshold_c + bin_half_c
        p = sum(1 for v in daily_aggs if lo <= v < hi) / n
    else:
        p = 0.0

    return Probability(
        p_yes=p,
        member_count=n,
        member_agreement_sd=statistics.pstdev(daily_aggs) if n > 1 else 0.0,
        daily_min_c=min(daily_aggs),
        daily_max_c=max(daily_aggs),
        bin_half_c=bin_half_c,
        insufficient_data=False,
    )


if __name__ == "__main__":
    # Smoke test against live markets
    from weatherbot.forecast_fetcher import CITIES, fetch_city_forecast
    from weatherbot.market_scanner import fetch_active_weather_markets

    markets = fetch_active_weather_markets(only_known_cities=True, max_days=2.5)
    print(f"markets to evaluate: {len(markets)}\n")

    # Cache forecasts per city
    cache: dict[str, CityForecast] = {}

    for m in markets[:12]:
        if m.city not in cache:
            cache[m.city] = fetch_city_forecast(m.city, *CITIES[m.city])
        prob = compute_probability(m, cache[m.city])
        if prob.insufficient_data:
            print(f"  SKIP {m.city:>15s} {m.op:>5s} thr={m.threshold_c:>5.1f}°C — insufficient")
            continue
        edge = prob.p_yes - m.yes_price
        flag = "★" if edge > 0.05 else " "
        print(
            f"  {flag} {m.city:>15s} {m.op:>5s} thr={m.threshold_c:>5.1f}°C  "
            f"p={prob.p_yes:.3f}  market={m.yes_price:.3f}  edge={edge:+.3f}  "
            f"sd={prob.member_agreement_sd:.2f}°C  members={prob.member_count}"
        )
