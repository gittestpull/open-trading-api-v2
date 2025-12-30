import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add examples_user to path for auth
sys.path.append(os.path.join(os.getcwd(), "examples_user"))
import kis_auth

def fetch_dividend_history(stock_code):
    print(f"Fetching dividend history for {stock_code}...")
    kis_auth.auth()
    
    API_URL = "/uapi/domestic-stock/v1/ksdinfo/dividend"
    tr_id = "HHKDB669102C0"
    
    # 1 year range
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    
    params = {
        "CTS": "",
        "GB1": "0", # 0: Total, 1: Final, 2: Interim
        "F_DT": start_date,
        "T_DT": end_date,
        "SHT_CD": stock_code,
        "HIGH_GB": ""
    }
    
    res = kis_auth._url_fetch(API_URL, tr_id, "", params)
    if res.isOK():
        output1 = res.getBody().output1
        if output1:
            df = pd.DataFrame(output1)
            print("\nDividend Data Found:")
            print(df.head())
            print("\nColumns:", df.columns.tolist())
            return df
        else:
            print("No dividend data found.")
    else:
        print(f"Error: {res.getErrorCode()} - {res.getErrorMessage()}")
    return None

if __name__ == "__main__":
    # Test with Samsung Electronics (005930) or Oriental Precision (014940)
    stock = sys.argv[1] if len(sys.argv) > 1 else "005930"
    fetch_dividend_history(stock)
