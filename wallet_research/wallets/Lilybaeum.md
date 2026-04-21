---
wallet: "0x01c78f8873c0c86d6b6b92ff627e3802237ee995"
username: Lilybaeum
join_date: unknown
category: Sports (ATP/WTA Tennis > Soccer Europe > NBA/NHL 약간)
monthly_pnl_usd: 477827
monthly_volume_usd: unknown
biggest_win_usd: 78392
total_predictions: 15499
daily_freq: 176
bot_score: 3/3
confidence: HIGH
fetched_on: 2026-04-20
tier: 2
archetype: tennis-soccer-inplay
---

# Lilybaeum — 테니스+축구 인플레이 봇

## 판별 점수 (3/3)
- ✓ 15,499 거래
- ✓ **일평균 176건** (테니스 토너먼트 1주일 동안 100+ 매치)
- ✓ 테니스/축구 집중 (Madrid Open, ATP, 유럽 리그)

## 전략 본체 (추정)

**Markov 테니스 모델 + Dixon-Coles 축구**:
- 테니스: 포인트 단위 Markov 모델로 세트/매치 승률 계산 (Klaassen-Magnus)
- 축구: in-play xG + Dixon-Coles 스코어 예측
- Polymarket 라이브 호가 vs 모델 공정가 차이 arb

**swisstony와 비교**:
- swisstony: **late-stage hold-to-settle** (85~95c → $1)
- Lilybaeum: **전 경기 구간 arb** (호가 편차 있으면 어디서든 진입)
- 거래수 Lilybaeum(15K) vs swisstony(82K) → swisstony가 더 극단적 고회전

## 실행 요건

| 항목 | 요구수준 |
|---|---|
| 자본 | $20K~100K (biggest win $78K) |
| 속도 | **초 단위** (매 포인트 결과 반영) |
| 데이터 | SofaScore/ATP Live Scoring API, Understat xG |
| 모델 | 테니스 Markov + 축구 Dixon-Coles |
| 인프라 | VPS 상시 + WebSocket |

## 복제 난이도: **중상**

- 테니스 Markov 모델은 공개 (논문/GitHub 다수)
- **moat = 데이터 소스 + 튜닝**. ATP 공식 피드는 유료
- 무료 대안(SofaScore 스크레이프)은 딜레이·차단 리스크

## 리스크

- 테니스는 한 포인트에 확률 크게 변동 → 오발 진입 시 손실 큼
- 토너먼트 시즌(그랜드슬램) vs 비시즌 유동성 차이
- biggest win $78K = 단일 매치 큰 베팅도 있음

## 신뢰도 노트

- ferrariChampions2026 (소형 테니스 매치 집중)와 형제 프로파일
- **swisstony만큼은 아니지만 네 전략 카테고리와 밀접**
- 테니스 도메인 튜닝 + 3~5개 주요 리그만 타깃팅해도 소규모 복제 가능
