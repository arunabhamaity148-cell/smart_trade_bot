# database.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import json
import os

@dataclass
class Trade:
    # Required fields (no defaults) - MUST come first
    id: str
    pair: str
    direction: str
    entry_min: float
    entry_max: float
    tp1: float
    tp2: float
    tp3: float
    stop_loss: float
    risk_percent: float
    leverage: str
    valid_hours: int
    strength: int
    created_at: datetime
    
    # Optional fields (with defaults) - come after
    breakeven_price: Optional[float] = None
    current_sl: Optional[float] = None
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    tp1_closed_percent: float = 0
    tp2_closed_percent: float = 0
    tp3_closed_percent: float = 0
    status: str = 'PENDING'
    entry_price: Optional[float] = None
    alerts_sent: List[str] = field(default_factory=list)
    price_history: List[dict] = field(default_factory=list)
    
    @property
    def entry_avg(self) -> float:
        return (self.entry_min + self.entry_max) / 2
    
    @property
    def expiry_time(self) -> datetime:
        return self.created_at + timedelta(hours=self.valid_hours)
    
    @property
    def current_tp(self) -> Optional[float]:
        if not self.tp1_hit:
            return self.tp1
        elif not self.tp2_hit:
            return self.tp2
        elif not self.tp3_hit:
            return self.tp3
        return None
    
    def get_remaining_position(self) -> float:
        return 100 - self.tp1_closed_percent - self.tp2_closed_percent - self.tp3_closed_percent
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expiry_time
    
    def to_dict(self):
        return {
            'id': self.id,
            'pair': self.pair,
            'direction': self.direction,
            'entry_min': self.entry_min,
            'entry_max': self.entry_max,
            'tp1': self.tp1,
            'tp2': self.tp2,
            'tp3': self.tp3,
            'stop_loss': self.stop_loss,
            'risk_percent': self.risk_percent,
            'leverage': self.leverage,
            'valid_hours': self.valid_hours,
            'strength': self.strength,
            'created_at': self.created_at.isoformat(),
            'breakeven_price': self.breakeven_price,
            'current_sl': self.current_sl,
            'tp1_hit': self.tp1_hit,
            'tp2_hit': self.tp2_hit,
            'tp3_hit': self.tp3_hit,
            'tp1_closed_percent': self.tp1_closed_percent,
            'tp2_closed_percent': self.tp2_closed_percent,
            'tp3_closed_percent': self.tp3_closed_percent,
            'status': self.status,
            'entry_price': self.entry_price,
            'alerts_sent': self.alerts_sent,
            'price_history': self.price_history,
        }
    
    @classmethod
    def from_dict(cls, data):
        # Convert datetime string back to object
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


class TradeDatabase:
    def __init__(self, filename="trades.json"):
        self.filename = filename
        self.trades: List[Trade] = []
        self.load()
    
    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    self.trades = [Trade.from_dict(t) for t in data]
            except Exception as e:
                print(f"Error loading database: {e}")
                self.trades = []
    
    def save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump([t.to_dict() for t in self.trades], f, indent=2)
        except Exception as e:
            print(f"Error saving database: {e}")
    
    def add(self, trade: Trade):
        self.trades.append(trade)
        self.save()
    
    def get_active(self) -> List[Trade]:
        return [t for t in self.trades if t.status not in ['CLOSED', 'EXPIRED']]
    
    def get_by_pair(self, pair: str) -> Optional[Trade]:
        for t in self.trades:
            if t.pair == pair and t.status not in ['CLOSED', 'EXPIRED']:
                return t
        return None
    
    def update(self, trade: Trade):
        for i, t in enumerate(self.trades):
            if t.id == trade.id:
                self.trades[i] = trade
                self.save()
                return
    
    def close_all(self, pair: str):
        for t in self.trades:
            if t.pair == pair:
                t.status = 'CLOSED'
        self.save()
    
    def get_closed(self) -> List[Trade]:
        return [t for t in self.trades if t.status in ['CLOSED', 'EXPIRED']]
