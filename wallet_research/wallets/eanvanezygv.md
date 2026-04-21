---
wallet: "0x9d94f602535e518ee1cb6aade0ca9569f1b1017d"
username: eanvanezygv
join_date: unknown
category: Esports (Dota 2 > CS/LoL > Soccer 약간)
monthly_pnl_usd: 345097
monthly_volume_usd: unknown
biggest_win_usd: 92186
total_predictions: 9834
daily_freq: 46
bot_score: 3/3
confidence: HIGH
fetched_on: 2026-04-20
tier: 2
archetype: esports-specialist
---

# eanvanezygv — Dota 2 전문 라이브 봇

## 판별 점수 (3/3)
- ✓ 9,834 거래
- ✓ 일평균 46건
- ✓ **포지션 20/50이 Dota 2** (PGL Wallachia, 각종 토너먼트)

## 전략 본체 (추정)

**Dota 2 라이브 승률 모델 arb**:
- 실시간 매치 데이터 (골드 리드, 킬 차이, 타워 상태, 로샨 쉴드) → 승리확률 계산
- Polymarket 라이브 호가와 편차 시 진입
- BO3/BO5 시리즈는 **게임 간 호가 슬로우** → 엣지 큼

**0x2a2C53 (Tier 1)의 esports 부분 전문화 버전**:
- 0x2a2C53는 esports를 '사이드메뉴'로 하면서 MM 주력
- eanvanezygv는 **esports가 메인 메뉴**. 월 PnL $345K로 전문성 입증

## 실행 요건

| 항목 | 요구수준 |
|---|---|
| 자본 | $10K~50K (biggest win $92K) |
| 속도 | **분 단위로 충분** — esports 시장은 전통 스포츠보다 호가 느림 |
| 데이터 | **OpenDota API (무료)**, Riot API (LoL), HLTV (CS) |
| 모델 | Dota 2 승률 모델 공개 다수 (GSI data, Stratz) |
| 인프라 | VPS 1대 or Railway |

## 복제 난이도: **중 — 강력 추천 카테고리**

- **OpenDota API 무료, 경쟁 적음, 모델 오픈소스**
- 전통 스포츠(NFL/NBA)는 이미 레드오션. **esports는 블루오션**
- GitHub Actions 5분 크론 + 매치 진행 중만 조회 → 복제 가능

## 리스크

- Dota 2 게임당 30~40분 → 포지션 홀드 시간 짧음 (OK)
- 메이저 토너먼트(The International) 시즌 vs 오프시즌 유동성 차이
- 라이브 피드 지연(2~5초)이 tournament 공식 피드 vs 일반 API 차이

## 신뢰도 노트

- **이 전략이 스포츠 중 가장 복제 가능성 높음**
- Tier 1 0x2a2C53와 묶어서 "esports 카테고리"로 심화 연구 권장
- 향후 액션: OpenDota API 써서 Polymarket Dota 시장 호가 편차 백테스트
