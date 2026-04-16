"""Polymarket 기회 스캐너 — 루프 돌면서 알림만. 자동매매 아님."""
import csv
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import config
from client import iter_active_markets
from detectors import (
    detect_near_resolution_bargain,
    detect_high_liquidity_mover,
    detect_extreme_longshot,
)

HERE = Path(__file__).parent
os.chdir(HERE)
Path(config.LOG_DIR).mkdir(exist_ok=True)

# 이전 스냅샷 가격 (ID -> price) — 메모리 유지, 런타임 상태
_prev_prices: dict = {}

_shutdown = False


def _handle_sigint(signum, frame):
    global _shutdown
    _shutdown = True
    print("\n[scanner] 종료 요청 받음. 다음 사이클 후 정지.")


signal.signal(signal.SIGINT, _handle_sigint)
signal.signal(signal.SIGTERM, _handle_sigint)


def _append_csv(path: str, row: dict, fieldnames: list):
    exists = Path(path).exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        w.writerow(row)


def _log_snapshot(ts: str, m: dict):
    if not m["prices"]:
        return
    _append_csv(
        config.SNAPSHOT_FILE,
        {
            "ts": ts,
            "id": m["id"],
            "slug": m["slug"],
            "price_yes": m["prices"][0] if len(m["prices"]) > 0 else "",
            "price_no": m["prices"][1] if len(m["prices"]) > 1 else "",
            "liquidity": m["liquidity"],
            "volume": m["volume"],
        },
        ["ts", "id", "slug", "price_yes", "price_no", "liquidity", "volume"],
    )


def _log_alert(ts: str, alert: dict):
    row = {"ts": ts, **alert}
    fieldnames = [
        "ts", "type", "question", "slug",
        "top_price", "implied_edge", "hours_to_close",
        "prev_price", "current_price", "move_pct",
        "longshot_price", "favorite_price",
        "liquidity", "volume",
    ]
    # 누락 필드 빈값으로
    for k in fieldnames:
        row.setdefault(k, "")
    _append_csv(config.ALERTS_FILE, row, fieldnames)


def _print_alert(alert: dict):
    t = alert["type"]
    q = alert["question"][:70]
    if t == "near_resolution_bargain":
        print(f"  [BARGAIN {alert['implied_edge']}%] {q} | "
              f"top={alert['top_price']:.3f} | close {alert['hours_to_close']}h | "
              f"liq=${alert['liquidity']:.0f}")
    elif t == "price_mover":
        print(f"  [MOVER {alert['move_pct']:+.1f}%] {q} | "
              f"{alert['prev_price']:.3f} -> {alert['current_price']:.3f} | "
              f"liq=${alert['liquidity']:.0f}")
    elif t == "longshot":
        print(f"  [LONGSHOT {alert['longshot_price']:.2f}] {q} | "
              f"close {alert['hours_to_close']}h | vol=${alert['volume']:.0f}")


def scan_cycle():
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"\n[{ts}] 스캔 시작")
    n_markets = 0
    n_alerts = 0
    for m in iter_active_markets():
        n_markets += 1
        _log_snapshot(ts, m)

        alerts = []
        a = detect_near_resolution_bargain(m)
        if a:
            alerts.append(a)
        prev = _prev_prices.get(m["id"])
        a = detect_high_liquidity_mover(m, prev)
        if a:
            alerts.append(a)
        a = detect_extreme_longshot(m)
        if a:
            alerts.append(a)

        if m["prices"]:
            _prev_prices[m["id"]] = m["prices"][0]

        for alert in alerts:
            n_alerts += 1
            _print_alert(alert)
            _log_alert(ts, alert)

    print(f"[{ts}] 완료: 마켓 {n_markets}개 스캔, 알림 {n_alerts}건")


def main():
    print("=" * 60)
    print("Polymarket 기회 스캐너")
    print(f"주기: {config.SCAN_INTERVAL_SECONDS}초")
    print(f"로그: {Path(config.ALERTS_FILE).resolve()}")
    print("Ctrl+C 로 종료")
    print("=" * 60)

    while not _shutdown:
        try:
            scan_cycle()
        except Exception as e:
            print(f"[scanner] 사이클 에러: {e}")
        if _shutdown:
            break
        # interruptible sleep
        for _ in range(config.SCAN_INTERVAL_SECONDS):
            if _shutdown:
                break
            time.sleep(1)

    print("[scanner] 정상 종료.")


if __name__ == "__main__":
    main()
