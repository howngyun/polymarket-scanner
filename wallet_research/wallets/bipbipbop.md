---
wallet: "0xc4d5a24a240ec9f52669e3251e0473fd0c5687cf"
username: bipbipbop
join_date: unknown
category: Politics/Culture (mention markets, Musk tweet counts, daily events)
monthly_pnl_usd: 49771
monthly_volume_usd: unknown
biggest_win_usd: 3739
total_predictions: 3233
daily_freq: 21
bot_score: 3/3
confidence: HIGH
fetched_on: 2026-04-20
tier: 2
archetype: mention-markets-grinder
---

# bipbipbop — Mention/메타 마켓 그라인더

## 판별 점수 (3/3)
- ✓ 3,233 거래
- ✓ 일평균 21건 (경계선이지만 통과)
- ✓ Mention/Culture 집중

## 전략 본체 (추정)

**특이 카테고리**: "Will Elon Musk post 65-89 tweets from April 18 to April 20?" 같은 **mention markets**와 일일 정치/문화 이벤트

**전략 가설**:
1. **Musk 트윗 카운터**: 실시간 X API / Nitter / twscrape로 카운트 → 만기 임박 정답 비닝
2. **데일리 뉴스 이벤트**: "Trump will say X word in speech today?" 류 → 실시간 transcript + NLP
3. Mention 마켓은 **정량적 정답이 나중에 결정** → hold-to-settle 스타일 가능

## 실행 요건

| 항목 | 요구수준 |
|---|---|
| 자본 | **$500~5K** (biggest win $3.7K = 소규모) |
| 속도 | 분 단위 |
| 데이터 | X API / Nitter (트윗 카운트), 뉴스 RSS, transcript feeds |
| 모델 | 간단한 카운팅/회귀 |
| 인프라 | **GitHub Actions 5분 크론 완벽 호환** |

## 복제 난이도: **낮~중 — 자본 낮고 인프라 간단**

- biggest win $3.7K = **$500 자본으로도 비례 복제 가능**
- Mention 마켓은 Top 20 봇이 관심 없음 → **경쟁 희박**
- X API 무료티어 제한 문제는 있음 (twscrape 우회 가능)

## 리스크

- PnL $50K/월로 클러스터 중 가장 작음 — **엣지 좁음**
- X API 정책 변경 시 데이터 공급 중단 위험
- 마켓 수 적음 → 스케일 한계

## 신뢰도 노트

- **자본 $500~3K 구간에 가장 잘 맞는 프로파일** (너의 현재 자본 구간)
- 하지만 엣지가 작아 월 수익 기대치도 낮음
- swisstony/justdance 대비 **보조 전략**으로 적합, 메인으로는 부족
