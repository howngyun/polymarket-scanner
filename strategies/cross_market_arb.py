"""전략 2: Cross-Market Arbitrage.

로직:
  - 같은 숫자 기준(strike) 이벤트의 여러 마켓을 그룹핑
  - 예: "BTC $100K reach" / "BTC $110K reach" / "BTC $120K reach"
  - 논리적 일관성 검증: 낮은 strike 확률 >= 높은 strike 확률
  - 어긋나면 저평가 쪽 매수 (YES), 고평가 쪽 매도(→NO 매수)

수익 구조:
  - 정적 차익 (확률 수렴 기다림)
  - 기회 드묾 but 이벤트 관찰/검증 쉬움
  - 슬리피지/수수료 후에도 남는 마진 필터

구현 단순화:
  1. 암호화폐 가격 임계값 마켓만 타깃 (BTC/ETH reach $X)
  2. "reach $X by [date]" 패턴 파싱 → strike 추출
  3. 동일 자산 + 동일 마감일 그룹 → strike 오름차순 정렬
  4. 순차 쌍별 검증: p(higher) <= p(lower) 위반 시 시그널
"""
import re
from collections import defaultdict
from typing import Iterator, Optional

import requests

from trader import config, polymarket_client


# "reach $100K" / "hit $100,000" / "$100k" 등 패턴
STRIKE_PATTERN = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*[kKmM]?",
)

ASSET_KWS = {
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "eth"),
    "SOL": ("solana", "sol"),
    "XRP": ("xrp",),
}

THRESHOLD_KWS = ("reach", "hit", "above", "over", "exceed", "greater than", "top", "surpass", "break")


def _extract_strike(question: str) -> Optional[float]:
    """질문에서 달러 임계값 추출."""
    match = STRIKE_PATTERN.search(question)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    # k/K 접미사 처리
    m = re.search(r"\$\s*[\d,\.]+\s*([kKmM])", question)
    if m:
        suffix = m.group(1).lower()
        if suffix == "k":
            value *= 1_000
        elif suffix == "m":
            value *= 1_000_000
    return value


def _extract_asset(question: str) -> Optional[str]:
    q = question.lower()
    for asset, kws in ASSET_KWS.items():
        if any(k in q for k in kws):
            return asset
    return None


def _is_threshold_market(question: str) -> bool:
    q = question.lower()
    return any(k in q for k in THRESHOLD_KWS)


def _fetch_crypto_threshold_markets(max_seconds: int) -> list:
    """crypto threshold 타입 마켓만 수집."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    markets = []
    offset = 0
    page_size = 500
    max_pages = 10

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
            print(f"[cross_market] 조회 실패: {e}")
            return markets

        if not batch:
            return markets

        for m in batch:
            question = m.get("question", "")
            asset = _extract_asset(question)
            if not asset:
                continue
            if not _is_threshold_market(question):
                continue
            strike = _extract_strike(question)
            if strike is None:
                continue
            # 유효성 범위 체크 (BTC $10~$10M, ETH $100~$1M 등)
            if asset == "BTC" and not (10_000 <= strike <= 10_000_000):
                continue
            if asset == "ETH" and not (100 <= strike <= 1_000_000):
                continue
            if asset == "SOL" and not (1 <= strike <= 100_000):
                continue
            if asset == "XRP" and not (0.1 <= strike <= 1_000):
                continue

            end = polymarket_client._parse_end_date(m.get("endDate"))
            if end is None:
                continue
            seconds_left = (end - now).total_seconds()
            if seconds_left < 60 or seconds_left > max_seconds:
                continue

            outcomes = polymarket_client._parse_list_field(m.get("outcomes"))
            prices = polymarket_client._parse_prices(m.get("outcomePrices"))
            if len(outcomes) != 2 or len(prices) != 2:
                continue
            low_out = [o.lower() for o in outcomes]
            if "yes" not in low_out or "no" not in low_out:
                continue

            yes_idx = low_out.index("yes")
            yes_price = prices[yes_idx]

            token_ids = polymarket_client._parse_list_field(m.get("clobTokenIds"))
            if len(token_ids) != 2:
                continue

            markets.append({
                "id": m.get("id"),
                "slug": m.get("slug"),
                "question": question,
                "asset": asset,
                "strike": strike,
                "yes_price": yes_price,
                "no_price": prices[1 - yes_idx],
                "yes_token_id": token_ids[yes_idx],
                "no_token_id": token_ids[1 - yes_idx],
                "endDate": m.get("endDate"),
                "seconds_left": seconds_left,
                "liquidity": float(m.get("liquidity") or 0),
                "token_ids": token_ids,
            })

        if len(batch) < page_size:
            return markets
        offset += page_size

    return markets


def _group_by_asset_and_date(markets: list) -> dict:
    """(asset, endDate) 키로 그룹핑."""
    groups = defaultdict(list)
    for m in markets:
        key = (m["asset"], m["endDate"][:10])  # 일 단위 그룹
        groups[key].append(m)
    return groups


def detect_signals() -> list:
    """Cross-Market 불일치 시그널 리스트."""
    markets = _fetch_crypto_threshold_markets(max_seconds=config.CM_MAX_SECONDS_TO_CLOSE)
    if len(markets) < 2:
        return []

    groups = _group_by_asset_and_date(markets)
    signals = []

    for (asset, date), group in groups.items():
        if len(group) < 2:
            continue

        # 유동성 필터
        group = [m for m in group if m["liquidity"] >= config.CM_MIN_LIQUIDITY]
        if len(group) < 2:
            continue

        # strike 오름차순 정렬
        group.sort(key=lambda x: x["strike"])

        # 순차 쌍 검증: strike 낮음 → 확률 높거나 같아야
        # YES("reach $100K") 확률 >= YES("reach $110K") 여야 함
        for i in range(len(group) - 1):
            low = group[i]
            high = group[i + 1]

            # 불일치: high의 YES 확률 > low의 YES 확률 (논리적으로 불가)
            inconsistency = high["yes_price"] - low["yes_price"]

            if inconsistency > config.CM_MIN_INCONSISTENCY_PCT:
                # 저평가: low의 YES (더 쉬운 조건인데 확률이 낮음 → 매수)
                # 고평가: high의 YES (더 어려운 조건인데 확률이 높음 → NO 매수)

                # 우선 low YES 매수 신호만 생성 (단방향 단순화)
                signal = {
                    "strategy": "cross_market_arb",
                    "market_id": low["id"],
                    "slug": low["slug"],
                    "question": low["question"],
                    "side": "yes",
                    "entry_price": low["yes_price"],
                    "my_prob_selected": high["yes_price"] + 0.01,  # 최소한 고strike 확률+1%p여야
                    "edge_pct": (high["yes_price"] + 0.01) - low["yes_price"],
                    "seconds_left": low["seconds_left"],
                    "liquidity": low["liquidity"],
                    "endDate": low["endDate"],
                    "token_ids": low["token_ids"],
                    "paired_market": {
                        "id": high["id"],
                        "question": high["question"],
                        "yes_price": high["yes_price"],
                    },
                    "asset": asset,
                    "strike": low["strike"],
                    "paired_strike": high["strike"],
                    "inconsistency_pct": inconsistency,
                }

                if signal["edge_pct"] >= config.MIN_EDGE_PCT:
                    signals.append(signal)

    return signals


def size_bet(signal: dict, capital: float) -> float:
    """Cross-Market 베팅 크기."""
    max_by_pct = capital * config.CM_MAX_POSITION_PCT
    max_by_cap = config.MAX_BET_USD
    return round(min(max_by_pct, max_by_cap), 2)
