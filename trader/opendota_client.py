"""OpenDota API 래퍼 (무료, 2026-04-21 신규).

무료 티어: 60 req/min, 50K req/day. 키 없이 호출 가능.

쓸 엔드포인트:
  - /live : 현재 진행 중인 프로 매치 (Polymarket에 상장되는 매치 매칭)
  - /proMatches : 최근 종료된 프로 매치 (백테스트용)
  - /matches/{match_id} : 특정 매치 상세 (최종 결과)
  - /teams/{team_id} : 팀 정보 (Elo, 최근 성적)

라이브 매치 → 승률 모델 입력으로 쓰는 주요 필드:
  - radiant_score / dire_score (킬 수)
  - radiant_gold_adv / xp_adv (골드·XP 리드)
  - game_time (경기 경과 시간, 초)
  - 빌딩/배럭 상태 (없으면 infer)

TODO:
  - 프로 매치 vs pub 매치 필터 (league_id 체크)
  - OpenDota 라이브 피드 지연 측정 (2~5초 예상)
  - Rate limit 핸들링 (60/min 초과 시 429)
"""
from typing import Optional
import time

import requests

from trader import config


_last_request_ts = 0.0
_MIN_INTERVAL = 1.05  # 60/min 보다 살짝 여유


def _rate_limit():
    global _last_request_ts
    elapsed = time.time() - _last_request_ts
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_ts = time.time()


def _get(path: str, params: Optional[dict] = None, timeout: int = 10) -> Optional[dict]:
    _rate_limit()
    url = f"{config.DOTA_OPENDOTA_BASE}{path}"
    try:
        r = requests.get(url, params=params or {}, timeout=timeout)
        if r.status_code == 429:
            print(f"[opendota] rate limited on {path}")
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[opendota] GET {path} 실패: {e}")
        return None


def get_live_matches() -> list:
    """현재 진행 중인 프로 매치 리스트.

    필드 예시:
      match_id, league_id, game_time, radiant_score, dire_score,
      radiant_team, dire_team, radiant_gold_adv, radiant_xp_adv, ...
    """
    data = _get("/live")
    if not isinstance(data, list):
        return []
    # 프로 매치만 (league_id 있는 것)
    return [m for m in data if m.get("league_id")]


def get_match(match_id: int) -> Optional[dict]:
    """매치 상세 (종료 후 결과 포함)."""
    return _get(f"/matches/{match_id}")


def get_pro_matches(less_than_match_id: Optional[int] = None) -> list:
    """최근 종료 프로 매치 (페이지네이션용)."""
    params = {}
    if less_than_match_id:
        params["less_than_match_id"] = less_than_match_id
    data = _get("/proMatches", params=params)
    return data if isinstance(data, list) else []


def get_team(team_id: int) -> Optional[dict]:
    """팀 정보 (rating, wins, losses, last_match_time)."""
    return _get(f"/teams/{team_id}")
