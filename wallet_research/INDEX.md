# Polymarket Bot Wallet Index

**Last updated**: 2026-04-20
**Sources**:
- Tier 1: Monthly leaderboard Top 20
- Tier 2: `data-api.polymarket.com/v1/leaderboard` (CRYPTO/POLITICS/CULTURE/SPORTS × offset)
**Screening**: `CRITERIA.md` 참조

---

## Tier 1 — 최상위 고래 ($1M+ 월 PnL, 참고용) [7개]

| # | 지갑 | 카테고리 | 월 PnL | 총 거래수 | 복제 우선순위 |
|---|---|---|---|---|---|
| 1 | [RN1](wallets/RN1.md) | 멀티리그 스포츠 | $2.20M | 54,824 | 중 |
| 2 | [sovereign2013](wallets/sovereign2013.md) | US 메이저 스포츠 | $1.88M | 40,263 | **높음** |
| 3 | [elkmonkey](wallets/elkmonkey.md) | NBA+시즌 선물 | $1.54M | 13,032 | 중 (하이브리드) |
| 4 | [CemeterySun](wallets/CemeterySun.md) | 스프레드+O/U | $1.50M | 5,233 | 중상 (자본 필요) |
| 5 | [432614799197](wallets/432614799197.md) | 유럽 축구 O/U | $1.50M | 4,548 | 낮음 (최근 DD) |
| 6 | [0x2a2C53](wallets/0x2a2C53.md) | 멀티+esports MM | $2.95M | 2,579 | 중 (esports 파트만) |
| 7 | [swisstony](wallets/swisstony.md) | 스포츠 hold-to-settle | $1.45M | ~82K (주장) | **최고** |

→ 자본·속도 moat가 크므로 현재 자본 ($500~3K)으로 복제 난이도 높음. 전략 카테고리 학습용.

---

## Tier 2 — 중위권 ($5K~$500K 월 PnL) [8개 카드, 16 지갑]

### 아키타입별

#### A. 5분 크립토 Up/Down HFT 클러스터 (7개 지갑, 1 카드)
- [crypto-hft-5min-cluster](wallets/crypto-hft-5min-cluster.md) — BTC/ETH/SOL/BNB/XRP 5분 바이너리
  - 0xB27BC932 ($490K / 17.9K trades / 381/d)
  - stingo43 ($372K / 3.5K / 77/d)
  - 0x04283f2F ($314K / 37K / **1,430/d**)
  - Marketing101 ($260K / 2.7K / 100/d)
  - 0x3A847382 ($256K / 18K / 692/d)
  - 0xbbc5zcZ96 ($160K / 7.2K / 57/d)
- [ohanism](wallets/ohanism.md) — 클러스터 중 **최고회전·최저마진** 별도 심화 (58K trades / 1,030/d / biggest win $2.3K)

#### B. 크립토 가격타겟 봇 (5분 아님, 시간~일 단위)
- [justdance](wallets/justdance.md) — "Will BTC reach $X?" hourly/daily 타겟. **GitHub Actions 5분 크론 호환** ← 네 스택에 가장 적합

#### C. Esports 전문
- [eanvanezygv](wallets/eanvanezygv.md) — **Dota 2 라이브 봇**. OpenDota API 무료 + 경쟁 희박

#### D. 스포츠 인플레이
- [Lilybaeum](wallets/Lilybaeum.md) — 테니스 Markov + 축구 Dixon-Coles
- [iDARKenjoyer](wallets/iDARKenjoyer.md) — NHL + NBA + Soccer 멀티 ML/스프레드 arb

#### E. Mention/메타 마켓
- [bipbipbop](wallets/bipbipbop.md) — Musk 트윗 카운트 등. 자본 $500~5K 최소 프로파일

### 미카드화 (중복 아키타입·약한 데이터)
- **vidarx** (0x2d8b401d2f) — CRYPTO #8, 16.9K trades / 115/d. 프로파일 SSR에 마켓 데이터 숨김. **크립토 HFT 클러스터 후보 가능성**
- **ferrariChampions2026** (0xfe787d2da7) — 테니스/축구, Lilybaeum과 아키타입 동일
- **VeryLucky888** (0x6d3c5bd139) — 축구 약하게, 신호 약함
- **winthunder** (0x161eb16874) — NBA, 일평균 6.5건 (봇 판별 2/3)

### 보더라인 분석 보류 (6개)
- rwo (biggest win $6.9M = 봇 아닐 가능성)
- kingofcoinflips, Car, APRIL26, Annica, Just2SeeULaugh (모두 거래수 낮거나 biggest win >$60K)

---

## 주요 패턴 발견 — Tier 1 vs Tier 2 비교

### 1. 크립토 HFT는 Tier 2에만 존재
- Tier 1 (월 $1M+): 크립토 5분 HFT **0개**, 전부 스포츠
- Tier 2 (월 $5K~$500K): **8개 지갑이 5분 크립토 HFT** (클러스터 7 + ohanism)
- **해석**: 5분 Up/Down은 중위권 경쟁 포화. 최상위로는 스케일 안 됨 (포지션 사이즈 제한)

### 2. 카테고리 스펙트럼
| 자본 | 아키타입 | 대표 |
|---|---|---|
| $500~5K | Mention/메타 | bipbipbop |
| $5K~50K | 크립토 HFT 5분, esports Dota | HFT 클러스터, eanvanezygv |
| $10K~100K | 크립토 가격타겟, 스포츠 인플레이 | justdance, Lilybaeum |
| $50K~500K | 멀티스포츠 ML arb | iDARKenjoyer, CemeterySun축소 |
| $500K+ | Tier 1 영역 | RN1, sovereign2013 |

### 3. 인프라 요구 스펙트럼
- **GitHub Actions 5분 크론 OK**: justdance, bipbipbop, eanvanezygv(부분)
- **Railway/VPS 필수**: 크립토 HFT 클러스터, Lilybaeum, ohanism
- 네 현재 스택 → justdance/bipbipbop/eanvanezygv 조합이 현실적

### 4. 계정 생성일 클러스터링
- 크립토 HFT 클러스터: 전부 **2026-02~03 생성** → Polymarket 5분 Up/Down 상품 출시 시점과 일치
- → 새 마켓 출시 시점에 **오픈소스 봇이 우르르 배포**됨. 2026년 후반에도 관찰 필요

---

## 네 프로젝트 연결 — 복제 우선순위 재정리

자본 $500~3K 기준:

1. **swisstony형 스포츠 hold-to-settle** (Tier 1) — 94~98c 그라인딩. 이미 설계 중
2. **justdance형 크립토 가격타겟** (Tier 2) — 5분 크론 호환. `polymarket-scanner` 확장
3. **eanvanezygv형 Dota 2 라이브** (Tier 2) — 블루오션, 무료 API. 중장기 과제
4. **bipbipbop형 Mention 마켓** (Tier 2) — 최소 자본 실험. 엣지 작음
5. (패스) 5분 크립토 HFT 클러스터 — 네 스택으로 속도 경쟁 불가

---

## 다음 액션 제안

- [ ] `justdance` 실제 포지션 히스토리 스크레이프 → 만기 분포·평균 포지션 크기 확인
- [ ] `eanvanezygv` Dota 2 매치별 진입 타이밍 분석 → OpenDota 피드 지연 측정
- [ ] 5분 HFT 클러스터 7개 지갑 **활동 타임스탬프 correlate** → 동일 봇 소스코드 여부 검증
- [ ] Polymarket 5분 Up/Down 시장 오픈소스 코드(@sopersone GitHub) 검토 → 클러스터 원본 봇 가능성
- [ ] 2026-05 월말 리더보드 재스캔 → 클러스터 엣지 수축 여부 추적
