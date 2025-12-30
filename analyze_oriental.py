import sys
import os
import pandas as pd
import logging

# Add examples_user to path to import kis_auth
# Using examples_user/kis_auth.py as it was verified earlier
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))

try:
    import kis_auth
except ImportError as e:
    print(f"Error importing kis_auth: {e}")
    sys.exit(1)

# API URL for current price

# API URLs
API_URL_PRICE = "/uapi/domestic-stock/v1/quotations/inquire-price"
API_URL_SHORT = "/uapi/domestic-stock/v1/quotations/daily-short-sale"
API_URL_CREDIT = "/uapi/domestic-stock/v1/quotations/daily-credit-balance"

def get_current_price(stock_code):
    kis_auth.auth()
    tr_id = "FHKST01010100" 
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code
    }
    res = kis_auth._url_fetch(API_URL_PRICE, tr_id, "", params)
    if res.isOK():
        return res.getBody().output
    else:
        res.printError(url=API_URL_PRICE)
        return None

def get_short_sale_trend(stock_code):
    # Fetch data for the last 5 days
    from datetime import datetime, timedelta
    end_dt = datetime.now().strftime("%Y%m%d")
    start_dt = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    
    tr_id = "FHPST04830000"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": start_dt,
        "FID_INPUT_DATE_2": end_dt
    }
    
    res = kis_auth._url_fetch(API_URL_SHORT, tr_id, "", params)
    if res.isOK():
        # output2 contains the daily list
        return res.getBody().output2
    else:
        # Short sale API might fail on holidays or for certain stocks
        return None

def get_credit_balance_trend(stock_code):
    # Fetch most recent data
    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")
    
    tr_id = "FHPST04760000"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "20476",
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": date_str
    }
    
    res = kis_auth._url_fetch(API_URL_CREDIT, tr_id, "", params)
    if res.isOK():
        return res.getBody().output
    else:
        return None

def analyze_oriental_precision():
    stock_code = "014940"
    stock_name = "오리엔탈정공"
    
    print(f"Analyzing {stock_name} ({stock_code})...")
    
    # 1. Price
    data = get_current_price(stock_code)
    
    # 2. Short Sale
    short_data = get_short_sale_trend(stock_code)
    
    # 3. Credit Balance
    credit_data = get_credit_balance_trend(stock_code)
    
    print("\n" + "="*40)
    print(f" [ 종목 분석 보고서: {stock_name} ]")
    print("="*40)
    
    if data:
        print(f" 현재가    : {int(data['stck_prpr']):,} 원")
        print(f" 전일대비  : {int(data['prdy_vrss']):,} 원 ({float(data['prdy_ctrt']):.2f}%)")
        print(f" 거래량    : {int(data['acml_vol']):,} 주")
    else:
        print(" 현재가 정보를 불러오지 못했습니다.")

    print("-" * 40)
    
    if short_data and len(short_data) > 0:
        latest_short = short_data[0] # List is usually sorted by date desc
        date = latest_short['stck_bsop_date']
        vol = latest_short['ssts_cntg_qty']
        rate = latest_short['ssts_vol_rlim'] 
        
        print(f" [공매도 현황] ({date} 기준)")
        print(f" - 공매도 수량 : {int(vol):,} 주")
        print(f" - 공매도 비중 : {float(rate):.2f} %")
    else:
        print(" 공매도 정보를 불러오지 못했습니다.")
        
    print("-" * 40)

    if credit_data and len(credit_data) > 0:
        latest_credit = credit_data[0]
        date = latest_credit['deal_date'] # Confirmed key
        rate = latest_credit['whol_loan_rmnd_rate']
        
        print(f" [신용잔고 현황] ({date} 기준)")
        print(f" - 신용잔고율  : {float(rate):.2f} %")
    else:
        print(" 신용잔고 정보를 불러오지 못했습니다.")
        
    print("="*40 + "\n")
    
    # Existing Analysis Message
    if data:
        try:
            current = float(data['stck_prpr'])
            prev_close = float(data['stck_sdpr']) 
            if current > prev_close:
                print(" -> 현재 주가가 전일 종가보다 상승했습니다.")
            elif current < prev_close:
                print(" -> 현재 주가가 전일 종가보다 하락했습니다.")
            else:
                print(" -> 현재 주가가 전일 종가와 동일합니다.")
        except:
            pass

if __name__ == "__main__":
    analyze_oriental_precision()
