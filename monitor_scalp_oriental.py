import sys
import os
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse

# Add examples_user to path to import kis_auth
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))

try:
    import kis_auth
except ImportError as e:
    print(f"Error importing kis_auth: {e}")
    sys.exit(1)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("oriental_scalp.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Constants
STOCK_CODE = "014940"  # Oriental Precision & Engineering (오리엔탈정공)
STOCK_NAME = "오리엔탈정공"
INTERVAL = 30  # Poll every 30 seconds for scalping
ENV_DV = "real"

# Strategy Parameters
RSI_PERIOD = 9
RSI_BUY_LEVEL = 30
RSI_SELL_LEVEL = 70
BB_PERIOD = 20
BB_STD = 2
TARGET_PROFIT = 0.005  # 0.5% Target profit from average price

# Averaging Down Strategy (추매)
MAX_STEPS = 4          # 최대 4차 매수까지
PYRAMIDING_THRESHOLD = 0.01  # -1% drop from avg price to trigger next buy
WEIGHTS = [1, 2, 4, 8]  # 비중 비율 (Total 15)

def get_minute_chart(stock_code):
    """Fetches 1-minute chart data (last 30 minutes)."""
    kis_auth.auth()
    tr_id = "FHKST03010200"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_HOUR_1": datetime.now().strftime("%H%M%S"),
        "FID_PW_DATA_INCU_YN": "Y",
        "FID_ETC_CLS_CODE": ""
    }
    API_URL = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    res = kis_auth._url_fetch(API_URL, tr_id, "", params)
    
    if res.isOK():
        output2 = res.getBody().output2
        df = pd.DataFrame(output2)
        # Convert columns to numeric
        cols = ['stck_prpr', 'stck_oprc', 'stck_hgpr', 'stck_lwpr', 'cntg_vol']
        for col in cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        # Reverse to get chronological order
        df = df.iloc[::-1].reset_index(drop=True)
        return df
    else:
        res.printError(url=API_URL)
        return pd.DataFrame()

def calculate_indicators(df):
    """Calculates RSI and Bollinger Bands."""
    if len(df) < BB_PERIOD:
        return None

    # RSI Calculation
    delta = df['stck_prpr'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Bollinger Bands
    df['ma20'] = df['stck_prpr'].rolling(window=BB_PERIOD).mean()
    df['std20'] = df['stck_prpr'].rolling(window=BB_PERIOD).std()
    df['bb_upper'] = df['ma20'] + (BB_STD * df['std20'])
    df['bb_lower'] = df['ma20'] - (BB_STD * df['std20'])

    return df.iloc[-1]  # Return the latest values

def place_order(ord_dv, qty, price, dry_run=True):
    """Places a limit order."""
    if qty <= 0:
        logger.warning(f"Order skipped: Quantity is {qty}")
        return False

    trenv = kis_auth.getTREnv()
    if not trenv.my_acct:
        logger.error("Account error")
        return False

    action = "BUY" if ord_dv == "buy" else "SELL"
    logger.info(f"[{'DRY RUN' if dry_run else 'LIVE'}] {action} Order: {int(qty)} of {STOCK_NAME} at {price}")

    if dry_run:
        return True

    tr_id = "TTTC0012U" if ord_dv == "buy" else "TTTC0011U"
    params = {
        "CANO": trenv.my_acct,
        "ACNT_PRDT_CD": trenv.my_prod,
        "PDNO": STOCK_CODE,
        "ORD_DVSN": "00", # Limit
        "ORD_QTY": str(int(qty)),
        "ORD_UNPR": str(price),
        "EXCG_ID_DVSN_CD": "KRX",
        "SLL_TYPE": "",
        "CNDT_PRIC": ""
    }
    API_URL_ORDER = "/uapi/domestic-stock/v1/trading/order-cash"
    res = kis_auth._url_fetch(API_URL_ORDER, tr_id, "", params, postFlag=True)
    
    if res.isOK():
        logger.info(f"Order Successful: {res.getBody().output.get('ODNO')}")
        return True
    return False

def run_scalping(dry_run=True, budget=1000000):
    logger.info(f"Starting Scalping Bot with Budget: {budget:,} KRW (Averaging Down)...")
    state = "SEARCHING"
    avg_buy_price = 0
    total_qty = 0
    current_step = 0 # 0 to MAX_STEPS-1
    
    # Calculate quantity units for each step based on initial price estimate
    # We will refine this at the time of purchase
    sum_weights = sum(WEIGHTS)
    
    try:
        while True:
            df = get_minute_chart(STOCK_CODE)
            if df.empty:
                time.sleep(INTERVAL)
                continue
            
            latest = calculate_indicators(df)
            if latest is None:
                logger.info("Gathering more data for indicators...")
                time.sleep(INTERVAL)
                continue

            current_price = int(latest['stck_prpr'])
            rsi = latest['rsi']
            bb_low = latest['bb_lower']
            bb_up = latest['bb_upper']

            logger.info(f"Price: {current_price} | RSI: {rsi:.1f} | BB: [{bb_low:.0f}, {bb_up:.0f}] | Avg: {avg_buy_price:.0f} ({total_qty}주) | State: {state}")

            if state == "SEARCHING":
                # Initial Buy Condition
                if rsi <= RSI_BUY_LEVEL and current_price <= bb_low:
                    # Calculate qty for this step based on weight and budget
                    step_budget = budget * (WEIGHTS[0] / sum_weights)
                    qty = int(step_budget / current_price)
                    
                    logger.info(f"!!! INITIAL BUY SIGNAL !!! Budget Step 1: {step_budget:,.0f} KRW. Qty: {qty}")
                    if place_order("buy", qty, current_price, dry_run=dry_run):
                        avg_buy_price = current_price
                        total_qty = qty
                        current_step = 1
                        state = "HOLDING"
            
            elif state == "HOLDING":
                profit_rate = (current_price - avg_buy_price) / avg_buy_price
                
                # Check for Averaging Down
                if profit_rate <= -PYRAMIDING_THRESHOLD and current_step < MAX_STEPS:
                    step_budget = budget * (WEIGHTS[current_step] / sum_weights)
                    qty = int(step_budget / current_price)
                    
                    logger.info(f"!!! PYRAMIDING BUY SIGNAL !!! Price dropped {profit_rate:.2%}. Budget Step {current_step+1}: {step_budget:,.0f} KRW. Next Qty: {qty}")
                    if place_order("buy", qty, current_price, dry_run=dry_run):
                        new_total_qty = total_qty + qty
                        avg_buy_price = ((avg_buy_price * total_qty) + (current_price * qty)) / new_total_qty
                        total_qty = new_total_qty
                        current_step += 1
                        logger.info(f"New Average Price: {avg_buy_price:.0f} (Total: {total_qty}주)")

                # Sell Conditions
                if current_price >= bb_up:
                    logger.info(f"!!! SELL SIGNAL (BB Upper) !!! Price: {current_price} vs BB Up: {bb_up:.0f}")
                    if place_order("sell", total_qty, current_price, dry_run=dry_run):
                        state = "SEARCHING"
                        avg_buy_price = 0
                        total_qty = 0
                        current_step = 0
                elif profit_rate >= TARGET_PROFIT:
                    logger.info(f"!!! SELL SIGNAL (Target Profit {profit_rate:.2%}) !!! Price: {current_price} vs Avg: {avg_buy_price:.0f}")
                    if place_order("sell", total_qty, current_price, dry_run=dry_run):
                        state = "SEARCHING"
                        avg_buy_price = 0
                        total_qty = 0
                        current_step = 0

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logger.info("Scalping stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Execute actual trades")
    parser.add_argument("--budget", type=int, default=1000000, help="Total budget in KRW (default: 1,000,000)")
    args = parser.parse_args()
    
    run_scalping(dry_run=not args.live, budget=args.budget)
