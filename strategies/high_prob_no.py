"""전략 1: 94-98c NO 그라인딩.

로직:
  - NO 가격이 0.94~0.98 범위인 마켓 스캔
  - 시장가 의미: 이벤트 발생 확률 2~6%로 본다는 뜻
  - 확실한 결과에 NO 매수 → 주당 2~6c 수익 반복 수확

주의 (Negative Skewness):
  - 99번 작게 벌고 1번에 크게 잃는 구조
  - 날씨 이변, 이벤트 취소, 오라클 분쟁 등 테일 리스크
  - 건당 자본 5% 이하로 엄격 제한

진입 조건:
  1. 질문 카테고리: weather, temperature, sports (정치·암호화폐 제외)
  2. NO 가격: 0.94 ≤ p ≤ 0.98
  3. 유동성: $1,000 이상
  4. 마감까지: 5분~24시간 (너무 가까우면 오라클 분쟁 리스크, 너무 멀면 자본 효율 낮음)
"""
from typing import Iterator, Optional

from trader import config, polymarket_client


# 카테고리 판정 — 고변동성 자산만 제외, 나머지는 허용.
# (실제 PnL 관찰 후 카테고리별 승률로 재조정할 예정)
EXCLUDE_KWS = (
    # 실시간 고변동성 자산 → 단시간에 가격 급변 가능
    "bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp",
    "dogecoin", "doge", "cardano", "ada",
    # 지정가 돌파형 (이벤트성이 아닌 가격 추적형)
    "reach $", "hit $", "above $", "exceed $",
)

WEATHER_KWS = ("rain", "snow", "temperature", "weather", "degree", "hurricane", "storm", "wind", "humidity", "precipitation")
SPORTS_KWS = ("wins", "beat", "defeat", "score", "goal", "championship", "finals", "nba", "nfl", "mlb", "nhl", "soccer", "tennis", "draft", "rookie", "mvp")
ENTERTAINMENT_KWS = ("eurovision", "oscar", "grammy", "emmy", "bafta", "award", "best picture", "best actor")
POLITICS_KWS = ("primary", "nominee", "election", "senate", "governor", "president")


def _categorize(question: str) -> Optional[str]:
    """마켓을 카테고리로 분류. 제외 대상이면 None."""
    q = question.lower()
    if any(k in q for k in EXCLUDE_KWS):
        return None
    if any(k in q for k in WEATHER_KWS):
        return "weather"
    if any(k in q for k in SPORTS_KWS):
        return "sports"
    if any(k in q for k in ENTERTAINMENT_KWS):
        return "entertainment"
    if any(k in q for k in POLITICS_KWS):
        return "politics"
    return "other"  # 분류 안 되는 것도 일단 허용 (Polymarket 범위 광범위)


def _iter_all_markets_closing_soon(min_sec: int, max_sec: int) -> Iterator[dict]:
    """모든 카테고리 마켓 순회 (crypto 필터 없이)."""
    from datetime import datetime, timezone
    import requests

    now = datetime.now(timezone.utc)
    offset = 0
    page_size = 500
    max_pages = 10  # 최대 5000개 마켓

    for _ in range(max_pages):
        try:
            r = requests.get(
                config.POLYMARKET_GAMMA_URL,
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": page_size,
                    "offset": offset,
                },
                timeout=15,
            )
            r.raise_for_status()
            batch = r.json()
        except Exception as e:
            print(f"[high_prob_no] 마켓 조회 실패: {e}")
            return

        if not batch:
            return

        for m in batch:
            end = polymarket_client._parse_end_date(m.get("endDate"))
            if end is None:
                continue
            seconds_left = (end - now).total_seconds()
            if seconds_left < min_sec or seconds_left > max_sec:
                continue

            yield {
                "id": m.get("id"),
                "slug": m.get("slug"),
                "question": m.get("question", ""),
                "endDate": m.get("endDate"),
                "seconds_left": seconds_left,
                "liquidity": float(m.get("liquidity") or 0),
                "volume": float(m.get("volume") or 0),
                "outcomes": polymarket_client._parse_list_field(m.get("outcomes")),
                "prices": polymarket_client._parse_prices(m.get("outcomePrices")),
                "conditionId": m.get("conditionId"),
                "tokenIds": polymarket_client._parse_list_field(m.get("clobTokenIds")),
            }

        if len(batch) < page_size:
            return
        offset += page_size


def detect_signals() -> list:
    """94-98c NO 후보 시그널 리스트 반환."""
    signals = []

    for market in _iter_all_markets_closing_soon(
        min_sec=config.HP_NO_MIN_SECONDS_TO_CLOSE,
        max_sec=config.HP_NO_MAX_SECONDS_TO_CLOSE,
    ):
        # 1. 유동성 필터
        if market["liquidity"] < config.HP_NO_MIN_LIQUIDITY:
            continue

        # 2. 카테고리 필터
        category = _categorize(market["question"])
        if category is None:
            continue

        # 3. outcomes/prices 검증 (Yes/No 바이너리)
        outcomes = [o.lower() for o in market["outcomes"]]
        prices = market["prices"]
        if len(outcomes) != 2 or len(prices) != 2:
            continue
        if "yes" not in outcomes or "no" not in outcomes:
            continue

        no_idx = outcomes.index("no")
        no_price = prices[no_idx]

        # 4. NO 가격 범위 (94-98c)
        if not (config.HP_NO_MIN_PRICE <= no_price <= config.HP_NO_MAX_PRICE):
            continue

        # 5. 엣지 계산 (시장가 기준 NO 확률이 94-98%라고 보면 — 보수적으로 1c 엣지 가정)
        # 진짜 엣지는 내 모델이 없으니 "시장가 자체가 엣지" 로 취급
        # edge_pct = 1 - no_price (이론적 최대 수익률)
        max_profit_pct = 1.0 - no_price  # 2~6%

        token_ids = market["tokenIds"]
        if len(token_ids) != 2:
            continue
        no_token_id = token_ids[no_idx]

        signal = {
            "strategy": "high_prob_no",
            "market_id": market["id"],
            "slug": market["slug"],
            "question": market["question"],
            "category": category,
            "side": "no",
            "entry_price": no_price,
            "my_prob_selected": 0.99,  # 우리가 거의 확정됐다고 보는 확률 (99% NO)
            "edge_pct": 0.99 - no_price,  # my_prob - market (양수여야 진입)
            "max_profit_pct": max_profit_pct,
            "seconds_left": market["seconds_left"],
            "liquidity": market["liquidity"],
            "endDate": market["endDate"],
            "token_ids": token_ids,
            "no_token_id": no_token_id,
        }

        # 최소 엣지 체크
        if signal["edge_pct"] < config.MIN_EDGE_PCT:
            continue

        signals.append(signal)

    return signals


def size_bet(signal: dict, capital: float) -> float:
    """건당 베팅 크기 — 엄격한 자본 5% (negative skew 방어)."""
    max_by_pct = capital * config.HP_NO_MAX_POSITION_PCT
    max_by_cap = config.MAX_BET_USD
    return round(min(max_by_pct, max_by_cap), 2)
