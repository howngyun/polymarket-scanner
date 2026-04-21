---
wallet: "0xcc500cbcc8b7cf5bd21975ebbea34f21b5644c82"
username: justdance
join_date: unknown
category: Crypto (hourly/daily price target questions)
monthly_pnl_usd: 208743
monthly_volume_usd: unknown
biggest_win_usd: 86106
total_predictions: 16562
daily_freq: 22
bot_score: 3/3
confidence: MEDIUM-HIGH
fetched_on: 2026-04-20
tier: 2
archetype: crypto-price-target
---

# justdance — 크립토 시간별/일별 가격 타겟 봇

## 판별 점수 (3/3)
- ✓ 16,562 거래
- ✓ 일평균 22건
- ✓ 크립토 집중 (질문 유형: "Will Bitcoin dip to $X?", "Will ETH reach $Y?")

## 전략 본체 (추정)

**5분 Up/Down 클러스터와 다른 카테고리**:
- 질문 구조: "Will [coin] reach/dip to [price] by [date]?"
- 만기 **수시간~수일** (5분 아님)
- 호가가 가격 움직임에 느리게 반응 → **단순 EV 계산**으로 진입

**전략 가설**:
1. 실시간 spot vs 타겟 가격 거리 계산
2. GBM (Geometric Brownian Motion) 또는 바닐라 바이너리 모델로 정답 확률 계산
3. 시장 호가 < 모델 확률 - 수수료 → 매수, 반대도 동일
4. 만기까지 홀드 (hold-to-settle 유사)

## 실행 요건

| 항목 | 요구수준 |
|---|---|
| 자본 | $10K~100K (biggest win $86K 시사) |
| 속도 | **분 단위로 충분** — 만기 길어서 ms 경쟁 X |
| 데이터 | CoinGecko/Binance REST + Polymarket CLOB |
| 모델 | GBM + 역사적 변동성 or IV 서베이 |
| 인프라 | **GitHub Actions 5분 크론으로 충분** ← 중요 |

## 복제 난이도: **중 — 네 현재 스택으로 가능**

- **너의 `polymarket-scanner` 5분 크론과 완벽 호환**
- 속도 경쟁 없음
- 모델 공개
- biggest win $86K = 가끔 큰 방향성 베팅도 있음 → 리스크 관리 필요

## 리스크

- 5분 HFT 클러스터 대비 **거래 빈도 낮아 엣지 좁을 수 있음**
- 만기 길수록 방향성 리스크 노출
- Kelly 분수 낮게 + 최대 포지션 캡 필요

## 신뢰도 노트

- 이 지갑이 **너한테 가장 현실적인 복제 타깃**. swisstony(스포츠) + justdance(크립토 target) 두 개 병행이 합리적 후보
- 데이터 한계: monthly_volume 미확인, 만기 분포 수동 검증 필요
