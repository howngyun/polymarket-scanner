"""
Railway HFT Runner — always-on WebSocket process
5-min crypto binary strategy. 15초마다 신호 체크.
GitHub Actions 4전략과 별도로 돌아감.
"""

import os
import sys
import asyncio
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).parent))
from trader import config, ledger, executor, risk_gate
from strategies.crypto_5min_binary import generate_signals

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

PRICE_CACHE: dict[str, deque] = defaultdict(lambda: deque(maxlen=60))

BINANCE_WS = (
    "wss://stream.binance.com:9443/stream?streams="
    + "/".join(f"{s}usdt@trade" for s in ["btc", "eth", "sol", "bnb", "xrp"])
)
ASSET_MAP = {
    "BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL",
    "BNBUSDT": "BNB", "XRPUSDT": "XRP"
}


async def price_feed():
    while True:
        try:
            async with websockets.connect(BINANCE_WS, ping_interval=20) as ws:
                logger.info("[price_feed] Binance WS 연결됨")
                async for msg in ws:
                    data = json.loads(msg).get("data", {})
                    symbol = data.get("s", "")
                    price = float(data.get("p", 0))
                    asset = ASSET_MAP.get(symbol)
                    if asset and price > 0:
                        PRICE_CACHE[asset].append(price)
        except Exception as e:
            logger.warning(f"[price_feed] 끊김: {e} — 5초 후 재연결")
            await asyncio.sleep(5)


def get_poly_client():
    import requests

    class SimpleClient:
        BASE = "https://clob.polymarket.com"

        def get_markets(self, keyword="", active=True, limit=20):
            r = requests.get(
                f"{self.BASE}/markets",
                params={"keyword": keyword, "active": str(active).lower(), "limit": limit},
                timeout=5,
            )
            r.raise_for_status()
            return r.json().get("data", [])

    return SimpleClient()


def get_open_positions() -> list:
    trades = ledger.load_ledger(live=config.LIVE_TRADING)
    return [t for t in trades if not t.get("resolved") and t.get("status") == "filled"]


async def trading_loop(poly_client):
    mode = "LIVE" if config.LIVE_TRADING else "PAPER"
    capital = float(os.environ.get("STARTING_CAPITAL", "500"))
    logger.info(f"[hft_runner] 시작 (모드: {mode}, 자본: ${capital})")

    while True:
        try:
            if not all(len(PRICE_CACHE[a]) >= 5 for a in ["BTC", "ETH"]):
                await asyncio.sleep(5)
                continue

            price_snapshot = {a: list(PRICE_CACHE[a]) for a in PRICE_CACHE}
            signals = generate_signals(poly_client, price_snapshot, config)
            open_positions = get_open_positions()

            for sig in signals:
                allowed, reason = risk_gate.check(sig, open_positions)
                if not allowed:
                    logger.debug(f"[hft_runner] 리스크 거부: {reason}")
                    continue

                bet_usd = min(
                    capital * getattr(config, "BINARY_MAX_POSITION_PCT", 0.05),
                    config.MAX_BET_USD,
                )
                bet_usd = max(bet_usd, config.MIN_BET_USD)

                result = executor.execute(sig, bet_usd)
                if result:
                    open_positions.append(result)
                    logger.info(
                        f"[hft_runner] {'✅ LIVE' if config.LIVE_TRADING else '📝 PAPER'} "
                        f"{sig['asset']} {sig['side'].upper()} ${bet_usd:.0f} "
                        f"@ {sig['entry_price']:.3f} edge={sig['edge_pct']:.1%} "
                        f"T={sig['secs_to_expiry']}s"
                    )

        except Exception as e:
            logger.error(f"[hft_runner] 루프 오류: {e}")

        await asyncio.sleep(15)


async def main():
    poly_client = get_poly_client()
    await asyncio.gather(price_feed(), trading_loop(poly_client))


if __name__ == "__main__":
    asyncio.run(main())
