---
wallet: swisstony
username: "@swisstony"
join_date: 2025-07
category: Sports (Soccer Europe/SA, Tennis ATP, NHL)
monthly_pnl_usd: 1448969
monthly_volume_usd: 64510589
biggest_win_usd: 83345
total_predictions: unknown (448K views shown)
claimed_cumulative_pnl_usd: 5604411
claimed_cumulative_trades: 82000
bot_score: 3/3
confidence: HIGH
fetched_on: 2026-04-20
referenced_in_tweets:
  - "https://x.com/Mikocrypto11/status/2046099528445837784"
---

# swisstony — 스포츠 레이트스테이지 hold-to-settle 봇

## 봇 판별 점수 (3/3)
- ✓ 누적 거래 많음 (Mikocrypto 인용 82K, 월 볼륨 $64.5M)
- ✓ 최근 30일 활발 (40+개 오픈 포지션)
- ✓ 스포츠 단일 카테고리

## 전략 본체 (추정 — 외부 분석 포함)

**Mikocrypto 공개 분해**: 3가지 구조 반복
1. **Hold to settle**: 61c 매수 → $1 정산 → $0.39/주 차익 (누적 $494M 거래량 → ~$4.96M 이익)
2. (나머지 2구조는 트윗 잘려있음)

**구조 해석**
- 레이트스테이지 (경기가 사실상 결정된 상태) 시점 시장가 = 85~95c
- 유동성 공급자들이 **정산 전에 현금화하려고** sub-$1 매도 호가 남김 → 봇이 sweep → 정산까지 홀드
- **거의 무위험 arb** (진짜 꼬리 이벤트만 주의)

## 실행 요건

| 항목 | 요구수준 |
|---|---|
| 자본 | $50K~500K (현재 $66.8K 포지션, biggest $83K) |
| 속도 | **초 단위로도 충분** (레이트스테이지는 ms 경쟁 X) |
| 데이터 | SofaScore/ESPN/ATP Live + Polymarket 호가 |
| 모델 | 경기 상태 → 승리확률 (Markov 테니스, Dixon-Coles 축구) |
| 인프라 | VPS 1대, 상시 프로세스 |

## 복제 난이도: **중 — 가장 복제 가능성 높은 카테고리**
- 속도 요구 낮음 → GitHub Actions 5분 주기로도 부분 커버 가능
- 자본 진입장벽 낮음 → $1K로도 소규모 실험 가능
- 리그별 도메인 튜닝이 moat

## 리스크
- **테일 역전**: 3-0 리드에서 역전골 2개 — 드물지만 발생
- 분석 시점 1D PnL **-$34,529** → 테일 이벤트 예시
- 대응: Kelly 분수 낮게 + 이벤트별 max-loss cap

## 참고 포지션
- Real Madrid 스프레드: $5,806
- Argentina 리그 O/U: $5,673
- 테니스/축구 매치: $800~3,000 소형 다수

## 신뢰도 노트
- **너의 94-98c NO 그라인딩 전략과 본질적으로 같은 구조 (크립토 버전)**
- 복제 우선순위 **최고**
