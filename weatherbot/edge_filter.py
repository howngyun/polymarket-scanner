"""
edge_filter.py — accept/reject a (market, prob) pair.

Net edge formula (Patch P4):
    net_edge = p_yes - ask_price - estimated_slippage
Enter if net_edge > tau (cold-start tau=0.10, decays toward 0.05 in W2).

Also applies:
  P5  — liquidity floor (set in scanner)
  P16 — ensemble agreement check (member sd window)
  P29 — use bestAsk instead of mid (alteregoeth pattern)
  P30 — min_hours_to_resolution (skip stale markets)
  P31 — max yes_price cap (skip extreme favorites where NO edge is tiny)
  P32 — z-score significance test (hcharper pattern)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from weatherbot.market_scanner import WeatherMarket
from weatherbot.prob_calculator import Probability


@dataclass
class FilterDecision:
    accept: bool
    side: str                  # 'YES' or 'NO' (only meaningful when accept=True)
    entry_price: float         # the price we'd be paying
    fair_p: float              # our estimate of the true prob for the side we'd take
    net_edge: float            # after slippage and threshold; >0 means pass
    reason: str                # short tag describing why we accepted/rejected


def _slippage_estimate(trade_size_usd: float, liquidity_usd: float) -> float:
    """Crude linear-impact estimate.

    Polymarket weather markets are thin. We assume a 1% price impact for every
    1% of liquidity our order represents, capped at 5%. This is intentionally
    conservative — we'd rather miss a real edge than book a phantom one.
    Refined in W2 against actual fills.
    """
    if liquidity_usd <= 0:
        return 0.05
    ratio = trade_size_usd / liquidity_usd
    return min(0.05, ratio)


def _ask_for_side(market: WeatherMarket, side: str) -> float:
    """Best ask for the given side (P29).

    Polymarket Gamma exposes bestAsk/bestBid on the YES token. The ask we'd
    pay buying NO is approximately 1 - best_bid_yes (the offered NO price
    on the other side of the book). Falls back to outcomePrices when the
    book quote is missing.
    """
    if side == "YES":
        if market.best_ask_yes is not None and market.best_ask_yes > 0:
            return market.best_ask_yes
        return market.yes_price
    # side == "NO"
    if market.best_bid_yes is not None and 0 < market.best_bid_yes < 1:
        return 1.0 - market.best_bid_yes
    return market.no_price


def _z_score(p: float, market_p: float, n_members: int) -> float:
    """Approx z-score of the edge under a binomial null.

    With n ensemble members each landing in/out of the bin, the standard
    error of our point estimate p is sqrt(p(1-p)/n). The market's implied
    probability is treated as the null. We reject low-confidence calls
    (Patch P32 — hcharper requires ≥ 1.5).
    """
    if n_members <= 0:
        return 0.0
    se = math.sqrt(max(1e-9, p * (1.0 - p)) / n_members)
    return (p - market_p) / se if se > 0 else 0.0


def evaluate(
    market: WeatherMarket,
    prob: Probability,
    *,
    tau: float = 0.10,
    trade_size_usd: float = 25.0,
    min_members: int = 100,
    max_member_sd_c: float = 4.0,
    min_member_sd_c: float = 0.05,
    resolution_source_whitelist: Optional[set[str]] = None,
    min_hours_to_resolution: float = 2.0,        # P30
    max_yes_side_price: float = 0.85,            # P31 — skip extreme favorites
    min_z_score: float = 1.5,                    # P32 — hcharper significance
    max_book_spread: float = 0.05,               # P35 — alteregoeth book quality
    now: Optional[datetime] = None,
) -> FilterDecision:
    """Decide whether to enter, and on which side.

    Patch references:
      P4   — slippage explicitly subtracted
      P5   — liquidity floor handled by market_scanner; here we cap trade vs depth
      P6   — resolution_source whitelist (caller supplies)
      P16  — sd thresholds: too-tight (likely common bias) and too-wide (noise) both reject
      P29  — use bestAsk instead of outcomePrices mid
      P30  — minimum hours to resolution
      P31  — skip when entry price > max_yes_side_price (other side too thin)
      P32  — require z-score >= min_z_score
    """
    if prob.insufficient_data or prob.member_count < min_members:
        return FilterDecision(False, "", 0.0, 0.0, 0.0,
                              f"insufficient_members({prob.member_count})")

    # P30 — too close to resolution: ensemble has nothing left to disagree about
    # and we can't even monitor through the next 5-min cron.
    now_ = now or datetime.now(timezone.utc)
    hours_left = (market.end_date - now_).total_seconds() / 3600.0
    if hours_left < min_hours_to_resolution:
        return FilterDecision(False, "", 0.0, 0.0, 0.0,
                              f"too_close({hours_left:.1f}h)")

    sd = prob.member_agreement_sd
    if sd < min_member_sd_c:
        return FilterDecision(False, "", 0.0, 0.0, 0.0,
                              f"sd_too_tight({sd:.2f}°C)")
    if sd > max_member_sd_c:
        return FilterDecision(False, "", 0.0, 0.0, 0.0,
                              f"sd_too_wide({sd:.2f}°C)")

    if resolution_source_whitelist is not None:
        src = market.resolution_source.lower()
        if not any(w.lower() in src for w in resolution_source_whitelist):
            return FilterDecision(False, "", 0.0, 0.0, 0.0,
                                  f"source_not_whitelisted({market.resolution_source!r})")

    # P35 — book spread check. If best_ask_yes - best_bid_yes is wide, the
    # quote is unreliable and any taker fill will be deep into the book.
    if (
        market.best_ask_yes is not None
        and market.best_bid_yes is not None
        and (market.best_ask_yes - market.best_bid_yes) > max_book_spread
    ):
        return FilterDecision(
            False, "", 0.0, 0.0, 0.0,
            f"spread_too_wide({market.best_ask_yes - market.best_bid_yes:.3f})",
        )

    slip = _slippage_estimate(trade_size_usd, market.liquidity)

    # P29 — use the ask we'd actually pay, not the midpoint.
    yes_ask = _ask_for_side(market, "YES")
    no_ask = _ask_for_side(market, "NO")

    # P31 — skip entries that are too expensive (deep favorites).
    # Symmetric: we cap whichever side we actually buy.
    yes_edge = prob.p_yes - yes_ask - slip
    no_edge = (1.0 - prob.p_yes) - no_ask - slip

    if yes_edge >= no_edge:
        side, ask, fair, edge = "YES", yes_ask, prob.p_yes, yes_edge
    else:
        side, ask, fair, edge = "NO", no_ask, (1.0 - prob.p_yes), no_edge

    if ask > max_yes_side_price:
        return FilterDecision(False, side, ask, fair, edge,
                              f"price_too_high({ask:.3f})")

    if edge <= tau:
        return FilterDecision(False, side, ask, fair, edge,
                              f"edge_below_tau({edge:+.3f})")

    # P32 — significance: how many SE is the edge from the market's null?
    z = _z_score(fair, ask, prob.member_count)
    if z < min_z_score:
        return FilterDecision(False, side, ask, fair, edge,
                              f"z_score_low({z:.2f})")

    return FilterDecision(
        accept=True,
        side=side,
        entry_price=ask,
        fair_p=fair,
        net_edge=edge,
        reason=f"pass(z={z:.2f})",
    )


if __name__ == "__main__":
    from weatherbot.forecast_fetcher import CITIES, fetch_city_forecast
    from weatherbot.market_scanner import fetch_active_weather_markets
    from weatherbot.prob_calculator import compute_probability

    markets = fetch_active_weather_markets(only_known_cities=True, max_days=2.5)
    cache: dict = {}
    accepted = rejected = 0
    print(f"evaluating {len(markets)} markets at tau=0.10\n")
    for m in markets:
        if m.city not in cache:
            cache[m.city] = fetch_city_forecast(m.city, *CITIES[m.city])
        prob = compute_probability(m, cache[m.city])
        decision = evaluate(m, prob, tau=0.10, trade_size_usd=25.0)
        if decision.accept:
            accepted += 1
            print(
                f"  ✓ {m.city:>15s} {m.op:>5s} thr={m.threshold_c:>5.1f}°C  "
                f"side={decision.side}  p={decision.fair_p:.3f}  "
                f"price={decision.entry_price:.3f}  net_edge={decision.net_edge:+.3f}  "
                f"liq=${m.liquidity:,.0f}"
            )
        else:
            rejected += 1
    print(f"\naccepted={accepted}  rejected={rejected}")
