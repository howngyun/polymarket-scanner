"""Binance에서 BTC/ETH/SOL 가격 + 최근 변동성 계산."""
import math
import time
from typing import Optional

import requests

from . import config

SYMBOLS = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
}


def get_current_price(symbol: str) -> Optional[float]:
    """현재가 (단일)."""
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": SYMBOLS.get(symbol.upper(), symbol)},
            timeout=5,
        )
        r.raise_for_status()
        return float(r.json()["price"])
    except Exception as e:
        print(f"[price_feed] {symbol} 현재가 실패: {e}")
        return None


def get_recent_volatility(symbol: str) -> float:
    """최근 15분 1초봉으로 실현변동성 (연환산) 계산.

    Binance klines API로 1분봉 15개 가져와서 로그수익률 표준편차 계산.
    """
    sym = SYMBOLS.get(symbol.upper(), symbol)
    try:
        # 1분봉 15개 = 15분치
        r = requests.get(
            config.BINANCE_TICKER_URL,
            params={"symbol": sym, "interval": "1m", "limit": 15},
            timeout=5,
        )
        r.raise_for_status()
        klines = r.json()
        closes = [float(k[4]) for k in klines]  # close price at index 4
        if len(closes) < 5:
            return config.VOLATILITY_MIN

        # 로그 수익률
        log_returns = [
            math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
        ]

        # 분당 표준편차
        n = len(log_returns)
        mean = sum(log_returns) / n
        var = sum((r - mean) ** 2 for r in log_returns) / max(n - 1, 1)
        std_per_min = math.sqrt(var)

        # 연환산 (분 → 연)
        # 1년 = 525,600분
        annual_vol = std_per_min * math.sqrt(525600)

        # 캡
        annual_vol = max(config.VOLATILITY_MIN, min(annual_vol, config.VOLATILITY_MAX))
        return annual_vol
    except Exception as e:
        print(f"[price_feed] {symbol} 변동성 실패: {e}")
        return 0.6  # 기본값: 연 60%


def get_price_and_vol(symbol: str) -> tuple:
    """(price, annualized_vol) 튜플. 둘 다 성공해야 유효."""
    price = get_current_price(symbol)
    if price is None:
        return (None, None)
    vol = get_recent_volatility(symbol)
    return (price, vol)
