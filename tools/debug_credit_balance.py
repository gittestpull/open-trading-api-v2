import sys
import os
import json
import pandas as pd
import logging

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Add examples_user to path for internal imports
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'examples_user'))

import kis_auth as ka
import examples_user.domestic_stock.domestic_stock_functions as d_func

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_credit_balance():
    # Load config
    ka.auth()

    # Parameters
    ticker = "014940" # Oriental Precision
    
    # Get account info from loaded config
    trenv = ka.getTREnv()
    
    print(f"Checking Credit Balance for {ticker}...")
    print(f"Account: {trenv.my_acct}, Product: {trenv.my_prod}")

    # Call inquire_credit_psamount
    # Try both '21' (Self) and '23' (Circulation)
    # Use inquire-balance (TTTC8434R) to find holding details
    url = "/uapi/domestic-stock/v1/trading/inquire-balance"
    tr_id = "TTTC8434R"
    params = {
        "CANO": trenv.my_acct,
        "ACNT_PRDT_CD": trenv.my_prod,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "01",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": ""
    }

    print(f"\n--- Checking Holding Balance (TTTC8434R) ---")
    import kis_auth
    res = kis_auth._url_fetch(url, tr_id, "", params)

    if res.isOK():
        out1 = res.getBody().output1
        if out1:
            print("Holding Found!")
            for item in out1:
                # Print all items to find the right one
                if item['pdno'] == "014940":
                    print(json.dumps(item, indent=2, ensure_ascii=False))
                    break
        else:
            print("No holdings found.")
    else:
        res.printError()

if __name__ == "__main__":
    debug_credit_balance()
