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

# ========== RAILWAY WEBHOOK ==========
PORT = int(os.getenv('PORT', '8080'))
RAILWAY_PUBLIC_DOMAIN = os.getenv('RAILWAY_PUBLIC_DOMAIN')

# Webhook URL auto-generate
WEBHOOK_URL = None
if RAILWAY_PUBLIC_DOMAIN:
    WEBHOOK_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}/webhook/{BOT_TOKEN}"

# ========== SETTINGS ==========
CHECK_INTERVAL = 10

TP_STRATEGY = {
    'TP1_PERCENT': 30,
    'TP2_PERCENT': 30,
    'TP3_PERCENT': 40,
    'TP1_MOVE_SL_TO_BE': True,
    'TP2_MOVE_SL_TO_TP1': True,
    'TP3_MOVE_SL_TO_TP2': True,
}

ALERT_THRESHOLDS = {
    'TP_APPROACH': 0.80,
    'WARNING': 0.01,
    'DANGER': 0.50,
    'CRITICAL': 0.25,
    'LIQUIDATION': 0.10,
    'NEAR_BE': 0.002,
    'RAPID_MOVE': 0.01,
}

COOLDOWNS = {
    'DEFAULT': 60,
    'RAPID': 300,
    'TIME': 1800,
}

def validate_config():
    missing = []
    if not BOT_TOKEN:
        missing.append('BOT_TOKEN')
    if not CHAT_ID:
        missing.append('CHAT_ID')
    
    if missing:
        raise ValueError(f"Missing: {', '.join(missing)}")
    
    if WEBHOOK_URL:
        print(f"🌐 Webhook URL: {WEBHOOK_URL}")
    else:
        print("🔄 Polling mode (local)")
    
    print("✅ Config OK!")

validate_config()
