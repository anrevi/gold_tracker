#!/usr/bin/env python3
"""
Enhanced TATA Gold ETF Trading Bot with Charts and Technical Analysis
"""

import os
import sys
import io
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import json

# Check if optional dependencies are available
try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import pandas as pd
    import numpy as np
    CHARTS_ENABLED = True
except ImportError:
    CHARTS_ENABLED = False
    logging.warning("Chart generation disabled. Install matplotlib and pandas to enable.")

from gold_telegram_bot import GoldDataFetcher, TelegramBot, GoldData, logger


class TechnicalAnalysis:
    """Technical analysis calculations for gold prices"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return None
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi, 2)
    
    @staticmethod
    def calculate_moving_average(prices: List[float], period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return None
        return round(sum(prices[-period:]) / period, 2)
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price - ema) * multiplier + ema
        
        return round(ema, 2)
    
    @staticmethod
    def get_signal(rsi: Optional[float]) -> str:
        """Get trading signal based on RSI"""
        if rsi is None:
            return "📊 Insufficient data"
        
        if rsi > 70:
            return "🔴 OVERBOUGHT - Consider selling"
        elif rsi < 30:
            return "🟢 OVERSOLD - Consider buying"
        elif rsi > 60:
            return "🟡 Bullish momentum"
        elif rsi < 40:
            return "🟡 Bearish pressure"
        else:
            return "⚪ Neutral zone"


class ChartGenerator:
    """Generate price charts for Telegram"""
    
    def __init__(self):
        if not CHARTS_ENABLED:
            raise ImportError("Chart generation requires matplotlib and pandas")
    
    def create_price_chart(
        self, 
        timestamps: List[datetime], 
        prices: List[float], 
        title: str = "Gold Price Trend"
    ) -> io.BytesIO:
        """Create a price chart"""
        plt.figure(figsize=(12, 6))
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # Plot price line
        plt.plot(timestamps, prices, linewidth=2, color='#FFD700', label='Price')
        
        # Calculate and plot moving averages if enough data
        if len(prices) >= 20:
            ma20 = pd.Series(prices).rolling(window=20).mean()
            plt.plot(timestamps, ma20, '--', linewidth=1.5, color='#FF6B6B', label='MA20')
        
        if len(prices) >= 50:
            ma50 = pd.Series(prices).rolling(window=50).mean()
            plt.plot(timestamps, ma50, '--', linewidth=1.5, color='#4ECDC4', label='MA50')
        
        plt.title(title, fontsize=16, fontweight='bold')
        plt.xlabel('Time', fontsize=12)
        plt.ylabel('Price (₹)', fontsize=12)
        plt.legend(loc='best')
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Save to BytesIO
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
    
    def create_comparison_chart(
        self, 
        data: dict
    ) -> io.BytesIO:
        """Create a comparison chart for multiple gold metrics"""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Gold Market Overview', fontsize=16, fontweight='bold')
        
        # Chart 1: TATA Gold ETF
        axes[0, 0].bar(['NAV', 'iNAV'], 
                       [data.get('nav', 0), data.get('inav', 0)], 
                       color=['#FFD700', '#FFA500'])
        axes[0, 0].set_title('TATA Gold ETF')
        axes[0, 0].set_ylabel('Price (₹)')
        
        # Chart 2: US Gold Trend
        us_prices = [data.get('us_prev', 0), data.get('us_current', 0)]
        colors = ['#FF6B6B' if us_prices[1] < us_prices[0] else '#51CF66']
        axes[0, 1].bar(['Previous', 'Current'], us_prices, color=colors)
        axes[0, 1].set_title('US Gold Spot')
        axes[0, 1].set_ylabel('Price ($)')
        
        # Chart 3: MCX Gold
        axes[1, 0].bar(['MCX Gold'], [data.get('mcx', 0)], color='#4ECDC4')
        axes[1, 0].set_title('MCX Gold')
        axes[1, 0].set_ylabel('Price (₹/10g)')
        
        # Chart 4: Currency & Landed Rate
        axes[1, 1].bar(['USD/INR', 'Landed Rate (₹/g)'], 
                       [data.get('usd_inr', 0), data.get('landed_rate', 0)/10], 
                       color=['#FF6B6B', '#51CF66'])
        axes[1, 1].set_title('Forex & Landed Rate')
        
        plt.tight_layout()
        
        # Save to BytesIO
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf


class EnhancedTelegramBot(TelegramBot):
    """Enhanced Telegram bot with chart and image support"""
    
    def send_photo(self, photo: io.BytesIO, caption: str = "") -> bool:
        """Send photo to Telegram"""
        try:
            url = f"{self.base_url}/sendPhoto"
            files = {'photo': photo}
            data = {
                'chat_id': self.chat_id,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
            
            import requests
            response = requests.post(url, files=files, data=data, timeout=30)
            response.raise_for_status()
            
            logger.info("Photo sent successfully to Telegram")
            return True
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            return False
    
    def format_enhanced_message(self, data: GoldData, technical_signals: dict = None) -> str:
        """Format enhanced message with technical analysis"""
        base_message = self.format_message(data)
        
        if technical_signals:
            tech_section = f"""
📊 *TECHNICAL ANALYSIS*
├ RSI (14): {technical_signals.get('rsi', 'N/A')}
├ Signal: {technical_signals.get('signal', 'N/A')}
├ MA20: ₹{technical_signals.get('ma20', 'N/A')}
└ MA50: ₹{technical_signals.get('ma50', 'N/A')}
"""
            base_message = base_message.replace(
                "📈 *TRADING SIGNALS*", 
                tech_section + "\n📈 *TRADING SIGNALS*"
            )
        
        return base_message


class HistoricalDataStore:
    """Store and retrieve historical gold price data"""
    
    def __init__(self, filepath: str = "historical_data.json"):
        self.filepath = filepath
        self.data = self._load_data()
    
    def _load_data(self) -> dict:
        """Load historical data from file"""
        try:
            if os.path.exists(self.filepath):
                with open(self.filepath, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load historical data: {e}")
        return {'prices': [], 'timestamps': []}
    
    def save_data(self, price: float, timestamp: str = None):
        """Save new price point"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        self.data['prices'].append(price)
        self.data['timestamps'].append(timestamp)
        
        # Keep only last 1000 data points
        if len(self.data['prices']) > 1000:
            self.data['prices'] = self.data['prices'][-1000:]
            self.data['timestamps'] = self.data['timestamps'][-1000:]
        
        try:
            with open(self.filepath, 'w') as f:
                json.dump(self.data, f)
        except Exception as e:
            logger.error(f"Could not save historical data: {e}")
    
    def get_recent_prices(self, count: int = 50) -> List[float]:
        """Get recent prices"""
        return self.data['prices'][-count:] if self.data['prices'] else []


def main_enhanced():
    """Enhanced main function with charts and technical analysis"""
    # Get environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        sys.exit(1)
    
    # Initialize components
    fetcher = GoldDataFetcher()
    bot = EnhancedTelegramBot(bot_token, chat_id)
    historical_store = HistoricalDataStore()
    
    try:
        # Fetch current data
        data = fetcher.fetch_all_data()
        
        # Save to historical store
        if data.tata_gold_nav:
            historical_store.save_data(data.tata_gold_nav, data.timestamp)
        
        # Calculate technical indicators
        recent_prices = historical_store.get_recent_prices()
        technical_signals = {}
        
        if len(recent_prices) >= 14:
            ta = TechnicalAnalysis()
            rsi = ta.calculate_rsi(recent_prices)
            ma20 = ta.calculate_moving_average(recent_prices, 20)
            ma50 = ta.calculate_moving_average(recent_prices, 50)
            
            technical_signals = {
                'rsi': rsi,
                'signal': ta.get_signal(rsi),
                'ma20': ma20,
                'ma50': ma50
            }
        
        # Format and send message
        message = bot.format_enhanced_message(data, technical_signals)
        bot.send_message(message)
        
        # Generate and send chart if enabled
        if CHARTS_ENABLED and len(recent_prices) >= 20:
            try:
                chart_gen = ChartGenerator()
                
                # Create comparison chart
                chart_data = {
                    'nav': data.tata_gold_nav,
                    'inav': data.tata_gold_inav,
                    'mcx': data.mcx_gold_price,
                    'us_prev': data.us_previous_close,
                    'us_current': data.us_gold_price,
                    'usd_inr': data.usd_inr,
                    'landed_rate': data.india_landed_rate
                }
                
                chart = chart_gen.create_comparison_chart(chart_data)
                bot.send_photo(chart, "📊 Gold Market Comparison Chart")
                
                logger.info("Chart sent successfully")
            except Exception as e:
                logger.warning(f"Could not generate chart: {e}")
        
        logger.info("Enhanced update sent successfully")
        
    except Exception as e:
        logger.error(f"Error in enhanced bot: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Check if enhanced mode is requested
    if "--enhanced" in sys.argv or os.getenv("ENABLE_CHARTS") == "true":
        if CHARTS_ENABLED:
            main_enhanced()
        else:
            logger.error("Enhanced mode requires matplotlib and pandas")
            logger.info("Install with: pip install matplotlib pandas")
            sys.exit(1)
    else:
        # Run standard bot
        from gold_telegram_bot import main
        main()
