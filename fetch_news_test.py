import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.join(os.getcwd(), "examples_user"))
import kis_auth
import pandas as pd
from datetime import datetime, timedelta

load_dotenv()

def test_fetch_news(stock_code="010140"):
    kis_auth.auth()
    
    # API: /uapi/domestic-stock/v1/quotations/news-title
    # TR_ID: FHKST01010800  (This is for searching news)
    # Actually from the file viewed (domestic_stock_functions.py), the tr_id was not shown inside the function body in the snippet, 
    # but the docstring says [국내주식-141] which maps to FHKST01010800 usually.
    # Let's check the viewed file content again or just trust the snippet logic if available.
    # The snippet showed: api_url = "/uapi/domestic-stock/v1/quotations/news-title"
    # and params.
    
    # Let's use the manual fetch approach to be sure of params
    tr_id = "FHKST01011800"
    now_date = datetime.now().strftime("%Y%m%d")
    
    # Based on example in examples_user/domestic_stock/domestic_stock_functions.py
    params = {
        "FID_NEWS_OFER_ENTP_CODE": "0",  # 0: All Providers (or try '2' as per example?)
        "FID_COND_MRKT_CLS_CODE": "00",  # Unsure, using '00' from example
        "FID_INPUT_ISCD": stock_code,
        "FID_TITL_CNTT": "",
        "FID_INPUT_DATE_1": now_date,
        "FID_INPUT_HOUR_1": "235959",
        "FID_RANK_SORT_CLS_CODE": "0",   # 0: Recent?
        "FID_INPUT_SRNO": ""
    }
    
    api_url = "/uapi/domestic-stock/v1/quotations/news-title"
    print(f"Fetching news for {stock_code} using {api_url}...")
    
    curr_date = now_date
    curr_time = "235959"
    
    for i in range(5):
        params["FID_INPUT_DATE_1"] = curr_date
        params["FID_INPUT_HOUR_1"] = curr_time
        
        print(f"Fetching with Date={curr_date}, Time={curr_time}...")
        res = kis_auth._url_fetch(api_url, tr_id, "", params)
        
        if res.isOK():
            out = res.getBody().output
            if out:
                if isinstance(out, dict): out = [out]
                df = pd.DataFrame(out)
                print(f"Page {i+1}: {len(df)} rows.")
                
                if 'data_dt' in df.columns and 'data_tm' in df.columns:
                    min_dt = df['data_dt'].min()
                    min_tm = df.loc[df['data_dt'] == min_dt, 'data_tm'].min()
                    
                    print(f"  Range: {df['data_dt'].max()} ~ {min_dt}")
                    title_col = 'hts_pbnt_titl_cntt' if 'hts_pbnt_titl_cntt' in df.columns else 'cntt'
                    if title_col in df.columns:
                        print(f"  First: {df.iloc[0]['data_dt']} {df.iloc[0]['data_tm']} {df.iloc[0][title_col][:20]}...")

                    # Prepare next request: 1 second before oldest record
                    # If min_dt/min_tm is exact, we need to subtract time.
                    # Simplification: just use the min_dt/min_tm of the last record.
                    # But if date is same, we rely on time.
                    
                    # Parse min datetime
                    min_datetime_str = f"{min_dt}{min_tm}"
                    dt_obj = datetime.strptime(min_datetime_str, "%Y%m%d%H%M%S")
                    next_dt_obj = dt_obj - timedelta(seconds=1)
                    
                    curr_date = next_dt_obj.strftime("%Y%m%d")
                    curr_time = next_dt_obj.strftime("%H%M%S")
                    
                else:
                    print("  No date column?")
                    break
            else:
                print("No output.")
                break
        else:
            print("Error fetching news.")
            res.printError(url=api_url)
            break

if __name__ == "__main__":
    test_fetch_news()
