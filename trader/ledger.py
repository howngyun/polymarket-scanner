"""거래 이력 분석 + 통계."""
import json
from pathlib import Path

from . import config


def load_ledger(live: bool = False) -> list:
    path = config.LIVE_LEDGER if live else config.PAPER_LEDGER
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def summary(live: bool = False) -> dict:
    """누적 통계."""
    trades = load_ledger(live)
    total = len(trades)
    filled = [t for t in trades if t.get("status") == "filled"]
    resolved = [t for t in filled if t.get("resolved")]

    if not resolved:
        return {
            "total_signals": total,
            "total_filled": len(filled),
            "total_resolved": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
            "avg_edge_at_entry": 0.0,
            "sharpe_estimate": None,
        }

    wins = [t for t in resolved if t.get("won")]
    total_pnl = sum(t.get("pnl", 0) for t in resolved)
    win_rate = len(wins) / len(resolved) if resolved else 0

    edges = [t.get("edge_pct_at_entry", 0) for t in resolved]
    avg_edge = sum(edges) / len(edges) if edges else 0

    # 간단한 샤프 추정: mean_pnl / std_pnl * sqrt(n)
    pnls = [t.get("pnl", 0) for t in resolved]
    if len(pnls) > 5:
        mean_p = sum(pnls) / len(pnls)
        var = sum((p - mean_p) ** 2 for p in pnls) / (len(pnls) - 1)
        std = var ** 0.5 if var > 0 else 0
        sharpe = (mean_p / std * (len(pnls) ** 0.5)) if std > 0 else None
    else:
        sharpe = None

    return {
        "total_signals": total,
        "total_filled": len(filled),
        "total_resolved": len(resolved),
        "total_pnl": round(total_pnl, 2),
        "wins": len(wins),
        "losses": len(resolved) - len(wins),
        "win_rate": round(win_rate * 100, 1),
        "avg_edge_at_entry": round(avg_edge * 100, 2),
        "sharpe_estimate": round(sharpe, 2) if sharpe else None,
    }
