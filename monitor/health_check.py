"""헬스체크 진입점 — GitHub Actions에서 1시간마다 실행.

Flow:
  1. 자동 수정 룰 실행 (손상 파일 복구 등)
  2. 이상 감지 룰 실행
  3. critical이면 Telegram 즉시 경고
  4. docs/health.json + docs/anomalies.log 업데이트
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from monitor import anomaly_rules, auto_fix


def main():
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[health_check] {ts} 시작")

    # 1. auto_fix
    fixes = auto_fix.run_all()
    if fixes:
        print(f"[health_check] 자동 수정 {len(fixes)}건")
        for f in fixes:
            print(f"  - {f}")

    # 2. anomaly 감지
    anomalies = anomaly_rules.run_all()
    critical = [a for a in anomalies if a["severity"] == "critical"]
    warnings = [a for a in anomalies if a["severity"] == "warn"]

    print(f"[health_check] anomalies: critical={len(critical)} warn={len(warnings)}")

    # 3. Telegram 경고 (critical만)
    for a in critical:
        try:
            from notifier import telegram
            telegram.notify_anomaly(a["title"], a["detail"])
        except Exception as e:
            print(f"[health_check] telegram 실패: {e}")

    # 4. 결과 저장
    health_file = ROOT / "docs" / "health.json"
    health_file.parent.mkdir(parents=True, exist_ok=True)
    status = "critical" if critical else ("warn" if warnings else "ok")
    health_file.write_text(json.dumps({
        "checked_at": ts,
        "status": status,
        "auto_fixes": fixes,
        "anomalies": anomalies,
    }, indent=2, default=str))

    # 5. 로그 파일 append
    log_file = ROOT / "docs" / "anomalies.log"
    if anomalies:
        with log_file.open("a", encoding="utf-8") as f:
            for a in anomalies:
                f.write(f"{a['timestamp']} [{a['severity'].upper()}] {a['title']}: {a['detail']}\n")


if __name__ == "__main__":
    main()
