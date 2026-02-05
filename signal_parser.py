# signal_parser.py
import re
from datetime import datetime
from database import Trade
import uuid

class SignalParser:
    def parse(self, text: str) -> Trade:
        """Parse signal from your bot format"""
        
        # Extract pair and direction
        pair_match = re.search(r'🔴\s+(\w+)\s+\|\s+(LONG|SHORT)', text)
        pair = pair_match.group(1) if pair_match else "UNKNOWN"
        direction = pair_match.group(2) if pair_match else "LONG"
        
        # Extract strength
        strength_match = re.search(r'(\d+)/100', text)
        strength = int(strength_match.group(1)) if strength_match else 50
        
        # Extract timeframe
        tf_match = re.search(r'⏱️\s+(\w+)', text)
        timeframe = tf_match.group(1) if tf_match else "1h"
        
        # Extract entry zone
        entry_match = re.search(r'\$(\d+\.\d+)\s*-\s*\$(\d+\.\d+)', text)
        entry_min = float(entry_match.group(1)) if entry_match else 0.0
        entry_max = float(entry_match.group(2)) if entry_match else 0.0
        
        # Extract all prices
        prices = re.findall(r'\$(\d+\.\d+)', text)
        
        sl_price = 0.0
        tp1 = tp2 = tp3 = 0.0
        
        if len(prices) >= 4:
            sl_price = float(prices[2])
            tp1 = float(prices[3])
            tp2 = float(prices[4]) if len(prices) > 4 else 0.0
            tp3 = float(prices[5]) if len(prices) > 5 else 0.0
        
        # Calculate missing TPs
        if tp2 == 0 and tp1 > 0:
            if direction == "LONG":
                tp2 = tp1 + (tp1 - entry_min) * 0.6
                tp3 = tp2 + (tp1 - entry_min) * 0.6
            else:
                tp2 = tp1 - (entry_max - tp1) * 0.6
                tp3 = tp2 - (entry_max - tp1) * 0.6
        
        # Extract risk
        risk_match = re.search(r'💵\s*Risk:\s*(\d+\.?\d*)%', text)
        risk = float(risk_match.group(1)) if risk_match else 1.0
        
        # Extract leverage
        lev_match = re.search(r'⚡\s*Leverage:\s*([\d\-]+)x', text)
        leverage = lev_match.group(1) if lev_match else "1-2x"
        
        # Extract validity
        valid_match = re.search(r'⏳\s*Valid:\s*(\d+)h', text)
        valid_hours = int(valid_match.group(1)) if valid_match else 4
        
        entry_avg = (entry_min + entry_max) / 2
        
        return Trade(
            id=str(uuid.uuid4())[:8],
            pair=pair,
            direction=direction,
            entry_min=entry_min,
            entry_max=entry_max,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            stop_loss=sl_price,
            breakeven_price=entry_avg,
            current_sl=sl_price,
            risk_percent=risk,
            leverage=leverage,
            valid_hours=valid_hours,
            strength=strength,
            created_at=datetime.utcnow(),
            status='PENDING'
        )
    
    def format_summary(self, trade: Trade) -> str:
        """Format trade summary"""
        emoji = "🟢" if trade.direction == "LONG" else "🔴"
        
        entry = trade.entry_avg
        
        if trade.direction == "LONG":
            rr1 = (trade.tp1 - entry) / (entry - trade.stop_loss) if entry != trade.stop_loss else 0
            rr2 = (trade.tp2 - entry) / (entry - trade.stop_loss) if entry != trade.stop_loss else 0
            rr3 = (trade.tp3 - entry) / (entry - trade.stop_loss) if entry != trade.stop_loss else 0
        else:
            rr1 = (entry - trade.tp1) / (trade.stop_loss - entry) if entry != trade.stop_loss else 0
            rr2 = (entry - trade.tp2) / (trade.stop_loss - entry) if entry != trade.stop_loss else 0
            rr3 = (entry - trade.tp3) / (trade.stop_loss - entry) if entry != trade.stop_loss else 0
        
        return f"""
{emoji} <b>{trade.pair} {trade.direction}</b> মনিটরিং শুরু!

📊 স্ট্রেন্থ: {trade.strength}/100
🎯 এন্ট্রি: ${trade.entry_min} - ${trade.entry_max}

<b>🎯 TAKE PROFIT লেভেলস:</b>
🥇 TP1: ${trade.tp1} (R:R {rr1:.1f}) → 30% Close
🥈 TP2: ${trade.tp2} (R:R {rr2:.1f}) → 30% Close  
🥉 TP3: ${trade.tp3} (R:R {rr3:.1f}) → 40% Close

<b>🛡️ STOP LOSS:</b>
Initial SL: ${trade.stop_loss}
BE Price: ${trade.breakeven_price:.4f}

<b>📋 অটো স্ট্র্যাটেজি:</b>
✅ TP1 হিট → 30% বন্ধ + SL → BE
✅ TP2 হিট → 30% বন্ধ + SL → TP1  
✅ TP3 হিট → 40% বন্ধ + Full Close
🛑 SL হিট → Emergency Close

<b>🚨 ডেঞ্জার অ্যালার্টস:</b>
🟡 Warning: Entry এর বিপরীতে 1%
🟠 Danger: SL এর 50% দূরত্বে
🔴 Critical: SL এর 25% দূরত্বে
💀 Liquidation: SL এর 10% দূরত্বে

বট এখন সারাক্ষণ মনিটর করছে...
"""
