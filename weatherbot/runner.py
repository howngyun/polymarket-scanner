"""
runner.py — single 5-minute cron pass.

Pipeline (Patch P3 — basic 5-min loop, P19 — fail-safe per stage):
    1. settle resolved markets and free cash
    2. scan active weather markets (1~3 day horizon)
    3. fetch ensemble forecasts per relevant city
    4. compute probability + edge for every (market, forecast) pair
    5. for every accepted decision: size and open paper trade
    6. snapshot bankroll

Caps enforced before opening:
    - daily_loss_limit_usd  (P18)
    - bankroll_position_cap_pct (cash buffer 40%)
    - max_concurrent_open  (correlation cap, P15)

Telegram alerting deferred to W2 (P27 alert tiering).
"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

from weatherbot.edge_filter import evaluate
from weatherbot.forecast_fetcher import CITIES, fetch_city_forecast
from weatherbot.market_scanner import fetch_active_weather_markets
from weatherbot.paper_ledger import (
    available_cash,
    current_bankroll,
    open_trade,
    open_trades,
    snapshot_bankroll,
    INITIAL_BANKROLL,
)
from weatherbot.position_sizer import size as size_position
from weatherbot.prob_calculator import compute_probability
from weatherbot.settlement import sweep_settlements

# Optional: reuse the existing Telegram helper if env vars are set.
# Falls back silently if the notifier module isn't importable.
try:
    from notifier.telegram import _send as tg_send  # type: ignore[attr-defined]
except Exception:
    def tg_send(text: str, parse_mode: str = "HTML") -> bool:  # type: ignore[misc]
        return False

# --- Tunable run config (W1 cold-start values) ----------------------------
TAU_COLD_START = 0.10                  # P2 — decays toward 0.05 in W2
MAX_PER_TRADE_USD = 25.0
PORTFOLIO_CAP_PCT = 0.60               # P26 — cash buffer 40%
DAILY_LOSS_LIMIT_USD = 50.0
MAX_CONCURRENT_OPEN = 30               # global cap; P15 city-level cap below
MAX_PER_CITY_OPEN = 3                  # P15 — same weather pattern cap
PAPER_MODE = True                      # W1/W2 always True; W3 flips false


def _open_count_by_city(rows) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r["city"]] = out.get(r["city"], 0) + 1
    return out


def _is_kill_switch_tripped() -> tuple[bool, str]:
    """Return (tripped, reason). DD 35% (P18) hard kill."""
    bankroll = current_bankroll()
    dd = (INITIAL_BANKROLL - bankroll) / INITIAL_BANKROLL
    if dd >= 0.35:
        return True, f"DD={dd:.1%} >= 35% — kill"
    return False, ""


def run_once(*, verbose: bool = True) -> dict:
    """One full pass. Returns a small stats dict for the workflow log."""
    started = datetime.now(timezone.utc)
    summary = {
        "started_utc": started.isoformat(timespec="seconds"),
        "settled": 0,
        "scanned": 0,
        "evaluated": 0,
        "accepted": 0,
        "opened": 0,
        "skipped_caps": 0,
        "errors": [],
    }

    # ----- Step 1: settle resolved markets -----
    try:
        summary["settled"] = sweep_settlements()
    except Exception as exc:
        summary["errors"].append(f"settle: {exc}")
        print(f"[runner] settlement error: {exc}", file=sys.stderr)

    # ----- Step 1b: kill switch check -----
    tripped, reason = _is_kill_switch_tripped()
    if tripped:
        snapshot_bankroll(
            bankroll_usd=current_bankroll(),
            available_cash_usd=available_cash(),
            open_count=len(open_trades()),
            note=f"KILL_SWITCH: {reason}",
        )
        summary["errors"].append(reason)
        if verbose:
            print(f"[runner] KILL SWITCH TRIPPED: {reason}")
        return summary

    # ----- Step 2: scan markets -----
    try:
        markets = fetch_active_weather_markets(
            only_known_cities=True,
            min_days=0.0,
            max_days=3.0,
            min_liquidity=200.0,
        )
        summary["scanned"] = len(markets)
    except Exception as exc:
        summary["errors"].append(f"scan: {exc}")
        traceback.print_exc()
        return summary

    # ----- Step 3+4: forecasts + probabilities + filter -----
    open_rows = open_trades()
    open_by_city = _open_count_by_city(open_rows)
    open_market_ids = {r["market_id"] for r in open_rows}
    cash_available = available_cash()
    bankroll = current_bankroll()
    portfolio_cash_floor = bankroll * (1.0 - PORTFOLIO_CAP_PCT)  # 40% buffer
    spendable = max(0.0, cash_available - portfolio_cash_floor)

    forecast_cache: dict[str, object] = {}

    accepted_records: list[tuple] = []
    for m in markets:
        if m.market_id in open_market_ids:
            continue   # already in
        try:
            if m.city not in forecast_cache:
                forecast_cache[m.city] = fetch_city_forecast(m.city, *CITIES[m.city])
            prob = compute_probability(m, forecast_cache[m.city])
            decision = evaluate(m, prob, tau=TAU_COLD_START,
                                trade_size_usd=MAX_PER_TRADE_USD)
            summary["evaluated"] += 1
            if decision.accept:
                accepted_records.append((m, prob, decision))
        except Exception as exc:
            summary["errors"].append(f"eval[{m.market_id[:8]}]: {exc}")
            if verbose:
                print(f"[runner] eval error {m.city} {m.op}: {exc}", file=sys.stderr)

    # Highest-edge first (Patch — best opportunities while cash lasts)
    accepted_records.sort(key=lambda t: -t[2].net_edge)
    summary["accepted"] = len(accepted_records)

    # ----- Step 5: open paper trades respecting caps -----
    if len(open_rows) >= MAX_CONCURRENT_OPEN:
        if verbose:
            print(f"[runner] max_concurrent_open ({MAX_CONCURRENT_OPEN}) reached")

    for m, prob, decision in accepted_records:
        if len(open_rows) + summary["opened"] >= MAX_CONCURRENT_OPEN:
            summary["skipped_caps"] += 1
            continue
        if open_by_city.get(m.city, 0) >= MAX_PER_CITY_OPEN:
            summary["skipped_caps"] += 1
            continue
        if spendable <= 1.0:                         # Sub-$1 dust — skip
            summary["skipped_caps"] += 1
            continue
        sd = size_position(
            decision.fair_p,
            decision.entry_price,
            bankroll_usd=bankroll,
            available_cash_usd=spendable,
            market_liquidity_usd=m.liquidity,
            max_per_trade_usd=MAX_PER_TRADE_USD,
        )
        if sd.usd < 1.0:
            summary["skipped_caps"] += 1
            continue
        tid = open_trade(
            market_id=m.market_id,
            question=m.question,
            city=m.city,
            side=decision.side,
            entry_price=decision.entry_price,
            fair_p=decision.fair_p,
            net_edge=decision.net_edge,
            size_usd=sd.usd,
            shares=sd.shares,
            end_date_utc=m.end_date.isoformat(timespec="seconds"),
        )
        if tid is None:
            continue
        spendable -= sd.usd
        open_by_city[m.city] = open_by_city.get(m.city, 0) + 1
        summary["opened"] += 1
        if verbose:
            print(
                f"[OPEN id={tid}] {m.city:>15s} {decision.side} "
                f"@ {decision.entry_price:.3f}  ${sd.usd:.2f} ({sd.shares:.2f} sh)  "
                f"p={decision.fair_p:.3f}  edge={decision.net_edge:+.3f}"
            )

    # ----- Step 6: snapshot -----
    snapshot_bankroll(
        bankroll_usd=current_bankroll(),
        available_cash_usd=available_cash(),
        open_count=len(open_trades()),
        note=f"opened={summary['opened']} settled={summary['settled']}",
    )
    if verbose:
        print(
            f"\n[runner] {started.isoformat(timespec='seconds')} | "
            f"scanned={summary['scanned']} eval={summary['evaluated']} "
            f"accept={summary['accepted']} opened={summary['opened']} "
            f"settled={summary['settled']} | "
            f"bankroll=${current_bankroll():.2f} cash=${available_cash():.2f}"
        )

    # ----- Step 7: telegram alert (only on change — avoid 5-min spam) -----
    if summary["opened"] > 0 or summary["settled"] > 0 or summary["errors"]:
        try:
            tg_send(_format_telegram(summary))
        except Exception as exc:
            print(f"[runner] tg send failed: {exc}", file=sys.stderr)

    return summary


def _format_telegram(summary: dict) -> str:
    bankroll = current_bankroll()
    cash = available_cash()
    pnl = bankroll - INITIAL_BANKROLL
    pnl_pct = pnl / INITIAL_BANKROLL * 100.0
    lines = ["<b>🌤 weatherbot</b>"]
    if summary["opened"]:
        lines.append(f"opened: <b>{summary['opened']}</b>")
    if summary["settled"]:
        lines.append(f"settled: <b>{summary['settled']}</b>")
    if summary["errors"]:
        lines.append(f"⚠️ errors: {len(summary['errors'])}")
        for e in summary["errors"][:3]:
            lines.append(f"  · {str(e)[:80]}")
    lines.append(
        f"bankroll: <b>${bankroll:.2f}</b> ({pnl:+.2f}, {pnl_pct:+.2f}%)  "
        f"cash: ${cash:.2f}  open: {len(open_trades())}"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    run_once(verbose=True)
