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
MAX_CONCURRENT_POSITIONS = 5  # 동시 오픈 포지션 수 ($500 기준 늘림)
MIN_BET_USD = 1.0            # 최소 베팅 (Polymarket 제약)
MAX_BET_USD = 50.0           # 건당 최대 베팅 ($500 × 10%)

# ============ 전략 스위치 ============
# 워크플로우에서 전략별 활성/비활성 제어
STRATEGY_HIGH_PROB_NO = True     # 94-98c NO 그라인딩
STRATEGY_CROSS_MARKET = True     # Cross-Market Arbitrage
STRATEGY_LEGACY_BTC   = False    # 기존 BTC 2분 (폐기)

# ============ 전략 1: 94-98c NO 그라인딩 ============
HP_NO_MIN_PRICE = 0.94       # NO 최소 가격 (94c)
HP_NO_MAX_PRICE = 0.98       # NO 최대 가격 (98c)
HP_NO_MIN_LIQUIDITY = 1000   # 최소 유동성 $1K (슬리피지 방어)
HP_NO_MIN_SECONDS_TO_CLOSE = 3600           # 1시간 이상 남은 것 (너무 가까우면 오라클 분쟁 리스크)
HP_NO_MAX_SECONDS_TO_CLOSE = 30 * 86400     # 30일 이내 (Eurovision 등 중기 이벤트 포함)
HP_NO_CATEGORIES = ("weather", "temperature", "sports")  # 이벤트 기반만
HP_NO_MAX_POSITION_PCT = 0.05  # 건당 5% (음의 왜도 방어 — 엄격)

# ============ 전략 2: Cross-Market Arbitrage ============
# 같은 사건 관련 마켓 간 확률 불일치 포착
CM_MIN_INCONSISTENCY_PCT = 0.03   # 3%p 이상 불일치만
CM_MIN_LIQUIDITY = 500
CM_MAX_SECONDS_TO_CLOSE = 180 * 86400  # 180일 이내 (정적 차익은 수렴 기다림, 긴 마켓 OK)
CM_MAX_POSITION_PCT = 0.10

# ============ 공통 엣지 기준 ============
MIN_EDGE_PCT = 0.03          # 3%p 이상 엣지 (기존 5%에서 완화, 저변동 전략)
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
