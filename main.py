# main.py
import asyncio
import os
from telegram_bot import TelegramBot

async def main():
    port = int(os.getenv('PORT', '8080'))
    print(f"🚀 Starting bot on port {port}...")
    
    bot = TelegramBot()
    await bot.run()  # await added here

if __name__ == "__main__":
    asyncio.run(main())
