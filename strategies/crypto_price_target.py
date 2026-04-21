"""전략 3: 크립토 가격타겟 (justdance 아키타입, 2026-04-21 추가).

차이점 vs high_prob_no:
  - high_prob_no: NO 측만, 94-98c 대역, negative-skew 방어 엄격
  - crypto_price_target: 양방향 YES/NO, 0.05~0.95 대역 전체, Kelly fractional sizing

로직:
  1. 크립토 마켓 (BTC/ETH/SOL/XRP) 중 만기 1h~30일 스캔
  2. 같은 Black-Scholes 로그정규 모델 (probability.py 재사용)
  3. |my_prob - market_price| > MIN_EDGE_PCT 면 엣지 큰 쪽 매수
     - my_prob_yes > market_yes + edge → YES 매수
     - my_prob_no  > market_no  + edge → NO 매수
  4. Fractional Kelly (0.25 Kelly) 사이즈 — high_prob_no 보다 공격적이나 full Kelly는 금지

근거 (wallet_research):
  justdance (0xcc500cbcc8) — 월 PnL $208K, 16,562 trades, biggest win $86K.
  같은 BS 모델이지만 양방향 잡아먹는 구조로 추정.
  high_prob_no가 놓치는 mid-range (40-80c) 엣지를 커버.

리스크:
  - high_prob_no와 겹치는 시장은 high_prob_no 우선 (중복 진입 방지)
  - Kelly fractional도 연속 3패 시 포지션 축소 필요 (거버넌스는 risk_gate에서)
  - News blackout 윈도우는 공유
"""
from typing import Iterator, Optional

from trader import config, polymarket_client, price_feed, probability


CRYPTO_SYMBOLS = ("BTC", "ETH", "SOL", "XRP")


def _iter_crypto_markets(min_sec: int, max_sec: int) -> Iterator[dict]:
    """크립토 마켓 중 만기 윈도우 내 것."""
    from datetime import datetime, timezone
    import requests

    now = datetime.now(timezone.utc)
    offset = 0
    page_size = 500
    max_pages = 10
    crypto_kws = ("bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp")

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
            print(f"[crypto_price_target] 마켓 조회 실패: {e}")
            return

        if not batch:
            return

        for m in batch:
            q = (m.get("question") or "").lower()
            if not any(k in q for k in crypto_kws):
                continue
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


def _compute_my_prob_yes(symbol: str, strike: float, direction: str,
                         is_barrier: bool, seconds_left: float,
                         price_cache: dict, vol_cache: dict) -> Optional[float]:
    """BS 모델로 YES 확률 계산. (high_prob_no._compute_my_prob_no의 YES 버전)"""
    if symbol not in price_cache:
        try:
            price_cache[symbol] = price_feed.get_current_price(symbol)
        except Exception as e:
            print(f"[crypto_price_target] 가격 조회 실패 {symbol}: {e}")
            return None
    if symbol not in vol_cache:
        try:
            vol_cache[symbol] = price_feed.get_recent_volatility(symbol, minutes=60)
        except Exception as e:
            print(f"[crypto_price_target] 변동성 조회 실패 {symbol}: {e}")
            return None

    current = price_cache[symbol]
    vol = vol_cache[symbol]

    if is_barrier:
        if direction == "above":
            p_yes = probability.prob_touch_above_before(current, strike, seconds_left, vol)
        elif direction == "below":
            p_yes = probability.prob_touch_below_before(current, strike, seconds_left, vol)
        else:
            return None
    else:
        p_yes_above = probability.prob_above_strike(current, strike, seconds_left, vol)
        if direction == "above":
            p_yes = p_yes_above
        elif direction == "below":
            p_yes = 1.0 - p_yes_above
        else:
            return None

    # fat-tail floor + ceiling (양방향 대칭 방어)
    p_yes = max(p_yes, config.P_YES_FLOOR)
    p_yes = min(p_yes, 1.0 - config.P_YES_FLOOR)
    return p_yes


def _in_news_blackout(now_utc) -> bool:
    """high_prob_no와 동일 로직 (공유)."""
    from datetime import datetime, timezone, timedelta
    if not config.NEWS_BLACKOUT_EVENTS:
        return False
    window = timedelta(hours=config.NEWS_BLACKOUT_HOURS)
    for iso in config.NEWS_BLACKOUT_EVENTS:
        try:
            event = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except Exception:
            continue
        if abs((now_utc - event).total_seconds()) <= window.total_seconds():
            return True
    return False


def detect_signals() -> list:
    """크립토 가격타겟 양방향 엣지 시그널."""
    from datetime import datetime, timezone

    if _in_news_blackout(datetime.now(timezone.utc)):
        print("[crypto_price_target] 뉴스 블랙아웃 — 스킵")
        return []

    signals = []
    price_cache: dict = {}
    vol_cache: dict = {}

    min_sec = getattr(config, "CPT_MIN_SECONDS_TO_CLOSE", 3600)
    max_sec = getattr(config, "CPT_MAX_SECONDS_TO_CLOSE", 30 * 86400)
    min_edge = getattr(config, "CPT_MIN_EDGE_PCT", 0.05)
    min_liq = getattr(config, "CPT_MIN_LIQUIDITY", 5000)
    skip_no_band_low = getattr(config, "HP_NO_MIN_PRICE", 0.94)
    skip_no_band_high = getattr(config, "HP_NO_MAX_PRICE", 0.98)

    for market in _iter_crypto_markets(min_sec=min_sec, max_sec=max_sec):
        if market["liquidity"] < min_liq:
            continue

        outcomes = [o.lower() for o in market["outcomes"]]
        prices = market["prices"]
        if len(outcomes) != 2 or len(prices) != 2:
            continue
        if "yes" not in outcomes or "no" not in outcomes:
            continue

        yes_idx = outcomes.index("yes")
        no_idx = outcomes.index("no")
        yes_price = prices[yes_idx]
        no_price = prices[no_idx]

        # high_prob_no 영역과 완전 겹치는 경우 스킵 (중복 진입 방지)
        # high_prob_no: NO 0.94~0.98. crypto_price_target은 그 외 영역만 먹음
        if skip_no_band_low <= no_price <= skip_no_band_high:
            continue

        parsed = probability.parse_market_question(market["question"])
        symbol = parsed.get("symbol")
        strike = parsed.get("strike")
        direction = parsed.get("direction")

        if symbol not in CRYPTO_SYMBOLS:
            continue
        if strike is None or strike <= 0:
            continue
        if direction not in ("above", "below"):
            continue

        is_barrier = probability.detect_barrier_question(market["question"])
        my_prob_yes = _compute_my_prob_yes(
            symbol, strike, direction, is_barrier,
            market["seconds_left"], price_cache, vol_cache,
        )
        if my_prob_yes is None:
            continue
        my_prob_no = 1.0 - my_prob_yes

        # 양방향 엣지 계산 → 큰 쪽 선택
        edge_yes = my_prob_yes - yes_price
        edge_no = my_prob_no - no_price

        if edge_yes >= edge_no and edge_yes >= min_edge:
            side = "yes"
            entry_price = yes_price
            my_prob_side = my_prob_yes
            edge = edge_yes
        elif edge_no > edge_yes and edge_no >= min_edge:
            side = "no"
            entry_price = no_price
            my_prob_side = my_prob_no
            edge = edge_no
        else:
            continue

        token_ids = market["tokenIds"]
        if len(token_ids) != 2:
            continue
        side_token_id = token_ids[yes_idx] if side == "yes" else token_ids[no_idx]

        signals.append({
            "strategy": "crypto_price_target",
            "market_id": market["id"],
            "slug": market["slug"],
            "question": market["question"],
            "symbol": symbol,
            "strike": strike,
            "direction": direction,
            "is_barrier": is_barrier,
            "side": side,
            "entry_price": entry_price,
            "my_prob_selected": my_prob_side,
            "edge_pct": edge,
            "current_price": price_cache.get(symbol),
            "annual_vol": vol_cache.get(symbol),
            "seconds_left": market["seconds_left"],
            "liquidity": market["liquidity"],
            "endDate": market["endDate"],
            "token_ids": token_ids,
            "no_token_id": token_ids[no_idx],
            "yes_token_id": token_ids[yes_idx],
            "side_token_id": side_token_id,
        })

    signals.sort(key=lambda s: s["edge_pct"], reverse=True)
    return signals


def size_bet(signal: dict, capital: float) -> float:
    """Fractional Kelly sizing (0.25 Kelly).

    Kelly 공식 (바이너리):
      f* = (p * b - q) / b
      p = my_prob, q = 1-p, b = (1 - price) / price  (payout 비율)

    0.25 × f* 적용. HP_NO 대비 더 공격적이지만 full Kelly 방지.
    자본 대비 건당 상한은 config.CPT_MAX_POSITION_PCT로 캡.
    """
    p = signal["my_prob_selected"]
    price = signal["entry_price"]
    if price <= 0 or price >= 1:
        return 0.0
    b = (1.0 - price) / price
    q = 1.0 - p
    f_full = (p * b - q) / b
    if f_full <= 0:
        return 0.0

    fraction = getattr(config, "CPT_KELLY_FRACTION", 0.25)
    max_pct = getattr(config, "CPT_MAX_POSITION_PCT", 0.08)

    f_clamped = min(fraction * f_full, max_pct)
    bet = capital * f_clamped
    bet = min(bet, config.MAX_BET_USD)
    bet = max(bet, 0.0)
    return round(bet, 2)
