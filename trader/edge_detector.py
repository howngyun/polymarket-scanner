"""엣지 탐지 — 마켓가 vs 내 확률 비교 + 오라클 검증."""
from typing import Optional

from . import config, price_feed, probability


def detect_edge(market: dict) -> Optional[dict]:
    """마켓 하나 분석 → 엣지 있으면 dict 반환, 없으면 None.

    반환 구조:
    {
      "market_id": ..., "side": "yes"|"no", "entry_price": float,
      "my_prob": float, "edge_pct": float, "bet_usd": float,
      "reasoning": str, ...
    }
    """
    # 1. 질문 파싱
    parsed = probability.parse_market_question(market["question"])
    symbol = parsed.get("symbol")
    strike = parsed.get("strike")
    direction = parsed.get("direction")

    if not symbol or strike is None:
        return None  # 파싱 실패 → 스킵 (보수적)

    # 2. 시간 필터
    seconds_left = market["seconds_left"]
    if seconds_left < config.MIN_SECONDS_TO_CLOSE or seconds_left > config.MAX_SECONDS_TO_CLOSE:
        return None

    # 3. 유동성 필터
    if market["liquidity"] < config.MIN_MARKET_LIQUIDITY:
        return None

    # 4. 현재가 + 변동성 조회
    current_price, annual_vol = price_feed.get_price_and_vol(symbol)
    if current_price is None or annual_vol is None:
        return None

    # 5. 확률 계산
    p_above = probability.prob_above_strike(
        current_price=current_price,
        strike=strike,
        seconds_to_expiry=seconds_left,
        annual_volatility=annual_vol,
    )

    # 6. YES/NO 가격
    prices = market.get("prices", [])
    outcomes = market.get("outcomes", [])
    if len(prices) < 2 or len(outcomes) < 2:
        return None

    # outcomes = ["Yes", "No"] 일반적. 순서는 일치 가정.
    yes_idx = 0
    for i, o in enumerate(outcomes):
        if str(o).lower() == "yes":
            yes_idx = i
            break

    yes_price = prices[yes_idx]
    no_price = prices[1 - yes_idx]

    # 7. 방향에 따라 my_prob 결정
    #    "above" 마켓: YES = (price > strike) = p_above
    #    "below" 마켓: YES = (price < strike) = 1 - p_above
    if direction == "above":
        my_prob_yes = p_above
    elif direction == "below":
        my_prob_yes = 1.0 - p_above
    else:
        return None  # 방향 모호

    my_prob_no = 1.0 - my_prob_yes

    # 8. 엣지 계산 (양쪽 다 검토)
    edge_yes = my_prob_yes - yes_price
    edge_no = my_prob_no - no_price

    best_side = None
    best_edge = 0.0
    best_entry = 0.0
    if edge_yes > edge_no and edge_yes > config.MIN_EDGE_PCT:
        best_side = "yes"
        best_edge = edge_yes
        best_entry = yes_price
    elif edge_no > config.MIN_EDGE_PCT:
        best_side = "no"
        best_edge = edge_no
        best_entry = no_price

    if best_side is None:
        return None

    # 9. 베팅 사이즈 (Quarter Kelly)
    # Kelly: f* = (p*b - q) / b, b = (1-price)/price
    b = (1.0 - best_entry) / best_entry if best_entry > 0 else 1
    p = my_prob_yes if best_side == "yes" else my_prob_no
    q = 1.0 - p
    kelly_full = (p * b - q) / b if b > 0 else 0
    kelly_fraction = max(0, min(kelly_full * 0.25, config.MAX_POSITION_PCT))

    # 10. 결과 조합
    return {
        "market_id": market["id"],
        "slug": market.get("slug", ""),
        "question": market["question"],
        "symbol": symbol,
        "strike": strike,
        "direction": direction,
        "current_price": current_price,
        "annual_vol": annual_vol,
        "seconds_left": seconds_left,
        "my_prob_yes": my_prob_yes,
        "my_prob_selected": p,
        "market_yes_price": yes_price,
        "market_no_price": no_price,
        "side": best_side,
        "entry_price": best_entry,
        "edge_pct": best_edge,
        "kelly_fraction": kelly_fraction,
        "liquidity": market["liquidity"],
        "token_ids": market.get("tokenIds", []),
    }
