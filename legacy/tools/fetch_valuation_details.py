import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.join(os.getcwd(), "examples_user"))
import kis_auth
import pandas as pd

load_dotenv()

def test_fetch_details():
    kis_auth.auth()
    stock_code = "014940"
    
    # 1. Get Shares Outstanding (lstn_stcn)
    # API: /uapi/domestic-stock/v1/quotations/inquire-price
    tr_id = "FHKST01010100"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code
    }
    print("Fetching Stock Info...")
    res = kis_auth._url_fetch("/uapi/domestic-stock/v1/quotations/inquire-price", tr_id, "", params)
    if res.isOK():
        out = res.getBody().output
        shares = out.get('lstn_stcn', '0')
        print(f"Shares Outstanding: {shares}")
    else:
        print("Failed to fetch price/shares")
        
    # 2. Get Balance Sheet (Total Equity)
    # API: /uapi/domestic-stock/v1/finance/balance-sheet
    tr_id_bal = "FHKST66430100" # Balance Sheet
    params_bal = {
        "FID_DIV_CLS_CODE": "1", # Quarter
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": stock_code
    }
    print("Fetching Balance Sheet...")
    res_bal = kis_auth._url_fetch("/uapi/domestic-stock/v1/finance/balance-sheet", tr_id_bal, "", params_bal)
    if res_bal.isOK():
        df = pd.DataFrame(res_bal.getBody().output)
        print("BS Columns:", df.columns.tolist())
        # Look for Total Equity (tcpt_amnt?)
        print(df.head())
    else:
        print("Failed to fetch BS")

if __name__ == "__main__":
    test_fetch_details()
