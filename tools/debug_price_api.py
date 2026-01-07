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

def debug_price_api():
    ka.auth()

    ticker = "014940" # Oriental Precision
    print(f"Checking Price API for {ticker}...")
    
    # 1. Inquire Price (FHKST01010100)
    print("\n--- Inquire Price (FHKST01010100) ---")
    try:
        df = d_func.inquire_price("real", "J", ticker)
        if not df.empty:
            data = df.iloc[0].to_dict()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # Check keywords
            print("\nPotential Credit/Short Keys:")
            for k, v in data.items():
                if any(x in k for x in ['crdt', 'credit', 'loan', 'short', 'rate', 'fcam']):
                    print(f"  {k}: {v}")
    except Exception as e:
        print(f"Error: {e}")

    # 2. Investor Trend Estimate (HHPTJ04160200)
    print("\n--- Investor Trend Estimate (HHPTJ04160200) ---")
    try:
        df = d_func.investor_trend_estimate(ticker)
        if not df.empty:
            print("Row 0:")
            print(json.dumps(df.iloc[0].to_dict(), indent=2, ensure_ascii=False))
        else:
            print("Empty DataFrame returned.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_price_api()
