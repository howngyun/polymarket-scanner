"""latest.json 읽어서 GitHub Pages용 index.html 생성."""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / "docs"


def generate():
    data_file = DOCS_DIR / "latest.json"
    if not data_file.exists():
        print("[dashboard] latest.json 없음. run_once.py 먼저 실행.")
        return

    data = json.loads(data_file.read_text())
    scanned_at = data.get("scanned_at", "")
    n_markets = data.get("n_markets", 0)
    bargains = data.get("bargains", [])
    movers = data.get("movers", [])
    longshots = data.get("longshots", [])

    def rows_bargain(items):
        if not items:
            return "<tr><td colspan='5' style='text-align:center;color:#888'>없음</td></tr>"
        out = []
        for b in items:
            edge = b.get("implied_edge", 0)
            color = "#c0392b" if edge >= 3 else "#e67e22" if edge >= 2 else "#27ae60"
            q = b.get("question", "")
            slug = b.get("slug", "")
            url = f"https://polymarket.com/event/{slug}" if slug else "#"
            out.append(
                f"<tr>"
                f"<td><a href='{url}' target='_blank'>{q[:80]}</a></td>"
                f"<td style='color:{color};font-weight:bold'>{edge}%</td>"
                f"<td>{b.get('top_price',0):.3f}</td>"
                f"<td>{b.get('hours_to_close','')}h</td>"
                f"<td>${b.get('liquidity',0):,.0f}</td>"
                f"</tr>"
            )
        return "\n".join(out)

    def rows_mover(items):
        if not items:
            return "<tr><td colspan='5' style='text-align:center;color:#888'>없음</td></tr>"
        out = []
        for m in items:
            move = m.get("move_pct", 0)
            color = "#c0392b" if move < 0 else "#27ae60"
            sign = "+" if move > 0 else ""
            q = m.get("question", "")
            slug = m.get("slug", "")
            url = f"https://polymarket.com/event/{slug}" if slug else "#"
            out.append(
                f"<tr>"
                f"<td><a href='{url}' target='_blank'>{q[:80]}</a></td>"
                f"<td style='color:{color};font-weight:bold'>{sign}{move:.1f}%</td>"
                f"<td>{m.get('prev_price',0):.3f}</td>"
                f"<td>{m.get('current_price',0):.3f}</td>"
                f"<td>${m.get('liquidity',0):,.0f}</td>"
                f"</tr>"
            )
        return "\n".join(out)

    def rows_longshot(items):
        if not items:
            return "<tr><td colspan='4' style='text-align:center;color:#888'>없음</td></tr>"
        out = []
        for ls in items:
            q = ls.get("question", "")
            slug = ls.get("slug", "")
            url = f"https://polymarket.com/event/{slug}" if slug else "#"
            out.append(
                f"<tr>"
                f"<td><a href='{url}' target='_blank'>{q[:80]}</a></td>"
                f"<td>{ls.get('longshot_price',0):.3f}</td>"
                f"<td>{ls.get('hours_to_close','')}h</td>"
                f"<td>${ls.get('volume',0):,.0f}</td>"
                f"</tr>"
            )
        return "\n".join(out)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Polymarket Scanner</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, sans-serif; background: #0f1117; color: #e0e0e0; padding: 20px; }}
  h1 {{ font-size: 1.4rem; margin-bottom: 4px; }}
  .meta {{ color: #888; font-size: 0.85rem; margin-bottom: 24px; }}
  .section {{ margin-bottom: 32px; }}
  h2 {{ font-size: 1rem; color: #aaa; border-bottom: 1px solid #2a2a2a; padding-bottom: 6px; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; padding: 7px 10px; background: #1a1a2e; color: #aaa; font-weight: 500; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #1e1e1e; }}
  tr:hover td {{ background: #1a1a1a; }}
  a {{ color: #7eb8f7; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{ display: inline-block; padding: 2px 7px; border-radius: 3px; font-size: 0.75rem; }}
  .stat {{ display: inline-block; margin-right: 20px; }}
  .stat-num {{ font-size: 1.5rem; font-weight: bold; color: #7eb8f7; }}
  .stat-lbl {{ font-size: 0.75rem; color: #888; }}
  .stats {{ margin-bottom: 24px; }}
</style>
</head>
<body>
<h1>Polymarket Scanner</h1>
<div class="meta">마지막 스캔: {scanned_at} &nbsp;|&nbsp; 5분마다 자동 새로고침</div>

<div class="stats">
  <div class="stat"><div class="stat-num">{n_markets:,}</div><div class="stat-lbl">스캔한 마켓</div></div>
  <div class="stat"><div class="stat-num">{len(bargains)}</div><div class="stat-lbl">임박 기회</div></div>
  <div class="stat"><div class="stat-num">{len(movers)}</div><div class="stat-lbl">가격 변동</div></div>
  <div class="stat"><div class="stat-num">{len(longshots)}</div><div class="stat-lbl">롱샷</div></div>
</div>

<div class="section">
  <h2>임박 기회 (결제 6h 이내, 거의 확정인데 가격 차이 있음)</h2>
  <table>
    <thead><tr><th>마켓</th><th>엣지</th><th>현재가</th><th>마감</th><th>유동성</th></tr></thead>
    <tbody>{rows_bargain(bargains[:30])}</tbody>
  </table>
</div>

<div class="section">
  <h2>가격 변동 (전 스캔 대비 5% 이상 이동)</h2>
  <table>
    <thead><tr><th>마켓</th><th>변동</th><th>이전가</th><th>현재가</th><th>유동성</th></tr></thead>
    <tbody>{rows_mover(movers[:20])}</tbody>
  </table>
</div>

<div class="section">
  <h2>롱샷 (1-8% 저확률 + 거래량 있음)</h2>
  <table>
    <thead><tr><th>마켓</th><th>롱샷가</th><th>마감</th><th>거래량</th></tr></thead>
    <tbody>{rows_longshot(longshots[:30])}</tbody>
  </table>
</div>

<div class="meta" style="margin-top:40px">
  자동매매 아님 — 감지 전용 도구. 실제 투자 전 충분히 검증할 것.
</div>
</body>
</html>"""

    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"[dashboard] index.html 생성 완료 ({DOCS_DIR / 'index.html'})")


if __name__ == "__main__":
    generate()
