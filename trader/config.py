"""Polymarket 멀티 전략 트레이더 설정.

2026-04-18 업데이트:
- BTC 2분 전략 → 멀티 전략 (94-98c NO + Cross-Market Arb) 로 피봇
- 페이퍼 슬리피지 현실화 (0.5% → 2%)
- 페이퍼 가상 자본 $70 → $500
"""
import os

# ============ 실전/페이퍼 모드 ============
# LIVE_TRADING=1 환경변수 설정 시만 실거래. 기본은 페이퍼.
LIVE_TRADING = os.environ.get("LIVE_TRADING", "0") == "1"

# ============ 자본 관리 ============
STARTING_CAPITAL = float(os.environ.get("STARTING_CAPITAL", "500"))
MAX_POSITION_PCT = 0.10      # 건당 최대 자본 10% (기존 15%에서 보수화)
MAX_CONCURRENT_POSITIONS = 3  # 동시 오픈 포지션 수 (블랙스완 1방 방어)
MIN_BET_USD = 1.0            # 최소 베팅 (Polymarket 제약)
MAX_BET_USD = 50.0           # 건당 최대 베팅 ($500 × 10%)

# ============ 전략 스위치 ============
# 워크플로우에서 전략별 활성/비활성 제어
STRATEGY_HIGH_PROB_NO = True     # 94-98c NO 그라인딩 (swisstony 아키타입)
STRATEGY_CROSS_MARKET = True     # Cross-Market Arbitrage (CemeterySun 축소판)
STRATEGY_CRYPTO_PRICE_TARGET = True  # 크립토 가격타겟 양방향 (justdance 아키타입, 2026-04-21)
STRATEGY_ESPORTS_DOTA = os.path.exists(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "dota_win_v0.json")
)  # 모델 파일 있으면 자동 ON (eanvanezygv 아키타입)
STRATEGY_LEGACY_BTC   = False    # 기존 BTC 2분 (폐기)

# ============ 전략 1: 94-98c NO 그라인딩 ============
HP_NO_MIN_PRICE = 0.94       # NO 최소 가격 (94c)
HP_NO_MAX_PRICE = 0.98       # NO 최대 가격 (98c)
HP_NO_MIN_LIQUIDITY = 5000   # 최소 유동성 $5K (슬리피지 방어 — 얕은 책 제외)
HP_NO_MIN_SECONDS_TO_CLOSE = 3600           # 1시간 이상 남은 것 (너무 가까우면 오라클 분쟁 리스크)
HP_NO_MAX_SECONDS_TO_CLOSE = 7 * 86400      # 7일 이내 (크립토 BS 모델 유효 범위)
HP_NO_MAX_POSITION_PCT = 0.05  # 건당 5% (음의 왜도 방어 — 엄격)

# --- Strategy 3: Crypto Price Target (CPT) — justdance 아키타입 ---
CPT_MIN_SECONDS_TO_CLOSE = 3600          # 1시간 이상 남은 것
CPT_MAX_SECONDS_TO_CLOSE = 30 * 86400    # 30일 이내 (BS 모델 신뢰 구간)
CPT_MIN_EDGE_PCT = 0.05                  # 5%p 이상 엣지 (슬리피지+수수료 4% 커버)
CPT_MIN_LIQUIDITY = 5000                 # 최소 유동성 $5K
CPT_KELLY_FRACTION = 0.25                # 0.25 Kelly (full Kelly 금지)
CPT_MAX_POSITION_PCT = 0.08              # 건당 자본 8% 상한 (HP_NO의 5%보다는 공격적)

# --- Strategy 4: Esports Dota 2 (DOTA) — eanvanezygv 아키타입 ---
DOTA_MIN_LIVE_MINUTES = 15               # early segment AUC 0.68 → 15min 이상만 진입 (mid/late는 AUC 0.85/0.89)
DOTA_MIN_EDGE_PCT = 0.06                 # Dota 시장은 스프레드 큼 → 6%p 이상
DOTA_MIN_LIQUIDITY = 2000                # Dota 시장 유동성 얕음 → 낮게
DOTA_MAX_POSITION_PCT = 0.05             # 보수적 (도메인 검증 전)
DOTA_OPENDOTA_BASE = "https://api.opendota.com/api"  # 무료 (rate: 60req/min)

# ============ 뉴스/이벤트 회피 블랙아웃 (수동 업데이트) ============
# ISO 8601 UTC 포맷. 해당 시각 ±NEWS_BLACKOUT_HOURS 이내에는 크립토 마켓 진입 금지.
# 사용자 수동 업데이트 — 까먹으면 구멍. 추후 API 자동화 필요.
NEWS_BLACKOUT_EVENTS = [
    # FOMC (참고용 — 실제 날짜 확인 후 업데이트)
    # "2026-05-07T18:00:00+00:00",  # FOMC May 2026
    # "2026-06-18T18:00:00+00:00",  # FOMC June 2026
    # CPI
    # "2026-05-13T12:30:00+00:00",  # CPI Apr 2026 release
]
NEWS_BLACKOUT_HOURS = 12  # 이벤트 ±12시간 진입 금지

# ============ BS 모델 안전장치 ============
# fat-tail 보정: BS가 계산한 P(YES)에 최소 floor 부여.
# 이유: BS는 로그정규 가정 → 크립토 점프/블랙스완 과소평가.
# 0.005 = "극단 OTM이라도 최소 0.5% 확률은 존재" 로 가정.
P_YES_FLOOR = 0.005

# ============ 전략 2: Cross-Market Arbitrage ============
# 같은 사건 관련 마켓 간 확률 불일치 포착
CM_MIN_INCONSISTENCY_PCT = 0.03   # 3%p 이상 불일치만
CM_MIN_LIQUIDITY = 500
CM_MAX_SECONDS_TO_CLOSE = 180 * 86400  # 180일 이내 (정적 차익은 수렴 기다림, 긴 마켓 OK)
CM_MAX_POSITION_PCT = 0.10

# ============ 공통 엣지 기준 ============
MIN_EDGE_PCT = 0.04          # 4%p 이상 엣지 (슬리피지 2% + 수수료 2% 커버)
MIN_MARKET_LIQUIDITY = 500
MAX_SLIPPAGE_PCT = 0.02

# ============ 리스크 게이트 ============
DAILY_LOSS_LIMIT_USD = 50    # 일 -$50 손실 도달 시 중단 ($500의 10%)
DRAWDOWN_LIMIT_PCT = 0.20    # 시작 대비 20% 손실 시 완전 정지
MAX_TRADES_PER_HOUR = 20

# ============ API ============
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com/markets"
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"

# 가격 피드 (레거시 BTC 전략용 — 더 이상 안 씀)
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/klines"

# Polymarket 인증 (실거래 시만 필요)
POLYMARKET_API_KEY = os.environ.get("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET = os.environ.get("POLYMARKET_API_SECRET", "")
WALLET_PRIVATE_KEY = os.environ.get("WALLET_PRIVATE_KEY", "")

# ============ 페이퍼 모드 시뮬 (현실화) ============
PAPER_FILL_RATE = 0.70       # 70% 체결
PAPER_SLIPPAGE_PCT = 0.02    # 2% 슬리피지 (기존 0.5% → 현실화)

# ============ 레거시 BTC 2분 (호환성 위해 유지 — 곧 제거) ============
MIN_SECONDS_TO_CLOSE = 60
MAX_SECONDS_TO_CLOSE = 180
VOLATILITY_WINDOW_SEC = 900
VOLATILITY_MIN = 0.3
VOLATILITY_MAX = 2.0

# ============ 경로 ============
from pathlib import Path
ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
TRADES_DIR = DOCS / "trades"
TRADES_DIR.mkdir(parents=True, exist_ok=True)
PAPER_LEDGER = TRADES_DIR / "paper_ledger.json"
LIVE_LEDGER = TRADES_DIR / "live_ledger.json"
STATE_FILE = DOCS / "trader_state.json"
