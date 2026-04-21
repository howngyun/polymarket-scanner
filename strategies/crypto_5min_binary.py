"""
5-min Crypto Up/Down Binary Strategy (HFT tier)
Target archetype: 0xB27BC932 cluster ($490K / 47d)

Market type: "Will BTC be higher at HH:MM ET than HH:MM-5 ET?"
Edge: BS-binary fair price vs Polymarket offer. Enter when edge > threshold.
Requires: always-on process + sub-minute price feed (WebSocket)
"""

import math
import time
import logging
from datetime import datetime, timezone
from scipy.stats import norm

logger = logging.getLogger(__name__)


def bs_binary_price(spot: float, strike: float, T_sec: float, sigma_annual: float, mu_annual: float = 0.0) -> float:
    """
    Binary call fair value: P(S_T > strike)
    For Up/Down market: strike = current spot (at market open)
    mu_annual: drift estimate from recent momentum
    """
    if T_sec <= 0 or sigma_annual <= 0:
        return 0.5
    T = T_sec / (365 * 24 * 3600)  # seconds → years
    d = (math.log(spot / strike) + (mu_annual - 0.5 * sigma_annual ** 2) * T) / (sigma_annual * math.sqrt(T))
    return norm.cdf(d)


def estimate_vol_and_drift(prices: list[float], window_sec: int = 300) -> tuple[float, float]:
    """
    Annualized realized vol + drift from recent price list.
    prices: list of close prices, newest last.
    """
    if len(prices) < 3:
        return 0.80, 0.0  # default: 80% annual vol, zero drift

    log_returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]
    n = len(log_returns)

    # realized vol (annualized from 5-sec bars → ×√(252*24*720))
    bars_per_year = 365 * 24 * 3600 / window_sec
    mean_r = sum(log_returns) / n
    var_r = sum((r - mean_r) ** 2 for r in log_returns) / max(n - 1, 1)
    sigma = math.sqrt(var_r * bars_per_year)
    sigma = max(sigma, 0.20)  # floor 20% (prevents BS blow-up on calm periods)

    # drift: use recent 3-candle momentum
    recent = log_returns[-3:]
    mu = sum(recent) / len(recent) * bars_per_year

    return sigma, mu


def find_5min_markets(poly_client, assets: list[str]) -> list[dict]:
    """
    Fetch active 5-min Up/Down markets from Polymarket CLOB.
    Returns markets with >2 min remaining (too close = skip).
    """
    markets = []
    now = datetime.now(timezone.utc)

    for asset in assets:
        try:
            # CLOB search by keyword
            results = poly_client.get_markets(
                keyword=f"{asset} higher",
                active=True,
                limit=20
            )
            for m in results:
                end_dt = m.get("end_date_iso") or m.get("endDateIso")
                if not end_dt:
                    continue
                end = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
                secs_left = (end - now).total_seconds()

                # sweet spot: 30s ~ 240s before expiry
                if 30 < secs_left < 240:
                    m["_secs_left"] = secs_left
                    m["_asset"] = asset
                    markets.append(m)
        except Exception as e:
            logger.warning(f"[5min_binary] {asset} 마켓 조회 실패: {e}")

    return markets


def generate_signals(poly_client, price_cache: dict, config) -> list[dict]:
    """
    Main signal generator.
    price_cache: {asset: [price_t-n, ..., price_t]} (recent prices, newest last)
    """
    from trader import config as cfg

    assets = ["BTC", "ETH", "SOL", "BNB", "XRP"]
    markets = find_5min_markets(poly_client, assets)
    signals = []

    for m in markets:
        asset = m["_asset"]
        secs_left = m["_secs_left"]
        prices = price_cache.get(asset, [])

        if len(prices) < 3:
            continue

        spot = prices[-1]
        strike = prices[0]  # market opened at this price (approximation)
        sigma, mu = estimate_vol_and_drift(prices)

        fair_yes = bs_binary_price(spot, strike, secs_left, sigma, mu)
        fair_no = 1.0 - fair_yes

        # Get best offers from CLOB
        yes_ask = m.get("bestAsk") or m.get("best_ask")
        no_ask = 1.0 - (m.get("bestBid") or m.get("best_bid") or 0.5)

        if yes_ask is None:
            continue

        yes_ask = float(yes_ask)
        no_ask = float(no_ask)

        yes_edge = fair_yes - yes_ask
        no_edge = fair_no - no_ask

        min_edge = getattr(cfg, "BINARY_MIN_EDGE_PCT", 0.05)
        min_liq = getattr(cfg, "BINARY_MIN_LIQUIDITY", 1000)

        liquidity = float(m.get("volume24hr", 0) or 0)

        for side, edge, entry_price in [("yes", yes_edge, yes_ask), ("no", no_edge, no_ask)]:
            if edge >= min_edge and liquidity >= min_liq:
                signals.append({
                    "market_id": m["condition_id"],
                    "slug": m.get("slug", ""),
                    "question": m.get("question", ""),
                    "asset": asset,
                    "side": side,
                    "entry_price": entry_price,
                    "fair_price": fair_yes if side == "yes" else fair_no,
                    "edge_pct": round(edge, 4),
                    "secs_to_expiry": int(secs_left),
                    "sigma": round(sigma, 3),
                    "mu": round(mu, 3),
                    "strategy": "crypto_5min_binary",
                })
                logger.info(
                    f"[5min_binary] SIGNAL {asset} {side.upper()} "
                    f"fair={entry_price + edge:.3f} ask={entry_price:.3f} "
                    f"edge={edge:.1%} T={int(secs_left)}s"
                )

    return signals
