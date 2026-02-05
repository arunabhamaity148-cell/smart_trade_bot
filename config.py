# config.py
# ========== TELEGRAM SETTINGS ==========
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
CHAT_ID = "YOUR_CHAT_ID_HERE"

# ========== BINANCE API ==========
BINANCE_API_KEY = "YOUR_API_KEY"
BINANCE_SECRET = "YOUR_SECRET"

# ========== MONITOR SETTINGS ==========
CHECK_INTERVAL = 10  # seconds
PRICE_HISTORY_LIMIT = 100

# ========== TP STRATEGY ==========
TP_STRATEGY = {
    'TP1_PERCENT': 30,
    'TP2_PERCENT': 30,
    'TP3_PERCENT': 40,
    
    'TP1_MOVE_SL_TO_BE': True,
    'TP2_MOVE_SL_TO_TP1': True,
    'TP3_MOVE_SL_TO_TP2': True,
}

# ========== ALERT THRESHOLDS ==========
ALERT_THRESHOLDS = {
    'TP_APPROACH': 0.80,      # 80% to TP
    'WARNING': 0.01,          # 1% against position
    'DANGER': 0.50,           # 50% to SL
    'CRITICAL': 0.25,         # 25% to SL
    'LIQUIDATION': 0.10,      # 10% to SL
    'NEAR_BE': 0.002,         # 0.2% to BE
    'RAPID_MOVE': 0.01,       # 1% in 5 min
}

# ========== COOLDOWNS (seconds) ==========
COOLDOWNS = {
    'DEFAULT': 60,
    'RAPID': 300,
    'TIME': 1800,
}
