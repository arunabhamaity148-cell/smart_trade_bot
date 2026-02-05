# telegram_bot.py
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from signal_parser import SignalParser
from database import TradeDatabase
from trade_monitor import TradeMonitor
from config import BOT_TOKEN, CHAT_ID
import asyncio
import os

class TelegramBot:
    def __init__(self):
        self.parser = SignalParser()
        self.db = TradeDatabase()
        self.monitor = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"""
🤖 <b>Smart Multi-TP Trade Bot</b> (CoinDCX Edition)

<b>✅ Connected to CoinDCX</b>

<b>ফিচারস:</b>
✅ TP1, TP2, TP3 মনিটরিং
✅ Auto Partial Close (30%-30%-40%)
✅ Auto BE Move
✅ Auto Trailing SL
✅ ২৫টি ডেঞ্জার অ্যালার্ট
✅ Railway Cloud Deploy

<b>কমান্ডস:</b>
/start - শুরু
/status - সব ট্রেড
/history - ক্লোজড ট্রেড
/close SYMBOL - বন্ধ করুন
/stop - মনিটরিং বন্ধ
/test - কানেকশন টেস্ট

<b>ব্যবহার:</b>
সিগন্যাল কপি করে পেস্ট করুন!
""", parse_mode='HTML')
    
    async def test_connection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test CoinDCX connection"""
        from coindcx_api import coindcx
        
        await update.message.reply_text("🔄 Testing CoinDCX connection...")
        
        try:
            price = coindcx.get_price("BTCUSDT")
            if price > 0:
                await update.message.reply_text(f"""
✅ <b>CoinDCX Connected!</b>

BTC Price: ${price:,.2f}

Ready to monitor trades!
""")
            else:
                await update.message.reply_text("⚠️ Using backup price sources")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
    
    async def handle_signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        
        # Check if it's a signal
        if '🔴' not in text and 'SETP' not in text:
            await update.message.reply_text("❌ এটা সিগন্যাল নয়!")
            return
        
        try:
            trade = self.parser.parse(text)
        except Exception as e:
            await update.message.reply_text(f"❌ পার্স এরর: {e}")
            return
        
        # Check duplicate
        existing = self.db.get_by_pair(trade.pair)
        if existing:
            await update.message.reply_text(
                f"⚠️ {trade.pair} ইতিমধ্যে আছে!\n"
                f"/close {trade.pair} দিয়ে আগেরটা বন্ধ করুন।"
            )
            return
        
        # Save and confirm
        self.db.add(trade)
        summary = self.parser.format_summary(trade)
        
        # Add CoinDCX note
        summary += "\n<b>💹 Price Source: CoinDCX API</b>"
        
        await update.message.reply_text(summary, parse_mode='HTML')
        
        # Start monitor
        if self.monitor is None:
            self.monitor = TradeMonitor(BOT_TOKEN)
            asyncio.create_task(self.monitor.monitor_loop())
            await update.message.reply_text("✅ মনিটরিং শুরু হয়েছে!\n🌐 Running on Railway Cloud")
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        active = self.db.get_active()
        
        if not active:
            await update.message.reply_text("কোনো অ্যাক্টিভ ট্রেড নেই।")
            return
        
        msg = "📊 <b>অ্যাক্টিভ ট্রেডস:</b>\n\n"
        
        for t in active:
            emoji = "🟢" if t.direction == "LONG" else "🔴"
            tp_status = ""
            
            if t.tp3_hit:
                tp_status = "🥉 TP3"
            elif t.tp2_hit:
                tp_status = "🥈 TP2"
            elif t.tp1_hit:
                tp_status = "🥇 TP1"
            else:
                tp_status = "⏳ পেন্ডিং"
            
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
            msg += f"   স্ট্যাটাস: {t.status}\n\n"
        
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
        
        await update.message.reply_text("🛑 মনিটরিং বন্ধ করা হয়েছে।")
    
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Health check for Railway"""
        await update.message.reply_text("✅ Bot is healthy!")
    
    def run(self):
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("test", self.test_connection))
        application.add_handler(CommandHandler("status", self.status))
        application.add_handler(CommandHandler("history", self.history))
        application.add_handler(CommandHandler("close", self.close_trade))
        application.add_handler(CommandHandler("stop", self.stop_monitor))
        application.add_handler(CommandHandler("health", self.health_check))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_signal))
        
        # Railway health check endpoint
        port = int(os.getenv('PORT', 8080))
        
        print(f"🤖 Bot starting on port {port}...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
