# Polymarket 자동화

prediction market 자동 트레이딩 시스템. 현재 **기획 단계** — 코드 없음.

## 현재 상태
- [ ] 엣지(edge) 정의
- [ ] 전략 1개 선정
- [ ] 드라이런 시뮬레이터
- [ ] 실제 주문 실행
- [ ] 모니터링·알림
- [ ] 리스크 관리

## 진행 원칙
1. **엣지 없으면 코드 X** — 무엇으로 돈 버는지 설명 못 하면 코딩 금지
2. **드라이런이 기본** — 실제 주문은 환경변수 플래그로만 활성화
3. **소액으로 시작** — $50~$200
4. **로그 전부 남기기** — 실수는 재현 가능해야 복구됨

## 구조 (계획)
```
polymarket/
├── data/           # 마켓 스냅샷, 히스토리
├── strategies/     # 전략별 모듈
├── execution/      # 주문 실행 (CLOB SDK 래퍼)
├── risk/           # 포지션 사이징, 한도
├── monitoring/     # 알림·리포팅
├── backtest/       # 과거 데이터 시뮬레이션
├── .env.example    # 시크릿 템플릿
└── requirements.txt
```

## 시크릿 (실제 코딩 시)
`.env` (git 무시):
```
POLYGON_PRIVATE_KEY=
POLYMARKET_API_KEY=
POLYMARKET_API_SECRET=
POLYMARKET_API_PASSPHRASE=
EXECUTE=false   # true로 바꾸기 전 세 번 생각
MAX_POSITION_USD=10
```

## 참고
- 공식 문서: https://docs.polymarket.com
- Python SDK: https://github.com/Polymarket/py-clob-client
- Skill 파일: `.claude/skills/polymarket/SKILL.md`
