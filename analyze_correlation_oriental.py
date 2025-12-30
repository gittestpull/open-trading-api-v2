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
API_URL_CHART = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
API_URL_SHORT = "/uapi/domestic-stock/v1/quotations/daily-short-sale"
API_URL_CREDIT = "/uapi/domestic-stock/v1/quotations/daily-credit-balance"

STOCK_CODE = "014940"
START_DATE = "20250901"
END_DATE = datetime.now().strftime("%Y%m%d")

def fetch_weekly_prices():
    """Fetch weekly price chart data"""
    print(f"Fetching weekly prices from {START_DATE}...")
    kis_auth.auth()
    tr_id = "FHKST03010100"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": STOCK_CODE,
        "FID_INPUT_DATE_1": START_DATE,
        "FID_INPUT_DATE_2": END_DATE,
        "FID_PERIOD_DIV_CODE": "W", # Weekly
        "FID_ORG_ADJ_PRC": "1"      # Adjusted Price
    }
    
    res = kis_auth._url_fetch(API_URL_CHART, tr_id, "", params)
    if res.isOK():
        df = pd.DataFrame(res.getBody().output2)
        if df.empty: return pd.DataFrame()
        
        # Keep Date (stck_bsop_date) and Close Price (stck_clpr)
        df['date'] = pd.to_datetime(df['stck_bsop_date'])
        df['price'] = pd.to_numeric(df['stck_clpr'])
        return df[['date', 'price']].sort_values('date')
    else:
        print("Error fetching prices")
        return pd.DataFrame()

def fetch_daily_short_sale_full():
    """Fetch daily short sale data iteratively to cover the range"""
    print("Fetching short sale data...")
    all_data = []
    
    # API usually returns limited data per call, but daily-short-sale takes range.
    # Let's try fetching monthly chunks to be safe or full range if allowed.
    # Docs usually say "recent 30 days" or similar limits might apply, but let's try 3 month chunks.
    
    current_start = datetime.strptime(START_DATE, "%Y%m%d")
    end_dt = datetime.strptime(END_DATE, "%Y%m%d")
    
    while current_start < end_dt:
        current_end = current_start + timedelta(days=30)
        if current_end > end_dt:
            current_end = end_dt
            
        s_date = current_start.strftime("%Y%m%d")
        e_date = current_end.strftime("%Y%m%d")
        
        tr_id = "FHPST04830000"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": STOCK_CODE,
            "FID_INPUT_DATE_1": s_date,
            "FID_INPUT_DATE_2": e_date
        }
        
        res = kis_auth._url_fetch(API_URL_SHORT, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output2)
            if not chunk.empty:
                all_data.append(chunk)
        
        current_start = current_end + timedelta(days=1)
        
    if not all_data:
        return pd.DataFrame()
        
    df = pd.concat(all_data, ignore_index=True)
    # Deduplicate in case of overlap
    df = df.drop_duplicates(subset=['stck_bsop_date'])
    
    df['date'] = pd.to_datetime(df['stck_bsop_date'])
    # ssts_vol_rlim: Short Sale Volume Ratio
    df['short_ratio'] = pd.to_numeric(df['ssts_vol_rlim'])
    # acml_ssts_cntg_qty: Accumulated Short Sale Volume (Proxy for Balance/Activity)
    df['short_balance'] = pd.to_numeric(df['acml_ssts_cntg_qty'])
    return df[['date', 'short_ratio', 'short_balance']].sort_values('date')

def fetch_daily_credit_balance_full():
    """Fetch credit balance history. Iterating backwards."""
    print("Fetching credit balance data...")
    all_data = []
    
    # Start from today and go back
    curr_date_str = END_DATE
    target_start_dt = datetime.strptime(START_DATE, "%Y%m%d")
    
    for _ in range(10): 
        tr_id = "FHPST04760000"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "20476",
            "FID_INPUT_ISCD": STOCK_CODE,
            "FID_INPUT_DATE_1": curr_date_str
        }
        
        res = kis_auth._url_fetch(API_URL_CREDIT, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output)
            if chunk.empty: break
            
            all_data.append(chunk)
            
            if 'deal_date' in chunk.columns:
                oldest_date_str = chunk['deal_date'].min()
            elif 'stck_bsop_date' in chunk.columns:
                oldest_date_str = chunk['stck_bsop_date'].min()
            else:
                oldest_date_str = chunk.iloc[-1, 0] 
                
            oldest_dt = datetime.strptime(oldest_date_str, "%Y%m%d")
            
            if oldest_dt <= target_start_dt:
                break
                
            curr_date_str = (oldest_dt - timedelta(days=1)).strftime("%Y%m%d")
        else:
            break
            
    if not all_data:
        return pd.DataFrame()
        
    df = pd.concat(all_data, ignore_index=True)
    df = df.drop_duplicates()
    
    date_key = 'deal_date' if 'deal_date' in df.columns else 'stck_bsop_date'
    
    df['date'] = pd.to_datetime(df[date_key])
    df['credit_rate'] = pd.to_numeric(df['whol_loan_rmnd_rate'])
    # whol_loan_rmnd_stcn: Whole Loan Remaining Share Count (Balance)
    df['credit_balance'] = pd.to_numeric(df['whol_loan_rmnd_stcn'])
    
    df = df[df['date'] >= target_start_dt]
    return df[['date', 'credit_rate', 'credit_balance']].sort_values('date')

def analyze():
    print(f"Running Correlation Analysis for {STOCK_CODE} (Sep 2025 ~ Present)...\n")
    
    # 1. Fetch Data
    df_price = fetch_weekly_prices()
    df_short = fetch_daily_short_sale_full()
    df_credit = fetch_daily_credit_balance_full()
    
    if df_price.empty or df_short.empty or df_credit.empty:
        print("Error: insufficient data fetched.")
        return


    # 2. Resample/Align to Weekly (Friday anchor)
    # Set index
    df_price = df_price.set_index('date')
    df_short = df_short.set_index('date')
    df_credit = df_credit.set_index('date')

    # Resample all to Weekly Friday to ensure alignment
    # Price: Use 'last' (Close price)
    df_price_weekly = df_price.resample('W-FRI').last()
    
    # Short: Mean of daily ratios, Last of accumulated balance?
    # Balance is stock -> Last. Volume Ratio is flow -> Mean.
    df_short_weekly = df_short.resample('W-FRI').agg({
        'short_ratio': 'mean',
        'short_balance': 'last' 
    })
    
    # Credit: Last for Rate and Balance
    df_credit_weekly = df_credit.resample('W-FRI').agg({
        'credit_rate': 'last',
        'credit_balance': 'last'
    })

    # Concat on index (Date)
    df_final = pd.concat([df_price_weekly, df_short_weekly, df_credit_weekly], axis=1)
    
    # Drop rows with any NaN (e.g. strict intersection)
    df_final = df_final.dropna()
    
    # 3. Calculate Correlation
    corr_matrix = df_final[['price', 'short_ratio', 'short_balance', 'credit_rate', 'credit_balance']].corr()
    
    print("\n" + "="*80)
    print(f" [ 주간 단위 데이터 상관관계 분석 결과 (비율 + 잔고 포함) ] ")
    print(f" * 분석 기간: {df_final.index.min().strftime('%Y-%m-%d')} ~ {df_final.index.max().strftime('%Y-%m-%d')}")
    print(f" * 데이터 개수: {len(df_final)} 주 (Weeks)")
    print("="*80)
    
    # Rename columns for display
    display_df = df_final.copy()
    display_df.columns = ['주가', '공매도비중', '공매도누적수량', '신용잔고율', '신용잔고수량']
    
    print("\n[Data Preview (First 5 rows)]")
    print(display_df.head(5))
    print("\n...\n")
    print("[Data Preview (Last 5 rows)]")
    print(display_df.tail(5)) 
    print("-" * 80)
    
    print("\n[상관계수 행렬]")
    print(display_df.corr())

    print("\n" + "="*50)
    
    # Summary
    p_s_corr = corr_matrix.loc['price', 'short_ratio']
    p_c_corr = corr_matrix.loc['price', 'credit_rate']
    
    print("\n[요약]")
    print(f"1. 주가 vs 공매도 비중 상관계수: {p_s_corr:.4f}")
    if abs(p_s_corr) < 0.2:
        print("   -> 뚜렷한 상관관계가 없습니다.")
    elif p_s_corr > 0:
        print("   -> 공매도가 늘어나면 주가도 오르는 경향 (이례적 양의 상관관계)이 있습니다.")
    else:
        print("   -> 공매도가 늘어나면 주가가 내려가는 경향 (음의 상관관계)이 있습니다.")
        
    print(f"2. 주가 vs 신용잔고율 상관계수: {p_c_corr:.4f}")
    if abs(p_c_corr) < 0.2:
        print("   -> 뚜렷한 상관관계가 없습니다.")
    elif p_c_corr > 0:
        print("   -> 신용잔고가 많으면 주가가 높은 경향 (양의 상관관계)이 있습니다.")
    else:
        print("   -> 신용잔고가 많으면 주가가 낮은 경향 (음의 상관관계)이 있습니다.")

if __name__ == "__main__":
    try:
        analyze()
    except Exception as e:
        print(f"Analysis Failed: {e}")
        import traceback
        traceback.print_exc()
