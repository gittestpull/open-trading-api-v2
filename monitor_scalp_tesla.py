import sys
import os
import time
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import argparse

# Add path for kis_auth
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))
import kis_auth

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scalp_tesla.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
EXCH_CD = "NAS"      # For Price Inquiries (NASDAQ)
ORD_EXCH_CD = "NASD" # For Ordering (NASDAQ)
SYMBOL = "TSLA"
QTY = 1
GOAL_PROFIT = 0.005  # 0.5%
STOP_LOSS = -0.01    # -1.0%

class TSLAScalper:
    def __init__(self, live_mode=False):
        self.live_mode = live_mode
        self.state = "SEARCHING"
        self.entry_price = 0
        self.buy_order_no = ""
        
        # Auth
        kis_auth.auth()
        self.trenv = kis_auth.getTREnv()

    def get_minute_chart(self):
        """Fetches 1-minute chart data for TSLA"""
        url = "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
        tr_id = "HHDFS76950200"
        
        params = {
            "AUTH": "",
            "EXCD": EXCH_CD,
            "SYMB": SYMBOL,
            "NMIN": "1",
            "PINC": "0", # 당일
            "NEXT": "",
            "NREC": "40", # 40 candles
            "FILL": "",
            "KEYB": ""
        }
        
        res = kis_auth._url_fetch(url, tr_id, "", params)
        if res.isOK():
            output2 = res.getBody().output2
            df = pd.DataFrame(output2)
            # Convert columns to numeric
            cols = ['last', 'open', 'high', 'low', 'evol']
            for col in cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            return df.iloc[::-1].reset_index(drop=True) # Reverse to chronological
        else:
            logger.error(f"Failed to fetch minute chart: {res.getErrorMessage()}")
            return None

    def calculate_indicators(self, df):
        if df is None or len(df) < 20:
            return None, None
            
        # RSI (9)
        delta = df['last'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=9).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=9).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Bollinger Bands (20, 2)
        sma = df['last'].rolling(window=20).mean()
        std = df['last'].rolling(window=20).std()
        upper_bb = sma + (std * 2)
        lower_bb = sma - (std * 2)
        
        return rsi.iloc[-1], (lower_bb.iloc[-1], upper_bb.iloc[-1])

    def place_order(self, dv="buy", price=0):
        if not self.live_mode:
            logger.info(f"[DRY RUN] {dv.upper()} order for {SYMBOL} at {price}")
            return "DRY_RUN_ID"
            
        url = "/uapi/overseas-stock/v1/trading/order"
        # US Buy: TTTT1002U, US Sell: TTTT1006U
        tr_id = "TTTT1002U" if dv == "buy" else "TTTT1006U"
        
        params = {
            "CANO": self.trenv.my_acct,
            "ACNT_PRDT_CD": self.trenv.my_prod,
            "OVRS_EXCG_CD": ORD_EXCH_CD,
            "PDNO": SYMBOL,
            "ORD_QTY": str(QTY),
            "OVRS_ORD_UNPR": str(round(price, 2)), # US stocks need 2 decimal places
            "CTAC_TLNO": "",
            "MGCO_APTM_ODNO": "",
            "SLL_TYPE": "00" if dv == "sell" else "",
            "ORD_SVR_DVSN_CD": "0",
            "ORD_DVSN": "00" # Limit Order
        }
        
        res = kis_auth._url_fetch(url, tr_id, "", params, postFlag=True)
        if res.isOK():
            odno = res.getBody().output.get('ODNO')
            logger.info(f"SUCCESS: {dv.upper()} Order No {odno}")
            return odno
        else:
            logger.error(f"Order FAILED: {res.getErrorCode()} - {res.getErrorMessage()}")
            return None

    def run(self):
        logger.info(f"Starting Tesla Scalper (Live: {self.live_mode})")
        while True:
            df = self.get_minute_chart()
            rsi, bb = self.calculate_indicators(df)
            
            if rsi is None:
                time.sleep(10)
                continue
                
            curr_price = df['last'].iloc[-1]
            lower_bb, upper_bb = bb
            
            logger.info(f"Price: {curr_price:.2f} | RSI: {rsi:.1f} | BB: [{lower_bb:.2f}, {upper_bb:.2f}] | State: {self.state}")
            
            if self.state == "SEARCHING":
                if rsi <= 30 and curr_price <= lower_bb:
                    logger.info(">>> BUY SIGNAL TRIGGERED")
                    self.entry_price = curr_price
                    self.buy_order_no = self.place_order("buy", curr_price)
                    if self.buy_order_no:
                        self.state = "HOLDING"
            
            elif self.state == "HOLDING":
                profit_rate = (curr_price - self.entry_price) / self.entry_price
                
                if curr_price >= upper_bb or profit_rate >= GOAL_PROFIT or profit_rate <= STOP_LOSS:
                    reason = "BB Upper" if curr_price >= upper_bb else ("Target" if profit_rate >= GOAL_PROFIT else "StopLoss")
                    logger.info(f">>> SELL SIGNAL TRIGGERED ({reason}) | Profit: {profit_rate*100:.2f}%")
                    if self.place_order("sell", curr_price):
                        self.state = "SEARCHING"
            
            time.sleep(20) # Poll every 20 seconds

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Execute actual trades")
    args = parser.parse_args()
    
    scalper = TSLAScalper(live_mode=args.live)
    try:
        scalper.run()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
