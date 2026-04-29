"""
settlement.py — close out OPEN paper trades whose markets have resolved.

Polymarket Gamma reports `closed=true` after UMA finalizes the question. The
final outcomePrices for the YES token settle to ~1.000 or ~0.000. We use that
as the paper settlement source.

This is a daily / hourly job; runner.py invokes it before scanning for new
entries so cash freed by settlements becomes available immediately.
"""
from __future__ import annotations

import requests

from weatherbot.paper_ledger import open_trades, settle_trade

GAMMA_MARKETS_BY_ID = "https://gamma-api.polymarket.com/markets"
TIMEOUT_SEC = 15


def _fetch_market(market_id: str) -> dict | None:
    """Fetch one market by condition_id."""
    try:
        r = requests.get(
            GAMMA_MARKETS_BY_ID,
            params={"condition_ids": market_id, "limit": 1},
            timeout=TIMEOUT_SEC,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        print(f"[settlement] fetch {market_id} failed: {exc}")
        return None
    if isinstance(data, list) and data:
        return data[0]
    return None


def _settle_price_for_side(market: dict, side: str) -> float | None:
    """Read the final YES price; convert to the side we hold."""
    outcomes = market.get("outcomes")
    prices = market.get("outcomePrices")
    if isinstance(outcomes, str):
        import json as _j
        outcomes = _j.loads(outcomes)
        prices = _j.loads(prices) if isinstance(prices, str) else prices
    if not (outcomes and prices):
        return None
    try:
        yes_idx = outcomes.index("Yes")
    except ValueError:
        return None
    try:
        yes_p = float(prices[yes_idx])
    except (TypeError, ValueError):
        return None
    return yes_p if side == "YES" else (1.0 - yes_p)


def sweep_settlements() -> int:
    """Walk all OPEN trades and close any whose market is now resolved.

    Returns the number of trades settled this pass.
    """
    rows = open_trades()
    closed_n = 0
    for r in rows:
        market = _fetch_market(r["market_id"])
        if not market:
            continue
        if not market.get("closed"):
            continue
        settle_p = _settle_price_for_side(market, r["side"])
        if settle_p is None:
            continue
        settle_trade(r["id"], settle_price=settle_p,
                     notes=f"closed via gamma resolved")
        closed_n += 1
        print(f"[settlement] closed id={r['id']} {r['city']} {r['side']} "
              f"@ settle={settle_p:.3f} (entered @ {r['entry_price']:.3f})")
    return closed_n


if __name__ == "__main__":
    n = sweep_settlements()
    print(f"settled {n} trades")
