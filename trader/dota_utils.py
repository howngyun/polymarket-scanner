"""Dota 2 시장 매칭 유틸 (2026-04-21 신규).

1. Polymarket question ↔ OpenDota live 매치 매칭 (팀명 fuzzy)
2. Polymarket question에서 "어느 팀 승리가 YES인가" 파싱

의존: difflib만 사용 (rapidfuzz 없이 가능). 정확도 부족하면 추후 rapidfuzz로 교체.
"""
from difflib import SequenceMatcher
from typing import Optional
import re


def _normalize(name: str) -> str:
    """팀명 정규화 — 괄호, 태그, 공백 정리."""
    s = name.lower()
    s = re.sub(r"[()\[\]{}]", " ", s)
    s = re.sub(r"\bteam\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _find_in_question(team_name: str, question: str, threshold: float = 0.75) -> bool:
    """질문 내에 팀명이 (유사하게) 등장하는가."""
    if not team_name:
        return False
    q_norm = _normalize(question)
    t_norm = _normalize(team_name)
    if t_norm in q_norm:
        return True
    # 토큰 단위 체크
    for chunk in q_norm.split():
        if _similarity(chunk, t_norm) >= threshold:
            return True
    # 전체 substring 슬라이딩
    words = q_norm.split()
    for i in range(len(words)):
        for j in range(i + 1, min(i + 4, len(words)) + 1):
            phrase = " ".join(words[i:j])
            if _similarity(phrase, t_norm) >= threshold:
                return True
    return False


def match_live_match(question: str, live_matches: list, threshold: float = 0.75) -> Optional[dict]:
    """Polymarket question과 가장 잘 맞는 live 매치 반환.

    두 팀 이름 모두 question에 등장해야 통과.
    """
    best = None
    best_score = 0.0
    for lm in live_matches:
        r_team = (lm.get("radiant_team") or {}).get("team_name") or lm.get("radiant_name") or ""
        d_team = (lm.get("dire_team") or {}).get("team_name") or lm.get("dire_name") or ""
        if not r_team or not d_team:
            continue
        r_hit = _find_in_question(r_team, question, threshold)
        d_hit = _find_in_question(d_team, question, threshold)
        if not (r_hit and d_hit):
            continue
        # tie-breaker: 팀명 길이 합 (더 구체적인 매칭 선호)
        score = len(_normalize(r_team)) + len(_normalize(d_team))
        if score > best_score:
            best_score = score
            best = lm
    return best


def resolve_yes_team(question: str, live_match: dict) -> Optional[str]:
    """YES 토큰이 radiant/dire 중 어느 쪽을 가리키는가.

    Returns: "radiant", "dire", or None
    """
    r_team = (live_match.get("radiant_team") or {}).get("team_name") or live_match.get("radiant_name") or ""
    d_team = (live_match.get("dire_team") or {}).get("team_name") or live_match.get("dire_name") or ""
    q_lower = question.lower()

    # 패턴 1: "Will {team} win" → 그 팀이 YES
    m = re.search(r"will\s+([\w\s\-\.]+?)\s+(?:win|beat|defeat)", q_lower)
    if m:
        subject = m.group(1).strip()
        r_score = _similarity(subject, r_team)
        d_score = _similarity(subject, d_team)
        if r_score > d_score and r_score > 0.6:
            return "radiant"
        if d_score > r_score and d_score > 0.6:
            return "dire"

    # 패턴 2: "{team_a} vs {team_b}" → 보통 좌측이 YES (Polymarket 관례)
    m = re.search(r"([\w\s\-\.]+?)\s+(?:vs\.?|v\.?)\s+([\w\s\-\.]+)", q_lower)
    if m:
        left = m.group(1).strip()
        r_score = _similarity(left, r_team)
        d_score = _similarity(left, d_team)
        if r_score > d_score and r_score > 0.6:
            return "radiant"
        if d_score > r_score and d_score > 0.6:
            return "dire"

    return None
