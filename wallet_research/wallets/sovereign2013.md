---
wallet: sovereign2013
username: "@sovereign2013"
join_date: 2025-07
category: Sports (NBA / MLB / NHL / Tennis)
monthly_pnl_usd: 1877713
monthly_volume_usd: 46993272
biggest_win_usd: 179100
total_predictions: 40263
bot_score: 3/3
confidence: HIGH
fetched_on: 2026-04-20
---

# sovereign2013 — US 메이저 스포츠 고빈도 봇

## 봇 판별 점수 (3/3)
- ✓ 누적 **40,263건** / 9개월 ≈ **일평균 149건**
- ✓ 최근 30일 일평균 >> 20건
- ✓ US 메이저 스포츠(NBA+MLB+NHL+ATP) 집중

## 전략 본체 (추정)

**가설 A — 라이브 인플레이 가격 수렴 arb**
- 경기 진행 중 스코어 변화에 따라 YES/NO 확률 변동
- sovereign의 모델이 호가보다 빨리 반영 → limit으로 포지션 잡고 시장이 따라올 때 청산 or 정산
- biggest win $179K는 단일 경기 레이트스테이지 확정성 매수로 추정 (예: 3-0 리드 9회말 85c 매수 → $1 정산)

**가설 B — 테니스 서브 홀드 확률 봇**
- ATP 시장에서 실시간 서브 홀드/브레이크 이벤트 기반 매치 승리 확률 업데이트
- 테니스는 closed-form(O'Malley)이 있어 구현 간단
- 노출 포지션: "Clement Chidekh 87.5¢" (대회 진출 확률 시장)

## 실행 요건

| 항목 | 요구수준 |
|---|---|
| 자본 | $50K~200K (현재 $16K 포지션, biggest $179K) |
| 속도 | 초 단위 (라이브 스코어 → 주문까지 1~5초) |
| 데이터 | ESPN/MLB Gameday/NHL API + ATP Live |
| 모델 | 스포츠별 3~5개. NBA는 scoreboard-based Win Prob 모델 (표준) |
| 인프라 | VPS, 상시 프로세스 |

## 복제 난이도: **중**
- NBA/MLB는 오픈소스 Win Prob 모델 존재 (nflfastR 스타일)
- 테니스도 표준 Markov 구현 공개
- moat는 **레이턴시 + 시장별 liquidity 맵**

## 참고 포지션
- "Clement Chidekh 87.5¢" (ATP) — 5,713주, +14%
- "Hawks 31.4¢" (NBA) — 포지션 지속 중
- "Red Sox 55¢" (MLB) — 소폭 이익

## 신뢰도 노트
- 40K 거래 / 9개월 = 확실한 봇
- 1일 PnL +$38,850 (페치 시점) — 지속적 수익 시그널
- RN1보다 **리그 다양성 낮고 US 메이저 집중** → 데이터 파이프 구축 부담 적음 → 복제 우선순위 **높음**
