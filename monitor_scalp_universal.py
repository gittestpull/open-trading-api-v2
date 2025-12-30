import sys
import os
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime
import argparse

# Add examples_user to path for kis_auth
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))
import kis_auth

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("universal_scalp.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Strategy Parameters
RSI_PERIOD = 9
RSI_BUY_LEVEL = 30
BB_PERIOD = 20
BB_STD = 2
TARGET_PROFIT = 0.005  # 0.5%
PYRAMIDING_THRESHOLD = 0.01  # 1.0% drop for next buy
MAX_STEPS = 4
WEIGHTS = [1, 2, 4, 8]

class UniversalScalper:
    def __init__(self, ticker, budget, live_mode=False):
        self.ticker = ticker.upper()
        self.budget = budget
        self.live_mode = live_mode
        self.is_domestic = ticker.isdigit() and len(ticker) == 6
        self.market = "Domestic" if self.is_domestic else "Overseas"
        
        # State management
        self.state = "SEARCHING"
        self.avg_buy_price = 0
        self.total_qty = 0
        self.current_step = 0
        
        # API Auth
        kis_auth.auth()
        self.trenv = kis_auth.getTREnv()
        
    def get_minute_chart(self):
        """Unified minute chart fetcher."""
        if self.is_domestic:
            url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            tr_id = "FHKST03010200"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": self.ticker,
                "FID_INPUT_HOUR_1": datetime.now().strftime("%H%M%S"),
                "FID_PW_DATA_INCU_YN": "Y",
                "FID_ETC_CLS_CODE": ""
            }
        else:
            url = "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
            tr_id = "HHDFS76950200"
            params = {
                "AUTH": "",
                "EXCD": "NAS", # Standardizing to NASDAQ for now, could be dynamic
                "SYMB": self.ticker,
                "NMIN": "1",
                "PINC": "0",
                "NEXT": "",
                "NREC": "40",
                "FILL": "",
                "KEYB": ""
            }

        res = kis_auth._url_fetch(url, tr_id, "", params)
        if res.isOK():
            output2 = res.getBody().output2
            df = pd.DataFrame(output2)
            
            # Map column names based on market
            if self.is_domestic:
                cols_map = {'stck_prpr': 'last', 'stck_oprc': 'open', 'stck_hgpr': 'high', 'stck_lwpr': 'low', 'cntg_vol': 'vol'}
            else:
                cols_map = {'last': 'last', 'open': 'open', 'high': 'high', 'low': 'low', 'evol': 'vol'}
            
            df = df.rename(columns=cols_map)
            # Convert to numeric
            cols = ['last', 'open', 'high', 'low', 'vol']
            for col in cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df.iloc[::-1].reset_index(drop=True)
        else:
            logger.error(f"Failed to fetch chart: {res.getErrorMessage()}")
            return None

    def calculate_indicators(self, df):
        if df is None or len(df) < BB_PERIOD:
            return None, None
            
        delta = df['last'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        sma = df['last'].rolling(window=BB_PERIOD).mean()
        std = df['last'].rolling(window=BB_PERIOD).std()
        upper_bb = sma + (std * BB_STD)
        lower_bb = sma - (std * BB_STD)
        
        return rsi.iloc[-1], (lower_bb.iloc[-1], upper_bb.iloc[-1])

    def place_order(self, dv="buy", qty=0, price=0):
        if qty <= 0: return False
        
        mode_str = "LIVE" if self.live_mode else "DRY RUN"
        logger.info(f"[{mode_str}] {dv.upper()} {qty} of {self.ticker} at {price}")
        
        if not self.live_mode: 
            # Play a distinct sound for Universal bot even in dry run
            os.system("afplay /System/Library/Sounds/Ping.aiff")
            return True
        
        if self.is_domestic:
            url = "/uapi/domestic-stock/v1/trading/order-cash"
            tr_id = "TTTC0012U" if dv == "buy" else "TTTC0011U"
            params = {
                "CANO": self.trenv.my_acct,
                "ACNT_PRDT_CD": self.trenv.my_prod,
                "PDNO": self.ticker,
                "ORD_DVSN": "00",
                "ORD_QTY": str(int(qty)),
                "ORD_UNPR": str(int(price)), # Domestic is int
                "EXCG_ID_DVSN_CD": "KRX"
            }
        else:
            url = "/uapi/overseas-stock/v1/trading/order"
            tr_id = "TTTT1002U" if dv == "buy" else "TTTT1006U"
            params = {
                "CANO": self.trenv.my_acct,
                "ACNT_PRDT_CD": self.trenv.my_prod,
                "OVRS_EXCG_CD": "NASD", # Hardcoded for NASDAQ
                "PDNO": self.ticker,
                "ORD_QTY": str(int(qty)),
                "OVRS_ORD_UNPR": str(round(price, 2)), # Overseas has decimals
                "ORD_DVSN": "00"
            }
            if dv == "sell": params["SLL_TYPE"] = "00"

        res = kis_auth._url_fetch(url, tr_id, "", params, postFlag=True)
        if res.isOK():
            os.system("afplay /System/Library/Sounds/Ping.aiff")
            logger.info(f"Order Success! No: {res.getBody().output.get('ODNO')}")
            return True
        else:
            logger.error(f"Order Failed: {res.getErrorMessage()}")
            return False

    def run(self):
        logger.info(f"Starting Universal Scalper | Ticker: {self.ticker} ({self.market}) | Budget: {self.budget:,}")
        sum_weights = sum(WEIGHTS)
        
        while True:
            df = self.get_minute_chart()
            rsi, bb = self.calculate_indicators(df)
            
            if rsi is None or np.isnan(rsi):
                time.sleep(10)
                continue
                
            curr_price = df['last'].iloc[-1]
            lower_bb, upper_bb = bb
            
            logger.info(f"Price: {curr_price:.2f} | RSI: {rsi:.1f} | BB: [{lower_bb:.2f}, {upper_bb:.2f}] | Avg: {self.avg_buy_price:.2f} ({self.total_qty}) | Step: {self.current_step} | State: {self.state}")
            
            if self.state == "SEARCHING":
                if rsi <= RSI_BUY_LEVEL and curr_price <= lower_bb:
                    step_budget = self.budget * (WEIGHTS[0] / sum_weights)
                    qty = int(step_budget / curr_price)
                    if self.place_order("buy", qty, curr_price):
                        self.avg_buy_price = curr_price
                        self.total_qty = qty
                        self.current_step = 1
                        self.state = "HOLDING"
            
            elif self.state == "HOLDING":
                profit_rate = (curr_price - self.avg_buy_price) / self.avg_buy_price
                
                # Pyramiding (Averaging Down)
                if profit_rate <= -PYRAMIDING_THRESHOLD and self.current_step < MAX_STEPS:
                    step_budget = self.budget * (WEIGHTS[self.current_step] / sum_weights)
                    qty = int(step_budget / curr_price)
                    if self.place_order("buy", qty, curr_price):
                        new_total_qty = self.total_qty + qty
                        self.avg_buy_price = ((self.avg_buy_price * self.total_qty) + (curr_price * qty)) / new_total_qty
                        self.total_qty = new_total_qty
                        self.current_step += 1
                        logger.info(f"Averaged Down. New Avg Price: {self.avg_buy_price:.2f}")

                # Exit Conditions
                if curr_price >= upper_bb or profit_rate >= TARGET_PROFIT:
                    reason = "BB Upper" if curr_price >= upper_bb else "Target Profit"
                    logger.info(f"EXIT Triggered: {reason} | Profit: {profit_rate:.2%}")
                    if self.place_order("sell", self.total_qty, curr_price):
                        self.state = "SEARCHING"
                        self.avg_buy_price = 0
                        self.total_qty = 0
                        self.current_step = 0
            
            time.sleep(30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True, help="Ticker symbol (e.g., 014940, TSLA)")
    parser.add_argument("--budget", type=int, default=1000000, help="Total budget in KRW (default: 1M)")
    parser.add_argument("--live", action="store_true", help="Execute real orders")
    args = parser.parse_args()
    
    scalper = UniversalScalper(args.ticker, args.budget, args.live)
    try:
        scalper.run()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
