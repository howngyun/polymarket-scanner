"""Dota 승률 모델 로더 (2026-04-21).

models/dota_win_v0.json에서 시간 segment별 로지스틱 계수 로드.
학습은 tools/dota_training/train_model.py.

사용:
    from trader import dota_model
    p = dota_model.predict_radiant_win(gold_adv, xp_adv, game_time_sec)
    # p is None if 모델 미학습 or 시간 segment 벗어남
"""
import json
import math
from pathlib import Path
from typing import Optional


_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "dota_win_v0.json"
_cached_model: Optional[dict] = None


def is_loaded() -> bool:
    return _load() is not None


def _load() -> Optional[dict]:
    global _cached_model
    if _cached_model is not None:
        return _cached_model
    if not _MODEL_PATH.exists():
        return None
    try:
        _cached_model = json.loads(_MODEL_PATH.read_text())
    except Exception:
        return None
    return _cached_model


def _segment_for(minute: int) -> str:
    if minute < 15:
        return "early"
    if minute < 30:
        return "mid"
    return "late"


def predict_radiant_win(gold_adv: float, xp_adv: float, game_time_sec: float) -> Optional[float]:
    """P(radiant_win). 모델 없거나 세그먼트 미지원이면 None."""
    model = _load()
    if model is None:
        return None
    minute = int(max(0, game_time_sec) / 60)
    seg_name = _segment_for(minute)
    seg = (model.get("segments") or {}).get(seg_name)
    if not seg:
        return None
    coef = seg["coef"]
    z = (
        seg["intercept"]
        + coef["gold_adv"] * gold_adv
        + coef["xp_adv"] * xp_adv
        + coef["minute"] * minute
    )
    # clip for numerical safety
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def auc_summary() -> dict:
    """세그먼트별 AUC (로드 전이면 빈 dict)."""
    model = _load()
    if not model:
        return {}
    return {name: seg.get("auc_oos") for name, seg in (model.get("segments") or {}).items()}
