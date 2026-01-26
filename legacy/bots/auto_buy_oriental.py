import sys
import os
import pandas as pd
import logging

# Add examples_user to path to import kis_auth
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))

try:
    import kis_auth
except ImportError as e:
    print(f"Error importing kis_auth: {e}")
    sys.exit(1)

# Constants
API_URL_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-price"
API_URL_ORDER = "/uapi/domestic-stock/v1/trading/order-cash"
STOCK_CODE = "014940" # Oriental Precision & Engineering
STOCK_NAME = "오리엔탈정공"
TARGET_DROP_PERCENT = -3.0
ORDER_QTY = "1" # Buy 1 share
ENV_DV = "real" # 'real' or 'demo'

def get_current_price(stock_code):
    # Authenticate (Token/Env management handled by kis_auth)
    kis_auth.auth()

    # TR ID for current price
    tr_id = "FHKST01010100" 

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code
    }

    res = kis_auth._url_fetch(API_URL_PRICE, tr_id, "", params)

    if res.isOK():
        return res.getBody().output
    else:
        res.printError(url=API_URL_PRICE)
        return None

def place_buy_order(stock_code, qty, price="0"):
    """
    Places a cash buy order.
    price="0" usually means market price (requires different ORD_DVSN) or used with ORD_DVSN="01" (Market Price).
    For limit price, provide specific price.
    Here we use Market Price ("01") for guaranteed execution if condition met.
    """
    
    # Get environment variables managed by kis_auth
    trenv = kis_auth.getTREnv()
    
    # Check if we have account details
    if not trenv.my_acct:
        print("Error: Account number not found in configuration.")
        return False

    print(f"Preparing to buy {qty} share(s) of {stock_code} at Market Price...")

    # TR ID for Cash Buy (Real: TTTC0012U, Demo: VTTC0012U)
    # kis_auth.py handles this but let's be explicit based on our env
    if ENV_DV == "real":
        tr_id = "TTTC0012U"
    else:
        tr_id = "VTTC0012U"

    params = {
        "CANO": trenv.my_acct,           # Account Number (8 digits)
        "ACNT_PRDT_CD": trenv.my_prod,   # Product Code (2 digits)
        "PDNO": stock_code,              # Stock Code
        "ORD_DVSN": "01",                # 01: Market Price (시장가)
        "ORD_QTY": str(qty),             # Quantity
        "ORD_UNPR": "0",                 # Price (0 for market price)
        "EXCG_ID_DVSN_CD": "KRX",        # Exchange Code
        "SLL_TYPE": "",                  # Sell Type (N/A for buy)
        "CNDT_PRIC": ""                  # Condition Price
    }
    
    # Sending Order
    res = kis_auth._url_fetch(API_URL_ORDER, tr_id, "", params, postFlag=True)
    
    if res.isOK():
        print(">>> [매수 주문 성공]")
        output = res.getBody().output
        print(f"주문번호: {output.get('ODNO', 'Unknown')}")
        return True
    else:
        print(">>> [매수 주문 실패]")
        res.printError(url=API_URL_ORDER)
        return False

def run_logic(dry_run=True):
    print(f"--- {STOCK_NAME} ({STOCK_CODE}) 매수 조건 확인 ---")
    print(f"조건: 전일 대비 {TARGET_DROP_PERCENT}% 이상 하락 시 매수")
    
    data = get_current_price(STOCK_CODE)
    
    if not data:
        print("시세 조회 실패")
        return

    try:
        current_price = int(data['stck_prpr'])
        change_rate = float(data['prdy_ctrt'])
        
        print(f"현재가: {current_price} 원")
        print(f"등락률: {change_rate}%")
        
        if change_rate <= TARGET_DROP_PERCENT:
            print(f">>> 조건 만족! ({change_rate}% <= {TARGET_DROP_PERCENT}%)")
            
            if dry_run:
                print(">>> [Dry Run] 매수 주문이 실행되었을 것입니다. (실제 주문 아님)")
                # To enable actual trading, change dry_run to False in main block
            else:
                place_buy_order(STOCK_CODE, ORDER_QTY)
                
        else:
            print(f">>> 조건 불만족. 매수하지 않습니다.")
            
    except Exception as e:
        print(f"데이터 처리 중 오류: {e}")

if __name__ == "__main__":
    # WARNING: Set dry_run=False to actually place orders
    run_logic(dry_run=True)
