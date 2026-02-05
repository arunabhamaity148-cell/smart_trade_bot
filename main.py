# app.py
import os
import re
import json
import uuid
import threading
import time
import requests
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from flask import Flask, request, jsonify
from telegram import Bot, Update

# ========== CONFIG ==========
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
PORT = int(os.getenv('PORT', '8080'))
RAILWAY_URL = os.getenv('RAILWAY_PUBLIC_DOMAIN')

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN and CHAT_ID required!")

# ========== DATA MODEL ==========
@dataclass
class Trade:
    id: str
    pair: str
    direction: str
    entry_min: float
    entry_max: float
    tp1: float
    tp2: float
    tp3: float
    stop_loss: float
    risk_percent: float
    leverage: str
    valid_hours: int
    strength: int
    created_at: str
    
    breakeven_price: Optional[float] = None
    current_sl: Optional[float] = None
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    tp1_closed_percent: float = 0
    tp2_closed_percent: float = 0
    tp3_closed_percent: float = 0
    status: str = 'PENDING'
    entry_price: Optional[float] = None
    alerts_sent: List[str] = field(default_factory=list)
    price_history: List[Dict] = field(default_factory=list)
    
    @property
    def entry_avg(self) -> float:
        return (self.entry_min + self.entry_max) / 2
    
    def to_dict(self):
        return {
            'id': self.id,
            'pair': self.pair,
            'direction': self.direction,
            'entry_min': self.entry_min,
            'entry_max': self.entry_max,
            'tp1': self.tp1,
            'tp2': self.tp2,
            'tp3': self.tp3,
            'stop_loss': self.stop_loss,
            'risk_percent': self.risk_percent,
            'leverage': self.leverage,
            'valid_hours': self.valid_hours,
            'strength': self.strength,
            'created_at': self.created_at,
            'breakeven_price': self.breakeven_price,
            'current_sl': self.current_sl,
            'tp1_hit': self.tp1_hit,
            'tp2_hit': self.tp2_hit,
            'tp3_hit': self.tp3_hit,
            'tp1_closed_percent': self.tp1_closed_percent,
            'tp2_closed_percent': self.tp2_closed_percent,
            'tp3_closed_percent': self.tp3_closed_percent,
            'status': self.status,
            'entry_price': self.entry_price,
            'alerts_sent': self.alerts_sent,
            'price_history': self.price_history,
        }

# ========== DATABASE ==========
class Database:
    def __init__(self, filename="trades.json"):
        self.filename = filename
        self.trades: List[Trade] = []
        self.load()
    
    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    for t in data:
                        trade = Trade(**{k: v for k, v in t.items() if k in Trade.__dataclass_fields__})
                        self.trades.append(trade)
            except Exception as e:
                print(f"Load error: {e}")
    
    def save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump([t.to_dict() for t in self.trades], f, indent=2)
        except Exception as e:
            print(f"Save error: {e}")
    
    def add(self, trade: Trade):
        self.trades.append(trade)
        self.save()
    
    def get_active(self) -> List[Trade]:
        return [t for t in self.trades if t.status not in ['CLOSED', 'EXPIRED']]
    
    def get_by_pair(self, pair: str) -> Optional[Trade]:
        for t in self.trades:
            if t.pair == pair and t.status not in ['CLOSED', 'EXPIRED']:
                return t
        return None
    
    def update(self, trade: Trade):
        for i, t in enumerate(self.trades):
            if t.id == trade.id:
                self.trades[i] = trade
                self.save()
                return

db = Database()

# ========== BOT SETUP ==========
bot = Bot(token=BOT_TOKEN)

# ========== SIGNAL PARSER ==========
def parse_signal(text: str) -> Optional[Trade]:
    try:
        pair_match = re.search(r'🔴\s+(\w+)\s+\|\s+(LONG|SHORT)', text)
        if not pair_match:
            return None
        
        pair = pair_match.group(1)
        direction = pair_match.group(2)
        
        strength_match = re.search(r'(\d+)/100', text)
        strength = int(strength_match.group(1)) if strength_match else 50
        
        entry_match = re.search(r'\$(\d+\.\d+)\s*-\s*\$(\d+\.\d+)', text)
        entry_min = float(entry_match.group(1)) if entry_match else 0.0
        entry_max = float(entry_match.group(2)) if entry_match else 0.0
        
        prices = re.findall(r'\$(\d+\.\d+)', text)
        
        sl_price = 0.0
        tp1 = tp2 = tp3 = 0.0
        
        if len(prices) >= 4:
            sl_price = float(prices[2])
            tp1 = float(prices[3])
            tp2 = float(prices[4]) if len(prices) > 4 else 0.0
            tp3 = float(prices[5]) if len(prices) > 5 else 0.0
        
        entry_avg = (entry_min + entry_max) / 2
        
        if tp2 == 0 and tp1 > 0:
            if direction == "LONG":
                tp2 = tp1 + (tp1 - entry_min) * 0.6
                tp3 = tp2 + (tp1 - entry_min) * 0.6
            else:
                tp2 = tp1 - (entry_max - tp1) * 0.6
                tp3 = tp2 - (entry_max - tp1) * 0.6
        
        risk_match = re.search(r'💵\s*Risk:\s*(\d+\.?\d*)%', text)
        risk = float(risk_match.group(1)) if risk_match else 1.0
        
        lev_match = re.search(r'⚡\s*Leverage:\s*([\d\-]+)x', text)
        leverage = lev_match.group(1) if lev_match else "1-2x"
        
        valid_match = re.search(r'⏳\s*Valid:\s*(\d+)h', text)
        valid_hours = int(valid_match.group(1)) if valid_match else 4
        
        return Trade(
            id=str(uuid.uuid4())[:8],
            pair=pair,
            direction=direction,
            entry_min=entry_min,
            entry_max=entry_max,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            stop_loss=sl_price,
            risk_percent=risk,
            leverage=leverage,
            valid_hours=valid_hours,
            strength=strength,
            created_at=datetime.utcnow().isoformat(),
            breakeven_price=entry_avg,
            current_sl=sl_price,
        )
    except Exception as e:
        print(f"Parse error: {e}")
        return None

# ========== PRICE FETCHER ==========
def get_price(symbol: str) -> float:
    try:
        coin = symbol.replace('USDT', '').lower()
        
        coin_map = {
            'sei': 'sei-network', 'btc': 'bitcoin', 'eth': 'ethereum',
            'sol': 'solana', 'tia': 'celestia', 'bnb': 'binancecoin',
            'ada': 'cardano', 'dot': 'polkadot', 'link': 'chainlink',
        }
        coin_id = coin_map.get(coin, coin)
        
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if coin_id in data:
            return float(data[coin_id]['usd'])
        
        return 0.0
    except Exception as e:
        print(f"Price error: {e}")
        return 0.0

# ========== ALERT CHECKER ==========
def check_alerts(trade: Trade, price: float) -> List[str]:
    alerts = []
    
    # Entry
    if trade.status == 'PENDING':
        if trade.entry_min <= price <= trade.entry_max:
            if 'ENTRY' not in trade.alerts_sent:
                alerts.append(f"🎯 <b>{trade.pair}</b> এন্ট্রি জোনে! <code>${price}</code>")
                trade.alerts_sent.append('ENTRY')
                trade.status = 'ACTIVE'
                trade.entry_price = price
    
    # TP1
    if not trade.tp1_hit:
        hit = (trade.direction == 'LONG' and price >= trade.tp1) or \
              (trade.direction == 'SHORT' and price <= trade.tp1)
        if hit:
            alerts.append(f"🥇 <b>{trade.pair} TP1 HIT!</b> <code>${price}</code>\n✅ 30% Close + SL→BE")
            trade.tp1_hit = True
            trade.status = 'TP1'
            trade.tp1_closed_percent = 30
            trade.current_sl = trade.breakeven_price
    
    # TP2
    if trade.tp1_hit and not trade.tp2_hit:
        hit = (trade.direction == 'LONG' and price >= trade.tp2) or \
              (trade.direction == 'SHORT' and price <= trade.tp2)
        if hit:
            alerts.append(f"🥈 <b>{trade.pair} TP2 HIT!</b> <code>${price}</code>\n✅ 30% Close + SL→TP1")
            trade.tp2_hit = True
            trade.status = 'TP2'
            trade.tp2_closed_percent = 30
            trade.current_sl = trade.tp1
    
    # TP3
    if trade.tp2_hit and not trade.tp3_hit:
        hit = (trade.direction == 'LONG' and price >= trade.tp3) or \
              (trade.direction == 'SHORT' and price <= trade.tp3)
        if hit:
            alerts.append(f"🥉 <b>{trade.pair} TP3 HIT!</b> <code>${price}</code>\n🎉 Trade Complete!")
            trade.tp3_hit = True
            trade.status = 'TP3'
            trade.tp3_closed_percent = 40
    
    # SL
    sl_hit = (trade.direction == 'LONG' and price <= trade.current_sl) or \
             (trade.direction == 'SHORT' and price >= trade.current_sl)
    if sl_hit and 'SL' not in trade.alerts_sent:
        alerts.append(f"🛑 <b>{trade.pair} SL HIT!</b> <code>${price}</code>")
        trade.alerts_sent.append('SL')
        trade.status = 'CLOSED'
    
    # Update history
    trade.price_history.append({'time': datetime.utcnow().isoformat(), 'price': price})
    trade.price_history = trade.price_history[-50:]
    
    return alerts

# ========== BACKGROUND MONITOR ==========
def monitor_loop():
    """Background thread for price monitoring"""
    print("🔄 Monitor started")
    
    while True:
        try:
            active = db.get_active()
            
            for trade in active:
                price = get_price(trade.pair)
                if price == 0:
                    continue
                
                alerts = check_alerts(trade, price)
                
                for alert in alerts:
                    try:
                        # Use requests to send message (no async)
                        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                        data = {
                            'chat_id': CHAT_ID,
                            'text': alert,
                            'parse_mode': 'HTML'
                        }
                        requests.post(url, data=data, timeout=10)
                        print(f"✅ Alert: {alert[:50]}")
                    except Exception as e:
                        print(f"❌ Send error: {e}")
                
                db.update(trade)
                print(f"📊 {trade.pair}: ${price:.6f} | {trade.status}")
            
            time.sleep(10)
            
        except Exception as e:
            print(f"❌ Monitor error: {e}")
            time.sleep(30)

# ========== FLASK APP ==========
app = Flask(__name__)

@app.route('/')
def health():
    """Health check for Railway"""
    return jsonify({
        'status': 'ok',
        'bot': 'running',
        'time': datetime.utcnow().isoformat(),
        'active_trades': len(db.get_active())
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook handler"""
    try:
        data = request.get_json()
        
        # Manual message handling
        if 'message' in data:
            msg = data['message']
            chat_id = msg['chat']['id']
            text = msg.get('text', '')
            
            # /start command
            if text == '/start':
                reply = """🤖 <b>Smart Trade Bot</b>

✅ Running 24/7 on Railway
✅ Auto TP/SL Monitoring
✅ Real-time Alerts

Send signal to start monitoring!"""
                send_message(chat_id, reply)
            
            # /status command
            elif text == '/status':
                active = db.get_active()
                if not active:
                    send_message(chat_id, "⏳ No active trades")
                else:
                    reply = "📊 <b>Active Trades:</b>\n\n"
                    for t in active:
                        emoji = "🟢" if t.direction == "LONG" else "🔴"
                        status = "🥉TP3" if t.tp3_hit else "🥈TP2" if t.tp2_hit else "🥇TP1" if t.tp1_hit else "⏳PENDING"
                        reply += f"{emoji} <b>{t.pair}</b> | {status}\n"
                        reply += f"   Entry: ${t.entry_avg:.4f}\n"
                        reply += f"   SL: ${t.current_sl:.4f}\n\n"
                    send_message(chat_id, reply)
            
            # Signal message
            elif '🔴' in text:
                trade = parse_signal(text)
                if not trade:
                    send_message(chat_id, "❌ Failed to parse signal")
                    return 'OK', 200
                
                existing = db.get_by_pair(trade.pair)
                if existing:
                    send_message(chat_id, f"⚠️ {trade.pair} already being monitored!")
                    return 'OK', 200
                
                db.add(trade)
                
                reply = f"""
🎯 <b>{trade.pair} {trade.direction}</b> Monitoring Started!

📊 Strength: {trade.strength}/100
🎯 Entry: ${trade.entry_min} - ${trade.entry_max}
🥇 TP1: ${trade.tp1}
🥈 TP2: ${trade.tp2}
🥉 TP3: ${trade.tp3}
🛡️ SL: ${trade.stop_loss}

✅ You'll receive alerts automatically!"""
                send_message(chat_id, reply)
        
        return 'OK', 200
    except Exception as e:
        print(f"Webhook error: {e}")
        return 'Error', 500

def send_message(chat_id, text):
    """Send Telegram message using HTTP API"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Send message error: {e}")

# ========== MAIN ==========
if __name__ == '__main__':
    # Start background monitor
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    
    # Set webhook
    if RAILWAY_URL:
        webhook_url = f"https://{RAILWAY_URL}/webhook"
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
            requests.post(url, data={'url': webhook_url}, timeout=10)
            print(f"✅ Webhook: {webhook_url}")
        except Exception as e:
            print(f"⚠️ Webhook error: {e}")
    
    # Start Flask
    print(f"🚀 Flask starting on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, threaded=True)
