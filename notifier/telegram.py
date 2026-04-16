"""Telegram 알림 — 거래 체결, 이상 감지, 일일 요약.

환경변수 없으면 silent (에러 안 남). 로컬 테스트 안전.
"""
import os
from typing import Optional

import requests

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def _send(text: str, parse_mode: str = "HTML") -> bool:
    if not TG_TOKEN or not TG_CHAT_ID:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT_ID,
                "text": text[:4000],  # Telegram 4096자 제한
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[telegram] 전송 실패: {e}")
        return False


def notify_trade(trade: dict) -> bool:
    """거래 체결 알림."""
    if trade.get("status") != "filled":
        return False
    mode = trade.get("mode", "paper").upper()
    q = trade.get("question", "")[:80]
    side = trade.get("side", "").upper()
    entry = trade.get("entry_price", 0)
    bet = trade.get("bet_usd", 0)
    edge = trade.get("edge_pct_at_entry", 0) * 100
    my_prob = (trade.get("my_prob") or 0) * 100

    text = (
        f"<b>[{mode}] 체결</b>\n"
        f"{q}\n"
        f"side: <b>{side}</b> @ {entry:.3f}\n"
        f"bet: ${bet:.2f}  edge: {edge:.2f}%  my_prob: {my_prob:.1f}%"
    )
    return _send(text)


def notify_settlement(trade: dict) -> bool:
    """결제 완료 알림."""
    if not trade.get("resolved"):
        return False
    won = trade.get("won")
    pnl = trade.get("pnl", 0)
    q = trade.get("question", "")[:80]
    emoji = "WIN" if won else "LOSS"
    text = (
        f"<b>[결제 {emoji}]</b>\n{q}\n"
        f"PnL: <b>${pnl:+.2f}</b>"
    )
    return _send(text)


def notify_anomaly(title: str, detail: str) -> bool:
    """이상 감지 경고."""
    text = f"<b>⚠️ 경고: {title}</b>\n{detail}"
    return _send(text)


def notify_daily_summary(summary: dict) -> bool:
    """일일 요약 리포트."""
    lines = ["<b>📊 일일 요약</b>"]
    if "date" in summary:
        lines.append(f"날짜: {summary['date']}")
    lines.append(f"총 거래: {summary.get('total_resolved', 0)}건")
    lines.append(f"승/패: {summary.get('wins', 0)}/{summary.get('losses', 0)}")
    lines.append(f"승률: {summary.get('win_rate', 0)}%")
    lines.append(f"PnL: ${summary.get('total_pnl', 0):+.2f}")
    if summary.get("sharpe_estimate"):
        lines.append(f"Sharpe: {summary['sharpe_estimate']}")
    if summary.get("claude_note"):
        lines.append(f"\n<i>Claude: {summary['claude_note']}</i>")
    return _send("\n".join(lines))


def is_configured() -> bool:
    return bool(TG_TOKEN and TG_CHAT_ID)
