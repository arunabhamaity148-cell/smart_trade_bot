# trade_monitor.py
import ccxt
import asyncio
from database import TradeDatabase, Trade
from alert_manager import AlertManager
from telegram import Bot
from config import CHAT_ID, CHECK_INTERVAL

class TradeMonitor:
    def __init__(self, api_key: str, api_secret: str, telegram_token: str):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        self.db = TradeDatabase()
        self.alerts = AlertManager()
        self.telegram = Bot(token=telegram_token)
        self.running = False
    
    async def get_price(self, symbol: str) -> float:
        """Get current price"""
        try:
            formatted = symbol.replace('USDT', '/USDT')
            ticker = await asyncio.to_thread(self.exchange.fetch_ticker, formatted)
            return ticker['last']
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return 0.0
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        self.running = True
        
        while self.running:
            try:
                active_trades = self.db.get_active()
                
                if not active_trades:
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue
                
                for trade in active_trades:
                    current_price = await self.get_price(trade.pair)
                    
                    if current_price == 0:
                        continue
                    
                    # Check all alerts
                    alert_messages = self.alerts.check_alerts(trade, current_price)
                    
                    # Send to Telegram
                    for msg in alert_messages:
                        try:
                            await self.telegram.send_message(
                                chat_id=CHAT_ID,
                                text=msg,
                                parse_mode='HTML'
                            )
                            print(f"✅ Alert sent: {trade.pair} - {msg[:30]}...")
                        except Exception as e:
                            print(f"❌ Telegram error: {e}")
                    
                    # Update database
                    self.db.update(trade)
                    
                    # Console log
                    status_icon = "🟢" if trade.status == 'ACTIVE' else "🟡" if trade.status.startswith('TP') else "⚪"
                    print(f"{status_icon} {trade.pair}: ${current_price:.4f} | {trade.status}")
                
                await asyncio.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                print(f"❌ Monitor error: {e}")
                await asyncio.sleep(30)
    
    def stop(self):
        self.running = False
        print("🛑 Monitor stopped")
