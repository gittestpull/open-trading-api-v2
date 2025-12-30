import sys
import os
from dotenv import load_dotenv

# Add path to examples_user for authentication module
sys.path.append(os.path.join(os.getcwd(), "examples_user"))
import kis_auth
import pandas as pd

load_dotenv()

def test_fetch_lending():
    # Use the auth approach from visualize_investor_trends.py
    kis_auth.auth()
    
    # Oriental Precision & Engineering (014940)
    # HHPST074500C0: Daily Loan Transaction
    tr_id = "HHPST074500C0"
    params = {
        "MRKT_DIV_CLS_CODE": "3",  # 3: Stock
        "MKSC_SHRN_ISCD": "014940",
        "START_DATE": "20250101",
        "END_DATE": "20250401",
        "CTS": ""
    }
    
    # Note: Using URL from domestic_stock_functions.py
    api_url = "/uapi/domestic-stock/v1/quotations/daily-loan-trans"
    
    res = kis_auth._url_fetch(api_url, tr_id, "", params)
    
    if res.isOK():
        df = pd.DataFrame(res.getBody().output1)
        print("Columns:", df.columns.tolist())
        print(f"Row count: {len(df)}")
        print(df.head())
    else:
        print("Error fetching data")
        res.printError()

if __name__ == "__main__":
    test_fetch_lending()
