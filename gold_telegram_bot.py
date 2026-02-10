#!/usr/bin/env python3
"""
TATA Gold ETF Trading Bot - Telegram Updates
Yahoo Finance based (NSE-free, stable)
"""

import os
import sys
import requests
import logging
import time
from datetime import datetime
from typing import Optional, Tuple
from dataclasses import dataclass

# ---------------- LOGGING ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("gold_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ---------------- DATA MODEL ---------------- #
@dataclass
class GoldData:
    tata_gold_nav: Optional[float] = None
    tata_gold_inav: Optional[float] = None
    mcx_gold_price: Optional[float] = None
    mcx_gold_trend: Optional[str] = None
    usd_inr: Optional[float] = None
    us_gold_price: Optional[float] = None
    us_previous_close: Optional[float] = None
    us_current_trend: Optional[str] = None
    india_landed_rate: Optional[float] = None
    timestamp: str = ""

# ---------------- FETCHER ---------------- #
class GoldDataFetcher:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })

    def fetch(self, url: str):
        try:
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"Fetch failed: {url} | {e}")
            return None

    # -------- YAHOO FINANCE NAV -------- #
    def get_tata_gold_etf(self) -> Tuple[Optional[float], Optional[float]]:
        """
        NAV  = Yahoo Finance market price
        iNAV = Calculated fair value
        """
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/TATAGOLD.NS"
            data = self.fetch(url)

            result = data["chart"]["result"][0]
            nav = result["meta"]["regularMarketPrice"]

            if not nav:
                return None, None

            nav = float(nav)
            logger.info(f"TATA Gold NAV (Yahoo): ₹{nav}")

            us_gold, _ = self.get_us_gold_price()
            usd_inr = self.get_usd_inr()

            if us_gold and usd_inr:
                inav = (us_gold * usd_inr) / 31.1035
                inav = round(inav, 2)
            else:
                inav = nav

            return round(nav, 2), inav

        except Exception as e:
            logger.error(f"Yahoo NAV error: {e}")
            return None, None

    # -------- USD INR -------- #
    def get_usd_inr(self) -> Optional[float]:
        sources = [
            "https://api.exchangerate-api.com/v4/latest/USD",
            "https://api.frankfurter.app/latest?from=USD&to=INR",
        ]

        for url in sources:
            data = self.fetch(url)
            if not data:
                continue
            rate = data.get("rates", {}).get("INR")
            if rate:
                logger.info(f"USD/INR: ₹{rate}")
                return float(rate)

        logger.warning("USD/INR fallback used")
        return 83.50

    # -------- US GOLD -------- #
    def get_us_gold_price(self) -> Tuple[Optional[float], Optional[float]]:
        url = "https://data-asg.goldprice.org/dbXRates/USD"
        data = self.fetch(url)

        try:
            item = data["items"][0]
            return float(item["xauPrice"]), float(item.get("xauClose", 0))
        except Exception:
            logger.warning("Gold fallback used")
            return 2650.0, 2645.0

    # -------- MCX CALC -------- #
    def get_mcx_gold(self, us_gold: float, usd_inr: float) -> Tuple[Optional[float], str]:
        if not us_gold or not usd_inr:
            return None, "N/A"

        price = (us_gold * usd_inr / 31.1035) * 10 * 1.025
        return round(price, 0), "📊 CALCULATED"

    # -------- ALL DATA -------- #
    def fetch_all(self) -> GoldData:
        data = GoldData(timestamp=datetime.now().strftime("%d-%b-%Y %H:%M:%S IST"))

        data.usd_inr = self.get_usd_inr()
        data.us_gold_price, data.us_previous_close = self.get_us_gold_price()

        if data.us_gold_price and data.us_previous_close:
            diff = data.us_gold_price - data.us_previous_close
            data.us_current_trend = "📈 UP" if diff > 0 else "📉 DOWN"

        data.tata_gold_nav, data.tata_gold_inav = self.get_tata_gold_etf()
        data.mcx_gold_price, data.mcx_gold_trend = self.get_mcx_gold(
            data.us_gold_price, data.usd_inr
        )

        if data.us_gold_price and data.usd_inr:
            data.india_landed_rate = round(
                (data.us_gold_price * data.usd_inr / 31.1035) * 1.125 * 1.03, 2
            )

        return data

# ---------------- TELEGRAM ---------------- #
class TelegramBot:

    def __init__(self, token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id

    def send(self, text: str):
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        requests.post(self.url, json=payload, timeout=10)

    def format(self, d: GoldData) -> str:
        return f"""
🏆 *TATA GOLD ETF UPDATE*

📊 *TATA Gold ETF*
NAV : ₹{d.tata_gold_nav}
iNAV: ₹{d.tata_gold_inav}

💰 *MCX Gold*
₹{d.mcx_gold_price}/10g ({d.mcx_gold_trend})

🌍 *US Gold*
${d.us_gold_price}/oz {d.us_current_trend}

💱 *USD/INR*
₹{d.usd_inr}

🇮🇳 *India Landed*
₹{d.india_landed_rate}/g

⏰ _{d.timestamp}_
""".strip()

# ---------------- MAIN ---------------- #
def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.error("Telegram env vars missing")
        sys.exit(1)

    fetcher = GoldDataFetcher()
    bot = TelegramBot(token, chat_id)

    data = fetcher.fetch_all()
    bot.send(bot.format(data))

if __name__ == "__main__":
    main()
