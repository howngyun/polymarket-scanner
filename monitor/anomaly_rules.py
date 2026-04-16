"""이상 감지 룰 — 순수 Python, 토큰 0.

각 룰은 (triggered: bool, severity: str, title: str, detail: str) 반환.
severity: "info" / "warn" / "critical"
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _load_list(path: Path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _parse_ts(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def check_trader_alive() -> tuple:
    """마지막 트레이더 실행이 2시간 이상 지났으면 warn."""
    last_run = _load_json(DOCS / "trader_last_run.json")
    ts = _parse_ts(last_run.get("timestamp", ""))
    if ts is None:
        return (True, "warn", "트레이더 미실행", "trader_last_run.json 없음")
    age = (datetime.now(timezone.utc) - ts).total_seconds() / 60
    if age > 120:
        return (True, "critical", "트레이더 정지",
                f"마지막 실행 {age:.0f}분 전. Actions 확인 필요.")
    if age > 30:
        return (True, "warn", "트레이더 지연",
                f"마지막 실행 {age:.0f}분 전. cron 주기 5분인데 지연됨.")
    return (False, "info", "", "")


def check_drawdown() -> tuple:
    """드로다운 20% 이상이면 warn, 30% 이상 critical."""
    state = _load_json(DOCS / "trader_state.json")
    starting = state.get("starting_capital")
    current = state.get("current_capital")
    if starting is None or current is None:
        return (False, "info", "", "")
    if starting <= 0:
        return (False, "info", "", "")
    dd = (starting - current) / starting
    if dd >= 0.30:
        return (True, "critical", "드로다운 30%+",
                f"시작 ${starting:.2f} → 현재 ${current:.2f} (-{dd*100:.1f}%)")
    if dd >= 0.20:
        return (True, "warn", "드로다운 20%+",
                f"시작 ${starting:.2f} → 현재 ${current:.2f} (-{dd*100:.1f}%)")
    return (False, "info", "", "")


def check_kill_switch() -> tuple:
    state = _load_json(DOCS / "trader_state.json")
    if state.get("kill_switch"):
        return (True, "critical", "킬스위치 발동",
                f"이유: {state.get('kill_reason', 'unknown')}. 수동 재개 필요.")
    return (False, "info", "", "")


def check_win_rate_drop() -> tuple:
    """최근 20건 승률이 40% 미만이면 경고."""
    ledger = _load_list(DOCS / "trades" / "paper_ledger.json")
    resolved = [t for t in ledger if t.get("resolved")]
    if len(resolved) < 20:
        return (False, "info", "", "")
    recent = resolved[-20:]
    wins = sum(1 for t in recent if t.get("won"))
    wr = wins / len(recent)
    if wr < 0.40:
        return (True, "warn", "최근 승률 저조",
                f"최근 20건 승률 {wr*100:.0f}% (기준 40% 미만). 모델 드리프트 의심.")
    return (False, "info", "", "")


def check_consecutive_losses() -> tuple:
    """5연속 패배 이상이면 warn."""
    ledger = _load_list(DOCS / "trades" / "paper_ledger.json")
    resolved = [t for t in ledger if t.get("resolved")]
    if len(resolved) < 5:
        return (False, "info", "", "")
    streak = 0
    for t in reversed(resolved):
        if not t.get("won"):
            streak += 1
        else:
            break
    if streak >= 5:
        return (True, "warn", f"{streak}연속 패배",
                "변동성 증가 또는 모델 문제 가능성. 내일까지 지속되면 점검.")
    return (False, "info", "", "")


def check_fill_rate() -> tuple:
    """최근 30건 체결률 < 50%이면 warn (시그널 놓침 많음)."""
    ledger = _load_list(DOCS / "trades" / "paper_ledger.json")
    recent = ledger[-30:]
    if len(recent) < 10:
        return (False, "info", "", "")
    filled = sum(1 for t in recent if t.get("status") == "filled")
    rate = filled / len(recent)
    if rate < 0.50:
        return (True, "warn", "체결률 저조",
                f"최근 30건 중 {rate*100:.0f}%만 체결. 기회 놓침.")
    return (False, "info", "", "")


def check_no_signals() -> tuple:
    """최근 실행에서 시그널 0건 연속이면 모델 문제."""
    last_run = _load_json(DOCS / "trader_last_run.json")
    if last_run.get("signals_found", -1) == 0:
        # 1회는 괜찮음. 여러 번 연속인지는 history 필요.
        # 여기선 힌트만.
        return (False, "info", "", "")
    return (False, "info", "", "")


ALL_RULES = [
    check_trader_alive,
    check_drawdown,
    check_kill_switch,
    check_win_rate_drop,
    check_consecutive_losses,
    check_fill_rate,
    check_no_signals,
]


def run_all() -> list:
    """모든 룰 실행 → triggered된 것만 반환."""
    results = []
    for rule in ALL_RULES:
        try:
            triggered, severity, title, detail = rule()
            if triggered:
                results.append({
                    "rule": rule.__name__,
                    "severity": severity,
                    "title": title,
                    "detail": detail,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as e:
            results.append({
                "rule": rule.__name__,
                "severity": "warn",
                "title": "룰 실행 에러",
                "detail": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    return results
