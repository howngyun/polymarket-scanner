"""Kraken Public API에서 BTC/ETH/SOL/XRP 가격 + 변동성 계산."""

import math
import time
import requests

BASE = "https://api.kraken.com/0/public"

# Kraken 심볼 매핑
SYMBOLS = {
    "BTC": "XBTUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
    "XRP": "XRPUSD",
}


def _get(endpoint: str, params: dict) -> dict:
    r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise ValueError(f"Kraken error: {data['error']}")
    return data["result"]


def get_current_price(symbol: str) -> float:
    """현재가 반환 (USD)."""
    pair = SYMBOLS.get(symbol.upper())
    if not pair:
        raise ValueError(f"Unknown symbol: {symbol}")
    result = _get("Ticker", {"pair": pair})
    # result key가 'XXBTZUSD' 같은 형태일 수 있음 — 첫 번째 값 사용
    ticker = next(iter(result.values()))
    return float(ticker["c"][0])  # last trade close price


def get_recent_volatility(symbol: str, minutes: int = 15) -> float:
    """최근 N분 데이터로 연간화 변동성 계산."""
    pair = SYMBOLS.get(symbol.upper())
    if not pair:
        raise ValueError(f"Unknown symbol: {symbol}")

    # 1분 OHLC, since = (now - minutes - 버퍼) 초
    since = int(time.time()) - (minutes + 5) * 60
    result = _get("OHLC", {"pair": pair, "interval": 1, "since": since})

    # 'last' 키 제외하고 실제 OHLC 데이터
    ohlc_key = [k for k in result if k != "last"][0]
    candles = result[ohlc_key][-minutes:]  # 최근 N개

    if len(candles) < 2:
        return 0.20  # 기본값 20%

    closes = [float(c[4]) for c in candles]  # index 4 = close
    log_returns = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0
    ]

    if not log_returns:
        return 0.20

    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / len(log_returns)
    std_per_min = math.sqrt(variance)

    # 연간화: 1분봉 기준 → 525600분/년
    annualized = std_per_min * math.sqrt(525600)
    return max(0.05, min(annualized, 5.0))  # 5%~500% 클램프
