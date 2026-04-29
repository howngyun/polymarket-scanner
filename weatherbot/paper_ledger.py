"""
paper_ledger.py — SQLite-backed paper trade ledger.

Two tables:
  - trades       open + closed paper positions (one row per entry)
  - bankroll     append-only snapshots so we can recover the run history

Why SQLite (not Supabase) for W1:
- Zero deps, runs on any GH Actions runner
- File commits to repo so history is durable across cron invocations
- W2 may swap to Supabase if multi-runner concurrency becomes an issue
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "paper.db"
INITIAL_BANKROLL = 500.0


@dataclass
class TradeRow:
    id: int
    ts_open_utc: str
    market_id: str
    question: str
    city: str
    side: str                # 'YES' or 'NO'
    entry_price: float
    fair_p_at_entry: float
    net_edge_at_entry: float
    size_usd: float
    shares: float
    end_date_utc: str        # market resolution time
    status: str              # 'OPEN' | 'WON' | 'LOST' | 'EXPIRED_VOID'
    settle_price: Optional[float]
    realized_pnl_usd: Optional[float]
    notes: str


SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_open_utc TEXT NOT NULL,
    market_id TEXT NOT NULL,
    question TEXT NOT NULL,
    city TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    fair_p_at_entry REAL NOT NULL,
    net_edge_at_entry REAL NOT NULL,
    size_usd REAL NOT NULL,
    shares REAL NOT NULL,
    end_date_utc TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    settle_price REAL,
    realized_pnl_usd REAL,
    notes TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS trades_unique_open
    ON trades(market_id, side) WHERE status='OPEN';

CREATE TABLE IF NOT EXISTS bankroll_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc TEXT NOT NULL,
    bankroll_usd REAL NOT NULL,
    available_cash_usd REAL NOT NULL,
    open_count INTEGER NOT NULL,
    note TEXT DEFAULT ''
);
"""


@contextmanager
def _conn(db_path: Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_trade(
    *,
    market_id: str,
    question: str,
    city: str,
    side: str,
    entry_price: float,
    fair_p: float,
    net_edge: float,
    size_usd: float,
    shares: float,
    end_date_utc: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> Optional[int]:
    """Insert a new OPEN trade. Returns the row id, or None if duplicate."""
    with _conn(db_path) as c:
        try:
            cur = c.execute(
                """
                INSERT INTO trades(ts_open_utc, market_id, question, city, side,
                    entry_price, fair_p_at_entry, net_edge_at_entry,
                    size_usd, shares, end_date_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (_now(), market_id, question, city, side,
                 entry_price, fair_p, net_edge, size_usd, shares, end_date_utc),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            # Already have an open position on the same (market, side)
            return None


def open_trades(db_path: Path = DEFAULT_DB_PATH) -> list[sqlite3.Row]:
    with _conn(db_path) as c:
        return list(c.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY id"))


def settle_trade(
    trade_id: int,
    *,
    settle_price: float,
    db_path: Path = DEFAULT_DB_PATH,
    notes: str = "",
) -> None:
    """Record final settlement. settle_price is 1.0 for win on YES side, 0.0 for loss
    (or any fractional if void). PnL = (settle - entry) * shares."""
    with _conn(db_path) as c:
        row = c.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
        if row is None or row["status"] != "OPEN":
            return
        pnl = (settle_price - row["entry_price"]) * row["shares"]
        if settle_price >= 0.99:
            status = "WON"
        elif settle_price <= 0.01:
            status = "LOST"
        else:
            status = "EXPIRED_VOID"
        c.execute(
            """
            UPDATE trades SET status=?, settle_price=?, realized_pnl_usd=?, notes=?
            WHERE id=?
            """,
            (status, settle_price, pnl, notes, trade_id),
        )


def snapshot_bankroll(
    *,
    bankroll_usd: float,
    available_cash_usd: float,
    open_count: int,
    note: str = "",
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    with _conn(db_path) as c:
        c.execute(
            """
            INSERT INTO bankroll_log(ts_utc, bankroll_usd, available_cash_usd, open_count, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (_now(), bankroll_usd, available_cash_usd, open_count, note),
        )


def current_bankroll(db_path: Path = DEFAULT_DB_PATH) -> float:
    """Compute live bankroll from initial + realized PnL of closed trades + MTM
    of open trades at their entry price (i.e. notionally locked but not yet realized).
    For paper accounting we treat OPEN positions' size as locked cash, not PnL."""
    with _conn(db_path) as c:
        row = c.execute(
            "SELECT COALESCE(SUM(realized_pnl_usd), 0.0) AS realized "
            "FROM trades WHERE status != 'OPEN'"
        ).fetchone()
        realized = float(row["realized"] or 0.0)
        return INITIAL_BANKROLL + realized


def available_cash(db_path: Path = DEFAULT_DB_PATH) -> float:
    """Bankroll minus the cash currently locked in OPEN positions."""
    with _conn(db_path) as c:
        row = c.execute(
            "SELECT COALESCE(SUM(size_usd), 0.0) AS locked "
            "FROM trades WHERE status='OPEN'"
        ).fetchone()
        locked = float(row["locked"] or 0.0)
        return current_bankroll(db_path) - locked


def stats(db_path: Path = DEFAULT_DB_PATH) -> dict:
    with _conn(db_path) as c:
        rows = list(c.execute("SELECT * FROM trades"))
    open_n = sum(1 for r in rows if r["status"] == "OPEN")
    closed = [r for r in rows if r["status"] != "OPEN"]
    won = sum(1 for r in closed if r["status"] == "WON")
    realized = sum((r["realized_pnl_usd"] or 0.0) for r in closed)
    return {
        "trades_total": len(rows),
        "open": open_n,
        "closed": len(closed),
        "won": won,
        "win_rate": (won / len(closed)) if closed else 0.0,
        "realized_pnl_usd": realized,
        "bankroll_usd": INITIAL_BANKROLL + realized,
    }


if __name__ == "__main__":
    import os
    test_db = Path("/tmp/weatherbot_paper_test.db")
    if test_db.exists():
        test_db.unlink()
    tid = open_trade(
        market_id="0xabc", question="test", city="NYC", side="YES",
        entry_price=0.30, fair_p=0.45, net_edge=0.10, size_usd=15.0, shares=50.0,
        end_date_utc="2026-04-30T12:00:00+00:00", db_path=test_db,
    )
    print(f"opened trade id={tid}")
    print(f"available cash = ${available_cash(test_db):.2f}")
    settle_trade(tid, settle_price=1.0, db_path=test_db, notes="WON paper")
    print(f"after settle, stats = {json.dumps(stats(test_db), indent=2)}")
    print(f"bankroll = ${current_bankroll(test_db):.2f}")
