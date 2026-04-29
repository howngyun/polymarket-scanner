"""
report.py — terminal status report for the paper bot.

Run any time:
    python -m weatherbot.report

Shows:
  - bankroll, cash, open count, win rate
  - open positions (sorted by edge at entry)
  - last N closed trades (PnL)
  - recent bankroll snapshots
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from weatherbot.paper_ledger import (
    DEFAULT_DB_PATH,
    INITIAL_BANKROLL,
    available_cash,
    current_bankroll,
    stats,
)


def _fmt_pct(x: float) -> str:
    return f"{x*100:+.2f}%"


def _short_question(q: str, n: int = 60) -> str:
    return (q[: n - 1] + "…") if len(q) > n else q


def _open_table(db: Path) -> str:
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(
            conn.execute(
                "SELECT * FROM trades WHERE status='OPEN' "
                "ORDER BY net_edge_at_entry DESC"
            )
        )
    if not rows:
        return "  (none)"
    out: list[str] = []
    out.append(
        f"  {'#':>3}  {'CITY':<14}  {'SIDE':<4}  {'PRICE':>6}  "
        f"{'SIZE':>7}  {'p':>5}  {'EDGE':>7}  {'AGE':>6}  Q"
    )
    out.append("  " + "─" * 92)
    now = datetime.now(timezone.utc)
    for r in rows:
        opened = datetime.fromisoformat(r["ts_open_utc"])
        age_h = (now - opened).total_seconds() / 3600.0
        out.append(
            f"  {r['id']:>3}  {r['city'][:14]:<14}  {r['side']:<4}  "
            f"{r['entry_price']:>.3f}  ${r['size_usd']:>6.2f}  "
            f"{r['fair_p_at_entry']:>.3f}  {r['net_edge_at_entry']:+.3f}  "
            f"{age_h:>5.1f}h  {_short_question(r['question'])}"
        )
    return "\n".join(out)


def _closed_table(db: Path, limit: int = 10) -> str:
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(
            conn.execute(
                "SELECT * FROM trades WHERE status != 'OPEN' "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        )
    if not rows:
        return "  (none yet)"
    out: list[str] = []
    out.append(
        f"  {'#':>3}  {'CITY':<14}  {'SIDE':<4}  {'STATUS':<7}  "
        f"{'ENTRY':>6}  {'SETT':>6}  {'PnL':>8}  Q"
    )
    out.append("  " + "─" * 88)
    for r in rows:
        pnl = r["realized_pnl_usd"]
        pnl_s = f"${pnl:+7.2f}" if pnl is not None else "    n/a"
        sett = r["settle_price"]
        sett_s = f"{sett:.3f}" if sett is not None else "  n/a"
        out.append(
            f"  {r['id']:>3}  {r['city'][:14]:<14}  {r['side']:<4}  "
            f"{r['status']:<7}  {r['entry_price']:>.3f}  {sett_s:>6}  "
            f"{pnl_s}  {_short_question(r['question'])}"
        )
    return "\n".join(out)


def _bankroll_log(db: Path, limit: int = 6) -> str:
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(
            conn.execute(
                "SELECT * FROM bankroll_log ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        )
    if not rows:
        return "  (no snapshots yet)"
    out = []
    for r in reversed(rows):
        out.append(
            f"  {r['ts_utc']}  bankroll=${r['bankroll_usd']:>7.2f}  "
            f"cash=${r['available_cash_usd']:>7.2f}  open={r['open_count']:>2}  "
            f"{r['note'] or ''}"
        )
    return "\n".join(out)


def render(db: Path = DEFAULT_DB_PATH) -> str:
    if not db.exists():
        return f"No paper.db yet at {db}\nRun:  python -m weatherbot.runner"

    s = stats(db)
    bankroll = current_bankroll(db)
    cash = available_cash(db)
    locked = bankroll - cash
    pnl = bankroll - INITIAL_BANKROLL
    pnl_pct = pnl / INITIAL_BANKROLL

    sections: list[str] = []
    sections.append("═" * 80)
    sections.append(
        f"WEATHERBOT PAPER  ·  {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    )
    sections.append("═" * 80)
    sections.append(
        f"bankroll  ${bankroll:>7.2f}   cash  ${cash:>7.2f}   "
        f"locked  ${locked:>7.2f}"
    )
    sections.append(
        f"PnL       ${pnl:+7.2f} ({_fmt_pct(pnl_pct)})   "
        f"trades  {s['trades_total']} ({s['open']} open / {s['closed']} closed)   "
        f"win-rate  {_fmt_pct(s['win_rate'])}"
    )
    sections.append("")
    sections.append("OPEN POSITIONS (sorted by edge at entry)")
    sections.append(_open_table(db))
    sections.append("")
    sections.append("LAST 10 CLOSED TRADES")
    sections.append(_closed_table(db, limit=10))
    sections.append("")
    sections.append("RECENT BANKROLL SNAPSHOTS")
    sections.append(_bankroll_log(db, limit=8))
    sections.append("═" * 80)

    return "\n".join(sections)


if __name__ == "__main__":
    db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    print(render(db))
