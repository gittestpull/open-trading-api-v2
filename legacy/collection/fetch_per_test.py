import sys
import os
from dotenv import load_dotenv

# Add path for authentication
sys.path.append(os.path.join(os.getcwd(), "examples_user"))
import kis_auth
import pandas as pd

load_dotenv()

def test_fetch_per():
    kis_auth.auth()
    stock_code = "014940"
    
    # Try FHKST01010400: Daily Price (Period)
    # This often contains more detailed daily info? Or just OHLCV?
    tr_id = "FHKST01010400"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0"
    }
    
    api_url = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
    
    print(f"Calling {api_url} with {tr_id}...")
    res = kis_auth._url_fetch(api_url, tr_id, "", params)
    
    if res.isOK():
        df = pd.DataFrame(res.getBody().output)
        print("Columns:", df.columns.tolist())
        if not df.empty:
            print(df.head(2))
    else:
        print("Error fetching.")
        res.printError()

if __name__ == "__main__":
    test_fetch_per()
