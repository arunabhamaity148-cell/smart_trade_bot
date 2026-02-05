# telegram_bot.py
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from signal_parser import SignalParser
from database import TradeDatabase
from trade_monitor import TradeMonitor
from config import BOT_TOKEN, CHAT_ID, PORT, WEBHOOK_URL
import asyncio
import os

class TelegramBot:
    def __init__(self):
        self.parser = SignalParser()
        self.db = TradeDatabase()
        self.monitor = None
        self.application = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"""
🤖 <b>Smart Multi-TP Trade Bot</b> (CoinDCX Edition)

<b>✅ Connected to CoinDCX</b>
<b>🌐 Mode: {'Webhook' if WEBHOOK_URL else 'Polling'}</b>

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
    
    def _add_handlers(self, app):
        """Add all handlers"""
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CommandHandler("history", self.history))
        app.add_handler(CommandHandler("close", self.close_trade))
        app.add_handler(CommandHandler("stop", self.stop_monitor))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_signal))
    
    def run(self):
        if WEBHOOK_URL:
            # ===== WEBHOOK MODE (Production) =====
            print(f"🌐 Starting WEBHOOK mode")
            print(f"🔗 URL: {WEBHOOK_URL}")
            
            self.application = Application.builder().token(BOT_TOKEN).build()
            self._add_handlers(self.application)
            
            # Setup webhook
            self.application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                webhook_url=WEBHOOK_URL,
                drop_pending_updates=True
            )
            
        else:
            # ===== POLLING MODE (Local) =====
            print("🔄 Starting POLLING mode")
            
            self.application = Application.builder().token(BOT_TOKEN).build()
            self._add_handlers(self.application)
            
            self.application.run_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
