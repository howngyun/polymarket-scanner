"""Dota 2 프로매치 학습 데이터 수집.

흐름:
  1. /proMatches 페이지네이션 → 매치 ID N개 수집
  2. 각 매치의 /matches/{id} 호출 → radiant_gold_adv / radiant_xp_adv / radiant_win 추출
  3. 매 분(minute)마다 하나의 샘플 → CSV

Rate limit: OpenDota 무료 60req/min. 50만 req/day. 500 매치 = ~8분.

사용법:
  python tools/dota_training/fetch_matches.py --n 500 --out data/dota_matches.csv
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import requests

BASE = "https://api.opendota.com/api"
MIN_INTERVAL = 1.05  # 60/min


def fetch_pro_match_ids(n: int) -> list:
    """최근 프로매치 ID N개. /proMatches는 페이지당 100개."""
    ids = []
    less_than = None
    while len(ids) < n:
        params = {}
        if less_than is not None:
            params["less_than_match_id"] = less_than
        r = requests.get(f"{BASE}/proMatches", params=params, timeout=15)
        if r.status_code != 200:
            print(f"[fetch] proMatches {r.status_code}", file=sys.stderr)
            break
        batch = r.json()
        if not batch:
            break
        # radiant_win이 None인 건 제외 (진행 중 or 취소)
        for m in batch:
            if m.get("radiant_win") is None:
                continue
            ids.append(m["match_id"])
            if len(ids) >= n:
                break
        less_than = batch[-1]["match_id"]
        time.sleep(MIN_INTERVAL)
    return ids[:n]


def fetch_match_detail(match_id: int) -> dict:
    r = requests.get(f"{BASE}/matches/{match_id}", timeout=20)
    if r.status_code != 200:
        return {}
    return r.json()


def extract_samples(match: dict) -> list:
    """매 분(minute) 샘플 추출. 빈 gold_adv/xp_adv면 skip."""
    gold = match.get("radiant_gold_adv") or []
    xp = match.get("radiant_xp_adv") or []
    if not gold or not xp:
        return []
    rwin = match.get("radiant_win")
    if rwin is None:
        return []
    match_id = match.get("match_id")
    duration = match.get("duration", 0)
    # gold/xp 배열 길이는 대체로 분 단위
    n = min(len(gold), len(xp))
    samples = []
    for minute in range(n):
        samples.append({
            "match_id": match_id,
            "minute": minute,
            "gold_adv": gold[minute],
            "xp_adv": xp[minute],
            "duration_min": duration / 60.0,
            "radiant_win": 1 if rwin else 0,
        })
    return samples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500, help="매치 수")
    ap.add_argument("--out", default="data/dota_matches.csv")
    ap.add_argument("--ids-cache", default="data/dota_match_ids.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]  # polymarket/
    out = root / args.out
    ids_cache = root / args.ids_cache
    out.parent.mkdir(parents=True, exist_ok=True)

    # 1) 매치 ID 수집 (캐시)
    if ids_cache.exists():
        ids = json.loads(ids_cache.read_text())
        if len(ids) >= args.n:
            ids = ids[:args.n]
            print(f"[fetch] {len(ids)}개 ID 캐시 재사용")
        else:
            print(f"[fetch] 캐시 {len(ids)}개 < 요청 {args.n}개 → 재수집")
            ids = fetch_pro_match_ids(args.n)
            ids_cache.write_text(json.dumps(ids))
    else:
        print(f"[fetch] 매치 ID {args.n}개 수집 중...")
        ids = fetch_pro_match_ids(args.n)
        ids_cache.write_text(json.dumps(ids))
    print(f"[fetch] ID {len(ids)}개 확보")

    # 2) 매치 상세 + 샘플 추출
    fieldnames = ["match_id", "minute", "gold_adv", "xp_adv", "duration_min", "radiant_win"]
    write_mode = "w"
    seen_ids = set()
    if out.exists():
        # 재개 지원 — 이미 있는 match_id는 스킵
        with out.open() as f:
            r = csv.DictReader(f)
            for row in r:
                seen_ids.add(int(row["match_id"]))
        write_mode = "a"
        print(f"[fetch] 재개: {len(seen_ids)}개 매치 이미 완료")

    todo = [i for i in ids if i not in seen_ids]
    print(f"[fetch] 남은 매치: {len(todo)}")

    total_samples = 0
    t0 = time.time()
    with out.open(write_mode, newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_mode == "w":
            w.writeheader()
        for i, mid in enumerate(todo, 1):
            detail = fetch_match_detail(mid)
            samples = extract_samples(detail)
            for s in samples:
                w.writerow(s)
            total_samples += len(samples)
            if i % 25 == 0 or i == len(todo):
                rate = i / max(time.time() - t0, 0.1)
                eta = (len(todo) - i) / max(rate, 0.001)
                print(f"[fetch] {i}/{len(todo)} 매치 | 샘플 {total_samples} | {rate:.1f}/s | ETA {eta/60:.1f}min")
            time.sleep(MIN_INTERVAL)

    print(f"[fetch] 완료. 총 샘플 {total_samples} → {out}")


if __name__ == "__main__":
    main()
