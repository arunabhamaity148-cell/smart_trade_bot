# alert_manager.py
from database import Trade
from typing import List
from datetime import datetime, timedelta
from config import TP_STRATEGY, ALERT_THRESHOLDS, COOLDOWNS

class AlertManager:
    def __init__(self):
        self.last_alert_time = {}
    
    def check_alerts(self, trade: Trade, current_price: float) -> List[str]:
        """Complete alert system - 25 alerts"""
        alerts = []
        now = datetime.utcnow()
        
        # 1. ENTRY ALERT
        if trade.status == 'PENDING':
            if trade.entry_min <= current_price <= trade.entry_max:
                if 'ENTRY_ZONE' not in trade.alerts_sent:
                    alerts.append(self._format_entry_alert(trade, current_price))
                    trade.alerts_sent.append('ENTRY_ZONE')
                    trade.status = 'ACTIVE'
                    trade.entry_price = current_price
        
        # 2-4. TP APPROACH ALERTS
        if trade.status == 'ACTIVE' and not trade.tp1_hit:
            if self._is_approaching_tp(trade, current_price, 1):
                if 'TP1_APPROACH' not in trade.alerts_sent:
                    alerts.append(self._format_tp1_approach_alert(trade, current_price))
                    trade.alerts_sent.append('TP1_APPROACH')
        
        if trade.status == 'TP1' and not trade.tp2_hit:
            if self._is_approaching_tp(trade, current_price, 2):
                if 'TP2_APPROACH' not in trade.alerts_sent:
                    alerts.append(self._format_tp2_approach_alert(trade, current_price))
                    trade.alerts_sent.append('TP2_APPROACH')
        
        if trade.status == 'TP2' and not trade.tp3_hit:
            if self._is_approaching_tp(trade, current_price, 3):
                if 'TP3_APPROACH' not in trade.alerts_sent:
                    alerts.append(self._format_tp3_approach_alert(trade, current_price))
                    trade.alerts_sent.append('TP3_APPROACH')
        
        # 5-7. TP HIT ALERTS
        if not trade.tp1_hit and self._is_tp_hit(trade, current_price, 1):
            if 'TP1_HIT' not in trade.alerts_sent:
                alerts.append(self._format_tp1_hit_alert(trade, current_price))
                trade.alerts_sent.append('TP1_HIT')
                trade.tp1_hit = True
                trade.status = 'TP1'
                trade.tp1_closed_percent = TP_STRATEGY['TP1_PERCENT']
                
                if TP_STRATEGY['TP1_MOVE_SL_TO_BE']:
                    old_sl = trade.current_sl
                    trade.current_sl = trade.breakeven_price
                    alerts.append(self._format_be_move_alert(trade, old_sl))
                    alerts.append(self._format_after_tp1_strategy(trade))
        
        if trade.tp1_hit and not trade.tp2_hit and self._is_tp_hit(trade, current_price, 2):
            if 'TP2_HIT' not in trade.alerts_sent:
                alerts.append(self._format_tp2_hit_alert(trade, current_price))
                trade.alerts_sent.append('TP2_HIT')
                trade.tp2_hit = True
                trade.status = 'TP2'
                trade.tp2_closed_percent = TP_STRATEGY['TP2_PERCENT']
                
                if TP_STRATEGY['TP2_MOVE_SL_TO_TP1']:
                    old_sl = trade.current_sl
                    trade.current_sl = trade.tp1
                    alerts.append(self._format_trailing_alert(trade, old_sl, 1))
                    alerts.append(self._format_after_tp2_strategy(trade))
        
        if trade.tp2_hit and not trade.tp3_hit and self._is_tp_hit(trade, current_price, 3):
            if 'TP3_HIT' not in trade.alerts_sent:
                alerts.append(self._format_tp3_hit_alert(trade, current_price))
                trade.alerts_sent.append('TP3_HIT')
                trade.tp3_hit = True
                trade.status = 'TP3'
                trade.tp3_closed_percent = TP_STRATEGY['TP3_PERCENT']
                
                if TP_STRATEGY['TP3_MOVE_SL_TO_TP2']:
                    old_sl = trade.current_sl
                    trade.current_sl = trade.tp2
                    alerts.append(self._format_trailing_alert(trade, old_sl, 2))
                    alerts.append(self._format_trade_complete_alert(trade))
        
        # 8-10. SL MOVE ALERTS (included in TP hits)
        
        # 11-13. STRATEGY ALERTS (included in TP hits)
        
        # 14-15. TP MISSED ALERTS
        if trade.tp1_hit and not trade.tp2_hit:
            if self._is_tp_missed(trade, current_price, 2):
                if 'TP2_MISSED' not in trade.alerts_sent:
                    alerts.append(self._format_tp2_missed_alert(trade, current_price))
                    trade.alerts_sent.append('TP2_MISSED')
        
        if trade.tp2_hit and not trade.tp3_hit:
            if self._is_tp_missed(trade, current_price, 3):
                if 'TP3_MISSED' not in trade.alerts_sent:
                    alerts.append(self._format_tp3_missed_alert(trade, current_price))
                    trade.alerts_sent.append('TP3_MISSED')
        
        # 16. SL HIT ALERT
        if self._is_sl_hit(trade, current_price):
            if 'SL_HIT' not in trade.alerts_sent:
                alerts.append(self._format_sl_hit_alert(trade, current_price))
                trade.alerts_sent.append('SL_HIT')
                trade.status = 'CLOSED'
        
        # 17-21. DANGER ALERTS
        if trade.status in ['ACTIVE', 'TP1', 'TP2'] and not trade.tp3_hit:
            metrics = self._calculate_metrics(trade, current_price)
            
            if metrics['pct_to_sl'] <= 25 and 'CRITICAL_25' not in trade.alerts_sent:
                if self._can_alert(trade.id, 'CRITICAL_25', now):
                    alerts.append(self._format_critical_alert(trade, current_price, metrics))
                    trade.alerts_sent.append('CRITICAL_25')
            
            elif metrics['pct_to_sl'] <= 50 and 'DANGER_50' not in trade.alerts_sent:
                if self._can_alert(trade.id, 'DANGER_50', now):
                    alerts.append(self._format_danger_alert(trade, current_price, metrics))
                    trade.alerts_sent.append('DANGER_50')
            
            if metrics['against_pct'] >= 1 and 'WARNING_1PCT' not in trade.alerts_sent:
                if self._can_alert(trade.id, 'WARNING_1PCT', now):
                    alerts.append(self._format_warning_alert(trade, current_price, metrics))
                    trade.alerts_sent.append('WARNING_1PCT')
            
            if metrics['near_be'] and 'NEAR_BE' not in trade.alerts_sent:
                if self._can_alert(trade.id, 'NEAR_BE', now):
                    alerts.append(self._format_near_be_alert(trade, current_price))
                    trade.alerts_sent.append('NEAR_BE')
            
            if metrics['pct_to_sl'] <= 10 and 'LIQUIDATION' not in trade.alerts_sent:
                if self._can_alert(trade.id, 'LIQUIDATION', now):
                    alerts.append(self._format_liquidation_alert(trade, current_price, metrics))
                    trade.alerts_sent.append('LIQUIDATION')
        
        # 22. BE REJECT ALERT
        if trade.status == 'TP1':
            if self._is_near_be(trade, current_price) and self._is_moving_against(trade, current_price):
                if 'BE_REJECT' not in trade.alerts_sent:
                    if self._can_alert(trade.id, 'BE_REJECT', now):
                        alerts.append(self._format_be_reject_alert(trade, current_price))
                        trade.alerts_sent.append('BE_REJECT')
        
        # 23. RAPID MOVE ALERT
        if self._detect_rapid_move(trade, current_price):
            if 'RAPID_MOVE' not in trade.alerts_sent:
                if self._can_alert(trade.id, 'RAPID_MOVE', now, COOLDOWNS['RAPID']):
                    alerts.append(self._format_rapid_alert(trade, current_price))
                    trade.alerts_sent.append('RAPID_MOVE')
        
        # 24-25. TIME ALERTS
        time_to_expiry = trade.expiry_time - now
        if timedelta(0) < time_to_expiry < timedelta(minutes=30):
            if 'TIME_30MIN' not in trade.alerts_sent:
                alerts.append(self._format_time_alert(trade, time_to_expiry))
                trade.alerts_sent.append('TIME_30MIN')
        
        if trade.is_expired() and trade.status == 'PENDING':
            if 'EXPIRED' not in trade.alerts_sent:
                alerts.append(self._format_expired_alert(trade))
                trade.alerts_sent.append('EXPIRED')
                trade.status = 'EXPIRED'
        
        # Update history
        trade.price_history.append({
            'time': now.isoformat(),
            'price': current_price
        })
        trade.price_history = trade.price_history[-100:]
        
        return alerts
    
    # ============ HELPER METHODS ============
    
    def _can_alert(self, trade_id: str, alert_type: str, now: datetime, cooldown: int = None) -> bool:
        if cooldown is None:
            cooldown = COOLDOWNS['DEFAULT']
        key = f"{trade_id}_{alert_type}"
        if key in self.last_alert_time:
            elapsed = (now - self.last_alert_time[key]).seconds
            return elapsed >= cooldown
        self.last_alert_time[key] = now
        return True
    
    def _is_tp_hit(self, trade: Trade, price: float, tp_num: int) -> bool:
        tp_price = getattr(trade, f'tp{tp_num}')
        if trade.direction == 'LONG':
            return price >= tp_price
        return price <= tp_price
    
    def _is_approaching_tp(self, trade: Trade, price: float, tp_num: int) -> bool:
        tp_price = getattr(trade, f'tp{tp_num}')
        entry = trade.entry_avg
        
        if trade.direction == 'LONG':
            total = tp_price - entry
            current = price - entry
        else:
            total = entry - tp_price
            current = entry - price
        
        if total <= 0:
            return False
        
        progress = current / total
        return ALERT_THRESHOLDS['TP_APPROACH'] <= progress < 1.0
    
    def _is_tp_missed(self, trade: Trade, price: float, tp_num: int) -> bool:
        tp_price = getattr(trade, f'tp{tp_num}')
        
        if len(trade.price_history) < 5:
            return False
        
        recent_prices = [p['price'] for p in trade.price_history[-10:]]
        
        if trade.direction == 'LONG':
            near_tp = any(p >= tp_price * 0.995 for p in recent_prices)
            now_below = price < tp_price * 0.99
            return near_tp and now_below
        else:
            near_tp = any(p <= tp_price * 1.005 for p in recent_prices)
            now_above = price > tp_price * 1.01
            return near_tp and now_above
    
    def _is_sl_hit(self, trade: Trade, price: float) -> bool:
        if trade.direction == 'LONG':
            return price <= trade.current_sl
        return price >= trade.current_sl
    
    def _is_near_be(self, trade: Trade, price: float) -> bool:
        be = trade.breakeven_price
        return abs(price - be) / be < ALERT_THRESHOLDS['NEAR_BE']
    
    def _is_moving_against(self, trade: Trade, price: float) -> bool:
        if len(trade.price_history) < 2:
            return False
        prev = trade.price_history[-2]['price']
        if trade.direction == 'LONG':
            return price < prev
        return price > prev
    
    def _calculate_metrics(self, trade: Trade, current_price: float) -> dict:
        entry = trade.entry_avg
        sl = trade.current_sl
        
        metrics = {}
        
        if trade.direction == 'LONG':
            dist_to_sl = current_price - sl
            total_risk = entry - sl
            pct_to_sl = (dist_to_sl / total_risk) * 100 if total_risk > 0 else 100
            against_pct = ((entry - current_price) / entry) * 100 if current_price < entry else 0
        else:
            dist_to_sl = sl - current_price
            total_risk = sl - entry
            pct_to_sl = (dist_to_sl / total_risk) * 100 if total_risk > 0 else 100
            against_pct = ((current_price - entry) / entry) * 100 if current_price > entry else 0
        
        metrics['pct_to_sl'] = max(0, pct_to_sl)
        metrics['against_pct'] = max(0, against_pct)
        metrics['near_be'] = self._is_near_be(trade, current_price)
        return metrics
    
    def _detect_rapid_move(self, trade: Trade, price: float) -> bool:
        if len(trade.price_history) < 3:
            return False
        
        five_min_ago = datetime.utcnow() - timedelta(minutes=5)
        recent = [p for p in trade.price_history if datetime.fromisoformat(p['time']) > five_min_ago]
        
        if len(recent) < 2:
            return False
        
        change = abs(recent[-1]['price'] - recent[0]['price']) / recent[0]['price']
        return change >= ALERT_THRESHOLDS['RAPID_MOVE']
    
    # ============ ALL 25 ALERT FORMATTERS ============
    
    def _format_entry_alert(self, trade: Trade, price: float) -> str:
        return f"""
🎯 <b>{trade.pair} এন্ট্রি জোনে!</b>

💰 দাম: ${price}
📊 জোন: ${trade.entry_min} - ${trade.entry_max}

<b>🎯 টার্গেটস:</b>
🥇 TP1: ${trade.tp1}
🥈 TP2: ${trade.tp2}
🥉 TP3: ${trade.tp3}
🛡️ SL: ${trade.stop_loss}

✅ এখনই ট্রেড খোলো!
"""
    
    def _format_tp1_approach_alert(self, trade: Trade, price: float) -> str:
        progress = self._calculate_progress(trade, price, 1)
        return f"""
🎯 <b>{trade.pair} APPROACHING TP1!</b>

💰 দাম: ${price}
🥇 TP1: ${trade.tp1}
📊 প্রোগ্রেস: {progress:.1f}%

<b>প্রস্তুতি নাও:</b>
✅ ৩০% ক্লোজ করতে প্রস্তুত থাকো
🛡️ SL BE তে মুভ করার জন্য রেডি
"""
    
    def _format_tp2_approach_alert(self, trade: Trade, price: float) -> str:
        progress = self._calculate_progress(trade, price, 2)
        return f"""
🎯 <b>{trade.pair} APPROACHING TP2!</b>

💰 দাম: ${price}
🥈 TP2: ${trade.tp2}
📊 প্রোগ্রেস: {progress:.1f}%

<b>অবস্থা:</b>
✅ TP1: {trade.tp1_closed_percent}% ক্লোজড
🛡️ SL: BE তে (${trade.current_sl})
"""
    
    def _format_tp3_approach_alert(self, trade: Trade, price: float) -> str:
        progress = self._calculate_progress(trade, price, 3)
        return f"""
🎯 <b>{trade.pair} APPROACHING TP3!</b>

💰 দাম: ${price}
🥉 TP3: ${trade.tp3}
📊 প্রোগ্রেস: {progress:.1f}%

<b>অবস্থা:</b>
✅ TP1: {trade.tp1_closed_percent}%
✅ TP2: {trade.tp2_closed_percent}%
🛡️ SL: TP1 তে (${trade.current_sl})
"""
    
    def _calculate_progress(self, trade: Trade, current_price: float, tp_num: int) -> float:
        tp_price = getattr(trade, f'tp{tp_num}')
        entry = trade.entry_avg
        
        if trade.direction == 'LONG':
            total = tp_price - entry
            current = current_price - entry
        else:
            total = entry - tp_price
            current = entry - current_price
        
        return (current / total * 100) if total > 0 else 0
    
    def _format_tp1_hit_alert(self, trade: Trade, price: float) -> str:
        if trade.direction == 'LONG':
            profit = ((trade.tp1 - trade.entry_avg) / trade.entry_avg) * 100
        else:
            profit = ((trade.entry_avg - trade.tp1) / trade.entry_avg) * 100
        
        return f"""
🥇🥇🥇 <b>{trade.pair} TP1 HIT!</b> 🥇🥇🥇

💰 দাম: ${price}
🎯 TP1: ${trade.tp1}
💵 প্রফিট: +{profit:.2f}%

<b>📋 এখন করো:</b>
1️⃣ <b>৩০% পজিশন বন্ধ করো</b> ✅
2️⃣ প্রফিট বুক করো 💰
3️⃣ SL মুভ করো → <b>BE</b> 🛡️

<b>🎉 রিস্ক-ফ্রি ট্রেড!</b>
"""
    
    def _format_after_tp1_strategy(self, trade: Trade) -> str:
        return f"""
📋 <b>TP1 পরের স্ট্র্যাটেজি:</b>

<b>বর্তমান:</b>
🥇 TP1: ✅ ডন (৩০% ক্লোজড)
🛡️ SL: BE তে (${trade.breakeven_price:.4f})
🥈 TP2: ${trade.tp2}
🥉 TP3: ${trade.tp3}

<b>পরবর্তী:</b>
🎯 TP2 হিট → ৩০% ক্লোজ + SL → TP1
🎯 TP3 হিট → ৪০% ক্লোজ + ফুল ক্লোজ
🛑 SL হিট → ব্রেকইভেন (নো লস!)

<b>✅ এখন আর লস হবে না!</b>
"""
    
    def _format_tp2_hit_alert(self, trade: Trade, price: float) -> str:
        if trade.direction == 'LONG':
            p1 = ((trade.tp1 - trade.entry_avg) / trade.entry_avg) * 100
            p2 = ((trade.tp2 - trade.entry_avg) / trade.entry_avg) * 100
        else:
            p1 = ((trade.entry_avg - trade.tp1) / trade.entry_avg) * 100
            p2 = ((trade.entry_avg - trade.tp2) / trade.entry_avg) * 100
        
        return f"""
🥈🥈🥈 <b>{trade.pair} TP2 HIT!</b> 🥈🥈🥈

💰 দাম: ${price}
🎯 TP2: ${trade.tp2}
💵 TP2 প্রফিট: +{p2:.2f}%

<b>📋 এখন করো:</b>
1️⃣ <b>আরও ৩০% বন্ধ করো</b> (মোট ৬০%) ✅
2️⃣ SL ট্রেইল করো → <b>TP1</b> 🔒

<b>লকড প্রফিট:</b>
🥇 TP1: ৩০% @ ${trade.tp1} (+{p1:.2f}%)
🥈 TP2: ৩০% @ ${trade.tp2} (+{p2:.2f}%)
<b>মোট: ৬০% লকড! 💰💰</b>
"""
    
    def _format_after_tp2_strategy(self, trade: Trade) -> str:
        return f"""
📋 <b>TP2 পরের স্ট্র্যাটেজি:</b>

<b>বর্তমান:</b>
🥇 TP1: ✅ ৩০% @ ${trade.tp1}
🥈 TP2: ✅ ৩০% @ ${trade.tp2}
🛡️ SL: TP1 তে (${trade.tp1}) 🔒
🥉 TP3: ${trade.tp3} (বাকি ৪০%)

<b>গ্যারান্টিড:</b>
💰 <b>মিনিমাম ৬০% প্রফিট লকড!</b>
🛡️ SL TP1 তে = TP1 প্রফিট সিকিউর!

<b>ফাইনাল:</b>
🎯 TP3 হিট → বাকি ৪০% ক্লোজ
🎉 ফুল ট্রেড কমপ্লিট
"""
    
    def _format_tp3_hit_alert(self, trade: Trade, price: float) -> str:
        if trade.direction == 'LONG':
            p1 = ((trade.tp1 - trade.entry_avg) / trade.entry_avg) * 100
            p2 = ((trade.tp2 - trade.entry_avg) / trade.entry_avg) * 100
            p3 = ((trade.tp3 - trade.entry_avg) / trade.entry_avg) * 100
        else:
            p1 = ((trade.entry_avg - trade.tp1) / trade.entry_avg) * 100
            p2 = ((trade.entry_avg - trade.tp2) / trade.entry_avg) * 100
            p3 = ((trade.entry_avg - trade.tp3) / trade.entry_avg) * 100
        
        avg_profit = (p1 + p2 + p3) / 3
        
        return f"""
🥉🥉🥉 <b>{trade.pair} TP3 HIT!</b> 🥉🥉🥉
🎉🎉🎉 <b>FINAL TARGET REACHED!</b> 🎉🎉🎉

💰 দাম: ${price}
🎯 TP3: ${trade.tp3}
💵 TP3 প্রফিট: +{p3:.2f}%

<b>🏆 ALL TARGETS COMPLETE!</b>

<b>📋 ফাইনাল একশন:</b>
1️⃣ <b>বাকি ৪০% বন্ধ করো</b> ✅
2️⃣ <b>ফুল পজিশন ক্লোজড!</b> 🎉

<b>💰 ফাইনাল সামারি:</b>
┌─────────────────────────┐
│ 🥇 TP1: ৩০% × +{p1:.2f}%    │
│ 🥈 TP2: ৩০% × +{p2:.2f}%    │
│ 🥉 TP3: ৪০% × +{p3:.2f}%    │
├─────────────────────────┤
│ 📊 অ্যাভারেজ: +{avg_profit:.2f}%  │
│ ✅ টোটাল: ১০০% ক্লোজড   │
└─────────────────────────┘
"""
    
    def _format_trade_complete_alert(self, trade: Trade) -> str:
        return f"""
🎊🎊🎊 <b>TRADE COMPLETE: {trade.pair}</b> 🎊🎊🎊

<b>সম্পূর্ণ সামারি:</b>
পেয়ার: {trade.pair}
ডিরেকশন: {trade.direction}
এন্ট্রি: ${trade.entry_avg:.4f}
স্ট্যাটাস: ✅ <b>ALL TP HIT</b>

<b>প্রফিট ডিস্ট্রিবিউশন:</b>
🥇 TP1 (${trade.tp1}): ৩০% ক্লোজড
🥈 TP2 (${trade.tp2}): ৩০% ক্লোজড
🥉 TP3 (${trade.tp3}): ৪০% ক্লোজড

<b>রিস্ক ম্যানেজমেন্ট:</b>
✅ SL BE তে মুভড
✅ ট্রেইলিং SL ব্যবহারড
✅ পারশিয়াল প্রফিট বুকড

🎉 <b>পরবর্তী ট্রেডের জন্য প্রস্তুত!</b> 🎉
"""
    
    def _format_tp2_missed_alert(self, trade: Trade, price: float) -> str:
        return f"""
😢 <b>{trade.pair} TP2 MISSED!</b>

💰 বর্তমান: ${price}
🥈 TP2 ছিল: ${trade.tp2}
📉 দাম TP2 থেকে নিচে নেমে গেছে

<b>অবস্থা:</b>
✅ TP1: ৩০% ক্লোজড
🛡️ SL: BE তে (${trade.current_sl})
❌ TP2: মিসড

<b>কী করবে:</b>
1️⃣ অপেক্ষা করো TP2 আবার হিট হতে
2️⃣ বর্তমান দামে বাকি ক্লোজ করো
3️⃣ SL BE তে = নো লস
"""
    
    def _format_tp3_missed_alert(self, trade: Trade, price: float) -> str:
        return f"""
😢 <b>{trade.pair} TP3 MISSED!</b>

💰 বর্তমান: ${price}
🥉 TP3 ছিল: ${trade.tp3}
📉 দাম TP3 থেকে নিচে নেমে গেছে

<b>অবস্থা:</b>
✅ TP1: ৩০% ক্লোজড
✅ TP2: ৩০% ক্লোজড
🛡️ SL: TP1 তে (${trade.current_sl})
❌ TP3: মিসড

<b>কী করবে:</b>
1️⃣ বর্তমান দামে বাকি ৪০% ক্লোজ করো
2️⃣ অপেক্ষা করো আবার উপরে উঠতে
3️⃣ ট্রেইলিং SL ব্যবহার করো

<b>লকড:</b>
💰 ৬০% ইতিমধ্যে লকড @ প্রফিট
"""
    
    def _format_be_move_alert(self, trade: Trade, old_sl: float) -> str:
        return f"""
⚪ <b>STOP LOSS MOVED TO BREAKEVEN!</b>

🛡️ Old SL: ${old_sl}
✅ New SL: ${trade.current_sl}
🎯 Entry: ${trade.breakeven_price:.4f}

<b>🎉 RISK-FREE TRADE!</b>
❌ এখন লস হবে না
✅ শুধু প্রফিট বা ব্রেকইভেন
💰 মিনিমাম ৩০% প্রফিট সিকিউরড
"""
    
    def _format_trailing_alert(self, trade: Trade, old_sl: float, level: int) -> str:
        levels = {1: "TP1", 2: "TP2"}
        new_level = levels.get(level, "TP")
        
        return f"""
🔒 <b>TRAILING SL UPDATED!</b>

🛡️ Old SL: ${old_sl}
✅ New SL: ${trade.current_sl} ({new_level})
💰 {new_level} প্রফিট লকড!

<b>গ্যারান্টিড:</b>
🥇 TP1 প্রফিট: লকড ✅
{'🥈 TP2 প্রফিট: লকড ✅' if level >= 2 else '🥈 TP2: চলছে...'}

<b>বেনিফিট:</b>
📉 দাম নিচে গেলেও {new_level} প্রফিট থাকবে
🚀 উপরে গেলে আরও প্রফিট
💯 রিস্ক ফ্রি!
"""
    
    def _format_sl_hit_alert(self, trade: Trade, price: float) -> str:
        if trade.tp2_hit:
            result = "💰💰 প্রফিটে (৬০% লকড)!"
            sl_type = "Trailing (TP2 লকড)"
        elif trade.tp1_hit:
            result = "⚪ ব্রেকইভেন (৩০% প্রফিট)!"
            sl_type = "BE (TP1 লকড)"
        else:
            result = "❌ লস"
            sl_type = "Initial SL"
        
        return f"""
🛑 <b>{trade.pair} STOP LOSS HIT!</b>

💰 দাম: ${price}
🛡️ SL: ${trade.current_sl}
📊 টাইপ: {sl_type}

<b>রেজাল্ট:</b>
{result}

<b>ক্লোজড:</b>
🥇 TP1: {trade.tp1_closed_percent}%
🥈 TP2: {trade.tp2_closed_percent}%
🥉 TP3: {trade.tp3_closed_percent}%

<b>পরবর্তী ট্রেডের জন্য প্রস্তুত! 💪</b>
"""
    
    def _format_critical_alert(self, trade: Trade, price: float, metrics: dict) -> str:
        return f"""
🚨🚨🚨 <b>CRITICAL DANGER: {trade.pair}</b> 🚨🚨🚨

💰 বর্তমান: ${price}
🛡️ SL: ${trade.current_sl}
📊 দূরত্ব: মাত্র {metrics['pct_to_sl']:.1f}% বাকি!

<b>⚡ তুরন্ত ক্লোজ করো!</b>
❌ <b>এখনই বন্ধ করো!</b>
📉 লস বড় হতে পারে
🔥 লিকুইডেশন রিস্ক!

<b>সময় নষ্ট করো না!</b>
"""
    
    def _format_danger_alert(self, trade: Trade, price: float, metrics: dict) -> str:
        return f"""
🚨 <b>DANGER ALERT: {trade.pair}</b> 🚨

💰 বর্তমান: ${price}
🛡️ SL: ${trade.current_sl}
📊 SL এর {metrics['pct_to_sl']:.1f}% দূরত্বে

<b>⚠️ সতর্কতা:</b>
👁️ স্ক্রিনে চোখ রাখো
🛑 প্রস্তুত থাকো বন্ধ করতে
⚡ দ্রুত মুভমেন্ট সম্ভব

<b>পরবর্তী: 25% দূরত্বে CRITICAL!</b>
"""
    
    def _format_warning_alert(self, trade: Trade, price: float, metrics: dict) -> str:
        return f"""
⚠️ <b>WARNING: {trade.pair}</b>

💰 বর্তমান: ${price}
📉 এন্ট্রির বিপরীতে: {metrics['against_pct']:.2f}%
🎯 এন্ট্রি ছিল: ${trade.entry_avg:.4f}

<b>খেয়াল করো:</b>
📊 ট্রেড ভুল দিকে যাচ্ছে
🛑 SL হিট হতে পারে
👁️ মনিটরিং বাড়াও

<b>ঐচ্ছিক:</b>
Early exit বিবেচনা করতে পারো
"""
    
    def _format_near_be_alert(self, trade: Trade, price: float) -> str:
        return f"""
⚪ <b>{trade.pair} Near Breakeven</b>

💰 বর্তমান: ${price}
⚪ BE: ${trade.breakeven_price:.4f}

<b>সুযোগ!</b>
🎯 দাম BE এর কাছে
✅ প্রফিট জোনে যেতে পারে
🛡️ SL রেডি রাখো

<b>পরবর্তী:</b>
উপরে গেলে → TP1
নিচে গেলে → SL চেক
"""
    
    def _format_liquidation_alert(self, trade: Trade, price: float, metrics: dict) -> str:
        return f"""
💀💀💀 <b>LIQUIDATION RISK: {trade.pair}</b> 💀💀💀

💰 বর্তমান: ${price}
🛡️ SL: ${trade.current_sl}
📊 দূরত্ব: মাত্র {metrics['pct_to_sl']:.1f}%!

<b>🚨 লিকুইডেশন সম্ভব!</b>
🔥 হাই লেভারেজ = বিপদ
❌ <b>তুরন্ত বন্ধ করো!</b>
📉 আর অপেক্ষা না

<b>বাঁচতে হলে এখনই ক্লোজ!</b>
"""
    
    def _format_be_reject_alert(self, trade: Trade, price: float) -> str:
        return f"""
💔 <b>{trade.pair} BE REJECTION!</b>

💰 বর্তমান: ${price}
⚪ BE ছিল: ${trade.breakeven_price:.4f}
📉 দিক: নিচে (বিপরীতে)

<b>⚠️ সতর্কতা:</b>
🛑 BE থেকে বাউন্স খেলো
📉 আবার লস জোনে
🛡️ SL এখন BE তে: ${trade.current_sl}

<b>কী করবে:</b>
1️⃣ অপেক্ষা করো SL হিটের
2️⃣ Early close করো
3️⃣ DCA বিবেচনা করো

<b>মনে রাখো:</b>
লস হবে না কারণ SL BE তে!
"""
    
    def _format_rapid_alert(self, trade: Trade, price: float) -> str:
        direction = "পাম্প" if trade.direction == "SHORT" else "ডাম্প"
        emoji = "🚀" if trade.direction == "LONG" else "💥"
        
        return f"""
{emoji} <b>RAPID {direction.upper()}: {trade.pair}</b> {emoji}

💰 বর্তমান: ${price}
⚡ গত ৫ মিনিটে: ১%+ মুভ
📊 অস্বাভাবিক ভোলাটিলিটি

<b>🚨 সতর্ক!</b>
👁️ স্ক্রিনে চোখ রাখো
🛑 ম্যানুয়ালি ক্লোজ করতে পারো
📉 বড় মুভ আসতে পারে

<b>কারণ:</b>
বড় নিউজ/হোয়েল এক্টিভিটি
"""
    
    def _format_time_alert(self, trade: Trade, time_left: timedelta) -> str:
        minutes = int(time_left.seconds / 60)
        
        return f"""
⏰ <b>TIME WARNING: {trade.pair}</b>

⏳ বাকি সময়: {minutes} মিনিট
⏱️ সিগন্যাল এক্সপায়ার হতে চলেছে

<b>স্ট্যাটাস:</b>
TP1: {'✅' if trade.tp1_hit else '❌'}
TP2: {'✅' if trade.tp2_hit else '❌'}
TP3: {'✅' if trade.tp3_hit else '❌'}

<b>কী করবে:</b>
🎯 এন্ট্রি নিতে হলে এখনই নাও
❌ না হলে নতুন সিগন্যাল অপেক্ষা করো
"""
    
    def _format_expired_alert(self, trade: Trade) -> str:
        return f"""
⏰ <b>{trade.pair} সিগন্যাল এক্সপায়ার্ড!</b>

⏱️ ভ্যালিডিটি শেষ হয়ে গেছে
📊 আর এন্ট্রি নিও না

<b>স্ট্যাটাস:</b>
❌ পেন্ডিং ছিল, এন্ট্রি হয়নি
🗑️ এই সিগন্যাল ইগনোর করো

<b>পরবর্তী:</b>
নতুন সিগন্যালের জন্য অপেক্ষা করো
"""
