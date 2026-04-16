"""리스크 게이트 — 주문 전 모든 체크.

한도 위반 시 거래 차단 + 킬스위치 발동.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from . import config


def load_state() -> dict:
    """트레이더 상태 로드."""
    if not config.STATE_FILE.exists():
        return {
            "starting_capital": config.STARTING_CAPITAL,
            "current_capital": config.STARTING_CAPITAL,
            "daily_pnl": 0.0,
            "daily_start_date": datetime.now(timezone.utc).date().isoformat(),
            "total_trades": 0,
            "kill_switch": False,
            "kill_reason": None,
            "recent_trades": [],  # 시간당 거래 수 체크용
        }
    try:
        return json.loads(config.STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: dict):
    config.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def reset_daily_if_needed(state: dict) -> dict:
    """일자 바뀌면 daily_pnl 초기화."""
    today = datetime.now(timezone.utc).date().isoformat()
    if state.get("daily_start_date") != today:
        state["daily_pnl"] = 0.0
        state["daily_start_date"] = today
    return state


def count_recent_trades(state: dict, hours: int = 1) -> int:
    """최근 N시간 내 거래 수."""
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(hours=hours)
    recent = []
    for t in state.get("recent_trades", []):
        try:
            t_time = datetime.fromisoformat(t.replace("Z", "+00:00"))
            if t_time >= threshold:
                recent.append(t)
        except Exception:
            pass
    state["recent_trades"] = recent  # 클린업
    return len(recent)


def check(signal: dict, open_positions: list) -> tuple:
    """(ok: bool, reason: str, bet_usd: float) 반환.

    ok=False면 reason에 이유.
    ok=True면 bet_usd에 최종 권장 베팅 금액.
    """
    state = load_state()
    state = reset_daily_if_needed(state)

    # 킬스위치 체크
    if state.get("kill_switch"):
        return (False, f"kill_switch: {state.get('kill_reason')}", 0.0)

    # 드로다운 체크
    current = state.get("current_capital", config.STARTING_CAPITAL)
    starting = state.get("starting_capital", config.STARTING_CAPITAL)
    drawdown = (starting - current) / starting if starting > 0 else 0
    if drawdown >= config.DRAWDOWN_LIMIT_PCT:
        state["kill_switch"] = True
        state["kill_reason"] = f"drawdown {drawdown*100:.1f}% 도달"
        save_state(state)
        return (False, state["kill_reason"], 0.0)

    # 일일 손실 한도
    daily_pnl = state.get("daily_pnl", 0.0)
    if daily_pnl <= -config.DAILY_LOSS_LIMIT_USD:
        return (False, f"일일 손실 한도: ${-daily_pnl:.2f}", 0.0)

    # 동시 포지션 수
    if len(open_positions) >= config.MAX_CONCURRENT_POSITIONS:
        return (False, f"포지션 한도 {config.MAX_CONCURRENT_POSITIONS}개 초과", 0.0)

    # 시간당 거래 수
    recent = count_recent_trades(state, hours=1)
    if recent >= config.MAX_TRADES_PER_HOUR:
        return (False, f"시간당 거래 한도 {config.MAX_TRADES_PER_HOUR} 초과", 0.0)

    # 베팅 사이즈 계산
    kelly_pct = signal.get("kelly_fraction", 0)
    bet_usd = current * kelly_pct
    bet_usd = max(config.MIN_BET_USD, min(bet_usd, config.MAX_BET_USD))
    bet_usd = min(bet_usd, current * 0.3)  # 절대 자본 30% 초과 금지

    if bet_usd < config.MIN_BET_USD:
        return (False, f"베팅 사이즈 ${bet_usd:.2f} < 최소 ${config.MIN_BET_USD}", 0.0)

    return (True, "ok", bet_usd)


def record_trade(trade: dict):
    """거래 발생 시 state 업데이트."""
    state = load_state()
    state = reset_daily_if_needed(state)

    pnl = trade.get("pnl", 0.0)
    state["daily_pnl"] = state.get("daily_pnl", 0.0) + pnl
    state["current_capital"] = state.get("current_capital", config.STARTING_CAPITAL) + pnl
    state["total_trades"] = state.get("total_trades", 0) + 1

    recent = state.get("recent_trades", [])
    recent.append(datetime.now(timezone.utc).isoformat())
    state["recent_trades"] = recent[-100:]  # 최근 100건만 유지

    save_state(state)
