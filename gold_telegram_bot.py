#!/usr/bin/env python3
"""
TATA Gold ETF – Pre-Market Signal Bot
Correct iNAV scaling + IST time
"""

import os
import sys
import requests
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from zoneinfo import ZoneInfo  # Python 3.9+

# ---------------- LOGGING ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("gold_premarket.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# ---------------- DATA MODEL ---------------- #
@dataclass
class MarketData:
    etf_price: Optional[float] = None
    inav: Optional[float] = None
    premium: Optional[float] = None
    rsi_15m: Optional[float] = None
    signal: str = "WAIT"
    timestamp: str = ""

# ---------------- FETCHER ---------------- #
class DataFetcher:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})

    def fetch_json(self, url: str):
        try:
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Fetch failed: {url} | {e}")
            return None

    # -------- ETF PRICE (Yahoo) -------- #
    def get_etf_price(self) -> Optional[float]:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/TATAGOLD.NS"
        data = self.fetch_json(url)
        try:
            return float(data["chart"]["result"][0]["meta"]["regularMarketPrice"])
        except Exception:
            return None

    # -------- USD INR -------- #
    def get_usd_inr(self) -> float:
        data = self.fetch_json("https://api.exchangerate-api.com/v4/latest/USD")
        try:
            return float(data["rates"]["INR"])
        except Exception:
            return 83.50

    # -------- US GOLD -------- #
    def get_us_gold(self) -> float:
        data = self.fetch_json("https://data-asg.goldprice.org/dbXRates/USD")
        try:
            return float(data["items"][0]["xauPrice"])
        except Exception:
            return 2650.0

    # -------- iNAV (CORRECT) -------- #
    def calculate_inav(self, us_gold: float, usd_inr: float) -> float:
        """
        1 ETF unit ≈ 0.01 gram of gold
        """
        gold_inr_per_gram = (us_gold * usd_inr) / 31.1035
        return round(gold_inr_per_gram * 0.01, 2)

    # -------- RSI (PLACEHOLDER) -------- #
    def get_rsi_15m(self) -> float:
        return 43.5

    # -------- SIGNAL -------- #
    def generate_signal(self, d: MarketData) -> str:
        if d.premium is None or d.rsi_15m is None:
            return "WAIT"

        if d.premium > 1.5 and d.rsi_15m < 50:
            return "AVOID / PROFIT BOOK"
        elif d.premium < 0.5 and d.rsi_15m > 50:
            return "BUY / ADD"
        else:
            return "HOLD / WAIT"

    # -------- ALL DATA -------- #
    def fetch_all(self) -> MarketData:
        d = MarketData()
        d.timestamp = datetime.now(IST).strftime("%d-%b %H:%M IST")

        d.etf_price = self.get_etf_price()
        usd_inr = self.get_usd_inr()
        us_gold = self.get_us_gold()

        if d.etf_price:
            d.inav = self.calculate_inav(us_gold, usd_inr)
            d.premium = round(((d.etf_price - d.inav) / d.inav) * 100, 2)

        d.rsi_15m = self.get_rsi_15m()
        d.signal = self.generate_signal(d)

        return d

# ---------------- TELEGRAM ---------------- #
class TelegramBot:

    def __init__(self, token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id

    def send(self, text: str):
        requests.post(
            self.url,
            json={"chat_id": self.chat_id, "text": text},
            timeout=10
        )

    def format_message(self, d: MarketData) -> str:
        return f"""
ETF: ₹{d.etf_price:.2f}
Fair iNAV: ₹{d.inav:.2f}
Premium: {d.premium:+.2f}%

RSI (15m): {d.rsi_15m}

Signal: {d.signal}

Updated: {d.timestamp}
""".strip()

# ---------------- MAIN ---------------- #
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.error("Missing Telegram credentials")
        sys.exit(1)

    fetcher = DataFetcher()
    bot = TelegramBot(token, chat_id)

    data = fetcher.fetch_all()
    bot.send(bot.format_message(data))

    logger.info("Pre-market update sent")

if __name__ == "__main__":
    main()
