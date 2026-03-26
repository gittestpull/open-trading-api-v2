# -*- coding: utf-8 -*-
import os
import sys
import logging
from datetime import datetime, timedelta

# Add paths for unified importing
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(base_dir, "src", "core"))
sys.path.insert(0, os.path.join(base_dir, "examples_user", "domestic_stock"))

import kis_auth as ka
import domestic_stock_functions as dsf

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # KIS API 인증
    ka.auth()
    
    ticker = "014940"  # 오리엔탈정공
    today = datetime.now()
    end_date = today.strftime("%Y%m%d")
    start_date = (today - timedelta(days=365)).strftime("%Y%m%d")
    
    print(f"--- Searching Investment Opinion for {ticker} from {start_date} to {end_date} ---")
    
    try:
        df = dsf.invest_opinion(
            fid_cond_mrkt_div_code="J",
            fid_cond_scr_div_code="16633",
            fid_input_iscd=ticker,
            fid_input_date_1=start_date,
            fid_input_date_2=end_date
        )
        
        if df is not None and not df.empty:
            print(df[['stck_bsop_date', 'mbcr_name', 'invt_opnn', 'hts_goal_prc']])
        else:
            print("No investment opinion found via KIS API.")
            
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    main()
