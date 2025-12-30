
import sys
import os
import pandas as pd
sys.path.append(os.path.join(os.getcwd(), "examples_user"))
import kis_auth

API_URL = "/uapi/domestic-stock/v1/quotations/invest-opinion"
TR_ID = "FHKST663300C0"
STOCK_CODE = "014940"

def test():
    kis_auth.auth()
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "16633",
        "FID_INPUT_ISCD": STOCK_CODE,
        "FID_INPUT_DATE_1": "20240101",
        "FID_INPUT_DATE_2": "20251231"
    }
    res = kis_auth._url_fetch(API_URL, TR_ID, "", params)
    if res.isOK():
        output = res.getBody().output
        if output:
            print("First item keys:", output[0].keys())
            print("First item values:", output[0])
        else:
            print("No data found")
    else:
        print("Error:", res.getErrorMessage())

if __name__ == "__main__":
    test()
