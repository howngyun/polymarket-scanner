"""멀티 전략 트레이더 엔트리포인트.

2026-04-18 신규. 기존 btc_trader.py (BTC 2분 전략) 대체.

흐름:
  1. 기존 페이퍼 포지션 결제 처리
  2. 모든 활성 전략 순회 → 시그널 수집
  3. 각 시그널 리스크 게이트 + 슬리피지 체크 → 주문
  4. 대시보드용 실행 기록 저장
  5. Telegram 알림 (체결 시)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from trader import config, executor, ledger, risk_gate
from strategies import high_prob_no, cross_market_arb


STRATEGIES = {
    "high_prob_no": (high_prob_no, config.STRATEGY_HIGH_PROB_NO),
    "cross_market_arb": (cross_market_arb, config.STRATEGY_CROSS_MARKET),
}


def get_open_positions() -> list:
    all_trades = ledger.load_ledger(live=False)
    return [t for t in all_trades if t.get("status") == "filled" and not t.get("resolved")]


def _settle_positions() -> int:
    """마감된 페이퍼 포지션 결제.

    단순화: endDate 지나면 현재 시장가 근사로 결제.
    실전에선 UMA 오라클 결과 조회 필요.
    """
    # 멀티 전략은 카테고리가 다양해서 자산 가격 기반 단순 결제 불가.
    # 대신 엔드데이트 지난 포지션을 "해당 마켓의 마지막 가격"으로 결제.
    # TODO: UMA 오라클 연동 (실전 전환 시)
    from datetime import datetime, timezone
    import requests

    trades = ledger.load_ledger(live=False)
    if not trades:
        return 0

    now = datetime.now(timezone.utc)
    settled = 0

    for trade in trades:
        if trade.get("resolved"):
            continue
        if trade.get("status") != "filled":
            continue
        end_str = trade.get("end_date") or trade.get("endDate", "")
        if not end_str:
            continue
        try:
            end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        except Exception:
            continue
        if now < end_date:
            continue

        # 마감 후 5분 대기 (오라클 레이턴시 시뮬)
        if (now - end_date).total_seconds() < 300:
            continue

        # 마켓 현재가 조회 → 해당 가격을 resolution으로 간주
        slug = trade.get("slug", "")
        if not slug:
            trade["resolved"] = True
            trade["pnl"] = -trade.get("bet_usd", 0)
            trade["won"] = False
            trade["settled_at"] = now.isoformat()
            settled += 1
            continue

        try:
            r = requests.get(
                f"{config.POLYMARKET_GAMMA_URL}",
                params={"slug": slug},
                timeout=10,
            )
            data = r.json()
        except Exception:
            continue

        if not data or not isinstance(data, list):
            continue

        market = data[0]
        prices = []
        raw_prices = market.get("outcomePrices")
        if isinstance(raw_prices, str):
            try:
                prices = [float(x) for x in json.loads(raw_prices)]
            except Exception:
                prices = []
        elif isinstance(raw_prices, list):
            try:
                prices = [float(x) for x in raw_prices]
            except Exception:
                prices = []

        outcomes_raw = market.get("outcomes")
        if isinstance(outcomes_raw, str):
            try:
                outcomes = [o.lower() for o in json.loads(outcomes_raw)]
            except Exception:
                outcomes = []
        else:
            outcomes = [o.lower() for o in (outcomes_raw or [])]

        if len(prices) != 2 or len(outcomes) != 2:
            continue

        side = trade.get("side", "yes")
        side_idx = outcomes.index(side) if side in outcomes else 0
        final_price = prices[side_idx]

        # 수렴 상태로 판정: 0.95+ 면 승, 0.05- 면 패
        if final_price >= 0.95:
            won = True
            payout = 1.0
        elif final_price <= 0.05:
            won = False
            payout = 0.0
        else:
            # 수렴 안 됨 (오라클 대기 중일 수 있음) — 다음 사이클에 재시도
            continue

        entry = trade["entry_price"]
        shares = trade["shares"]
        gross_pnl = (payout - entry) * shares
        fee = max(0, gross_pnl) * 0.02
        pnl = gross_pnl - fee

        trade["resolved"] = True
        trade["pnl"] = round(pnl, 4)
        trade["payout_per_share"] = payout
        trade["resolution_price"] = final_price
        trade["won"] = won
        trade["fee"] = round(fee, 4)
        trade["settled_at"] = now.isoformat()
        settled += 1

        risk_gate.record_trade({"pnl": pnl})

    if settled > 0:
        config.PAPER_LEDGER.write_text(json.dumps(trades, indent=2, default=str))

    return settled


def _current_capital() -> float:
    """현재 페이퍼 가용 자본 추정."""
    trades = ledger.load_ledger(live=False)
    start = config.STARTING_CAPITAL
    realized_pnl = sum(t.get("pnl", 0) for t in trades if t.get("resolved"))
    open_bets = sum(t.get("bet_usd", 0) for t in trades if t.get("status") == "filled" and not t.get("resolved"))
    return start + realized_pnl - open_bets


def run_strategy(name: str, module, open_positions: list, capital: float) -> dict:
    """전략 하나 실행."""
    stats = {"strategy": name, "signals": 0, "placed": 0, "blocked": 0}

    try:
        signals = module.detect_signals()
    except Exception as e:
        print(f"[{name}] detect_signals 에러: {e}")
        return stats

    stats["signals"] = len(signals)
    if not signals:
        print(f"[{name}] 시그널 없음")
        return stats

    print(f"[{name}] 시그널 {len(signals)}개 발견")

    for signal in signals:
        # 리스크 게이트
        bet_usd = module.size_bet(signal, capital)
        if bet_usd < config.MIN_BET_USD:
            stats["blocked"] += 1
            continue

        # 동시 포지션 제한
        if len(open_positions) >= config.MAX_CONCURRENT_POSITIONS:
            print(f"[{name}] 동시 포지션 한계")
            break

        # 일일 손실/드로다운 체크
        if not risk_gate.pre_trade_check_basic():
            print(f"[{name}] 리스크 게이트 차단")
            break

        # 중복 마켓 필터
        market_id = signal.get("market_id")
        if any(op.get("market_id") == market_id for op in open_positions):
            stats["blocked"] += 1
            continue

        # 주문
        print(f"  [{signal['strategy']}] {signal['question'][:50]}")
        print(f"    side={signal['side']} entry={signal['entry_price']:.3f} edge={signal['edge_pct']*100:.2f}% bet=${bet_usd:.2f}")

        result = executor.execute(signal, bet_usd)
        result_status = result.get("status")
        print(f"    status={result_status}")

        if result_status == "filled":
            # 전략 식별자 추가
            result["strategy"] = name
            # ledger에 저장 (execute_paper가 이미 저장하지만 strategy 필드 추가)
            _tag_last_trade_with_strategy(name, result.get("market_id"))

            stats["placed"] += 1
            open_positions.append(result)

            # Telegram 알림
            try:
                from notifier import telegram
                telegram.notify_trade(result)
            except Exception as e:
                print(f"    [telegram] 실패: {e}")

    return stats


def _tag_last_trade_with_strategy(strategy: str, market_id):
    """최근 추가된 trade에 strategy 필드 부착."""
    trades = ledger.load_ledger(live=False)
    for t in reversed(trades):
        if t.get("market_id") == market_id and "strategy" not in t:
            t["strategy"] = strategy
            break
    config.PAPER_LEDGER.write_text(json.dumps(trades, indent=2, default=str))


def main():
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mode = "LIVE" if config.LIVE_TRADING else "PAPER"
    print(f"\n[multi_trader] {ts} 실행 시작 (모드: {mode}, 자본: ${config.STARTING_CAPITAL})")

    # 1. 결제 처리
    settled = _settle_positions()
    if settled:
        print(f"[multi_trader] {settled}개 포지션 결제됨")

    # 2. 현재 자본 계산
    capital = _current_capital()
    print(f"[multi_trader] 가용 자본: ${capital:.2f}")

    # 3. 전략별 실행
    open_positions = get_open_positions()
    all_stats = []

    for name, (module, enabled) in STRATEGIES.items():
        if not enabled:
            print(f"[{name}] 비활성 스킵")
            continue
        stats = run_strategy(name, module, open_positions, capital)
        all_stats.append(stats)

    # 4. 요약 출력
    total_signals = sum(s["signals"] for s in all_stats)
    total_placed = sum(s["placed"] for s in all_stats)
    summary = ledger.summary(live=False)
    print(f"\n[multi_trader] 완료: 시그널 {total_signals}개, 신규 거래 {total_placed}건, 결제 {settled}건")
    print(f"[multi_trader] 누적 PnL: ${summary.get('total_pnl', 0)}, 승률: {summary.get('win_rate', 0)}%")

    # 5. 실행 기록 저장 (대시보드용)
    run_record = {
        "timestamp": ts,
        "mode": mode,
        "starting_capital": config.STARTING_CAPITAL,
        "current_capital": round(capital, 2),
        "settled": settled,
        "strategies": all_stats,
        "total_signals": total_signals,
        "total_placed": total_placed,
        "open_positions_count": len(open_positions),
        "summary": summary,
    }

    last_run_file = config.DOCS / "trader_last_run.json"
    last_run_file.write_text(json.dumps(run_record, indent=2, default=str))


if __name__ == "__main__":
    main()
