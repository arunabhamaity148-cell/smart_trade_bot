# trade_monitor.py
import asyncio
from database import TradeDatabase, Trade
from alert_manager import AlertManager
from telegram import Bot
from config import CHAT_ID, CHECK_INTERVAL
from coindcx_api import coindcx

class TradeMonitor:
    def __init__(self, telegram_token: str):
        self.db = TradeDatabase()
        self.alerts = AlertManager()
        self.telegram = Bot(token=telegram_token)
        self.running = False
        
        # Test CoinDCX connection
        if coindcx.test_connection():
            print("✅ CoinDCX API connected!")
        else:
            print("⚠️ Using backup price sources")
    
    async def get_price(self, symbol: str) -> float:
        """Get price from CoinDCX"""
        try:
            price = await asyncio.to_thread(coindcx.get_price, symbol)
            return price
        except Exception as e:
            print(f"❌ Price error for {symbol}: {e}")
            return 0.0
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        self.running = True
        
        # Send startup message
        try:
            await self.telegram.send_message(
                chat_id=CHAT_ID,
                text="🤖 <b>Trade Monitor Started!</b>\n\nMonitoring active trades...",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"⚠️ Startup message failed: {e}")
        
        while self.running:
            try:
                active_trades = self.db.get_active()
                
                if not active_trades:
                    print("⏳ No active trades...")
                    await asyncio.sleep(CHECK_INTERVAL)
                    continue
                
                print(f"🔍 Monitoring {len(active_trades)} trades...")
                
                for trade in active_trades:
                    current_price = await self.get_price(trade.pair)
                    
                    if current_price == 0:
                        print(f"⚠️ Could not get price for {trade.pair}")
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
                            print(f"✅ Alert: {trade.pair} - {msg[:40]}...")
                        except Exception as e:
                            print(f"❌ Telegram error: {e}")
                    
                    # Update database
                    self.db.update(trade)
                    
                    # Console log
                    status_icon = {
                        'PENDING': '⏳',
                        'ACTIVE': '🟢',
                        'TP1': '🥇',
                        'TP2': '🥈',
                        'TP3': '🥉',
                        'CLOSED': '🔴',
                        'EXPIRED': '⚪'
                    }.get(trade.status, '⚪')
                    
                    print(f"{status_icon} {trade.pair}: ${current_price:.6f} | {trade.status}")
                
                await asyncio.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                print(f"❌ Monitor error: {e}")
                await asyncio.sleep(30)
    
    def stop(self):
        self.running = False
        print("🛑 Monitor stopped")
