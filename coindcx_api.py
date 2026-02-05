# coindcx_api.py
import requests
import hmac
import hashlib
import json
import time
from typing import Dict, Optional
from config import COINDCX_API_KEY, COINDCX_SECRET

class CoinDCXAPI:
    def __init__(self):
        self.base_url = "https://api.coindcx.com"
        self.api_key = COINDCX_API_KEY
        self.secret = COINDCX_SECRET
    
    def _generate_signature(self, body: str = "") -> str:
        """Generate HMAC signature for private API"""
        if not self.secret:
            return ""
        
        timestamp = int(time.time() * 1000)
        signature_data = str(timestamp) + body
        signature = hmac.new(
            self.secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature, timestamp
    
    def get_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            # Convert SEIUSDT to SEI-INR or SEI-USDT based on market
            market = self._get_market(symbol)
            
            # Use public API for price
            url = f"{self.base_url}/exchange/ticker"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            # Find the market
            for ticker in data:
                if ticker.get('market') == market:
                    return float(ticker.get('last_price', 0))
            
            # Try alternative format
            url = f"{self.base_url}/market_data/current_prices"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            # Search in prices
            for key, value in data.items():
                if symbol.replace('USDT', '').lower() in key.lower():
                    return float(value)
            
            print(f"⚠️ Price not found for {symbol}, trying backup...")
            return self._get_price_backup(symbol)
            
        except Exception as e:
            print(f"❌ Error fetching price: {e}")
            return self._get_price_backup(symbol)
    
    def _get_price_backup(self, symbol: str) -> float:
        """Backup price source using CoinGecko"""
        try:
            coin = symbol.replace('USDT', '').lower()
            
            # Try common mappings
            coin_id_map = {
                'sei': 'sei-network',
                'btc': 'bitcoin',
                'eth': 'ethereum',
                'sol': 'solana',
                'tia': 'celestia',
                'bnb': 'binancecoin',
                'ada': 'cardano',
                'dot': 'polkadot',
                'link': 'chainlink',
                'uni': 'uniswap',
            }
            
            coin_id = coin_id_map.get(coin, coin)
            
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if coin_id in data:
                return float(data[coin_id]['usd'])
            
            # Try direct
            if coin in data:
                return float(data[coin]['usd'])
            
            return 0.0
            
        except Exception as e:
            print(f"❌ Backup price error: {e}")
            return 0.0
    
    def _get_market(self, symbol: str) -> str:
        """Convert symbol to CoinDCX market format"""
        # SEIUSDT -> SEIUSDT or SEI-USDT
        coin = symbol.replace('USDT', '')
        return f"{coin}USDT"
    
    def get_balance(self) -> Dict:
        """Get account balance (requires API key)"""
        if not self.api_key or not self.secret:
            return {}
        
        try:
            body = json.dumps({"timestamp": int(time.time() * 1000)})
            signature, timestamp = self._generate_signature(body)
            
            headers = {
                'Content-Type': 'application/json',
                'X-AUTH-APIKEY': self.api_key,
                'X-AUTH-SIGNATURE': signature,
                'X-AUTH-TIMESTAMP': str(timestamp)
            }
            
            url = f"{self.base_url}/exchange/v1/users/balances"
            response = requests.post(url, headers=headers, data=body, timeout=10)
            return response.json()
            
        except Exception as e:
            print(f"❌ Balance fetch error: {e}")
            return {}
    
    def test_connection(self) -> bool:
        """Test API connection"""
        try:
            price = self.get_price("BTCUSDT")
            return price > 0
        except:
            return False


# Global instance
coindcx = CoinDCXAPI()
