# 전략 4: Dota 2 라이브 승률 arb — 설계 문서

**Created**: 2026-04-21
**Status**: 스캐폴딩 완료, 모델 학습 전 (STRATEGY_ESPORTS_DOTA=False)
**Reference 지갑**: [eanvanezygv](../wallet_research/wallets/eanvanezygv.md) — 월 PnL $345K, 9,834 trades, Dota 2 전문

## 왜 Dota 2인가

- wallet_research Tier 2 분석에서 **eanvanezygv가 Dota 2 단일 카테고리로 월 $345K** 입증
- Polymarket Top 20 봇 중 **esports 전문 봇 0개** → 블루오션
- **OpenDota API 무료** (60 req/min, 키 불필요)
- Dota 승률 모델 공개 자료 풍부 (OpenDota, Stratz, 논문)
- GitHub Actions 5분 크론 호환 (ms 경쟁 X)

## 승률 모델 v0 (학습 대상)

**입력**:
- `gold_adv` (radiant - dire 골드 차이)
- `xp_adv` (radiant - dire XP 차이)
- `net_kills` (킬 차이)
- `game_time` (경기 경과 초)
- `radiant_score`, `dire_score` (팀 스코어)

**출력**: P(radiant_win)

**형태**: 로지스틱 회귀 (시간 segment별 계수 분리 권장)

```
logit(p) = b0(t) + b1(t)*gold_adv + b2(t)*xp_adv + b3(t)*net_kills
t ∈ {early(0~15min), mid(15~30min), late(30min+)}
```

**학습 데이터**: OpenDota `/proMatches` → 각 매치의 매 60초 스냅샷 + 최종 결과. 약 5,000~10,000 경기

**검증**:
- 과거 3개월 프로매치 out-of-sample AUC > 0.85 목표
- 시간 segment별 calibration plot (예측 vs 실제 승률)

## 구현 단계

| 단계 | 작업 | 예상 |
|---|---|---|
| 1 | `opendota_client.py` 기본 래퍼 | ✅ 완료 2026-04-21 |
| 2 | `esports_dota.py` 스캐폴딩 (스캐너 + 시그널 구조) | ✅ 완료 2026-04-21 |
| 3 | 과거 프로매치 10K개 스냅샷 다운로드 → CSV | 1~2일 |
| 4 | 로지스틱 회귀 학습 + 시간 segment별 계수 | 1~2일 |
| 5 | `_predict_radiant_win_prob` 실 모델로 교체 + MODEL_TRAINED=True | 0.5일 |
| 6 | Polymarket question ↔ OpenDota live 매치 매칭 로직 정교화 (팀명 fuzzy) | 1일 |
| 7 | YES/NO ↔ radiant/dire 매핑 파서 (question 해석) | 0.5일 |
| 8 | 2주 페이퍼 테스트 | 2주 |

## 매칭 난제 (꼭 해결해야 함)

### 1. 팀명 표기 차이
- Polymarket: "Will Xtreme Gaming beat South America Rejects?"
- OpenDota: `radiant_team.team_name = "Xtreme Gaming"`, `dire_team.team_name = "SA Rejects"`
- → rapidfuzz 기반 token_sort_ratio 매칭, 임계값 80

### 2. YES/NO → radiant/dire 매핑
- 질문 파서 필요: "Will {팀A} beat {팀B}" → YES = 팀A 승리
- OpenDota의 radiant/dire 구분과는 무관 (coin flip)
- 따라서 팀명 매치한 뒤 **radiant가 팀A인지 팀B인지** 판별 필요

### 3. BO3/BO5 시리즈 시장
- Polymarket에 시리즈 단위 시장 존재 ("Will {팀A} win the series 2-0?")
- 단일 매치 모델로는 못 잡음. **1차 버전은 단일 매치(single map) 시장만 타깃**

### 4. 라이브 피드 지연
- OpenDota `/live`는 Valve GSI 피드 기반, 약 2~5초 지연
- Polymarket 호가도 비슷한 지연 → 큰 문제는 아님
- 단, 팀 파이트 직후 30초는 호가 급변 → 진입 금지 윈도우 필요

## 리스크

| 리스크 | 대응 |
|---|---|
| 메타 패치 변화 | 패치 날짜 blackout + 패치 이후 2주 재학습 |
| 소규모 토너먼트 유동성 얕음 | `DOTA_MIN_LIQUIDITY = $2K` 낮게 설정 |
| 모델 overfit | out-of-sample AUC 검증, 시간 segment별 조각 학습 |
| 사용자 본인 Dota 도메인 부족 | 모델 100% 자동화, 질적 판단 개입 금지 |

## 페이퍼 성공 기준 (2주)

- 월 수익률 **>10%** (Dota 시장 유동성 얕아 실전 수익률은 하회 예상)
- 승률 (arb 성공 %) > 58%
- 샘플 수 > 50건 (Dota 프로매치 시즌 빈도 상 2주면 OK)

## 실전 전환 조건

- 페이퍼 2주 수익률 > 10%
- 전체 자본 $1K 이상
- Polymarket V2 SDK 안정화 (2026-04-28 마이그레이션 후)
