# pinger.py
import asyncio
import aiohttp
from datetime import datetime

class SelfPinger:
    def __init__(self, url: str, interval: int = 300):  # 5 minutes
        self.url = url
        self.interval = interval
        self.running = False
    
    async def start(self):
        """Start self-pinging"""
        self.running = True
        print(f"🔄 Self-pinger started: {self.url}")
        
        while self.running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.url) as response:
                        if response.status == 200:
                            print(f"✅ Ping OK at {datetime.now().strftime('%H:%M:%S')}")
                        else:
                            print(f"⚠️ Ping failed: {response.status}")
            except Exception as e:
                print(f"❌ Ping error: {e}")
            
            await asyncio.sleep(self.interval)
    
    def stop(self):
        self.running = False
        print("🛑 Self-pinger stopped")
