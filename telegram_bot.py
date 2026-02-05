# telegram_bot.py
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from aiohttp import web
import asyncio
from signal_parser import SignalParser
from database import TradeDatabase
from trade_monitor import TradeMonitor
from config import BOT_TOKEN, CHAT_ID, PORT, WEBHOOK_URL

class TelegramBot:
    def __init__(self):
        self.parser = SignalParser()
        self.db = TradeDatabase()
        self.monitor = None
        self.application = None
        self.webhook_path = f"/webhook/{BOT_TOKEN}"
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"""
🤖 <b>Smart Multi-TP Trade Bot</b> (CoinDCX Edition)

<b>✅ Connected to CoinDCX</b>
<b>🌐 Mode: Webhook</b>

<b>ফিচারস:</b>
✅ TP1, TP2, TP3 মনিটরিং
✅ Auto Partial Close (30%-30%-40%)
✅ Auto BE Move
✅ Auto Trailing SL
✅ ২৫টি ডেঞ্জার অ্যালার্ট

<b>কমান্ডস:</b>
/start - শুরু
/status - সব ট্রেড
/history - ক্লোজড ট্রেড
/close SYMBOL - বন্ধ করুন
/stop - মনিটরিং বন্ধ

<b>ব্যবহার:</b>
সিগন্যাল কপি করে পেস্ট করুন!
""", parse_mode='HTML')
    
    async def handle_signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        
        if '🔴' not in text and 'SETP' not in text:
            await update.message.reply_text("❌ এটা সিগন্যাল নয়!")
            return
        
        try:
            trade = self.parser.parse(text)
        except Exception as e:
            await update.message.reply_text(f"❌ পার্স এরর: {e}")
            return
        
        existing = self.db.get_by_pair(trade.pair)
        if existing:
            await update.message.reply_text(
                f"⚠️ {trade.pair} ইতিমধ্যে আছে!\n"
                f"/close {trade.pair} দিয়ে আগেরটা বন্ধ করুন।"
            )
            return
        
        self.db.add(trade)
        summary = self.parser.format_summary(trade)
        summary += "\n<b>💹 Price Source: CoinDCX API</b>"
        
        await update.message.reply_text(summary, parse_mode='HTML')
        
        if self.monitor is None:
            self.monitor = TradeMonitor(BOT_TOKEN)
            asyncio.create_task(self.monitor.monitor_loop())
            await update.message.reply_text("✅ মনিটরিং শুরু!")
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        active = self.db.get_active()
        
        if not active:
            await update.message.reply_text("কোনো অ্যাক্টিভ ট্রেড নেই।")
            return
        
        msg = "📊 <b>অ্যাক্টিভ ট্রেডস:</b>\n\n"
        
        for t in active:
            emoji = "🟢" if t.direction == "LONG" else "🔴"
            tp_status = "🥉 TP3" if t.tp3_hit else "🥈 TP2" if t.tp2_hit else "🥇 TP1" if t.tp1_hit else "⏳ পেন্ডিং"
            
            msg += f"{emoji} <b>{t.pair}</b> | {tp_status}\n"
            msg += f"   এন্ট্রি: ${t.entry_avg:.4f}\n"
            msg += f"   SL: ${t.current_sl:.4f}\n"
            msg += f"   Next TP: ${t.current_tp:.4f if t.current_tp else 'ডন'}\n\n"
        
        await update.message.reply_text(msg, parse_mode='HTML')
    
    async def history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        closed = self.db.get_closed()
        
        if not closed:
            await update.message.reply_text("কোনো হিস্টরি নেই।")
            return
        
        msg = "📜 <b>ক্লোজড ট্রেডস:</b>\n\n"
        
        for t in closed[-5:]:
            emoji = "✅" if t.tp1_hit else "❌"
            msg += f"{emoji} {t.pair} ({t.direction})\n"
            if t.tp1_hit:
                msg += f"   TP1: {t.tp1_closed_percent}%\n"
            if t.tp2_hit:
                msg += f"   TP2: {t.tp2_closed_percent}%\n"
            if t.tp3_hit:
                msg += f"   TP3: {t.tp3_closed_percent}%\n"
            msg += "\n"
        
        await update.message.reply_text(msg, parse_mode='HTML')
    
    async def close_trade(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            await update.message.reply_text("ব্যবহার: /close SEIUSDT")
            return
        
        symbol = context.args[0].upper()
        self.db.close_all(symbol)
        await update.message.reply_text(f"✅ {symbol} বন্ধ করা হয়েছে।")
    
    async def stop_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
        
        await update.message.reply_text("🛑 মনিটরিং বন্ধ।")
    
    async def run(self):
        """Run with webhook"""
        print(f"🌐 Starting WEBHOOK mode")
        print(f"🔗 Webhook path: {self.webhook_path}")
        
        # Create application
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("history", self.history))
        self.application.add_handler(CommandHandler("close", self.close_trade))
        self.application.add_handler(CommandHandler("stop", self.stop_monitor))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_signal))
        
        # Setup webhook
        await self.application.initialize()
        await self.application.start()
        
        # Set webhook
        await self.application.bot.set_webhook(
            url=f"{WEBHOOK_URL}{self.webhook_path}",
            drop_pending_updates=True
        )
        
        print(f"✅ Webhook set: {WEBHOOK_URL}{self.webhook_path}")
        
        # Create aiohttp app for webhook handling
        web_app = web.Application()
        web_app.router.add_post(self.webhook_path, self._handle_webhook)
        web_app.router.add_get('/', self._health_check)
        web_app.router.add_get('/health', self._health_check)
        
        # Run web server
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        
        print(f"🚀 Server running on port {PORT}")
        
        # Keep running
        while True:
            await asyncio.sleep(3600)
    
    async def _handle_webhook(self, request):
        """Handle incoming webhook updates"""
        data = await request.json()
        update = Update.de_json(data, self.application.bot)
        await self.application.process_update(update)
        return web.Response(status=200)
    
    async def _health_check(self, request):
        """Health check endpoint"""
        return web.Response(text="✅ Bot is healthy!", status=200)


# For compatibility with main.py
def main():
    bot = TelegramBot()
    asyncio.run(bot.run())

if __name__ == "__main__":
    main()
