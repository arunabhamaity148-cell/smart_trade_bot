# main.py
import asyncio
import os
from telegram_bot import TelegramBot
from pinger import SelfPinger
from config import WEBHOOK_URL

async def main():
    port = int(os.getenv('PORT', '8080'))
    print(f"🚀 Starting bot on port {port}...")
    
    # Start bot
    bot = TelegramBot()
    bot_task = asyncio.create_task(bot.run())
    
    # Start self-pinger (if webhook URL exists)
    if WEBHOOK_URL:
        health_url = f"{WEBHOOK_URL}/health"
        pinger = SelfPinger(health_url, interval=300)  # 5 minutes
        pinger_task = asyncio.create_task(pinger.start())
        
        print(f"🔄 Auto-pinger started: {health_url}")
    
    # Keep running
    try:
        await bot_task
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        if 'pinger' in locals():
            pinger.stop()

if __name__ == "__main__":
    asyncio.run(main())
