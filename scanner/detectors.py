"""기회 감지 로직. 각 함수는 기회면 dict, 아니면 None 반환."""
from datetime import datetime, timezone
from typing import Optional

import config


def _parse_end(end: Optional[str]) -> Optional[datetime]:
    if not end:
        return None
    try:
        return datetime.fromisoformat(end.replace("Z", "+00:00"))
    except Exception:
        return None


def _hours_until(end: Optional[datetime]) -> Optional[float]:
    if end is None:
        return None
    return (end - datetime.now(timezone.utc)).total_seconds() / 3600


def detect_near_resolution_bargain(m: dict) -> Optional[dict]:
    """결제 임박 + 한쪽이 거의 확정인데 시장가가 싸게 남아있는 경우.

    Polymarket 특성상 승리측 주식은 결제 시 $1. 0.95 근처라면 4-5% 먹을 수 있음.
    실제 실행은 속도 경쟁이 치열해서 개인은 어렵지만, 감지 자체는 유용."""
    if m["liquidity"] < config.MIN_LIQUIDITY:
        return None
    hours = _hours_until(_parse_end(m["endDate"]))
    if hours is None or hours < 0 or hours > config.NEAR_RESOLUTION_HOURS:
        return None
    if not m["prices"]:
        return None
    top = max(m["prices"])
    if top < config.NEAR_CERTAIN_PRICE:
        return None
    gap = 1.0 - top
    if gap < config.BARGAIN_GAP:
        return None
    return {
        "type": "near_resolution_bargain",
        "question": m["question"],
        "slug": m["slug"],
        "top_price": top,
        "implied_edge": round(gap * 100, 2),
        "hours_to_close": round(hours, 1),
        "liquidity": m["liquidity"],
        "volume": m["volume"],
    }


def detect_high_liquidity_mover(m: dict, prev_price: Optional[float]) -> Optional[dict]:
    """이전 스냅샷 대비 큰 가격 변동 + 유동성 있는 마켓."""
    if prev_price is None or not m["prices"]:
        return None
    if m["liquidity"] < config.MIN_LIQUIDITY * 5:
        return None
    current = m["prices"][0]
    move = current - prev_price
    if abs(move) < config.PRICE_MOVE_THRESHOLD:
        return None
    return {
        "type": "price_mover",
        "question": m["question"],
        "slug": m["slug"],
        "prev_price": round(prev_price, 4),
        "current_price": round(current, 4),
        "move_pct": round(move * 100, 2),
        "liquidity": m["liquidity"],
        "volume": m["volume"],
    }


def detect_extreme_longshot(m: dict) -> Optional[dict]:
    """극단 확률대(1-5%)인데 유동성 + 거래량 있는 것 — 캘리브레이션 타겟."""
    if m["liquidity"] < config.MIN_LIQUIDITY:
        return None
    if m["volume"] < config.MIN_VOLUME:
        return None
    if not m["prices"]:
        return None
    hours = _hours_until(_parse_end(m["endDate"]))
    if hours is None or hours < 24:
        return None
    top = max(m["prices"])
    bottom = min(m["prices"])
    if not (0.01 <= bottom <= 0.08):
        return None
    return {
        "type": "longshot",
        "question": m["question"],
        "slug": m["slug"],
        "longshot_price": bottom,
        "favorite_price": top,
        "hours_to_close": round(hours, 1),
        "volume": m["volume"],
    }
