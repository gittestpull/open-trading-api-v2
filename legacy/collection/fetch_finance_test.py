import sys
import os
from dotenv import load_dotenv

# Add path to examples_user for authentication module
sys.path.append(os.path.join(os.getcwd(), "examples_user"))
import kis_auth
import pandas as pd

load_dotenv()

def test_fetch_finance():
    kis_auth.auth()
    
    # Oriental Precision & Engineering (014940)
    # FHKST66430200: Income Statement
    tr_id = "FHKST66430200"
    params = {
        "FID_DIV_CLS_CODE": "1", # 0: Year, 1: Quarter
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": "014940"
    }
    
    api_url = "/uapi/domestic-stock/v1/finance/income-statement"
    
    res = kis_auth._url_fetch(api_url, tr_id, "", params)
    
    if res.isOK():
        df = pd.DataFrame(res.getBody().output)
        print("Columns:", df.columns.tolist())
        print(f"Row count: {len(df)}")
        print(df.head())
    else:
        print("Error fetching data")
        res.printError()

if __name__ == "__main__":
    test_fetch_finance()
