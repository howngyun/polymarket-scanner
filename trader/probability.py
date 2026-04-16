"""BTC > strike 확률 계산 (로그정규 모델).

수학:
  BTC 가격 로그정규 가정
  P(BTC_T > K | BTC_0, σ, t) = N(d)
  d = (ln(P_0/K) + (μ - σ²/2)*t) / (σ*√t)
  μ = 0 (짧은 시간, 드리프트 무시)
"""
import math


def norm_cdf(x: float) -> float:
    """표준정규분포 CDF using erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))


def prob_above_strike(
    current_price: float,
    strike: float,
    seconds_to_expiry: float,
    annual_volatility: float,
) -> float:
    """P(price_at_expiry > strike).

    현재가가 strike 이미 초과 + 시간 거의 없음 → 1에 수렴
    현재가 < strike + 시간 거의 없음 → 0에 수렴
    """
    if seconds_to_expiry <= 0:
        return 1.0 if current_price > strike else 0.0
    if annual_volatility <= 0:
        return 1.0 if current_price > strike else 0.0
    if strike <= 0 or current_price <= 0:
        return 0.5

    # 시간 연 단위 변환
    t_years = seconds_to_expiry / 31_536_000.0
    sigma = annual_volatility

    # d = (ln(S/K) - σ²t/2) / (σ√t)
    sqrt_t = math.sqrt(t_years)
    sigma_sqrt_t = sigma * sqrt_t
    if sigma_sqrt_t == 0:
        return 1.0 if current_price > strike else 0.0

    d = (math.log(current_price / strike) - 0.5 * sigma**2 * t_years) / sigma_sqrt_t
    return norm_cdf(d)


def prob_between(
    current_price: float,
    strike_low: float,
    strike_high: float,
    seconds_to_expiry: float,
    annual_volatility: float,
) -> float:
    """P(strike_low < price_at_expiry <= strike_high)."""
    p_high = prob_above_strike(current_price, strike_low, seconds_to_expiry, annual_volatility)
    p_low = prob_above_strike(current_price, strike_high, seconds_to_expiry, annual_volatility)
    return max(0.0, p_high - p_low)


def parse_market_question(question: str) -> dict:
    """Polymarket 질문 파싱 → 구조화 정보.

    패턴:
      - "Will Bitcoin (BTC) close above $85,000 on April 15?"
      - "Bitcoin Up or Down - April 15, 12:00PM-4:00PM ET"
      - "Will BTC close above $X at 3pm ET"
    """
    import re

    q = question.lower()

    # 심볼 추출
    symbol = None
    if "bitcoin" in q or "btc" in q:
        symbol = "BTC"
    elif "ethereum" in q or "eth" in q:
        symbol = "ETH"
    elif "solana" in q or "sol" in q:
        symbol = "SOL"
    elif "xrp" in q:
        symbol = "XRP"

    # strike 추출 (예: "$85,000" or "$85000")
    strike = None
    m = re.search(r"\$([0-9,]+(?:\.[0-9]+)?)", question)
    if m:
        try:
            strike = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    # 방향 (above/below)
    direction = None
    if "above" in q or "higher" in q:
        direction = "above"
    elif "below" in q or "lower" in q:
        direction = "below"

    return {
        "symbol": symbol,
        "strike": strike,
        "direction": direction,
    }
