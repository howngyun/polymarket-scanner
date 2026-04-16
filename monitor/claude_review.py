"""Claude 일일 리뷰 — GitHub Actions에서 1일 1회 실행.

Anthropic API 호출, ~3K 토큰 입력, 저비용.
트레이딩 통계 + 이상 로그 → Claude 분석 → docs/daily_review/{date}.md.
큰 이슈면 Telegram 경고.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DOCS = ROOT / "docs"
REVIEW_DIR = DOCS / "daily_review"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def gather_context() -> dict:
    """Claude에게 보낼 최소 컨텍스트. 토큰 절약을 위해 핵심만."""
    state = _load_json(DOCS / "trader_state.json") or {}
    last_run = _load_json(DOCS / "trader_last_run.json") or {}
    health = _load_json(DOCS / "health.json") or {}

    ledger = _load_json(DOCS / "trades" / "paper_ledger.json") or []
    # 최근 24h 거래만
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_trades = []
    for t in ledger:
        ts_str = t.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts >= cutoff:
                recent_trades.append(t)
        except Exception:
            pass

    # 샘플 축약 — 핵심 필드만
    trade_samples = []
    for t in recent_trades[-15:]:  # 최근 15건만
        trade_samples.append({
            "side": t.get("side"),
            "entry": t.get("entry_price"),
            "bet": t.get("bet_usd"),
            "edge": t.get("edge_pct_at_entry"),
            "my_prob": t.get("my_prob"),
            "won": t.get("won"),
            "pnl": t.get("pnl"),
            "symbol": "BTC" if "bitcoin" in (t.get("question") or "").lower() else "other",
        })

    # 집계
    resolved = [t for t in recent_trades if t.get("resolved")]
    wins = sum(1 for t in resolved if t.get("won"))
    losses = sum(1 for t in resolved if t.get("won") is False)
    pnl_24h = sum(t.get("pnl", 0) for t in resolved)

    return {
        "state": {
            "starting_capital": state.get("starting_capital"),
            "current_capital": state.get("current_capital"),
            "total_trades": state.get("total_trades"),
            "kill_switch": state.get("kill_switch"),
            "kill_reason": state.get("kill_reason"),
        },
        "last_run": last_run,
        "health_status": health.get("status"),
        "recent_anomalies": (health.get("anomalies") or [])[-10:],
        "last_24h": {
            "trades_count": len(recent_trades),
            "resolved_count": len(resolved),
            "wins": wins,
            "losses": losses,
            "pnl": round(pnl_24h, 2),
        },
        "trade_samples": trade_samples,
    }


REVIEW_PROMPT = """You are a quant trading auditor reviewing a Polymarket BTC-resolution-arb bot (paper mode).

Your job: analyze the provided 24h snapshot and output a SHORT structured review in JSON.

Focus on:
- Is the probability model calibrated? (my_prob vs actual outcomes)
- Any obvious edge decay or regime change?
- Are risk limits working?
- Suggested parameter adjustments (conservative, small steps only)

Return ONLY valid JSON matching this schema (no markdown fences, no prose outside JSON):
{
  "verdict": "healthy" | "watch" | "concerning" | "halt_recommended",
  "key_observations": ["string", ...],        // max 3 items
  "calibration_check": "string",              // 1 sentence
  "recommended_actions": ["string", ...],     // max 3, concrete changes only
  "summary": "string"                         // 1-2 sentences for Telegram
}

Do not invent numbers. If there's too little data (< 5 resolved trades), say so and return verdict "watch"."""


def call_claude(context: dict) -> dict:
    """Anthropic API 호출."""
    import requests

    if not ANTHROPIC_KEY:
        return {"verdict": "unknown", "summary": "ANTHROPIC_API_KEY 없음",
                "key_observations": [], "calibration_check": "",
                "recommended_actions": []}

    payload = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 1024,
        "system": REVIEW_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": f"Data snapshot:\n```json\n{json.dumps(context, default=str)}\n```"
            }
        ],
    }
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        r.raise_for_status()
        resp = r.json()
        text = resp["content"][0]["text"].strip()
        # 혹시 마크다운 펜스 포함 시 제거
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:].strip()
        return json.loads(text)
    except Exception as e:
        return {
            "verdict": "unknown",
            "summary": f"Claude 호출 실패: {e}",
            "key_observations": [],
            "calibration_check": "",
            "recommended_actions": [],
        }


def main():
    ts = datetime.now(timezone.utc)
    date_str = ts.strftime("%Y-%m-%d")
    print(f"[claude_review] {ts.isoformat(timespec='seconds')} 시작")

    context = gather_context()
    print(f"[claude_review] 컨텍스트 수집: {context['last_24h']['trades_count']}건")

    review = call_claude(context)
    print(f"[claude_review] verdict={review.get('verdict')}")

    # 리뷰 파일 저장 (markdown)
    md_lines = [
        f"# 일일 리뷰 — {date_str}",
        f"",
        f"**Verdict:** {review.get('verdict')}",
        f"",
        f"**Summary:** {review.get('summary', '')}",
        f"",
        f"## 핵심 관찰",
    ]
    for obs in review.get("key_observations", []):
        md_lines.append(f"- {obs}")
    md_lines.append(f"\n## 캘리브레이션")
    md_lines.append(review.get("calibration_check", ""))
    md_lines.append(f"\n## 권장 조치")
    for act in review.get("recommended_actions", []):
        md_lines.append(f"- {act}")
    md_lines.append(f"\n## 24h 데이터")
    md_lines.append(f"```json\n{json.dumps(context['last_24h'], indent=2)}\n```")

    (REVIEW_DIR / f"{date_str}.md").write_text("\n".join(md_lines), encoding="utf-8")
    (DOCS / "latest_review.json").write_text(json.dumps({
        "date": date_str,
        "review": review,
        "last_24h": context["last_24h"],
    }, indent=2, default=str))

    # Telegram 요약 전송
    try:
        from notifier import telegram
        telegram.notify_daily_summary({
            "date": date_str,
            "total_resolved": context["last_24h"]["resolved_count"],
            "wins": context["last_24h"]["wins"],
            "losses": context["last_24h"]["losses"],
            "win_rate": round(
                context["last_24h"]["wins"] /
                max(context["last_24h"]["resolved_count"], 1) * 100, 1
            ),
            "total_pnl": context["last_24h"]["pnl"],
            "claude_note": review.get("summary", ""),
        })

        # halt 권장이면 critical 알림
        if review.get("verdict") == "halt_recommended":
            telegram.notify_anomaly(
                "Claude halt 권장",
                review.get("summary", "")
            )
    except Exception as e:
        print(f"[claude_review] telegram 실패: {e}")


if __name__ == "__main__":
    main()
