# main.py
import os
from telegram_bot import TelegramBot

def main():
    # Railway requires PORT env var
    port = os.getenv('PORT', '8080')
    print(f"🚀 Starting bot on port {port}...")
    
    bot = TelegramBot()
    bot.run()

if __name__ == "__main__":
    main()
