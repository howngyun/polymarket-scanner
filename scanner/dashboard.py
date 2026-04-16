"""latest.json + trader 데이터 읽어서 GitHub Pages용 index.html 생성."""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / "docs"


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def generate():
    scan = _load(DOCS_DIR / "latest.json", {})
    state = _load(DOCS_DIR / "trader_state.json", {})
    last_run = _load(DOCS_DIR / "trader_last_run.json", {})
    health = _load(DOCS_DIR / "health.json", {})
    review = _load(DOCS_DIR / "latest_review.json", {})
    ledger = _load(DOCS_DIR / "trades" / "paper_ledger.json", [])

    # === 스캐너 섹션 ===
    scanned_at = scan.get("scanned_at", "—")
    n_markets = scan.get("n_markets", 0)
    bargains = scan.get("bargains", [])
    movers = scan.get("movers", [])
    longshots = scan.get("longshots", [])

    # === 트레이더 섹션 ===
    mode = last_run.get("mode", "—")
    mode_color = "#e67e22" if mode == "PAPER" else ("#e74c3c" if mode == "LIVE" else "#888")
    starting = state.get("starting_capital", 0)
    current = state.get("current_capital", 0)
    pnl_total = current - starting if starting else 0
    pnl_color = "#27ae60" if pnl_total >= 0 else "#e74c3c"
    total_trades = state.get("total_trades", 0)
    kill = state.get("kill_switch", False)
    kill_reason = state.get("kill_reason", "")

    # 오픈 포지션
    open_positions = [t for t in ledger if t.get("status") == "filled" and not t.get("resolved")]
    resolved = [t for t in ledger if t.get("resolved")]
    wins = sum(1 for t in resolved if t.get("won"))
    win_rate = (wins / len(resolved) * 100) if resolved else 0
    last_trader_run = last_run.get("timestamp", "—")

    # === 헬스 ===
    health_status = health.get("status", "—")
    anomalies = health.get("anomalies", [])

    # === Claude review ===
    review_data = review.get("review", {})
    verdict = review_data.get("verdict", "—")
    verdict_color = {
        "healthy": "#27ae60",
        "watch": "#e67e22",
        "concerning": "#e74c3c",
        "halt_recommended": "#c0392b",
    }.get(verdict, "#888")

    # === 테이블 로우 생성 ===
    def _rows_bargain(items):
        if not items:
            return "<tr><td colspan='5' style='text-align:center;color:#888'>없음</td></tr>"
        out = []
        for b in items:
            edge = b.get("implied_edge", 0)
            color = "#c0392b" if edge >= 3 else "#e67e22" if edge >= 2 else "#27ae60"
            url = f"https://polymarket.com/event/{b.get('slug','')}" if b.get("slug") else "#"
            out.append(
                f"<tr><td><a href='{url}' target='_blank'>{b.get('question','')[:80]}</a></td>"
                f"<td style='color:{color};font-weight:bold'>{edge}%</td>"
                f"<td>{b.get('top_price',0):.3f}</td>"
                f"<td>{b.get('hours_to_close','')}h</td>"
                f"<td>${b.get('liquidity',0):,.0f}</td></tr>"
            )
        return "\n".join(out)

    def _rows_longshot(items):
        if not items:
            return "<tr><td colspan='4' style='text-align:center;color:#888'>없음</td></tr>"
        out = []
        for ls in items:
            url = f"https://polymarket.com/event/{ls.get('slug','')}" if ls.get("slug") else "#"
            out.append(
                f"<tr><td><a href='{url}' target='_blank'>{ls.get('question','')[:80]}</a></td>"
                f"<td>{ls.get('longshot_price',0):.3f}</td>"
                f"<td>{ls.get('hours_to_close','')}h</td>"
                f"<td>${ls.get('volume',0):,.0f}</td></tr>"
            )
        return "\n".join(out)

    def _rows_positions(items):
        if not items:
            return "<tr><td colspan='5' style='text-align:center;color:#888'>오픈 포지션 없음</td></tr>"
        out = []
        for t in items[-10:]:
            out.append(
                f"<tr><td>{t.get('question','')[:60]}</td>"
                f"<td><b>{t.get('side','').upper()}</b></td>"
                f"<td>{t.get('entry_price',0):.3f}</td>"
                f"<td>${t.get('bet_usd',0):.2f}</td>"
                f"<td>{(t.get('edge_pct_at_entry',0) or 0)*100:.1f}%</td></tr>"
            )
        return "\n".join(out)

    def _rows_recent(items):
        recent = items[-15:] if items else []
        if not recent:
            return "<tr><td colspan='6' style='text-align:center;color:#888'>거래 없음</td></tr>"
        out = []
        for t in reversed(recent):
            pnl = t.get("pnl")
            if pnl is None:
                pnl_cell = "<span style='color:#888'>open</span>"
            else:
                color = "#27ae60" if pnl >= 0 else "#e74c3c"
                pnl_cell = f"<span style='color:{color}'>${pnl:+.2f}</span>"
            won = t.get("won")
            result = "—" if won is None else ("W" if won else "L")
            out.append(
                f"<tr><td>{t.get('timestamp','')[:16]}</td>"
                f"<td>{t.get('question','')[:50]}</td>"
                f"<td><b>{t.get('side','').upper()}</b></td>"
                f"<td>{t.get('entry_price',0):.3f}</td>"
                f"<td>{result}</td>"
                f"<td>{pnl_cell}</td></tr>"
            )
        return "\n".join(out)

    def _rows_anomalies(items):
        if not items:
            return "<tr><td colspan='3' style='text-align:center;color:#27ae60'>정상</td></tr>"
        out = []
        for a in items[:10]:
            sev = a.get("severity", "info")
            color = {"critical": "#c0392b", "warn": "#e67e22"}.get(sev, "#888")
            out.append(
                f"<tr><td style='color:{color}'>{sev.upper()}</td>"
                f"<td>{a.get('title','')}</td>"
                f"<td>{a.get('detail','')}</td></tr>"
            )
        return "\n".join(out)

    kill_banner = ""
    if kill:
        kill_banner = (
            f"<div style='background:#c0392b;color:#fff;padding:12px;margin-bottom:16px;"
            f"border-radius:4px;font-weight:bold'>KILL SWITCH 발동: {kill_reason}</div>"
        )

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Polymarket Bot</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, sans-serif; background: #0f1117; color: #e0e0e0;
         padding: 20px; max-width: 1400px; margin: 0 auto; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .meta {{ color: #888; font-size: 0.85rem; margin-bottom: 24px; }}
  .section {{ margin-bottom: 32px; }}
  h2 {{ font-size: 1rem; color: #aaa; border-bottom: 1px solid #2a2a2a;
        padding-bottom: 6px; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; padding: 7px 10px; background: #1a1a2e; color: #aaa;
        font-weight: 500; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #1e1e1e; }}
  tr:hover td {{ background: #1a1a1a; }}
  a {{ color: #7eb8f7; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .stat {{ display: inline-block; margin-right: 24px; margin-bottom: 10px;
           min-width: 100px; }}
  .stat-num {{ font-size: 1.5rem; font-weight: bold; }}
  .stat-lbl {{ font-size: 0.75rem; color: #888; }}
  .stats {{ margin-bottom: 24px; padding: 16px; background: #1a1a2e; border-radius: 6px; }}
  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 3px;
          font-size: 0.75rem; font-weight: bold; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>Polymarket Trading Bot</h1>
<div class="meta">
  스캐너: {scanned_at} | 트레이더: {last_trader_run} |
  헬스: <span style="color:{'#c0392b' if health_status=='critical' else ('#e67e22' if health_status=='warn' else '#27ae60')}">{health_status}</span>
  | 5분마다 자동 새로고침
</div>

{kill_banner}

<div class="section">
  <h2>트레이더 상태
    <span class="tag" style="background:{mode_color};color:#fff;margin-left:8px">{mode}</span>
    <span class="tag" style="background:{verdict_color};color:#fff;margin-left:4px">Claude: {verdict}</span>
  </h2>
  <div class="stats">
    <div class="stat"><div class="stat-num" style="color:#7eb8f7">${current:.2f}</div><div class="stat-lbl">현재 자본</div></div>
    <div class="stat"><div class="stat-num" style="color:{pnl_color}">${pnl_total:+.2f}</div><div class="stat-lbl">누적 PnL</div></div>
    <div class="stat"><div class="stat-num">{total_trades}</div><div class="stat-lbl">총 거래</div></div>
    <div class="stat"><div class="stat-num">{len(resolved)}</div><div class="stat-lbl">정산됨</div></div>
    <div class="stat"><div class="stat-num">{win_rate:.0f}%</div><div class="stat-lbl">승률</div></div>
    <div class="stat"><div class="stat-num">{len(open_positions)}</div><div class="stat-lbl">오픈 포지션</div></div>
  </div>
</div>

<div class="grid">
  <div class="section">
    <h2>오픈 포지션</h2>
    <table>
      <thead><tr><th>마켓</th><th>방향</th><th>진입가</th><th>베팅</th><th>엣지</th></tr></thead>
      <tbody>{_rows_positions(open_positions)}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>이상 감지 / 헬스 로그</h2>
    <table>
      <thead><tr><th>레벨</th><th>제목</th><th>상세</th></tr></thead>
      <tbody>{_rows_anomalies(anomalies)}</tbody>
    </table>
  </div>
</div>

<div class="section">
  <h2>최근 거래 이력</h2>
  <table>
    <thead><tr><th>시간</th><th>마켓</th><th>방향</th><th>진입가</th><th>결과</th><th>PnL</th></tr></thead>
    <tbody>{_rows_recent(ledger)}</tbody>
  </table>
</div>

<div class="section">
  <h2>스캐너: 임박 기회 (결제 6h 이내)</h2>
  <table>
    <thead><tr><th>마켓</th><th>엣지</th><th>현재가</th><th>마감</th><th>유동성</th></tr></thead>
    <tbody>{_rows_bargain(bargains[:15])}</tbody>
  </table>
</div>

<div class="section">
  <h2>스캐너: 롱샷 (1-8%)</h2>
  <table>
    <thead><tr><th>마켓</th><th>롱샷가</th><th>마감</th><th>거래량</th></tr></thead>
    <tbody>{_rows_longshot(longshots[:15])}</tbody>
  </table>
</div>

<div class="meta" style="margin-top:40px;padding:12px;background:#1a1a1a;border-radius:4px">
  <b>Claude 최신 리뷰:</b> {review_data.get('summary','—')}<br>
  <span style="color:#888">자동매매 전에 PAPER 모드로 2주 검증. 스캔 {n_markets:,}개 마켓.</span>
</div>
</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"[dashboard] index.html 생성 완료")


if __name__ == "__main__":
    generate()
