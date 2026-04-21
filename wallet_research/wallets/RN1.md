---
wallet: RN1
username: "@rn1"
join_date: 2024-12
category: Sports (Soccer / Tennis / Baseball / NHL / NBA)
monthly_pnl_usd: 2196835
monthly_volume_usd: 98772702
biggest_win_usd: 242700
total_predictions: 54824
bot_score: 3/3
confidence: HIGH
fetched_on: 2026-04-20
---

# RN1 — 고빈도 스포츠 멀티리그 봇

## 봇 판별 점수 (3/3)
- ✓ 누적 거래 **54,824건** — 16개월간 **하루 평균 ~114건**
- ✓ 최근 30일 일평균 >> 20건 (월 거래량 $98M 기준 상시 활동)
- ✓ 단일 카테고리 집중 (스포츠 100%, 멀티리그 분산)

## 전략 본체 (추정)

**가설 A — 전 리그 인플레이 가격 아비트라지 (최유력)**
- 브라질 Série A, 포르투갈 Liga, 아르헨티나 Primera, ATP, MLB, NHL, NBA 등 **15+ 리그 동시 스캔**
- 각 리그에 대해 closed-form 확률 모델 (테니스: Markov, 축구: Dixon-Coles, 야구: Win-Prob added)
- 시장 호가 vs 모델 확률 편차 > threshold 시 진입
- 포지션 사이즈 $500~5,000 수준 (현재 $238K / 54K 거래 ≈ 건당 $4~5K 회전)

**가설 B — Over/Under 그라인딩**
- 대표 수익 포지션: "Over 2.5 골" 103% 수익, "Over 3.5 골" 115% 수익 → **O/U 시장 편중** 시사
- O/U 모델은 리그별 평균 득점률 + 실시간 xG → Poisson 분포로 계산 가능
- Polymarket O/U 시장은 유럽 메이저 리그 제외하면 호가가 덜 효율적

**이례 지점**: 총 볼륨 $98M인데 biggest win은 $242K. 이건 **고회전·저마진** 전략 표시. MM/late-stage arb 섞인 구조로 추정.

## 실행 요건

| 항목 | 요구수준 |
|---|---|
| 자본 | $200K+ (현재 포지션 규모 기준) |
| 속도 | **초 단위면 충분** (분 단위로도 가능). 밀리초 필요 X |
| 데이터 | 리그별 라이브 피드 (SofaScore 비공식 + ATP Live + MLB Gameday). 월 $0~$200 |
| 모델 | 리그별 확률 모델 5~10개. 구현 2~4주 |
| 인프라 | VPS 1대, 상시 프로세스, Polymarket CLOB WS |
| 도메인 | **리그별 튜닝이 moat** — 브라질 3부 리그 같은 비주류가 특히 엣지 큼 |

## 복제 난이도: **중**
- 수학은 공개 (Markov 테니스, Poisson 축구)
- 진짜 장벽은: 라이브 피드 계약 + 리그별 상수 추정 + 인벤토리 관리

## 참고 포지션
- Red Bull Bragantino vs Remo **Over 2.5** → +103% ($44,744 수익)
- Clement Chidekh vs Coleman Wong (ATP) → +78.77% ($9,037)
- SC Braga vs Famalicão **Over 3.5** → +115.51% ($3,957)

## 신뢰도 노트
- 지갑/닉 실재, 54K 거래는 사람 불가능 → 봇 확실
- **전략 추정은 가설**. O/U 편중은 데이터로 지지됨, 하지만 내부 파라미터(threshold, size rule)는 블랙박스
- 복제 시도 시 **리그별 백테스트 먼저** — 브라질 3부 리그가 효율적 시장이 되면 엣지 소멸
