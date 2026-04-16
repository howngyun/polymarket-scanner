"""CI용 단일 스캔 사이클. GitHub Actions에서 실행됨.

결과를 docs/ 폴더에 저장 → GitHub Pages가 서빙.
Telegram 알림도 여기서 발송.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# 이 파일은 scanner/ 하위에 있음 — 부모 경로 기준으로 docs/ 찾기
ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)

# scanner/ 디렉토리를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

import config
from client import iter_active_markets
from detectors import (
    detect_near_resolution_bargain,
    detect_extreme_longshot,
    detect_high_liquidity_mover,
)

# CI에서는 임계값 강화 — 노이즈 제거
CI_BARGAIN_HOURS = 6          # 6시간 이내
CI_BARGAIN_PRICE = 0.97       # 97% 이상 확정
CI_BARGAIN_GAP = 0.015        # 1.5% 이상 갭
CI_MIN_LIQUIDITY = 3000       # 유동성 $3K 이상
CI_MIN_VOLUME = 10000         # 거래량 $10K 이상

# Telegram
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send_telegram(msg: str):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        print(f"[telegram] 전송 실패: {e}")


def run():
    ts = datetime.now(timezone.utc)
    ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")
    print(f"[run_once] 스캔 시작: {ts_str}")

    bargains = []
    movers = []
    longshots = []
    prev_prices: dict = {}

    # 이전 스냅샷 로드 (가격 변동 감지용)
    prev_file = DOCS_DIR / "prev_prices.json"
    if prev_file.exists():
        try:
            prev_prices = json.loads(prev_file.read_text())
        except Exception:
            pass

    n_markets = 0
    for m in iter_active_markets():
        n_markets += 1

        # near_resolution_bargain — CI 임계값 적용
        if m["liquidity"] >= CI_MIN_LIQUIDITY and m["volume"] >= CI_MIN_VOLUME:
            orig_hours = config.NEAR_RESOLUTION_HOURS
            orig_price = config.NEAR_CERTAIN_PRICE
            orig_gap = config.BARGAIN_GAP
            config.NEAR_RESOLUTION_HOURS = CI_BARGAIN_HOURS
            config.NEAR_CERTAIN_PRICE = CI_BARGAIN_PRICE
            config.BARGAIN_GAP = CI_BARGAIN_GAP
            a = detect_near_resolution_bargain(m)
            config.NEAR_RESOLUTION_HOURS = orig_hours
            config.NEAR_CERTAIN_PRICE = orig_price
            config.BARGAIN_GAP = orig_gap
            if a:
                bargains.append(a)

        # price mover
        a = detect_high_liquidity_mover(m, prev_prices.get(m["id"]))
        if a and m["liquidity"] >= CI_MIN_LIQUIDITY:
            movers.append(a)

        # longshot
        if m["volume"] >= CI_MIN_VOLUME:
            a = detect_extreme_longshot(m)
            if a:
                longshots.append(a)

        if m["prices"]:
            prev_prices[m["id"]] = m["prices"][0]

    # 정렬: edge 높은 순
    bargains.sort(key=lambda x: x.get("implied_edge", 0), reverse=True)
    movers.sort(key=lambda x: abs(x.get("move_pct", 0)), reverse=True)

    # 스냅샷 저장 (다음 사이클 비교용)
    prev_file.write_text(json.dumps(prev_prices))

    # 결과 JSON 저장
    result = {
        "scanned_at": ts_str,
        "n_markets": n_markets,
        "bargains": bargains[:50],
        "movers": movers[:30],
        "longshots": longshots[:50],
    }
    (DOCS_DIR / "latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))

    print(f"[run_once] 완료: 마켓 {n_markets}개, "
          f"bargain {len(bargains)}건, mover {len(movers)}건, longshot {len(longshots)}건")

    # Telegram 알림 — 상위 5건만
    if bargains:
        lines = [f"<b>Polymarket 기회 알림 ({ts_str})</b>"]
        for b in bargains[:5]:
            q = b["question"][:60]
            lines.append(
                f"[{b['implied_edge']}%] {q}\n"
                f"  top={b['top_price']:.3f} | close {b['hours_to_close']}h | "
                f"liq=${b['liquidity']:.0f}"
            )
        if len(bargains) > 5:
            lines.append(f"... 외 {len(bargains)-5}건")
        send_telegram("\n".join(lines))

    return result


if __name__ == "__main__":
    run()
