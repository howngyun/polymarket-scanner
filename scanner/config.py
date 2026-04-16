"""Scanner 설정. 값 조정하고 싶으면 여기만 고치면 됨."""

# 감지 임계값
NEAR_RESOLUTION_HOURS = 6         # 결제까지 N시간 이내면 "임박" 마켓 (짧을수록 진짜 임박)
NEAR_CERTAIN_PRICE = 0.97         # 한쪽 가격 >= 0.97 이어야 "거의 확정" (노이즈 감소)
BARGAIN_GAP = 0.015               # 확정가 - 시장가 차이가 이 이상이면 기회
MIN_LIQUIDITY = 1000              # 유동성 $1000 미만 마켓은 무시
MIN_VOLUME = 5000                 # 거래량 $5000 미만 무시
PRICE_MOVE_THRESHOLD = 0.05       # 스냅샷 간 5% 이상 움직이면 알림

# 스캔 주기
SCAN_INTERVAL_SECONDS = 300       # 5분마다

# Polymarket API
GAMMA_URL = "https://gamma-api.polymarket.com/markets"
PAGE_SIZE = 500                   # 한 번에 가져올 마켓 수

# 파일 경로
LOG_DIR = "logs"
SNAPSHOT_FILE = "logs/snapshots.csv"
ALERTS_FILE = "logs/alerts.csv"
