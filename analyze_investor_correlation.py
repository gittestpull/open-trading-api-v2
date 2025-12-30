import sys
import os
import pandas as pd
import logging
from datetime import datetime, timedelta

# Add examples_user to path to import kis_auth
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))

try:
    import kis_auth
except ImportError as e:
    print(f"Error importing kis_auth: {e}")
    sys.exit(1)

# API URLs
API_URL_INVESTOR = "/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily"
API_URL_CHART = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"

STOCK_CODE = "014940"
START_DATE = "20250101"
END_DATE = datetime.now().strftime("%Y%m%d")

def fetch_daily_prices():
    print(f"Fetching daily prices from {START_DATE}...")
    kis_auth.auth()
    tr_id = "FHKST03010100"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": STOCK_CODE,
        "FID_INPUT_DATE_1": START_DATE,
        "FID_INPUT_DATE_2": END_DATE,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "1"
    }
    
    res = kis_auth._url_fetch(API_URL_CHART, tr_id, "", params)
    if res.isOK():
        df = pd.DataFrame(res.getBody().output2)
        if df.empty: return pd.DataFrame()
        df['date'] = pd.to_datetime(df['stck_bsop_date'])
        df['price'] = pd.to_numeric(df['stck_clpr'])
        return df[['date', 'price']].sort_values('date')
    return pd.DataFrame()

def fetch_investor_trends():
    print("Fetching investor trading trends...")
    all_data = []
    
    # Needs iteration same as others
    curr_date_str = END_DATE
    target_start_dt = datetime.strptime(START_DATE, "%Y%m%d")
    
    # Iterate pages
    for _ in range(25):
        tr_id = "FHPTJ04160001"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": STOCK_CODE,
            "FID_INPUT_DATE_1": curr_date_str,
            "FID_ORG_ADJ_PRC": "0",
            "FID_ETC_CLS_CODE": ""
        }
        
        res = kis_auth._url_fetch(API_URL_INVESTOR, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output2) # output2 is the daily list
            if chunk.empty: break
            
            all_data.append(chunk)

            oldest_date_str = chunk.iloc[-1]['stck_bsop_date']
            oldest_dt = datetime.strptime(oldest_date_str, "%Y%m%d")
            
            if oldest_dt <= target_start_dt:
                break
                
            curr_date_str = (oldest_dt - timedelta(days=1)).strftime("%Y%m%d")
        else:
            res.printError(url=API_URL_INVESTOR)
            break
            
    if not all_data: return pd.DataFrame()
    
    df = pd.concat(all_data, ignore_index=True)
    df = df.drop_duplicates(subset=['stck_bsop_date'])
    
    df['date'] = pd.to_datetime(df['stck_bsop_date'])
    
    # Columns of interest (Net Buying Volume)
    # prsn_ntby_qty: Individual Net Buy
    # frgn_ntby_qty: Foreigner Net Buy
    # orgn_ntby_qty: Institution Net Buy
    
    cols = ['prsn_ntby_qty', 'frgn_ntby_qty', 'orgn_ntby_qty']
    for col in cols:
        df[col] = pd.to_numeric(df[col])
        
    df = df[df['date'] >= target_start_dt]
    return df[['date'] + cols].sort_values('date')

def analyze():
    df_price = fetch_daily_prices()
    df_investor = fetch_investor_trends()
    
    if df_price.empty or df_investor.empty:
        print("Data fetch failed or empty.")
        return
        
    df_final = pd.merge(df_price, df_investor, on='date', how='inner')
    
    print("\n" + "="*80)
    print(f" [ 투자자별 순매수 상관관계 분석 (Full Year 2025) ] ")
    print("="*80)
    
    print(df_final.tail())
    print("-" * 80)
    
    # Correlation
    # We correlate Price with *Cumulative* Net Buy? Or Daily Net Buy?
    # Daily Net Buy vs Daily Price Change?
    # Or Cumulative Net Buy (Balance proxy) vs Price Level?
    # Usually Price Level correlates well with Cumulative Net Buy (Who is holding?)
    
    # Let's calculate Cumulative Sum for Net Buy columns to simulate "Holdings Change"
    df_final['cum_individual'] = df_final['prsn_ntby_qty'].cumsum()
    df_final['cum_foreigner'] = df_final['frgn_ntby_qty'].cumsum()
    df_final['cum_institution'] = df_final['orgn_ntby_qty'].cumsum()
    
    corr_daily = df_final[['price', 'prsn_ntby_qty', 'frgn_ntby_qty', 'orgn_ntby_qty']].corr()
    corr_cum = df_final[['price', 'cum_individual', 'cum_foreigner', 'cum_institution']].corr()
    
    print("\n1. [주가 vs 일별 순매수량] 상관계수")
    print(corr_daily['price'])
    
    print("\n2. [주가 vs 누적 순매수량(추세)] 상관계수 (더 유의미함)")
    print(corr_cum['price'])
    
    # Interpretation
    print("\n[해석]")
    c_ind = corr_cum.loc['price', 'cum_individual']
    c_frg = corr_cum.loc['price', 'cum_foreigner']
    c_org = corr_cum.loc['price', 'cum_institution']
    
    best_corr = max(abs(c_ind), abs(c_frg), abs(c_org))
    
    if abs(c_ind) == best_corr: who = "개인"
    elif abs(c_frg) == best_corr: who = "외국인"
    else: who = "기관"
    
    print(f" -> 이 종목은 '{who}'의 누적 매매 추이와 가장 강한 상관관계({best_corr:.4f})를 보입니다.")
    
    if c_frg > 0.5:
        print(" -> **외국인**이 사면 오르고, 팔면 내리는 정직한 수급 주도주 성향입니다.")
    elif c_frg < -0.5:
        print(" -> 특이하게도 외국인이 팔 때 오르는 역상관 관계입니다.")
        
    print("="*80)

if __name__ == "__main__":
    analyze()
