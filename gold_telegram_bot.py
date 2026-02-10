#!/usr/bin/env python3
"""
TATA Gold ETF Trading Bot - Telegram Updates
Sends comprehensive gold market updates every 3 minutes
"""

import os
import sys
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import json
from dataclasses import dataclass
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gold_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class GoldData:
    """Data class for gold prices and related information"""
    tata_gold_nav: Optional[float] = None
    tata_gold_inav: Optional[float] = None
    mcx_gold_price: Optional[float] = None
    mcx_gold_trend: Optional[str] = None
    usd_inr: Optional[float] = None
    us_gold_price: Optional[float] = None
    india_landed_rate: Optional[float] = None
    us_previous_close: Optional[float] = None
    us_current_trend: Optional[str] = None
    timestamp: str = ""


class GoldDataFetcher:
    """Fetches gold price data from multiple sources"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_with_retry(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Fetch URL with retry logic"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        return None
    
    def get_tata_gold_etf(self) -> Tuple[Optional[float], Optional[float]]:
        """Fetch TATA Gold ETF NAV and iNAV"""
        try:
            # NSE API for TATA Gold ETF (TATAGOLD)
            url = "https://www.nseindia.com/api/quote-equity?symbol=TATAGOLD"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
                'Referer': 'https://www.nseindia.com/'
            }
            
            response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                nav = data.get('priceInfo', {}).get('lastPrice')
                # iNAV is typically close to current price
                inav = data.get('priceInfo', {}).get('close')
                return nav, inav
        except Exception as e:
            logger.error(f"Error fetching TATA Gold ETF: {e}")
        
        return None, None
    
    def get_mcx_gold(self) -> Tuple[Optional[float], Optional[str]]:
        """Fetch MCX Gold price and trend"""
        try:
            # MCX API endpoint
            url = "https://www.mcxindia.com/live-rates"
            # This is a placeholder - actual implementation would use MCX's official API
            # For now, using alternative gold price API
            alt_url = "https://www.goodreturns.in/gold-rates/mcx.json"
            
            response = self.fetch_with_retry(alt_url)
            if response:
                data = response.json()
                price = data.get('current_price')
                change = data.get('change', 0)
                trend = "📈 UP" if change > 0 else "📉 DOWN" if change < 0 else "➡️ FLAT"
                return price, trend
        except Exception as e:
            logger.error(f"Error fetching MCX Gold: {e}")
        
        return None, None
    
    def get_usd_inr(self) -> Optional[float]:
        """Fetch USD/INR exchange rate"""
        try:
            # Using exchangerate-api.com (free tier)
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            response = self.fetch_with_retry(url)
            
            if response:
                data = response.json()
                return data.get('rates', {}).get('INR')
            
            # Fallback to forex API
            alt_url = "https://api.frankfurter.app/latest?from=USD&to=INR"
            response = self.fetch_with_retry(alt_url)
            if response:
                data = response.json()
                return data.get('rates', {}).get('INR')
        except Exception as e:
            logger.error(f"Error fetching USD/INR: {e}")
        
        return None
    
    def get_us_gold_price(self) -> Tuple[Optional[float], Optional[float]]:
        """Fetch US Gold spot price (current and previous close)"""
        try:
            # Using metals-api.com or goldapi.io alternatives
            # Free alternative: using investing.com or kitco
            url = "https://data-asg.goldprice.org/dbXRates/USD"
            
            response = self.fetch_with_retry(url)
            if response:
                data = response.json()
                current_price = data.get('items', [{}])[0].get('xauPrice')
                prev_close = data.get('items', [{}])[0].get('xauClose')
                return current_price, prev_close
        except Exception as e:
            logger.error(f"Error fetching US Gold price: {e}")
        
        return None, None
    
    def calculate_india_landed_rate(self, us_gold_price: float, usd_inr: float) -> Optional[float]:
        """
        Calculate India landed gold rate
        Formula: (US Gold Price per oz * USD/INR / 31.1035) + Import Duty + GST
        """
        try:
            if not us_gold_price or not usd_inr:
                return None
            
            # Convert USD per troy oz to INR per gram
            inr_per_gram = (us_gold_price * usd_inr) / 31.1035
            
            # Add import duty (approx 12.5%) and GST (3%)
            import_duty_rate = 0.125
            gst_rate = 0.03
            
            landed_rate = inr_per_gram * (1 + import_duty_rate) * (1 + gst_rate)
            
            return round(landed_rate, 2)
        except Exception as e:
            logger.error(f"Error calculating landed rate: {e}")
            return None
    
    def fetch_all_data(self) -> GoldData:
        """Fetch all gold-related data"""
        logger.info("Fetching all gold market data...")
        
        data = GoldData(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"))
        
        # Fetch TATA Gold ETF
        nav, inav = self.get_tata_gold_etf()
        data.tata_gold_nav = nav
        data.tata_gold_inav = inav
        
        # Fetch MCX Gold
        mcx_price, mcx_trend = self.get_mcx_gold()
        data.mcx_gold_price = mcx_price
        data.mcx_gold_trend = mcx_trend
        
        # Fetch USD/INR
        data.usd_inr = self.get_usd_inr()
        
        # Fetch US Gold prices
        us_current, us_prev = self.get_us_gold_price()
        data.us_gold_price = us_current
        data.us_previous_close = us_prev
        
        # Calculate trend
        if us_current and us_prev:
            change = us_current - us_prev
            pct_change = (change / us_prev) * 100
            if change > 0:
                data.us_current_trend = f"📈 UP ${change:.2f} ({pct_change:.2f}%)"
            elif change < 0:
                data.us_current_trend = f"📉 DOWN ${abs(change):.2f} ({abs(pct_change):.2f}%)"
            else:
                data.us_current_trend = "➡️ FLAT"
        
        # Calculate India landed rate
        if us_current and data.usd_inr:
            data.india_landed_rate = self.calculate_india_landed_rate(us_current, data.usd_inr)
        
        logger.info("Data fetching completed")
        return data


class TelegramBot:
    """Telegram bot for sending updates"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    def format_message(self, data: GoldData) -> str:
        """Format gold data into readable Telegram message"""
        message = f"""
🏆 *TATA GOLD ETF TRADING UPDATE* 🏆
━━━━━━━━━━━━━━━━━━━━━━━━

📊 *TATA GOLD ETF*
├ NAV: ₹{data.tata_gold_nav:.2f} {self._get_emoji(data.tata_gold_nav)}
└ iNAV: ₹{data.tata_gold_inav:.2f}

💰 *MCX GOLD*
├ Price: ₹{data.mcx_gold_price:,.0f}/10g
└ Trend: {data.mcx_gold_trend}

🌍 *INTERNATIONAL MARKETS*
├ US Gold Spot: ${data.us_gold_price:.2f}/oz
├ Previous Close: ${data.us_previous_close:.2f}
└ Trend: {data.us_current_trend}

💱 *FOREX & RATES*
├ USD/INR: ₹{data.usd_inr:.2f}
└ India Landed Rate: ₹{data.india_landed_rate:,.2f}/g
  (incl. Import Duty 12.5% + GST 3%)

📈 *TRADING SIGNALS*
{self._generate_trading_signals(data)}

⏰ _Updated: {data.timestamp}_
━━━━━━━━━━━━━━━━━━━━━━━━
        """.strip()
        
        return message
    
    def _get_emoji(self, value: Optional[float]) -> str:
        """Get appropriate emoji based on value change"""
        # This is a placeholder - would need previous value to compare
        return "📊"
    
    def _generate_trading_signals(self, data: GoldData) -> str:
        """Generate basic trading signals"""
        signals = []
        
        # Compare US trend
        if data.us_current_trend and "UP" in data.us_current_trend:
            signals.append("✅ US Market: Bullish momentum")
        elif data.us_current_trend and "DOWN" in data.us_current_trend:
            signals.append("⚠️ US Market: Bearish pressure")
        
        # MCX trend
        if data.mcx_gold_trend and "UP" in data.mcx_gold_trend:
            signals.append("✅ MCX: Positive trend")
        elif data.mcx_gold_trend and "DOWN" in data.mcx_gold_trend:
            signals.append("⚠️ MCX: Negative trend")
        
        # USD/INR impact
        if data.usd_inr and data.usd_inr > 84:
            signals.append("💵 Rupee weakness - supports gold")
        
        return "\n".join(signals) if signals else "📊 Monitoring market conditions"
    
    def send_message(self, message: str) -> bool:
        """Send message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Message sent successfully to Telegram")
            return True
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False


def main():
    """Main function"""
    # Get environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables")
        sys.exit(1)
    
    # Initialize components
    fetcher = GoldDataFetcher()
    bot = TelegramBot(bot_token, chat_id)
    
    # Fetch and send data
    try:
        data = fetcher.fetch_all_data()
        message = bot.format_message(data)
        
        success = bot.send_message(message)
        
        if success:
            logger.info("Update sent successfully")
            sys.exit(0)
        else:
            logger.error("Failed to send update")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
