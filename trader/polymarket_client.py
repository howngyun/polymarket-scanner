"""Polymarket API 래퍼 — 마켓 조회 + 오더북 조회.

실거래 주문은 executor.py에서 처리.
"""
import json
from datetime import datetime, timezone
from typing import Iterator, Optional

import requests

from . import config


def _parse_list_field(raw):
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return []
    return []


def _parse_prices(raw) -> list:
    vals = _parse_list_field(raw)
    try:
        return [float(x) for x in vals]
    except Exception:
        return []


def _parse_end_date(end: Optional[str]) -> Optional[datetime]:
    if not end:
        return None
    try:
        return datetime.fromisoformat(end.replace("Z", "+00:00"))
    except Exception:
        return None


def iter_crypto_markets_closing_soon(
    max_seconds_to_close: int = 300,
    min_seconds_to_close: int = 30,
) -> Iterator[dict]:
    """암호화폐 관련 마켓 중 곧 마감되는 것만.

    키워드로 필터: bitcoin, btc, ethereum, eth, solana, sol, xrp
    """
    now = datetime.now(timezone.utc)
    crypto_kws = ("bitcoin", "btc", "ethereum", "eth", "solana", "sol", "xrp")

    offset = 0
    page_size = 500
    while True:
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
            print(f"[polymarket] 마켓 조회 실패: {e}")
            return

        if not batch:
            return

        for m in batch:
            q = (m.get("question") or "").lower()
            if not any(k in q for k in crypto_kws):
                continue
            end = _parse_end_date(m.get("endDate"))
            if end is None:
                continue
            seconds_left = (end - now).total_seconds()
            if seconds_left < min_seconds_to_close or seconds_left > max_seconds_to_close:
                continue

            yield {
                "id": m.get("id"),
                "slug": m.get("slug"),
                "question": m.get("question", ""),
                "endDate": m.get("endDate"),
                "seconds_left": seconds_left,
                "liquidity": float(m.get("liquidity") or 0),
                "volume": float(m.get("volume") or 0),
                "outcomes": _parse_list_field(m.get("outcomes")),
                "prices": _parse_prices(m.get("outcomePrices")),
                "conditionId": m.get("conditionId"),
                "tokenIds": _parse_list_field(m.get("clobTokenIds")),
            }

        if len(batch) < page_size:
            return
        offset += page_size


def get_orderbook(token_id: str) -> Optional[dict]:
    """특정 토큰의 오더북 조회 (슬리피지 계산용)."""
    try:
        r = requests.get(
            f"{config.POLYMARKET_CLOB_URL}/book",
            params={"token_id": token_id},
            timeout=5,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[polymarket] 오더북 실패 token={token_id}: {e}")
        return None


def estimate_avg_fill_price(orderbook: Optional[dict], side: str, size_usd: float) -> Optional[float]:
    """주문 크기에 대한 평균 체결가 추정.

    side="buy" → asks에서 매수 (낮은 가격부터 소진)
    side="sell" → bids에서 매도 (높은 가격부터 소진)
    """
    if not orderbook:
        return None
    levels = orderbook.get("asks" if side == "buy" else "bids", [])
    if not levels:
        return None

    # asks는 오름차순, bids는 내림차순이 아닐 수 있음 → 정렬
    try:
        if side == "buy":
            levels = sorted(levels, key=lambda x: float(x.get("price", 0)))
        else:
            levels = sorted(levels, key=lambda x: float(x.get("price", 0)), reverse=True)
    except Exception:
        return None

    remaining = size_usd
    total_cost = 0.0
    total_size = 0.0
    for lvl in levels:
        try:
            price = float(lvl.get("price", 0))
            size = float(lvl.get("size", 0))
        except Exception:
            continue
        level_notional = price * size
        take = min(level_notional, remaining)
        if take <= 0:
            continue
        shares = take / price
        total_cost += take
        total_size += shares
        remaining -= take
        if remaining <= 0:
            break

    if total_size == 0:
        return None
    if remaining > 0:  # 오더북 깊이 부족
        return None
    return total_cost / total_size
