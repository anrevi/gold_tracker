"""
Configuration settings for Gold Telegram Bot
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConfig:
    """Bot configuration settings"""
    
    # Telegram settings
    telegram_bot_token: str
    telegram_chat_id: str
    
    # Update settings
    update_interval_minutes: int = 3
    timezone: str = "Asia/Kolkata"
    
    # Feature flags
    enable_charts: bool = False
    enable_technical_analysis: bool = True
    enable_price_alerts: bool = False
    
    # API settings
    request_timeout: int = 10
    max_retries: int = 3
    
    # Data source settings
    use_premium_apis: bool = False
    metals_api_key: Optional[str] = None
    gold_api_key: Optional[str] = None
    
    # Message formatting
    use_emojis: bool = True
    include_timestamp: bool = True
    
    # Historical data
    store_historical_data: bool = True
    historical_data_file: str = "historical_data.json"
    max_historical_records: int = 1000
    
    # Alert thresholds
    price_change_alert_percent: float = 2.0  # Alert if price changes by 2%
    rsi_overbought: float = 70
    rsi_oversold: float = 30
    
    @classmethod
    def from_env(cls) -> 'BotConfig':
        """Create config from environment variables"""
        return cls(
            telegram_bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID', ''),
            update_interval_minutes=int(os.getenv('UPDATE_INTERVAL_MINUTES', '3')),
            timezone=os.getenv('TIMEZONE', 'Asia/Kolkata'),
            enable_charts=os.getenv('ENABLE_CHARTS', 'false').lower() == 'true',
            enable_technical_analysis=os.getenv('ENABLE_TECHNICAL_ANALYSIS', 'true').lower() == 'true',
            enable_price_alerts=os.getenv('ENABLE_PRICE_ALERTS', 'false').lower() == 'true',
            metals_api_key=os.getenv('METALS_API_KEY'),
            gold_api_key=os.getenv('GOLD_API_KEY'),
        )
    
    def validate(self) -> bool:
        """Validate configuration"""
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not self.telegram_chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is required")
        return True


# API Endpoints
class APIEndpoints:
    """API endpoint configurations"""
    
    # NSE India
    NSE_EQUITY_QUOTE = "https://www.nseindia.com/api/quote-equity"
    NSE_BASE_URL = "https://www.nseindia.com"
    
    # MCX
    MCX_LIVE_RATES = "https://www.mcxindia.com/live-rates"
    
    # Forex
    EXCHANGE_RATE_API = "https://api.exchangerate-api.com/v4/latest/USD"
    FRANKFURTER_API = "https://api.frankfurter.app/latest"
    
    # Gold prices
    GOLD_PRICE_ORG = "https://data-asg.goldprice.org/dbXRates/USD"
    METALS_API = "https://metals-api.com/api/latest"
    GOLD_API_IO = "https://www.goldapi.io/api"
    
    # Alternative sources
    GOOD_RETURNS_GOLD = "https://www.goodreturns.in/gold-rates/mcx.json"
    INVESTING_COM_GOLD = "https://www.investing.com/commodities/gold"


# Market Constants
class MarketConstants:
    """Market-related constants"""
    
    # Conversions
    TROY_OUNCE_TO_GRAMS = 31.1035
    
    # Indian taxes and duties
    GOLD_IMPORT_DUTY = 0.125  # 12.5%
    GOLD_GST = 0.03  # 3%
    
    # Market hours (IST)
    MCX_MARKET_OPEN = "09:00"
    MCX_MARKET_CLOSE = "23:30"
    NSE_MARKET_OPEN = "09:15"
    NSE_MARKET_CLOSE = "15:30"
    
    # Symbols
    TATA_GOLD_NSE_SYMBOL = "TATAGOLD"
    MCX_GOLD_SYMBOL = "GOLD"


# Message Templates
class MessageTemplates:
    """Message formatting templates"""
    
    HEADER = "🏆 *TATA GOLD ETF TRADING UPDATE* 🏆"
    SEPARATOR = "━━━━━━━━━━━━━━━━━━━━━━━━"
    
    ERROR_MESSAGE = """
⚠️ *Update Failed*
Unable to fetch gold prices at this time.
Please check again later.
    """
    
    ALERT_TEMPLATE = """
🚨 *PRICE ALERT* 🚨
{symbol} has moved {change}% in the last update!
Current: {current_price}
Previous: {previous_price}
    """


# Export default config
config = BotConfig.from_env()
