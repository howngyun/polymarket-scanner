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


def prob_touch_above_before(
    current_price: float,
    strike: float,
    seconds_to_expiry: float,
    annual_volatility: float,
) -> float:
    """P(max_{0<=t<=T} S_t >= strike) — 배리어 터치 확률 (upper barrier).

    Reflection principle (drift=0 근사):
      P(max S >= K) = N(d1) + (S/K) * N(d2)  (K > S일 때)
      d1 = (ln(S/K) + σ²t/2) / (σ√t)
      d2 = (ln(S/K) - σ²t/2) / (σ√t)

    Polymarket "Will X reach $K before April 20" 류 마켓에 사용.
    만기 시점 above 확률보다 ~2배 높음 (꼬리 관찰).
    """
    if seconds_to_expiry <= 0:
        return 1.0 if current_price >= strike else 0.0
    if annual_volatility <= 0:
        return 1.0 if current_price >= strike else 0.0
    if strike <= 0 or current_price <= 0:
        return 0.5

    # 현재가가 이미 strike 이상 → 이미 터치
    if current_price >= strike:
        return 1.0

    t_years = seconds_to_expiry / 31_536_000.0
    sigma = annual_volatility
    sqrt_t = math.sqrt(t_years)
    sigma_sqrt_t = sigma * sqrt_t
    if sigma_sqrt_t == 0:
        return 0.0

    log_ratio = math.log(current_price / strike)
    d1 = (log_ratio + 0.5 * sigma**2 * t_years) / sigma_sqrt_t
    d2 = (log_ratio - 0.5 * sigma**2 * t_years) / sigma_sqrt_t

    # K > S 이므로 log_ratio < 0 → d1, d2 < 0
    # P(max > K) = N(d1) + (S/K) * N(d2)  (단순화: μ=0)
    p = norm_cdf(d1) + (current_price / strike) * norm_cdf(d2)
    return min(max(p, 0.0), 1.0)


def prob_touch_below_before(
    current_price: float,
    strike: float,
    seconds_to_expiry: float,
    annual_volatility: float,
) -> float:
    """P(min_{0<=t<=T} S_t <= strike) — lower barrier.

    대칭성: reflection principle, K < S일 때.
    """
    if seconds_to_expiry <= 0:
        return 1.0 if current_price <= strike else 0.0
    if annual_volatility <= 0:
        return 1.0 if current_price <= strike else 0.0
    if strike <= 0 or current_price <= 0:
        return 0.5

    if current_price <= strike:
        return 1.0

    t_years = seconds_to_expiry / 31_536_000.0
    sigma = annual_volatility
    sqrt_t = math.sqrt(t_years)
    sigma_sqrt_t = sigma * sqrt_t
    if sigma_sqrt_t == 0:
        return 0.0

    # K < S → log(K/S) < 0
    log_ratio = math.log(strike / current_price)
    d1 = (log_ratio + 0.5 * sigma**2 * t_years) / sigma_sqrt_t
    d2 = (log_ratio - 0.5 * sigma**2 * t_years) / sigma_sqrt_t

    p = norm_cdf(d1) + (strike / current_price) * norm_cdf(d2)
    return min(max(p, 0.0), 1.0)


def detect_barrier_question(question: str) -> bool:
    """질문이 배리어(touch) 타입인지 판정.

    Vanilla: "Will BTC close above $80k on April 30?" (만기 시점)
    Barrier: "Will BTC reach $80k before April 30?" (기간 중 한 번이라도)
    """
    q = question.lower()
    barrier_kws = (
        "reach", "hit", "touch", "before", "by april", "by may", "by june",
        "by july", "by august", "by september", "by october", "by november",
        "by december", "by january", "by february", "by march",
        "at any point", "at any time", "ever", "between now",
    )
    vanilla_kws = (
        "close above", "close below", "at close", "on april", "on may",
        "on june", "on july", "end of day", "eod",
    )
    has_barrier = any(k in q for k in barrier_kws)
    has_vanilla = any(k in q for k in vanilla_kws)
    # 명확한 vanilla 표현 있으면 vanilla 우선
    if has_vanilla and not has_barrier:
        return False
    return has_barrier


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
