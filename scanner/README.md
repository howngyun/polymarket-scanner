# Polymarket 스캐너

**자동매매 아님.** 기회 감지 + CSV 로그만. 돈 위험 0.

## 실행

```bash
cd "/Users/rian/Claude code/polymarket/scanner"
bash run.sh
```

정지: `Ctrl+C`

백그라운드로 돌리려면:

```bash
cd "/Users/rian/Claude code/polymarket/scanner"
nohup bash run.sh > logs/scanner.out 2>&1 &
echo $! > logs/scanner.pid
```

백그라운드 정지:

```bash
kill $(cat "/Users/rian/Claude code/polymarket/scanner/logs/scanner.pid")
```

## 감지 항목

| 타입 | 의미 |
|------|------|
| `near_resolution_bargain` | 결제 임박 + 거의 확정인데 가격 차이 있음 (속도 경쟁 치열) |
| `price_mover` | 직전 스냅샷 대비 큰 가격 변동 |
| `longshot` | 저확률(1-8%) + 거래량 있는 마켓 (캘리브레이션 후보) |

## 출력

- `logs/snapshots.csv` — 모든 마켓 가격 타임라인
- `logs/alerts.csv` — 감지된 기회
- 콘솔 — 실시간 출력

## 설정 조정

`config.py` 수정:
- 알림 너무 많음 → `NEAR_CERTAIN_PRICE`, `BARGAIN_GAP` 올리기
- 알림 너무 적음 → 내리기
- 스캔 주기 변경 → `SCAN_INTERVAL_SECONDS`

## 다음 단계

1. 1-2주 돌리면서 `alerts.csv` 관찰
2. 어떤 알림이 실제로 돈 됐을지 **손으로** 검증 (체결가 vs 결제가)
3. 패턴 보이면 → 페이퍼 트레이더 모듈 추가
4. 페이퍼에서 수익 검증되면 → 소액 실전
