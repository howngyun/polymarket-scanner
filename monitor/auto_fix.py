"""알려진 문제 자동 수정 — 무조건 안전한 것만.

Claude 호출 없이 Python 룰로 처리. 복잡한 판단은 Claude review에 위임.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"


def _load(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def fix_corrupted_state() -> list:
    """state 파일 손상 시 복구."""
    fixes = []
    state_file = DOCS / "trader_state.json"
    if state_file.exists():
        content = state_file.read_text().strip()
        if not content or not content.startswith("{"):
            state_file.unlink()
            fixes.append("손상된 trader_state.json 삭제 (다음 실행 시 재생성)")
    return fixes


def fix_old_open_positions() -> list:
    """결제 시각 지난 지 24시간+ 된 미결제 포지션 강제 close.

    원인: 결제 사이클에서 놓쳤거나 symbol 파싱 실패.
    자동 결제 불가 시 무승부(0 PnL)로 처리.
    """
    fixes = []
    ledger_file = DOCS / "trades" / "paper_ledger.json"
    ledger = _load(ledger_file)
    if not ledger:
        return fixes

    now = datetime.now(timezone.utc)
    cleaned = 0
    for t in ledger:
        if t.get("status") != "filled" or t.get("resolved"):
            continue
        end_str = t.get("end_date", "")
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        except Exception:
            continue
        if now - end_dt > timedelta(hours=24):
            # 오래된 미결제 포지션 → 무승부 처리
            t["resolved"] = True
            t["won"] = None
            t["pnl"] = 0.0
            t["settled_at"] = now.isoformat()
            t["settlement_note"] = "auto_fix: 24시간+ 미결제 → 무승부 강제 처리"
            cleaned += 1
    if cleaned:
        _save(ledger_file, ledger)
        fixes.append(f"오래된 미결제 포지션 {cleaned}건 강제 정리")
    return fixes


def reset_kill_switch_if_dormant() -> list:
    """
    안전한 자동 재개는 안 함. 킬스위치는 항상 수동 해제 (안전 우선).
    """
    return []


def run_all() -> list:
    """모든 자동 수정 실행 → 수정된 항목 목록."""
    all_fixes = []
    for fn in [fix_corrupted_state, fix_old_open_positions, reset_kill_switch_if_dormant]:
        try:
            all_fixes.extend(fn())
        except Exception as e:
            all_fixes.append(f"auto_fix 에러 {fn.__name__}: {e}")
    return all_fixes
