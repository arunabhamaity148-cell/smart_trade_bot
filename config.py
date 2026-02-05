# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# ========== TELEGRAM ==========
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# ========== COINDCX API ==========
COINDCX_API_KEY = os.getenv('COINDCX_API_KEY')
COINDCX_SECRET = os.getenv('COINDCX_SECRET')
USE_PUBLIC_API = os.getenv('USE_PUBLIC_API', 'true').lower() == 'true'

# ========== RAILWAY ==========
PORT = int(os.getenv('PORT', 8080))

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
    'TP_APPROACH': 0.80,
    'WARNING': 0.01,
    'DANGER': 0.50,
    'CRITICAL': 0.25,
    'LIQUIDATION': 0.10,
    'NEAR_BE': 0.002,
    'RAPID_MOVE': 0.01,
}

# ========== COOLDOWNS ==========
COOLDOWNS = {
    'DEFAULT': 60,
    'RAPID': 300,
    'TIME': 1800,
}

# Validate required env vars
def validate_config():
    missing = []
    if not BOT_TOKEN:
        missing.append('BOT_TOKEN')
    if not CHAT_ID:
        missing.append('CHAT_ID')
    
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    print("✅ Configuration validated!")

validate_config()
