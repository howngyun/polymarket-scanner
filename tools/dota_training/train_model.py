"""Dota 2 승률 모델 학습 (2026-04-21).

입력: data/dota_matches.csv (fetch_matches.py 산출)
출력: models/dota_win_v0.json (계수 + 메타)

모델:
  시간 segment별 로지스틱 회귀 분리 학습
    early (0~15 min), mid (15~30), late (30+)
  features: gold_adv_norm, xp_adv_norm, minute
  target: radiant_win

계수 JSON 포맷:
  {
    "version": "v0",
    "trained_on": "YYYY-MM-DD",
    "n_samples": N,
    "segments": {
      "early":  {"intercept": b0, "coef": {"gold_adv": b1, "xp_adv": b2, "minute": b3}},
      "mid":    {...},
      "late":   {...}
    },
    "auc_oos": 0.XX
  }
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score


def load_samples(path: Path):
    rows = []
    with path.open() as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append({
                "match_id": int(row["match_id"]),
                "minute": int(row["minute"]),
                "gold_adv": float(row["gold_adv"]),
                "xp_adv": float(row["xp_adv"]),
                "radiant_win": int(row["radiant_win"]),
            })
    return rows


def segment_of(minute: int) -> str:
    if minute < 15:
        return "early"
    if minute < 30:
        return "mid"
    return "late"


def train_segment(samples: list, name: str) -> dict:
    if len(samples) < 100:
        print(f"[train] {name}: 샘플 {len(samples)} 부족 → 스킵")
        return {}

    X = np.array([[s["gold_adv"], s["xp_adv"], s["minute"]] for s in samples], dtype=float)
    y = np.array([s["radiant_win"] for s in samples], dtype=int)

    # match_id 단위로 train/test split (같은 매치가 train·test 양쪽 들어가지 않도록)
    # 빠른 버전: stratified random split 50/50 (matches 수준이 아닌 rows 수준)
    # TODO: group-aware split
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

    model = LogisticRegression(max_iter=500, C=1.0)
    model.fit(X_tr, y_tr)

    p_te = model.predict_proba(X_te)[:, 1]
    try:
        auc = float(roc_auc_score(y_te, p_te))
    except Exception:
        auc = float("nan")

    coefs = model.coef_[0]
    result = {
        "intercept": float(model.intercept_[0]),
        "coef": {
            "gold_adv": float(coefs[0]),
            "xp_adv": float(coefs[1]),
            "minute": float(coefs[2]),
        },
        "n_samples": len(samples),
        "auc_oos": auc,
    }
    print(f"[train] {name}: n={len(samples)} AUC_oos={auc:.3f} "
          f"intercept={result['intercept']:.3f} "
          f"gold={result['coef']['gold_adv']:.2e} xp={result['coef']['xp_adv']:.2e}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="data/dota_matches.csv")
    ap.add_argument("--out", default="models/dota_win_v0.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    inp = root / args.inp
    out = root / args.out

    if not inp.exists():
        print(f"[train] 입력 파일 없음: {inp}")
        print("       tools/dota_training/fetch_matches.py 먼저 실행")
        return 1

    rows = load_samples(inp)
    print(f"[train] 샘플 {len(rows)} 로드 ({len({r['match_id'] for r in rows})}개 매치)")

    segmented = defaultdict(list)
    for r in rows:
        segmented[segment_of(r["minute"])].append(r)

    segments = {}
    for name in ("early", "mid", "late"):
        seg = train_segment(segmented[name], name)
        if seg:
            segments[name] = seg

    if not segments:
        print("[train] 학습 가능한 segment 없음")
        return 1

    model_doc = {
        "version": "v0",
        "trained_on": datetime.now(timezone.utc).date().isoformat(),
        "n_samples_total": len(rows),
        "n_matches": len({r["match_id"] for r in rows}),
        "feature_order": ["gold_adv", "xp_adv", "minute"],
        "segments": segments,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(model_doc, indent=2))
    print(f"[train] 저장: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
