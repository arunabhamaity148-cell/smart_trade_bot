"""
Crypto Options Alpha Bot - Main Entry Point
FINAL FIXED VERSION - Real-time Price + Warmup + Validation
"""

import os
import sys
import asyncio
import logging
import json
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from threading import Thread

from flask import Flask, jsonify
from telegram import Bot

from config.settings import (
    PORT, 
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID, 
    ASSETS_CONFIG, 
    TRADING_CONFIG, 
    STEALTH_CONFIG
)
from core.websocket_manager import ws_manager
from core.stealth_request import StealthRequest
from core.data_aggregator import DataAggregator, AssetData
from core.multi_asset_manager import MultiAssetManager, TradingSignal
from core.time_filter import TimeFilter
from core.news_guard import news_guard
from core.trade_monitor import TradeMonitor, ActiveTrade
from tg_bot.bot import AlphaTelegramBot

# ============== LOGGING ==============
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ============== FLASK APP ==============
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return {
        'status': 'running',
        'bot': 'Crypto Options Alpha Bot',
        'version': '2.3-final',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'assets': list(ASSETS_CONFIG.keys())
    }

@flask_app.route('/health')
def health():
    ws_stats = ws_manager.get_stats()
    return {
        'status': 'healthy',
        'websocket': ws_stats,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, 200

# ============== MAIN BOT CLASS ==============
class AlphaBot:
    def __init__(self):
        self.telegram = AlphaTelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.stealth = StealthRequest(STEALTH_CONFIG)
        self.data_agg = DataAggregator(self.stealth)
        self.asset_manager = MultiAssetManager(TRADING_CONFIG, ASSETS_CONFIG)
        self.time_filter = TimeFilter()
        self.trade_monitor = TradeMonitor(self.telegram)
        self.running = False
        self.cycle_count = 0
        self.last_signal_time = None
        self.signals_sent_this_hour = 0
        self.hour_start = datetime.now(timezone.utc)
        self.deploy_time = datetime.now(timezone.utc)  # Track deploy time
        
    async def run(self):
        """Main bot loop - FINAL FIXED VERSION"""
        self.running = True
        logger.info("🚀 Bot v2.3-final starting")
        logger.info(f"Deploy time: {self.deploy_time.isoformat()}")
        
        # Start WebSocket
        ws_task = asyncio.create_task(ws_manager.start(ASSETS_CONFIG))
        await asyncio.sleep(3)
        
        # Start Trade Monitor
        monitor_task = asyncio.create_task(
            self.trade_monitor.start_monitoring(self.get_current_price)
        )
        
        # Start Flask
        flask_thread = Thread(target=self._run_flask, daemon=True)
        flask_thread.start()
        
        # Startup message
        try:
            await self.telegram.send_status(
                "🟢 Bot v2.3 Final Started\n"
                f"Assets: {', '.join(ASSETS_CONFIG.keys())}\n"
                f"Threshold: {TRADING_CONFIG['min_score_threshold']}+\n"
                "✅ Fixed: Real-time price, 5min warmup, slippage protection"
            )
        except Exception as e:
            logger.error(f"Startup message failed: {e}")
        
        # Main loop
        while self.running:
            try:
                self.cycle_count += 1
                cycle_start = datetime.now(timezone.utc)
                
                # WARMUP CHECK: 5 minutes after deploy
                elapsed = (cycle_start - self.deploy_time).total_seconds()
                if elapsed < 300:  # 5 minutes
                    remaining = 300 - elapsed
                    logger.info(f"⏸️ WARMUP: {remaining:.0f}s remaining")
                    await asyncio.sleep(min(60, remaining))
                    continue
                
                # Reset hourly counter
                if (cycle_start - self.hour_start).seconds >= 3600:
                    self.signals_sent_this_hour = 0
                    self.hour_start = cycle_start
                
                # Check daily reset
                if self.asset_manager.should_reset_daily():
                    self.asset_manager.reset_daily_counters()
                
                # Check news guard
                trading_allowed, news_reason = await news_guard.check_trading_allowed()
                if not trading_allowed:
                    logger.warning(f"Trading halted: {news_reason}")
                    await asyncio.sleep(300)
                    continue
                
                # Get time quality
                try:
                    time_ok, time_info = self.time_filter.is_best_time()
                    time_quality = time_info.get('quality', 'moderate')
                except Exception as e:
                    logger.error(f"Time filter error: {e}")
                    time_quality = 'moderate'
                
                # STRICT: Check global cooldown (30 min)
                if self.last_signal_time:
                    cooldown_remaining = 1800 - (cycle_start - self.last_signal_time).total_seconds()
                    if cooldown_remaining > 0:
                        logger.info(f"⏸️ Global cooldown: {cooldown_remaining/60:.1f}min left")
                        await asyncio.sleep(min(60, cooldown_remaining))
                        continue
                
                # Fetch data
                logger.info(f"=== Cycle {self.cycle_count} | {time_quality} ===")
                market_data = await self.data_agg.get_all_assets_data(ASSETS_CONFIG)
                ws_data = self._get_websocket_data()
                
                # Merge with priority to WebSocket for real-time
                merged_data = self._merge_data(market_data, ws_data)
                
                if merged_data:
                    await self._process_market_data(merged_data, time_quality)
                
                # Adaptive sleep
                cycle_duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
                sleep_time = 60 if time_quality in ['excellent', 'good'] else 120
                
                logger.info(f"Cycle complete | Duration: {cycle_duration:.1f}s | Sleep: {sleep_time}s")
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    def _get_websocket_data(self) -> Dict:
        ws_data = {}
        for asset, config in ASSETS_CONFIG.items():
            if config.get('enable'):
                symbol = config['symbol']
                data = ws_manager.get_price_data(symbol)
                if data:
                    ws_data[asset] = data
        return ws_data
    
    def _merge_data(self, rest_data: Dict, ws_data: Dict) -> Dict:
        """Merge with WebSocket priority for real-time prices"""
        merged = rest_data.copy()
        for asset, ws_info in ws_data.items():
            if asset in merged:
                if 'trades' in ws_info:
                    merged[asset].recent_trades = ws_info['trades']
                if 'last_price' in ws_info:
                    merged[asset].spot_price = ws_info['last_price']
                if 'orderbook' in ws_info:
                    ws_ob = ws_info['orderbook']
                    if 'ofi_ratio' in ws_ob:
                        merged[asset].orderbook['ofi_ratio'] = ws_ob['ofi_ratio']
                    if 'bid_walls' in ws_ob:
                        merged[asset].orderbook['bid_walls'] = ws_ob['bid_walls']
                    if 'ask_walls' in ws_ob:
                        merged[asset].orderbook['ask_walls'] = ws_ob['ask_walls']
                    if 'mid_price' in ws_ob:
                        merged[asset].orderbook['mid_price'] = ws_ob['mid_price']
        return merged
    
    async def get_current_price(self, asset: str) -> float:
        """Get current price - WebSocket priority"""
        symbol = ASSETS_CONFIG[asset]['symbol']
        ws_data = ws_manager.get_price_data(symbol)
        if ws_data and 'last_price' in ws_data:
            return ws_data['last_price']
        try:
            return await self.data_agg.get_spot_price(symbol)
        except:
            return 0
    
    async def _process_market_data(self, market_data: Dict, time_quality: str):
        """Process with strict limits"""
        from strategies.liquidity_hunt import LiquidityHuntStrategy
        from strategies.gamma_squeeze import GammaSqueezeStrategy
        from indicators.greeks_engine import GreeksEngine
        from signals.scorer import AlphaScorer
        
        # STRICT: Max 2 signals per hour globally
        if self.signals_sent_this_hour >= 2:
            logger.info("🚫 Hourly signal limit reached (2)")
            return
        
        signals = []
        
        for asset, data in market_data.items():
            # Check if can send
            if not self.asset_manager.can_send_signal(asset):
                continue
            
            config = ASSETS_CONFIG[asset]
            symbol = config['symbol']
            recent_trades = ws_manager.get_recent_trades(symbol, 30)
            
            # Get REAL-TIME current price for entry
            current_price = await self.get_current_price(asset)
            if current_price == 0:
                logger.warning(f"No price for {asset}, skipping")
                continue
            
            # Strategy 1: Liquidity Hunt
            try:
                lh_strategy = LiquidityHuntStrategy(asset, config)
                lh_setup = await lh_strategy.analyze(
                    {
                        'orderbook': data.orderbook, 
                        'funding_rate': data.funding_rate,
                        'current_price': current_price
                    }, 
                    recent_trades
                )
                
                if lh_setup:
                    lh_setup['asset'] = asset
                    lh_setup['current_price'] = current_price
                    signals.append(('liquidity_hunt', lh_setup))
                    logger.info(f"🎯 LH Signal: {asset} @ {lh_setup.get('confidence', 0)}")
                    
            except Exception as e:
                logger.error(f"LH error: {e}")
            
            # Strategy 2: Gamma Squeeze (only excellent time)
            if time_quality == 'excellent':
                try:
                    greeks = GreeksEngine()
                    gs_strategy = GammaSqueezeStrategy(asset, config, greeks)
                    gs_setup = await gs_strategy.analyze(
                        {'orderbook': data.orderbook},
                        []
                    )
                    
                    if gs_setup:
                        gs_setup['asset'] = asset
                        gs_setup['current_price'] = current_price
                        signals.append(('gamma_squeeze', gs_setup))
                        logger.info(f"🎯 GS Signal: {asset} @ {gs_setup.get('confidence', 0)}")
                        
                except Exception as e:
                    logger.error(f"GS error: {e}")
        
        if signals:
            await self._score_and_send_signals(signals, market_data, time_quality)
    
    async def _score_and_send_signals(self, signals: List, market_data: Dict, time_quality: str):
        """Score and send with REAL-TIME PRICE VALIDATION"""
        from signals.scorer import AlphaScorer
        
        scorer = AlphaScorer(TRADING_CONFIG)
        scored_signals = []
        
        # Score all signals
        for strategy_name, setup in signals:
            asset = setup['asset']
            data = market_data.get(asset)
            if not data:
                continue
            
            # GET REAL-TIME PRICE
            current_price = await self.get_current_price(asset)
            if current_price == 0:
                logger.warning(f"No current price for {asset}")
                continue
            
            # VALIDATE: Signal price vs Market price
            signal_price = setup.get('entry_price', 0)
            if signal_price == 0:
                logger.warning(f"No signal price for {asset}")
                continue
            
            slippage = abs(signal_price - current_price) / current_price
            
            if slippage > 0.003:  # 0.3% max slippage
                logger.warning(f"🚫 {asset}: Slippage {slippage:.2%} too high")
                logger.warning(f"   Signal: {signal_price:,.2f} | Market: {current_price:,.2f}")
                continue  # Skip this signal
            
            # UPDATE to real market price
            setup['entry_price'] = current_price
            setup['stop_loss'] = current_price * 0.992 if setup['direction'] == 'long' else current_price * 1.008
            setup['target_1'] = current_price * 1.018 if setup['direction'] == 'long' else current_price * 0.982
            setup['target_2'] = current_price * 1.030 if setup['direction'] == 'long' else current_price * 0.970
            
            logger.info(f"✅ {asset}: Price validated | Slippage: {slippage:.3%}")
            logger.info(f"   Updated entry: {current_price:,.2f}")
            
            # Prepare market data for scoring
            score_data = {
                'orderbook': data.orderbook,
                'funding_rate': data.funding_rate,
                'spot_price': current_price,
                'perp_price': data.perp_price,
            }
            
            score = scorer.calculate_score(
                setup, 
                score_data,
                news_status="safe",
                time_quality=time_quality
            )
            
            setup['score_data'] = score
            setup['total_score'] = score['total_score']
            scored_signals.append((strategy_name, setup, score))
            
            logger.info(f"📊 {asset} | Score: {score['total_score']} | Rec: {score['recommendation']}")
        
        if not scored_signals:
            logger.info("No valid signals after price validation")
            return
        
        # Sort by score
        scored_signals.sort(key=lambda x: x[2]['total_score'], reverse=True)
        
        # Take ONLY TOP 1
        best = scored_signals[0]
        strategy_name, setup, score = best
        
        total_score = score['total_score']
        threshold = TRADING_CONFIG['min_score_threshold']
        
        # STRICT: Must be above threshold
        if total_score < threshold:
            logger.info(f"Best signal {total_score} below threshold {threshold}")
            return
        
        # STRICT: Exceptional (90+) or good time with 85+
        if time_quality not in ['excellent', 'good'] and total_score < 90:
            logger.info(f"Moderate time, score {total_score} < 90, skipping")
            return
        
        # Check can send with direction
        if not self.asset_manager.can_send_signal(
            setup['asset'], 
            setup['direction'],
            setup['entry_price']
        ):
            logger.info(f"Cannot send {setup['asset']} - cooldown or opposite active")
            return
        
        # Calculate position size
        position_size = self.asset_manager.calculate_position_size(
            setup['asset'], 
            setup['entry_price'], 
            setup['stop_loss']
        )
        setup['position_size'] = position_size
        
        # Build signal
        signal = TradingSignal(
            asset=setup['asset'],
            strategy=strategy_name,
            direction=setup['direction'],
            entry_price=setup['entry_price'],
            stop_loss=setup['stop_loss'],
            target_1=setup['target_1'],
            target_2=setup['target_2'],
            strike_selection=setup['strike_selection'],
            expiry_suggestion=setup['expiry_suggestion'],
            confidence=setup['confidence'],
            score_breakdown=score['component_scores'],
            rationale=setup['rationale'],
            timestamp=datetime.now(timezone.utc),
            total_score=total_score
        )
        
        # Send signal
        try:
            print("\n" + "="*60)
            print(f"🚨 SIGNAL: {signal.asset} {signal.direction.upper()}")
            print(f"Score: {total_score}/100 | Strategy: {strategy_name}")
            print(f"Entry: {signal.entry_price:,.2f} | Stop: {signal.stop_loss:,.2f}")
            print(f"Targets: {signal.target_1:,.2f} / {signal.target_2:,.2f}")
            print(f"Position: {position_size} contracts")
            print("="*60 + "\n")
            
            # Send to Telegram with position size
            await self.telegram.send_signal(setup, score, {
                'orderbook': market_data[signal.asset].orderbook,
                'position_size': position_size
            })
            
            # Add to trade monitor
            trade = ActiveTrade(
                asset=signal.asset,
                direction=signal.direction,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                tp1=signal.target_1,
                tp2=signal.target_2,
                strike=signal.strike_selection,
                expiry=datetime.now(timezone.utc) + timedelta(hours=48),
                position_size=position_size
            )
            self.trade_monitor.add_trade(trade)
            
            # Record signal sent
            self.asset_manager.record_signal(
                signal.asset, 
                signal.direction,
                signal.entry_price
            )
            
            # Update global counters
            self.last_signal_time = datetime.now(timezone.utc)
            self.signals_sent_this_hour += 1
            
            logger.info(f"✅ SENT: {signal.asset} {signal.direction} @ {total_score} | Size: {position_size}")
            
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Send failed: {e}", exc_info=True)
    
    def _run_flask(self):
        flask_app.run(
            host='0.0.0.0',
            port=PORT,
            threaded=True,
            debug=False,
            use_reloader=False
        )
    
    def stop(self):
        self.running = False
        ws_manager.stop()
        self.trade_monitor.stop_monitoring()
        logger.info("Bot stopped")

# ============== ENTRY POINT ==============
if __name__ == "__main__":
    bot = AlphaBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        bot.stop()
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
