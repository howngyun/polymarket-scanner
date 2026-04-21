---
wallet: "0xf68a281980f8c13828e84e147e3822381d6e5b1b"
username: iDARKenjoyer
join_date: unknown
category: Sports (NHL + NBA + Soccer multi-sport)
monthly_pnl_usd: 217192
monthly_volume_usd: unknown
biggest_win_usd: 61550
total_predictions: 10498
daily_freq: 24
bot_score: 3/3
confidence: HIGH
fetched_on: 2026-04-20
tier: 2
archetype: multi-sport-ml-arb
---

# iDARKenjoyer — 멀티스포츠 ML/스프레드 arb

## 판별 점수 (3/3)
- ✓ 10,498 거래
- ✓ 일평균 24건
- ✓ 스포츠 집중 (NHL 13 / NBA 9 / Soccer 6 — 다각화)

## 전략 본체 (추정)

**CemeterySun(Tier 1) 축소판**:
- 한 경기의 ML(머니라인) / 스프레드 / O/U 세 시장 간 **확률 정합성 arb**
- 예: ML 승률 65%인데 스프레드 라인으로 역산한 승률 72% → 한쪽 엣지
- Polymarket은 세 시장을 **별도 마켓**으로 제공 → 호가 비동기 시 arb 기회

**왜 NHL이 많은가**:
- NHL은 변동성 높고 공개 모델 많음 (Elo, Corsi, xG for hockey)
- NBA는 경쟁 치열(Tier 1 sovereign2013 등)
- NHL은 중위권에서 덜 포화

## 실행 요건

| 항목 | 요구수준 |
|---|---|
| 자본 | $10K~100K (biggest win $61K) |
| 속도 | **초~분 단위** — 세 시장 호가 동시 스냅샷 필요 |
| 데이터 | ESPN API, NHL API (무료), FiveThirtyEight-style 모델 |
| 모델 | Elo + 경기 내 이벤트 기반 확률 업데이트 |
| 인프라 | VPS + WebSocket |

## 복제 난이도: **중**

- 모델 공개 (Elo, xG 기반)
- CemeterySun 대비 **포지션 크기 10분의 1 수준** → 자본 진입장벽 낮음
- NHL 중심 복제가 레드오션 회피 포인트

## 리스크

- 3-시장 정합성 arb은 하나만 틀려도 양쪽 손실
- 스프레드 시장 유동성 얕으면 언와인드 어려움
- 플레이오프 시즌 vs 정규시즌 엣지 차이

## 신뢰도 노트

- Tier 1 CemeterySun/elkmonkey와 같은 archetype. 자본 1/10 체급
- **자본 $10K+ 돌파 후 복제 후보**
