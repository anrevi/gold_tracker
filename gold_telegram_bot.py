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
            # Try NSE India API with proper headers
            url = "https://www.nseindia.com/api/quote-equity?symbol=TATAGOLD"
            
            # NSE requires cookies, so first visit the main page
            self.session.get("https://www.nseindia.com", timeout=10)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://www.nseindia.com/',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                nav = data.get('priceInfo', {}).get('lastPrice')
                inav = data.get('priceInfo', {}).get('close')
                if nav:
                    logger.info(f"TATA Gold ETF NAV: ₹{nav}")
                    return float(nav), float(inav) if inav else float(nav)
        except Exception as e:
            logger.warning(f"NSE API unavailable: {e}")
        
        # Fallback: Calculate approximate NAV from international gold prices
        try:
            us_gold, _ = self.get_us_gold_price()
            usd_inr = self.get_usd_inr()
            
            if us_gold and usd_inr:
                # TATA Gold ETF tracks international gold
                # Approximate: 1 unit = 1 gram of gold
                nav_estimate = (us_gold * usd_inr) / 31.1035
                logger.info(f"TATA Gold ETF (Estimated): ₹{nav_estimate:.2f}")
                return round(nav_estimate, 2), round(nav_estimate, 2)
        except Exception as e:
            logger.warning(f"Could not calculate estimate: {e}")
        
        return None, None
    
    def get_mcx_gold(self) -> Tuple[Optional[float], Optional[str]]:
        """Calculate MCX Gold price from international rates (free method)"""
        try:
            # Get international gold price and forex rate
            us_gold_current, us_gold_prev = self.get_us_gold_price()
            usd_inr = self.get_usd_inr()
            
            if us_gold_current and usd_inr:
                # Calculate MCX equivalent
                # MCX Gold is quoted per 10 grams
                # 1 troy ounce = 31.1035 grams
                inr_per_gram = (us_gold_current * usd_inr) / 31.1035
                
                # MCX typically trades at 2-3% premium to international
                mcx_premium = 1.025  # 2.5% premium
                mcx_price = inr_per_gram * 10 * mcx_premium
                
                # Calculate trend if we have previous price
                trend = "📊 CALCULATED"
                if us_gold_prev:
                    prev_mcx = (us_gold_prev * usd_inr) / 31.1035 * 10 * mcx_premium
                    change = mcx_price - prev_mcx
                    if change > 50:
                        trend = "📈 UP"
                    elif change < -50:
                        trend = "📉 DOWN"
                    else:
                        trend = "➡️ FLAT"
                
                logger.info(f"MCX Gold (Calculated): ₹{mcx_price:.0f}/10g")
                return round(mcx_price, 2), trend
            
            logger.info("MCX Gold: Insufficient data for calculation")
            return None, None
            
        except Exception as e:
            logger.error(f"Error calculating MCX Gold: {e}")
            return None, None
    
    def get_usd_inr(self) -> Optional[float]:
        """Fetch USD/INR exchange rate from multiple free sources"""
        
        sources = [
            {
                'name': 'ExchangeRate-API',
                'url': 'https://api.exchangerate-api.com/v4/latest/USD',
                'parser': lambda d: d['rates'].get('INR')
            },
            {
                'name': 'Frankfurter',
                'url': 'https://api.frankfurter.app/latest?from=USD&to=INR',
                'parser': lambda d: d['rates'].get('INR')
            },
            {
                'name': 'Fawaz Ahmed API',
                'url': 'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json',
                'parser': lambda d: d.get('usd', {}).get('inr')
            }
        ]
        
        for source in sources:
            try:
                response = self.fetch_with_retry(source['url'])
                if response and response.status_code == 200:
                    data = response.json()
                    rate = source['parser'](data)
                    if rate:
                        logger.info(f"USD/INR from {source['name']}: ₹{rate:.2f}")
                        return float(rate)
            except Exception as e:
                logger.warning(f"{source['name']} failed: {e}")
                continue
        
        # Fallback: Use approximate current rate
        logger.warning("Using fallback USD/INR rate")
        return 83.50  # Update this periodically
    
    def get_us_gold_price(self) -> Tuple[Optional[float], Optional[float]]:
        """Fetch US Gold spot price (current and previous close)"""
        
        # Try multiple free sources
        sources = [
            {
                'name': 'GoldPrice.org',
                'url': 'https://data-asg.goldprice.org/dbXRates/USD',
                'parser': lambda d: (d['items'][0]['xauPrice'], d['items'][0].get('xauClose'))
            },
            {
                'name': 'Metals.live',
                'url': 'https://api.metals.live/v1/spot/gold',
                'parser': lambda d: (d[0]['price'], d[0].get('previous_close'))
            },
        ]
        
        for source in sources:
            try:
                response = self.fetch_with_retry(source['url'])
                if response and response.status_code == 200:
                    data = response.json()
                    current, previous = source['parser'](data)
                    if current:
                        logger.info(f"US Gold from {source['name']}: ${current:.2f}/oz")
                        return float(current), float(previous) if previous else None
            except Exception as e:
                logger.warning(f"{source['name']} failed: {e}")
                continue
        
        # Ultimate fallback: Use a fixed approximate value (update this periodically)
        logger.warning("Using fallback gold price estimate")
        return 2650.0, 2645.0  # Approximate current gold prices
    
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
        
        # Fetch USD/INR first (needed for calculations)
        data.usd_inr = self.get_usd_inr()
        
        # Fetch US Gold prices (needed for calculations)
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
        
        # Now fetch/calculate TATA Gold ETF (may use US prices)
        nav, inav = self.get_tata_gold_etf()
        data.tata_gold_nav = nav
        data.tata_gold_inav = inav
        
        # Fetch/calculate MCX Gold (uses US prices and USD/INR)
        mcx_price, mcx_trend = self.get_mcx_gold()
        data.mcx_gold_price = mcx_price
        data.mcx_gold_trend = mcx_trend
        
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
        
        # Build message sections conditionally
        sections = []
        
        # Header
        sections.append("🏆 *TATA GOLD ETF TRADING UPDATE* 🏆")
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        sections.append("")
        
        # TATA Gold ETF
        if data.tata_gold_nav or data.tata_gold_inav:
            sections.append("📊 *TATA GOLD ETF*")
            if data.tata_gold_nav:
                sections.append(f"├ NAV: ₹{data.tata_gold_nav:.2f} {self._get_emoji(data.tata_gold_nav)}")
            if data.tata_gold_inav:
                sections.append(f"└ iNAV: ₹{data.tata_gold_inav:.2f}")
            sections.append("")
        
        # MCX Gold
        if data.mcx_gold_price or data.mcx_gold_trend:
            sections.append("💰 *MCX GOLD*")
            if data.mcx_gold_price:
                sections.append(f"├ Price: ₹{data.mcx_gold_price:,.0f}/10g")
            if data.mcx_gold_trend:
                sections.append(f"└ Trend: {data.mcx_gold_trend}")
            else:
                sections.append(f"└ Trend: Updating...")
            sections.append("")
        
        # US Markets
        if data.us_gold_price or data.us_previous_close:
            sections.append("🌍 *INTERNATIONAL MARKETS*")
            if data.us_gold_price:
                sections.append(f"├ US Gold Spot: ${data.us_gold_price:.2f}/oz")
            if data.us_previous_close:
                sections.append(f"├ Previous Close: ${data.us_previous_close:.2f}")
            if data.us_current_trend:
                sections.append(f"└ Trend: {data.us_current_trend}")
            sections.append("")
        
        # Forex & Rates
        if data.usd_inr or data.india_landed_rate:
            sections.append("💱 *FOREX & RATES*")
            if data.usd_inr:
                sections.append(f"├ USD/INR: ₹{data.usd_inr:.2f}")
            if data.india_landed_rate:
                sections.append(f"└ India Landed Rate: ₹{data.india_landed_rate:,.2f}/g")
                sections.append("  (incl. Import Duty 12.5% + GST 3%)")
            sections.append("")
        
        # Trading signals
        sections.append("📈 *TRADING SIGNALS*")
        sections.append(self._generate_trading_signals(data))
        sections.append("")
        
        # Footer
        sections.append(f"⏰ _Updated: {data.timestamp}_")
        sections.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        
        return "\n".join(sections)
    
    def _get_emoji(self, value: Optional[float]) -> str:
        """Get appropriate emoji based on value change"""
        # This is a placeholder - would need previous value to compare
        return "📊"
    
    def _generate_trading_signals(self, data: GoldData) -> str:
        """Generate basic trading signals"""
        signals = []
        
        # Compare US trend
        if data.us_current_trend:
            if "UP" in data.us_current_trend:
                signals.append("✅ US Market: Bullish momentum")
            elif "DOWN" in data.us_current_trend:
                signals.append("⚠️ US Market: Bearish pressure")
        
        # MCX trend
        if data.mcx_gold_trend:
            if "UP" in data.mcx_gold_trend:
                signals.append("✅ MCX: Positive trend")
            elif "DOWN" in data.mcx_gold_trend:
                signals.append("⚠️ MCX: Negative trend")
        
        # USD/INR impact
        if data.usd_inr:
            if data.usd_inr > 84:
                signals.append("💵 Rupee weakness - supports gold")
            elif data.usd_inr < 82:
                signals.append("💵 Rupee strength - pressure on gold")
        
        # Price levels (if available)
        if data.tata_gold_nav:
            if data.tata_gold_nav > 6500:
                signals.append("📊 TATA Gold at elevated levels")
            elif data.tata_gold_nav < 6000:
                signals.append("📊 TATA Gold at attractive levels")
        
        if not signals:
            return "📊 Monitoring market conditions\n💡 Data being collected from available sources"
        
        return "\n".join(signals)
    
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
        
        # Check if we have at least some data
        has_data = any([
            data.tata_gold_nav,
            data.tata_gold_inav,
            data.mcx_gold_price,
            data.usd_inr,
            data.us_gold_price
        ])
        
        if not has_data:
            logger.warning("No data available from any source")
            error_message = """
⚠️ *Gold Price Update - Data Unavailable*

Unable to fetch gold prices at this time.
All data sources are currently unavailable.

This could be due to:
- Market closed
- API maintenance
- Network issues

Will retry in next update cycle.
            """.strip()
            bot.send_message(error_message)
            sys.exit(0)
        
        message = bot.format_message(data)
        
        success = bot.send_message(message)
        
        if success:
            logger.info("Update sent successfully")
            # Log what data was available
            available = []
            if data.tata_gold_nav: available.append("TATA Gold")
            if data.mcx_gold_price: available.append("MCX")
            if data.us_gold_price: available.append("US Gold")
            if data.usd_inr: available.append("USD/INR")
            logger.info(f"Data sources available: {', '.join(available)}")
            sys.exit(0)
        else:
            logger.error("Failed to send update")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Try to send error notification
        try:
            error_msg = f"⚠️ Bot Error: {str(e)[:100]}"
            bot.send_message(error_msg)
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()
