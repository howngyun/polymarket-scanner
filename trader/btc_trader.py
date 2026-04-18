"""⚠️ DEPRECATED (2026-04-18): BTC 2분 창 전략 — 레드오션 경쟁 심함, 신호 0건.

이 파일은 참고용으로만 유지. 현재 트레이더 엔트리는 `multi_trader.py`.
새 전략: 94-98c NO 그라인딩 + Cross-Market Arbitrage.

---

기존 설명:

메인 트레이더 엔트리 포인트 — 5분마다 GitHub Actions에서 실행.

흐름:
  1. 기존 페이퍼 포지션 결제 처리
  2. 곧 마감될 크립토 마켓 조회
  3. 각 마켓 엣지 계산
  4. 엣지 있으면 리스크 체크 → 주문
  5. Telegram 알림
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# package 실행 허용
sys.path.insert(0, str(Path(__file__).parent.parent))

from trader import config, polymarket_client, price_feed, edge_detector, risk_gate, executor, ledger


def get_open_positions() -> list:
    """미결제 페이퍼 포지션 목록."""
    all_trades = ledger.load_ledger(live=False)
    return [t for t in all_trades if t.get("status") == "filled" and not t.get("resolved")]


def main():
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"\n[btc_trader] {ts} 실행 시작 (모드: {'LIVE' if config.LIVE_TRADING else 'PAPER'})")

    # 1. 결제 처리 (현재 가격으로 마감된 포지션 정산)
    current_prices = {}
    for sym in ["BTC", "ETH", "SOL", "XRP"]:
        p = price_feed.get_current_price(sym)
        if p is not None:
            current_prices[sym] = p
    print(f"[btc_trader] 현재가: {current_prices}")

    settled = executor.settle_paper_positions(current_prices)
    if settled:
        print(f"[btc_trader] {settled}개 포지션 결제됨")

    # 2. 마켓 스캔
    signals_found = 0
    trades_placed = 0
    open_positions = get_open_positions()

    for market in polymarket_client.iter_crypto_markets_closing_soon(
        max_seconds_to_close=config.MAX_SECONDS_TO_CLOSE,
        min_seconds_to_close=config.MIN_SECONDS_TO_CLOSE,
    ):
        signal = edge_detector.detect_edge(market)
        if signal is None:
            continue

        signals_found += 1
        print(f"\n[signal] {signal['question'][:60]}")
        print(f"  side={signal['side']} entry={signal['entry_price']:.3f} "
              f"my_prob={signal['my_prob_selected']:.3f} edge={signal['edge_pct']*100:.2f}%")
        print(f"  BTC={signal['current_price']:.2f} strike={signal['strike']} "
              f"vol={signal['annual_vol']*100:.1f}% close in {signal['seconds_left']:.0f}s")

        # 3. 리스크 체크
        ok, reason, bet_usd = risk_gate.check(signal, open_positions)
        if not ok:
            print(f"  [blocked] {reason}")
            continue

        # 4. 슬리피지 사전 체크 (오더북)
        if signal.get("token_ids"):
            # tokenIds는 [yes_token_id, no_token_id] 형태일 수 있음
            token_idx = 0 if signal["side"] == "yes" else 1
            if len(signal["token_ids"]) > token_idx:
                tid = signal["token_ids"][token_idx]
                ob = polymarket_client.get_orderbook(tid)
                avg_fill = polymarket_client.estimate_avg_fill_price(ob, "buy", bet_usd)
                if avg_fill is not None:
                    slippage = (avg_fill - signal["entry_price"]) / signal["entry_price"]
                    if slippage > config.MAX_SLIPPAGE_PCT:
                        print(f"  [blocked] 슬리피지 {slippage*100:.2f}% > {config.MAX_SLIPPAGE_PCT*100}%")
                        continue
                    # 실제 엣지 재검토
                    real_entry = avg_fill
                    real_edge = signal["my_prob_selected"] - real_entry
                    if real_edge < config.MIN_EDGE_PCT:
                        print(f"  [blocked] 슬리피지 반영 후 엣지 {real_edge*100:.2f}% < {config.MIN_EDGE_PCT*100}%")
                        continue
                    signal["entry_price"] = real_entry
                    signal["edge_pct"] = real_edge

        # 5. 주문 실행
        signal["endDate"] = market.get("endDate", "")
        result = executor.execute(signal, bet_usd)
        print(f"  [execute] status={result.get('status')} bet=${bet_usd:.2f}")

        if result.get("status") == "filled":
            trades_placed += 1
            open_positions.append(result)

            # Telegram 알림 (체결 시)
            try:
                from notifier import telegram
                telegram.notify_trade(result)
            except Exception as e:
                print(f"  [telegram] 알림 실패: {e}")

    # 6. 요약 출력
    stats = ledger.summary(live=False)
    print(f"\n[btc_trader] 완료: 시그널 {signals_found}개, 신규 거래 {trades_placed}건, 결제 {settled}건")
    print(f"[btc_trader] 누적: filled={stats['total_filled']} resolved={stats['total_resolved']} "
          f"PnL=${stats['total_pnl']} win_rate={stats['win_rate']}%")

    # 7. 실행 기록 저장 (대시보드용)
    run_record = {
        "timestamp": ts,
        "mode": "LIVE" if config.LIVE_TRADING else "PAPER",
        "current_prices": current_prices,
        "signals_found": signals_found,
        "trades_placed": trades_placed,
        "settled": settled,
        "open_positions_count": len(open_positions),
        "stats": stats,
    }

    last_run_file = config.DOCS / "trader_last_run.json"
    last_run_file.write_text(json.dumps(run_record, indent=2, default=str))


if __name__ == "__main__":
    main()
