import sys
import os
import time
import logging
from datetime import datetime

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
        logging.FileHandler("oriental_trade.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Constants
STOCK_CODE = "014940"  # Oriental Precision & Engineering (오리엔탈정공)
STOCK_NAME = "오리엔탈정공"
BUY_PRICE = 7650
SELL_PRICE = 8600
QTY = 5
INTERVAL = 10  # Seconds
ENV_DV = "real"  # 'real' or 'demo'

def get_current_price(stock_code):
    """Fetches the current price of the stock."""
    kis_auth.auth()
    tr_id = "FHKST01010100" 
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code
    }
    API_URL_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-price"
    res = kis_auth._url_fetch(API_URL_PRICE, tr_id, "", params)
    
    if res.isOK():
        return res.getBody().output
    else:
        res.printError(url=API_URL_PRICE)
        return None

def place_order(ord_dv, qty, price, dry_run=True):
    """Places a buy or sell limit order."""
    trenv = kis_auth.getTREnv()
    if not trenv.my_acct:
        logger.error("Account number not found in configuration.")
        return False

    action = "BUY" if ord_dv == "buy" else "SELL"
    logger.info(f"[{'DRY RUN' if dry_run else 'LIVE'}] {action} Order: {qty} shares of {STOCK_NAME} at {price} KRW")

    if dry_run:
        logger.info(f">>> [Dry Run Success] {action} order would have been placed.")
        return True

    # TR ID: Real Buy(TTTC0012U), Real Sell(TTTC0011U)
    if ENV_DV == "real":
        tr_id = "TTTC0012U" if ord_dv == "buy" else "TTTC0011U"
    else:
        tr_id = "VTTC0012U" if ord_dv == "buy" else "VTTC0011U"

    params = {
        "CANO": trenv.my_acct,           # Account Number
        "ACNT_PRDT_CD": trenv.my_prod,   # Product Code
        "PDNO": STOCK_CODE,
        "ORD_DVSN": "00",                # 00: Limit Price (지정가)
        "ORD_QTY": str(qty),
        "ORD_UNPR": str(price),
        "EXCG_ID_DVSN_CD": "KRX",
        "SLL_TYPE": "",
        "CNDT_PRIC": ""
    }
    
    API_URL_ORDER = "/uapi/domestic-stock/v1/trading/order-cash"
    res = kis_auth._url_fetch(API_URL_ORDER, tr_id, "", params, postFlag=True)
    
    if res.isOK():
        logger.info(f">>> [{action} ORDER SUCCESS] Order No: {res.getBody().output.get('ODNO', 'N/A')}")
        return True
    else:
        logger.error(f">>> [{action} ORDER FAILED]")
        res.printError(url=API_URL_ORDER)
        return False

def monitor_and_trade(dry_run=True):
    """Main monitoring loop."""
    state = "WAITING_TO_BUY"
    logger.info(f"Starting Monitor for {STOCK_NAME} ({STOCK_CODE})")
    logger.info(f"Settings: Buy at {BUY_PRICE}, Sell at {SELL_PRICE}, Qty: {QTY}, Mode: {'Dry Run' if dry_run else 'LIVE'}")

    try:
        while True:
            data = get_current_price(STOCK_CODE)
            if not data:
                logger.warning("Failed to fetch price. Retrying in 10s...")
                time.sleep(INTERVAL)
                continue

            current_price = int(data['stck_prpr'])
            logger.info(f"Current Price: {current_price} KRW | State: {state}")

            if state == "WAITING_TO_BUY":
                if current_price <= BUY_PRICE:
                    logger.info(f"Target Buy Price {BUY_PRICE} reached!")
                    if place_order("buy", QTY, BUY_PRICE, dry_run=dry_run):
                        state = "WAITING_TO_SELL"
                        logger.info("Transitioning to WAITING_TO_SELL state.")
                
            elif state == "WAITING_TO_SELL":
                if current_price >= SELL_PRICE:
                    logger.info(f"Target Sell Price {SELL_PRICE} reached!")
                    if place_order("sell", QTY, SELL_PRICE, dry_run=dry_run):
                        logger.info("Trade Cycle Completed. Exiting.")
                        break

            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user.")

if __name__ == "__main__":
    # Check for dry-run argument
    is_dry_run = "--live" not in sys.argv
    if not is_dry_run:
        logger.warning("!!!!! LIVE TRADING MODE ENABLED !!!!!")
    
    monitor_and_trade(dry_run=is_dry_run)
