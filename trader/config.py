"""BTC 2분 전략 트레이더 설정."""
import os

# ============ 실전/페이퍼 모드 ============
# LIVE_TRADING=1 환경변수 설정 시만 실거래. 기본은 페이퍼.
LIVE_TRADING = os.environ.get("LIVE_TRADING", "0") == "1"

# ============ 자본 관리 ============
STARTING_CAPITAL = float(os.environ.get("STARTING_CAPITAL", "70"))
MAX_POSITION_PCT = 0.15      # 건당 최대 자본 15% (Quarter Kelly 근사)
MAX_CONCURRENT_POSITIONS = 3  # 동시 오픈 포지션 수
MIN_BET_USD = 1.0            # 최소 베팅 (Polymarket 제약)
MAX_BET_USD = 10.0           # 건당 최대 베팅 (소액 기간)

# ============ 엣지 기준 ============
MIN_EDGE_PCT = 0.05          # 5%p 이상 엣지만 진입
MIN_MARKET_LIQUIDITY = 500   # 유동성 $500 이상
MAX_SLIPPAGE_PCT = 0.02      # 슬리피지 2% 이상이면 스킵

# ============ 시간 필터 ============
MIN_SECONDS_TO_CLOSE = 60    # 결제 60초 전 이내만
MAX_SECONDS_TO_CLOSE = 180   # 결제 180초 전 이전은 불확실성 큼
# → 마감 1-3분 전 구간 타깃

# ============ 변동성 파라미터 ============
VOLATILITY_WINDOW_SEC = 900  # 최근 15분 데이터로 변동성 추정
VOLATILITY_MIN = 0.3         # 연 30% (저변동성 방어)
VOLATILITY_MAX = 2.0         # 연 200% (이상치 캡)

# ============ 리스크 게이트 ============
DAILY_LOSS_LIMIT_USD = 10    # 일 -$10 손실 도달 시 중단
DRAWDOWN_LIMIT_PCT = 0.30    # 시작 대비 30% 손실 시 완전 정지
MAX_TRADES_PER_HOUR = 20     # 과도 거래 방지

# ============ API ============
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/klines"
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com/markets"
POLYMARKET_CLOB_URL = "https://clob.polymarket.com"

# Polymarket 인증 (실거래 시만 필요)
POLYMARKET_API_KEY = os.environ.get("POLYMARKET_API_KEY", "")
POLYMARKET_API_SECRET = os.environ.get("POLYMARKET_API_SECRET", "")
WALLET_PRIVATE_KEY = os.environ.get("WALLET_PRIVATE_KEY", "")

# ============ 페이퍼 모드 시뮬 ============
PAPER_FILL_RATE = 0.70       # 페이퍼에서 70%만 체결 가정 (리뷰어 지적)
PAPER_SLIPPAGE_PCT = 0.005   # 페이퍼 체결가에 0.5% 슬리피지 적용

# ============ 경로 ============
from pathlib import Path
ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs"
TRADES_DIR = DOCS / "trades"
TRADES_DIR.mkdir(parents=True, exist_ok=True)
PAPER_LEDGER = TRADES_DIR / "paper_ledger.json"
LIVE_LEDGER = TRADES_DIR / "live_ledger.json"
STATE_FILE = DOCS / "trader_state.json"
