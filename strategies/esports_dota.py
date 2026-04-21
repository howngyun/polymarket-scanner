"""전략 4: Dota 2 라이브 승률 arb (eanvanezygv 아키타입, 2026-04-21 신규).

⚠️ 현재 상태: 스캐폴딩만. 모델 v0 학습 전까지 STRATEGY_ESPORTS_DOTA=False로 꺼둠.

로직 (설계):
  1. Polymarket에서 Dota 2 라이브 매치 시장 스캔 (question에 "Dota" 포함)
  2. OpenDota /live에서 해당 match_id의 현재 상태 조회
     매칭 키: Polymarket question에 팀명 포함 → OpenDota live 매치의 team_name과 fuzzy match
  3. 승률 모델 v0:
        logit(p_radiant) = b0 + b1 * gold_adv + b2 * xp_adv + b3 * net_kills + b4 * game_time_min
     계수는 과거 프로매치 10K개로 로지스틱 회귀 학습 예정
  4. my_prob vs 시장 호가 비교 → 엣지 6%p 이상이면 진입

매칭 난제:
  - Polymarket 팀명 (e.g. "Xtreme Gaming") ↔ OpenDota team_name 표기 차이
  - BO3/BO5 시리즈 시장 vs 단일 게임 시장 구분 필요

데이터 소스:
  - OpenDota /live: 무료, 60 req/min, 라이브 피드 지연 ~2-5초
  - Polymarket gamma: 기존 클라이언트 재사용

리스크:
  - 모델 미학습 상태 → 단순 "골드 리드 > 5K면 승률 85% 가정" 같은 heuristic은 위험
  - 메타 변화 (패치 7.39 등) 시 모델 재학습 필요
  - Polymarket Dota 시장 유동성 얕음 → 포지션 쪼개기 필수
"""
from typing import Iterator, Optional

from trader import config, polymarket_client, opendota_client, dota_utils, dota_model


def _iter_dota_markets() -> Iterator[dict]:
    """Polymarket 활성 Dota 2 시장 스캔."""
    from datetime import datetime, timezone
    import requests

    now = datetime.now(timezone.utc)
    offset = 0
    page_size = 500
    max_pages = 6
    kws = ("dota", "dota 2")

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
            print(f"[esports_dota] 마켓 조회 실패: {e}")
            return

        if not batch:
            return

        for m in batch:
            q = (m.get("question") or "").lower()
            if not any(k in q for k in kws):
                continue
            end = polymarket_client._parse_end_date(m.get("endDate"))
            if end is None or (end - now).total_seconds() < 0:
                continue

            yield {
                "id": m.get("id"),
                "slug": m.get("slug"),
                "question": m.get("question", ""),
                "endDate": m.get("endDate"),
                "liquidity": float(m.get("liquidity") or 0),
                "outcomes": polymarket_client._parse_list_field(m.get("outcomes")),
                "prices": polymarket_client._parse_prices(m.get("outcomePrices")),
                "tokenIds": polymarket_client._parse_list_field(m.get("clobTokenIds")),
            }

        if len(batch) < page_size:
            return
        offset += page_size


def _predict_radiant_win_prob(live_match: dict) -> Optional[float]:
    """승률 모델 — dota_model.predict_radiant_win 래퍼. game_time 가드 포함."""
    gold_adv = live_match.get("radiant_gold_adv", 0) or 0
    xp_adv = live_match.get("radiant_xp_adv", 0) or 0
    game_time = live_match.get("game_time", 0) or 0

    if game_time < config.DOTA_MIN_LIVE_MINUTES * 60:
        return None
    return dota_model.predict_radiant_win(gold_adv, xp_adv, game_time)


def detect_signals() -> list:
    """Dota 2 라이브 승률 arb 시그널. 모델 파일 미존재 시 빈 리스트."""
    if not dota_model.is_loaded():
        print("[esports_dota] 모델 미로드 (models/dota_win_v0.json 없음) — 스킵")
        return []

    live_matches = opendota_client.get_live_matches()
    if not live_matches:
        return []

    signals = []
    min_edge = config.DOTA_MIN_EDGE_PCT
    min_liq = config.DOTA_MIN_LIQUIDITY

    for market in _iter_dota_markets():
        if market["liquidity"] < min_liq:
            continue

        outcomes = [o.lower() for o in market["outcomes"]]
        prices = market["prices"]
        if len(outcomes) != 2 or len(prices) != 2:
            continue

        lm = dota_utils.match_live_match(market["question"], live_matches)
        if not lm:
            continue

        p_radiant = _predict_radiant_win_prob(lm)
        if p_radiant is None:
            continue

        yes_team = dota_utils.resolve_yes_team(market["question"], lm)
        if yes_team not in ("radiant", "dire"):
            # 매핑 애매 → 진입 금지
            continue

        if "yes" not in outcomes or "no" not in outcomes:
            continue
        yes_idx = outcomes.index("yes")
        no_idx = outcomes.index("no")
        yes_price = prices[yes_idx]
        no_price = prices[no_idx]

        my_prob_yes = p_radiant if yes_team == "radiant" else (1.0 - p_radiant)
        edge_yes = my_prob_yes - yes_price
        edge_no = (1.0 - my_prob_yes) - no_price

        if edge_yes >= edge_no and edge_yes >= min_edge:
            side, entry, my_p, edge = "yes", yes_price, my_prob_yes, edge_yes
        elif edge_no > edge_yes and edge_no >= min_edge:
            side, entry, my_p, edge = "no", no_price, 1.0 - my_prob_yes, edge_no
        else:
            continue

        signals.append({
            "strategy": "esports_dota",
            "market_id": market["id"],
            "slug": market["slug"],
            "question": market["question"],
            "side": side,
            "entry_price": entry,
            "my_prob_selected": my_p,
            "edge_pct": edge,
            "seconds_left": None,
            "liquidity": market["liquidity"],
            "endDate": market["endDate"],
            "token_ids": market["tokenIds"],
            "side_token_id": market["tokenIds"][yes_idx] if side == "yes" else market["tokenIds"][no_idx],
            "live_match_id": lm.get("match_id"),
            "game_time": lm.get("game_time"),
            "gold_adv": lm.get("radiant_gold_adv"),
            "yes_team": yes_team,
            "p_radiant": p_radiant,
        })

    signals.sort(key=lambda s: s["edge_pct"], reverse=True)
    return signals


def size_bet(signal: dict, capital: float) -> float:
    """보수적 고정 분수 (모델 검증 전까지)."""
    max_pct = config.DOTA_MAX_POSITION_PCT
    bet = min(capital * max_pct, config.MAX_BET_USD)
    return round(bet, 2)
