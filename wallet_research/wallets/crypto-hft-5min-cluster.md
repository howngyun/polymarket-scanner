---
cluster: crypto-hft-5min
wallets:
  - 0xB27BC932 (0xb27bc932bf8110d8f78e55da7d5f0497a18b5b82)
  - stingo43 (0x0006af12cd4dacc450836a0e1ec6ce47365d8c63)
  - 0x04283f2F (0x04283f2fef49d70d8c55ab240450d17a65bf85b1)
  - ohanism (0x89b5cdaaa4866c1e738406712012a630b4078beb)
  - Marketing101 (0x8c901f67b036b5eebab4e1f2f904b8676743a904)
  - 0x3A847382 (0x3a847382ad6fff9be1db4e073fd9b869f6884d44)
  - 0xbbc5zcZ96 (0x45bc74efa620b45c02308acaecdff1f7c06f978b)
category: Crypto (BTC/ETH/SOL/BNB/XRP 5-minute "Up or Down")
tier: 2
fetched_on: 2026-04-20
---

# 5-min Crypto Up/Down HFT 클러스터 (7개 지갑)

Tier 1에는 **한 개도 없었던** 아키타입. 중위권에서 완전히 새로 나옴.

## 클러스터 공통 프로파일

| 지갑 | 월 PnL | 거래수 | 일평균 | biggest win | 활동일수 |
|---|---|---|---|---|---|
| 0xB27BC932 | $490K | 17,905 | 381/d | $18K | 47일 |
| stingo43 | $372K | 3,524 | 77/d | $15K | 46일 |
| 0x04283f2F | $314K | 37,174 | **1,430/d** | $27K | 26일 |
| ohanism | $294K | **58,684** | 1,030/d | $2K | 57일 |
| Marketing101 | $260K | 2,690 | 100/d | $24K | 27일 |
| 0x3A847382 | $256K | 17,986 | 692/d | $8K | 26일 |
| 0xbbc5zcZ96 | $160K | 7,246 | 57/d | $10K | 127일 |

**공통점**:
- 전부 `"BTC/ETH/SOL/BNB/XRP Up or Down - [date], [HH:MM]-[HH:MM+5] ET"` 시장
- 일평균 거래 77~1,430건 → **사람 불가, 봇 확정**
- biggest win 대부분 $2K~$27K → **포지션 크기 작고 반복**
- 계정 나이 26~127일 → **전부 최근 6개월 이내 신규 오픈**

## 전략 본체 (강력 추정)

**구조**: Polymarket의 5분 바이너리 옵션 시장을 **Black-Scholes/변동성 모델**로 공정가 계산 → 호가 편차 있을 때 진입.

```
공정가 = N(d1) where d1 = (ln(S/K) + (σ²/2)T) / (σ√T)
```

- 실시간 BTC/ETH spot 가격 (Binance/Coinbase/Kraken WebSocket)
- 5분짜리 바이너리이므로 T = 300초 / 연율 환산
- IV는 최근 5분 실현 변동성 or BVIV
- 공정가 > 시장 YES + 수수료 → YES 매수
- 공정가 < 시장 NO + 수수료 → NO 매수

**왜 새 계정인가**: 2026년 초 Polymarket이 5-min Up/Down 시장을 정식 상품화한 시점에 맞춰 **동일 전략 돌리는 봇들이 우르르 오픈**. 이전에는 hourly/daily만 있었음.

## 실행 요건

| 항목 | 요구수준 |
|---|---|
| 자본 | $5K~50K (회전 빠름, 포지션당 $100~$2K) |
| 속도 | **초 단위** — 5분 바이너리는 만기 30~60초 전이 스위트스팟 |
| 데이터 | Binance/Coinbase WebSocket (spot), Polymarket CLOB WebSocket |
| 모델 | Black-Scholes 바이너리 + 최근 변동성 추정 |
| 인프라 | **VPS 상시 프로세스** + WebSocket 연결 유지. GitHub Actions 5분 주기로는 **부분만 가능** (만기 임박 시점 캐치 못함) |

## 복제 난이도: **중상**

- 모델 자체는 학부 금융공학 수준 — 공개 수두룩
- **moat = 속도와 상시 가동**. GitHub Actions로는 어려움. Railway/VPS 필수
- **7개 봇 동시 존재 = 경쟁 이미 진행 중**. 엣지 수축 주의
- ohanism (biggest win $2K, 58K trades) = **초저마진 고회전** 프로파일 → MM 또는 거의 arb 수준

## 리스크

- 변동성 급변(뉴스 이벤트) 시 모델 이탈 → **이벤트 블랙아웃 필요**
- Polymarket 수수료 바뀌면 엣지 소멸
- 7개 봇이 같은 시장에 몰리면 스프레드 축소 → 수익률 감소 진행형

## 네 전략과의 관계

- 네 `polymarket-scanner`가 목표로 하는 **BTC 5분 트레이더**와 직접 경쟁 클래스
- 하지만 GitHub Actions 5분 크론으로는 만기 30초 전 타이밍 못 잡음 → **구조적 한계**
- 권장: 이 카테고리 복제하려면 **Railway + WebSocket 필수**, 아니면 swisstony형 hold-to-settle로 가는 게 더 현실적

## 신뢰도 노트

- ohanism `@seemeohan` 트위터 핸들 노출 — 유일하게 공개 신원
- 나머지 6개는 익명. 동일인 여러 지갑 or 동일 오픈소스 봇 사본일 가능성 높음
- 코드 공개 소스 후보: @sopersone GitHub (노션 스크랩에 확인됨)
