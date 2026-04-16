"""주문 실행 — 페이퍼 모드 (기본) + 실전 모드.

페이퍼: 실제 돈 안 쓰고 시뮬레이션. 70% fill rate + 0.5% 슬리피지.
실전: Polymarket CLOB API로 실제 주문 (환경변수 LIVE_TRADING=1 필요).
"""
import json
import random
from datetime import datetime, timezone
from typing import Optional

from . import config, polymarket_client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_ledger(path) -> list:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _save_ledger(path, ledger: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, default=str))


def execute_paper(signal: dict, bet_usd: float) -> dict:
    """페이퍼 주문 — 현실적 시뮬."""
    # 70% fill rate 시뮬
    filled = random.random() < config.PAPER_FILL_RATE
    if not filled:
        return {
            "status": "not_filled",
            "timestamp": _now_iso(),
            "signal": signal,
            "bet_usd": bet_usd,
            "reason": f"simulated {config.PAPER_FILL_RATE*100}% fill rate — 이번엔 미체결",
        }

    # 슬리피지 적용
    slippage_direction = 1 if signal["side"] == "yes" else 1  # buy 시 항상 불리
    entry_with_slip = signal["entry_price"] * (1 + config.PAPER_SLIPPAGE_PCT)
    entry_with_slip = min(entry_with_slip, 0.99)  # max 0.99

    shares = bet_usd / entry_with_slip

    # 기대 PnL (페이퍼는 즉시 계산은 아니고 체결만 기록)
    # 실제 결제 결과는 settle_paper_positions()에서 처리

    trade = {
        "status": "filled",
        "timestamp": _now_iso(),
        "mode": "paper",
        "market_id": signal["market_id"],
        "slug": signal.get("slug", ""),
        "question": signal["question"],
        "side": signal["side"],
        "entry_price": entry_with_slip,
        "shares": shares,
        "bet_usd": bet_usd,
        "my_prob": signal.get("my_prob_selected"),
        "edge_pct_at_entry": signal.get("edge_pct"),
        "end_date": signal.get("endDate", ""),
        "current_btc": signal.get("current_price"),
        "strike": signal.get("strike"),
        "resolved": False,
        "pnl": None,
    }

    ledger = _load_ledger(config.PAPER_LEDGER)
    ledger.append(trade)
    _save_ledger(config.PAPER_LEDGER, ledger)

    return trade


def execute_live(signal: dict, bet_usd: float) -> dict:
    """실전 주문 — Polymarket CLOB.

    실제 주문 로직은 py-clob-client 라이브러리 필요.
    안전을 위해 기본 비활성화 — LIVE_TRADING=1 명시되어야 함.
    """
    if not config.LIVE_TRADING:
        return {
            "status": "blocked",
            "reason": "LIVE_TRADING=0 (환경변수로 활성화 필요)",
            "timestamp": _now_iso(),
        }

    # TODO: 실제 CLOB API 주문 (py-clob-client 설치 + 키 있을 때)
    try:
        from py_clob_client.client import ClobClient  # type: ignore
        # 실전 주문 구현은 키 설정 후 추가
        return {
            "status": "not_implemented",
            "reason": "실전 주문 로직은 키 등록 후 활성화. 현재는 페이퍼만.",
            "timestamp": _now_iso(),
        }
    except ImportError:
        return {
            "status": "error",
            "reason": "py-clob-client 미설치",
            "timestamp": _now_iso(),
        }


def execute(signal: dict, bet_usd: float) -> dict:
    """모드에 따라 페이퍼/실전 분기."""
    if config.LIVE_TRADING:
        return execute_live(signal, bet_usd)
    return execute_paper(signal, bet_usd)


def settle_paper_positions(current_prices: dict) -> int:
    """페이퍼 포지션 중 결제 시각 지난 것 처리.

    current_prices: {symbol: current_price_for_resolution}
                   (단순화: 현재 Binance 가격 사용)

    결제 로직:
      - 결제 시각(endDate) 지난 포지션 조회
      - 결과 확인 (BTC > strike 인지)
      - YES/NO 승패 판정
      - 승리 → $1/share, 패배 → $0
      - PnL = (결제가 - 진입가) * shares
      - Polymarket 수수료 2% (수익에 대해서만)

    Returns: 결제한 포지션 수
    """
    ledger = _load_ledger(config.PAPER_LEDGER)
    settled_count = 0
    now = datetime.now(timezone.utc)

    for trade in ledger:
        if trade.get("resolved"):
            continue
        if trade.get("status") != "filled":
            continue

        end_date_str = trade.get("end_date", "")
        if not end_date_str:
            continue
        try:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        except Exception:
            continue

        if now < end_date:
            continue

        # 결제 진행
        symbol = None
        question_lower = trade.get("question", "").lower()
        if "bitcoin" in question_lower or "btc" in question_lower:
            symbol = "BTC"
        elif "ethereum" in question_lower or "eth" in question_lower:
            symbol = "ETH"
        elif "solana" in question_lower or "sol" in question_lower:
            symbol = "SOL"
        elif "xrp" in question_lower:
            symbol = "XRP"

        resolution_price = current_prices.get(symbol)
        if resolution_price is None:
            # 결제 가격 없으면 다음 사이클에 재시도
            continue

        strike = trade.get("strike")
        if strike is None:
            continue

        # 결과 판정 (단순화: above 가정)
        # 실제론 질문의 direction도 고려해야 함
        btc_above = resolution_price > strike
        side = trade.get("side")
        # YES 샀는데 above + direction=above 이면 YES 승
        # 현재는 direction 정보 없음 → 보수적으로 스킵
        # TODO: direction 포함해서 정확 판정. 지금은 above 가정.
        if side == "yes":
            won = btc_above
        else:
            won = not btc_above

        payout_per_share = 1.0 if won else 0.0
        entry = trade["entry_price"]
        shares = trade["shares"]
        bet = trade["bet_usd"]

        gross_pnl = (payout_per_share - entry) * shares
        # 수수료 2% (수익에만)
        fee = max(0, gross_pnl) * 0.02
        pnl = gross_pnl - fee

        trade["resolved"] = True
        trade["pnl"] = round(pnl, 4)
        trade["payout_per_share"] = payout_per_share
        trade["resolution_price"] = resolution_price
        trade["won"] = won
        trade["fee"] = round(fee, 4)
        trade["settled_at"] = _now_iso()

        settled_count += 1

        # 리스크 게이트에 기록
        from . import risk_gate
        risk_gate.record_trade({"pnl": pnl})

    _save_ledger(config.PAPER_LEDGER, ledger)
    return settled_count
