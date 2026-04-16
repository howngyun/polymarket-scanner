"""Polymarket Gamma API 클라이언트 — 공개 API, 인증 불필요."""
import json
import time
from typing import Iterator

import requests

import config


def _parse_price_list(raw) -> list:
    """outcomePrices는 JSON 문자열로 올 때도 있어서 정규화."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [float(x) for x in raw]
    if isinstance(raw, str):
        try:
            return [float(x) for x in json.loads(raw)]
        except Exception:
            return []
    return []


def _parse_outcomes(raw) -> list:
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


def iter_active_markets() -> Iterator[dict]:
    """활성 마켓 전체 페이징 조회."""
    offset = 0
    while True:
        for attempt in range(3):
            try:
                r = requests.get(
                    config.GAMMA_URL,
                    params={
                        "active": "true",
                        "closed": "false",
                        "limit": config.PAGE_SIZE,
                        "offset": offset,
                    },
                    timeout=15,
                )
                r.raise_for_status()
                batch = r.json()
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[client] fetch 실패 offset={offset}: {e}")
                    return
                time.sleep(2 ** attempt)
        if not batch:
            return
        for m in batch:
            yield _normalize(m)
        if len(batch) < config.PAGE_SIZE:
            return
        offset += config.PAGE_SIZE


def _normalize(m: dict) -> dict:
    prices = _parse_price_list(m.get("outcomePrices"))
    outcomes = _parse_outcomes(m.get("outcomes"))
    return {
        "id": m.get("id"),
        "slug": m.get("slug"),
        "question": (m.get("question") or "")[:200],
        "endDate": m.get("endDate"),
        "liquidity": float(m.get("liquidity") or 0),
        "volume": float(m.get("volume") or 0),
        "outcomes": outcomes,
        "prices": prices,
        "conditionId": m.get("conditionId"),
    }
