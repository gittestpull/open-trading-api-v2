import sys
import os
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from dotenv import load_dotenv

# Add examples_user to path to import kis_auth
import platform
import matplotlib.font_manager as fm

# Add examples_user to path for auth
sys.path.append(os.path.join(os.getcwd(), "examples_user"))
import kis_auth
from stock_code_lookup import StockMaster

load_dotenv()

# Configure Korean Font
system_name = platform.system()
if system_name == 'Darwin': # Mac
    plt.rc('font', family='AppleGothic')
elif system_name == 'Windows': # Windows
    plt.rc('font', family='Malgun Gothic')
elif system_name == 'Linux': # Linux
    plt.rc('font', family='NanumGothic')

# Disable minus sign corruption
plt.rcParams['axes.unicode_minus'] = False

# API URLs
API_URL_INVESTOR = "/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily"
API_URL_CHART = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
API_URL_SHORT = "/uapi/domestic-stock/v1/quotations/daily-short-sale"
API_URL_CREDIT = "/uapi/domestic-stock/v1/quotations/daily-credit-balance"

STOCK_CODE = "014940"
STOCK_NAME = "Oriental Precision (014940)"

if len(sys.argv) > 1:
    input_str = sys.argv[1]
    
    # If input is digits, assume Code
    if input_str.isdigit():
        STOCK_CODE = input_str
        if len(sys.argv) > 2:
            STOCK_NAME = sys.argv[2]
        else:
            STOCK_NAME = f"Stock_{STOCK_CODE}"
    else:
        # Assume input is Name
        print(f"Looking up code for '{input_str}'...")
        sm = StockMaster()
        found_code = sm.get_code(input_str)
        
        if found_code:
            STOCK_CODE = found_code
            STOCK_NAME = input_str # Use input name as display name
            print(f"Found Code: {STOCK_CODE}")
        else:
            print(f"Error: Could not find stock code for '{input_str}'")
            sys.exit(1)
        
        # Optional: Overwrite name if 2nd arg provided
        if len(sys.argv) > 2:
            STOCK_NAME = sys.argv[2]

START_DATE = "20250101"
END_DATE = datetime.now().strftime("%Y%m%d")

def fetch_daily_prices():
    print(f"Fetching daily prices from {START_DATE}...")
    kis_auth.auth()
    all_data = []
    
    curr_end_str = END_DATE
    target_start_dt = datetime.strptime(START_DATE, "%Y%m%d")
    
    # Iterate backwards (max 20 pages e.g. 2000 days, plenty for 1 year)
    for _ in range(20):
        tr_id = "FHKST03010100"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": STOCK_CODE,
            "FID_INPUT_DATE_1": START_DATE, # API takes range, but returns truncated from end? No, usually range.
            # Actually for chart price, input date 1 is Start, 2 is End.
            # If it truncates, it usually gives the LATEST 100 days.
            # So we should shift the END date backwards.
            "FID_INPUT_DATE_2": curr_end_str,
            "FID_PERIOD_DIV_CODE": "D",
            "FID_ORG_ADJ_PRC": "1"
        }
        
        # print(f"DEBUG: Fetching price {START_DATE} ~ {curr_end_str}")
        res = kis_auth._url_fetch(API_URL_CHART, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output2)
            if chunk.empty: break
            
            all_data.append(chunk)
            
            # Check oldest date in this chunk
            oldest_date_str = chunk.iloc[-1]['stck_bsop_date']
            oldest_dt = datetime.strptime(oldest_date_str, "%Y%m%d")
            
            # If we reached our start target, stop
            if oldest_dt <= target_start_dt:
                break
                
            # Otherwise, set next end date to one day before oldest
            curr_end_str = (oldest_dt - timedelta(days=1)).strftime("%Y%m%d")
            
            # Stop if we are going in circles or weird date
            if curr_end_str < START_DATE:
                break
        else:
            print("Fetch failed or limits.")
            break
            
    if not all_data: return pd.DataFrame()
    
    df = pd.concat(all_data, ignore_index=True)
    df = df.drop_duplicates(subset=['stck_bsop_date'])
    df['date'] = pd.to_datetime(df['stck_bsop_date'])
    df['price'] = pd.to_numeric(df['stck_clpr'])
    df['volume'] = pd.to_numeric(df['acml_vol'])
    
    # Filter strictly >= START_DATE (in case loops overshot)
    df = df[df['date'] >= target_start_dt]
    
    return df[['date', 'price', 'volume']].sort_values('date')

def fetch_investor_trends():
    print("Fetching investor trading trends...")
    all_data = []
    
    curr_date_str = END_DATE
    target_start_dt = datetime.strptime(START_DATE, "%Y%m%d")
    
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
            chunk = pd.DataFrame(res.getBody().output2)
            if chunk.empty: break
            all_data.append(chunk)

            oldest_date_str = chunk.iloc[-1]['stck_bsop_date']
            oldest_dt = datetime.strptime(oldest_date_str, "%Y%m%d")
            
            if oldest_dt <= target_start_dt:
                break
                
            curr_date_str = (oldest_dt - timedelta(days=1)).strftime("%Y%m%d")
        else:
            break
            
    if not all_data: return pd.DataFrame()
    
    df = pd.concat(all_data, ignore_index=True)
    df = df.drop_duplicates(subset=['stck_bsop_date'])
    df['date'] = pd.to_datetime(df['stck_bsop_date'])
    
    cols = ['prsn_ntby_qty', 'frgn_ntby_qty', 'orgn_ntby_qty']
    for col in cols:
        df[col] = pd.to_numeric(df[col])
        
    df = df[df['date'] >= target_start_dt]
    return df[['date'] + cols].sort_values('date')

def fetch_daily_short_sale_full():
    print("Fetching short sale data...")
    all_data = []
    
    current_start = datetime.strptime(START_DATE, "%Y%m%d")
    end_dt = datetime.strptime(END_DATE, "%Y%m%d")
    
    while current_start < end_dt:
        current_end = current_start + timedelta(days=30)
        if current_end > end_dt: current_end = end_dt
            
        s_date = current_start.strftime("%Y%m%d")
        e_date = current_end.strftime("%Y%m%d")
        
        tr_id = "FHPST04830000"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": STOCK_CODE, "FID_INPUT_DATE_1": s_date, "FID_INPUT_DATE_2": e_date}
        
        res = kis_auth._url_fetch(API_URL_SHORT, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output2)
            if not chunk.empty:
                all_data.append(chunk)
        
        current_start = current_end + timedelta(days=1)
        
    if not all_data: return pd.DataFrame()
        
    df = pd.concat(all_data, ignore_index=True)
    df = df.drop_duplicates(subset=['stck_bsop_date'])
    df['date'] = pd.to_datetime(df['stck_bsop_date'])
    
    # ssts_cntg_qty: Daily Short Sale Volume
    df['short_vol'] = pd.to_numeric(df['ssts_cntg_qty'])
    # ssts_vol_rlim: Short Sale Volume Ratio
    df['short_ratio'] = pd.to_numeric(df['ssts_vol_rlim'])
    
    return df[['date', 'short_vol', 'short_ratio']].sort_values('date')

def fetch_daily_credit_balance_full():
    print("Fetching credit balance data...")
    all_data = []
    
    curr_date_str = END_DATE
    target_start_dt = datetime.strptime(START_DATE, "%Y%m%d")
    
    for _ in range(25): 
        tr_id = "FHPST04760000"
        params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20476", "FID_INPUT_ISCD": STOCK_CODE, "FID_INPUT_DATE_1": curr_date_str}
        
        res = kis_auth._url_fetch(API_URL_CREDIT, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output)
            if chunk.empty: break
            all_data.append(chunk)
            
            date_key = 'deal_date' if 'deal_date' in chunk.columns else 'stck_bsop_date'
            if date_key not in chunk.columns: break 
            
            oldest_date_str = chunk[date_key].min()
            oldest_dt = datetime.strptime(oldest_date_str, "%Y%m%d")
            if oldest_dt <= target_start_dt: break
            curr_date_str = (oldest_dt - timedelta(days=1)).strftime("%Y%m%d")
        else:
            break
            
    if not all_data: return pd.DataFrame()
    df = pd.concat(all_data, ignore_index=True)
    df = df.drop_duplicates()
    date_key = 'deal_date' if 'deal_date' in df.columns else 'stck_bsop_date'
    df['date'] = pd.to_datetime(df[date_key])
    
    df['credit_balance'] = pd.to_numeric(df['whol_loan_rmnd_stcn'])
    df['credit_rate'] = pd.to_numeric(df['whol_loan_rmnd_rate'])
    
    df = df[df['date'] >= target_start_dt]
    return df[['date', 'credit_balance', 'credit_rate']].sort_values('date')

def fetch_daily_lending_balance_full():
    print("Fetching lending balance (short proxy) data...")
    all_data = []
    
    current_start = datetime.strptime(START_DATE, "%Y%m%d")
    end_dt = datetime.strptime(END_DATE, "%Y%m%d")
    
    # 3-month chunks to stay within 100 limit
    while current_start < end_dt:
        current_end = current_start + timedelta(days=90)
        if current_end > end_dt: current_end = end_dt
            
        s_date = current_start.strftime("%Y%m%d")
        e_date = current_end.strftime("%Y%m%d")
        
        tr_id = "HHPST074500C0"
        params = {
            "MRKT_DIV_CLS_CODE": "3", # Stock
            "MKSC_SHRN_ISCD": STOCK_CODE,
            "START_DATE": s_date,
            "END_DATE": e_date,
            "CTS": ""
        }
        
        # Lending Balance URL
        API_URL_LENDING = "/uapi/domestic-stock/v1/quotations/daily-loan-trans"
        
        res = kis_auth._url_fetch(API_URL_LENDING, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output1)
            if not chunk.empty:
                all_data.append(chunk)
        
        current_start = current_end + timedelta(days=1)
        
    if not all_data: return pd.DataFrame()
        
    df = pd.concat(all_data, ignore_index=True)
    df = df.drop_duplicates(subset=['bsop_date'])
    df['date'] = pd.to_datetime(df['bsop_date'])
    
    # rmnd_stcn: Remaining Lending Balance (Shares)
    df['lending_balance'] = pd.to_numeric(df['rmnd_stcn'])
    # new_stcn: New Lending (Shares)
    df['lending_new'] = pd.to_numeric(df['new_stcn'])
    # rdmp_stcn: Repayment Lending (Shares)
    df['lending_repaid'] = pd.to_numeric(df['rdmp_stcn'])
    
    return df[['date', 'lending_balance', 'lending_new', 'lending_repaid']].sort_values('date')

def fetch_financial_data():
    print("Fetching financial data (Sales/Net Income)...")
    tr_id = "FHKST66430200"
    params = {
        "FID_DIV_CLS_CODE": "1", # 1: Quarter
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": STOCK_CODE
    }
    
    API_URL_FINANCE = "/uapi/domestic-stock/v1/finance/income-statement"
    
    res = kis_auth._url_fetch(API_URL_FINANCE, tr_id, "", params)
    if res.isOK():
        df = pd.DataFrame(res.getBody().output)
        # Columns: stac_yymm, sale_account, thtr_ntin
        df['date'] = pd.to_datetime(df['stac_yymm'], format='%Y%m') + pd.offsets.MonthEnd(0) # End of month
        df['revenue'] = pd.to_numeric(df['sale_account']) * 100000000 # Unit: 100 Million KRW -> KRW
        df['net_income'] = pd.to_numeric(df['thtr_ntin']) * 100000000
        return df[['date', 'revenue', 'net_income']].sort_values('date')
    else:
        return pd.DataFrame()

def fetch_balance_sheet_data():
    print("Fetching Balance Sheet (Total Equity)...")
    tr_id = "FHKST66430100"
    params = {
        "FID_DIV_CLS_CODE": "1",
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": STOCK_CODE
    }
    API_URL = "/uapi/domestic-stock/v1/finance/balance-sheet"
    res = kis_auth._url_fetch(API_URL, tr_id, "", params)
    if res.isOK():
        df = pd.DataFrame(res.getBody().output)
        df['date'] = pd.to_datetime(df['stac_yymm'], format='%Y%m') + pd.offsets.MonthEnd(0)
        # total_cptl: Total Capital (Equity) in 100M KRW
        df['equity'] = pd.to_numeric(df['total_cptl']) * 100000000
        return df[['date', 'equity']].sort_values('date')
    return pd.DataFrame()

def fetch_stock_info():
    print("Fetching Stock Info (Shares)...")
    tr_id = "FHKST01010100"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": STOCK_CODE
    }
    res = kis_auth._url_fetch("/uapi/domestic-stock/v1/quotations/inquire-price", tr_id, "", params)
    if res.isOK():
        return float(res.getBody().output.get('lstn_stcn', 0))
    return 0

def fetch_news_events(start_date_str=START_DATE):
    print("Fetching News Events (Pagination - Date Walking)...")
    tr_id = "FHKST01011800"
    params = {
        "FID_NEWS_OFER_ENTP_CODE": "0",  
        "FID_COND_MRKT_CLS_CODE": "00", 
        "FID_INPUT_ISCD": STOCK_CODE,
        "FID_TITL_CNTT": "",
        "FID_INPUT_DATE_1": datetime.now().strftime("%Y%m%d"),
        "FID_INPUT_HOUR_1": "235959",
        "FID_RANK_SORT_CLS_CODE": "0",
        "FID_INPUT_SRNO": ""
    }
    API_URL = "/uapi/domestic-stock/v1/quotations/news-title"
    
    all_news_rows = []
    target_date = pd.to_datetime(start_date_str, format='%Y%m%d')
    curr_date = datetime.now().strftime("%Y%m%d")
    curr_time = "235959"
    
    max_pages = 100 # Increase limit to cover full year (approx 365/5 = 73 pages)
    
    for i in range(max_pages):
        params["FID_INPUT_DATE_1"] = curr_date
        params["FID_INPUT_HOUR_1"] = curr_time
        
        # print(f"  Fetching page {i+1} (Date: {curr_date})...")
        res = kis_auth._url_fetch(API_URL, tr_id, "", params)
        if not res.isOK():
            break
            
        output = res.getBody().output
        if not output: break
        if not isinstance(output, list): output = [output]
        
        all_news_rows.extend(output)
        
        # formatting check to update next cursor
        temp_df = pd.DataFrame(output)
        if 'data_dt' in temp_df.columns and 'data_tm' in temp_df.columns:
            temp_df['dt'] = pd.to_datetime(temp_df['data_dt'], format='%Y%m%d', errors='coerce')
            min_dt_val = temp_df['data_dt'].min()
            
            # Find row with min date
            min_rows = temp_df[temp_df['data_dt'] == min_dt_val]
            min_tm_val = min_rows['data_tm'].min()
            
            # Update cursor to 1 second before oldest record
            min_datetime_str = f"{min_dt_val}{min_tm_val}"
            try:
                dt_obj = datetime.strptime(min_datetime_str, "%Y%m%d%H%M%S")
                next_dt_obj = dt_obj - timedelta(seconds=1)
                
                curr_date = next_dt_obj.strftime("%Y%m%d")
                curr_time = next_dt_obj.strftime("%H%M%S")
                
                # Check stop condition
                if dt_obj < target_date:
                    break
            except ValueError:
                break
        else:
            break
            
    if not all_news_rows:
        return pd.DataFrame()
        
    df = pd.DataFrame(all_news_rows)
    df['date'] = pd.to_datetime(df['data_dt'], format='%Y%m%d', errors='coerce')
    df = df[df['date'] >= target_date]
    
    # Filter by keywords and categorize
    title_col = 'hts_pbnt_titl_cntt' if 'hts_pbnt_titl_cntt' in df.columns else 'cntt'
    if title_col in df.columns:
        # Define keywords
        order_keywords = ['수주', '단일판매', '계약']
        disclosure_keywords = ['공시']
        
        # Create category column
        def categorize(text):
            for kw in order_keywords:
                if kw in text: return 'Order'
            for kw in disclosure_keywords:
                if kw in text: return 'Disclosure'
            return 'Other'
            
        df['category'] = df[title_col].apply(categorize)
        
        # Filter only relevant categories
        df = df[df['category'].isin(['Order', 'Disclosure'])]
    
    # Deduplicate by date and category
    return df[['date', 'category']].drop_duplicates().sort_values('date')

def fetch_analyst_opinion(start_date_str=START_DATE):
    print("Fetching Analyst Consensus/Target Prices...")
    all_data = []
    
    # 6633: Investment Opinion
    # Input Date 1 (Start), 2 (End)
    # Recursion might be needed if many opinions, but typically not that many in 1 year.
    # We'll rely on the default (latest).
    
    tr_id = "FHKST663300C0"
    params_start_date = datetime.strptime(start_date_str, "%Y%m%d").strftime("%Y%m%d")
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "16633",
        "FID_INPUT_ISCD": STOCK_CODE,
        "FID_INPUT_DATE_1": params_start_date,
        "FID_INPUT_DATE_2": datetime.now().strftime("%Y%m%d")
    }
    
    API_URL = "/uapi/domestic-stock/v1/quotations/invest-opinion"
    
    res = kis_auth._url_fetch(API_URL, tr_id, "", params)
    if res.isOK():
        chunk = pd.DataFrame(res.getBody().output)
        if not chunk.empty:
            # required cols: stck_bsop_date, mbcr_name, invt_opnn, hts_goal_prc
            chunk['date'] = pd.to_datetime(chunk['stck_bsop_date'], format='%Y%m%d', errors='coerce')
            chunk['target_price'] = pd.to_numeric(chunk['hts_goal_prc'], errors='coerce')
            chunk['broker'] = chunk['mbcr_name']
            chunk['opinion'] = chunk['invt_opnn']
            
            # Filter non-zero target prices
            chunk = chunk[chunk['target_price'] > 0]
            
            return chunk[['date', 'broker', 'opinion', 'target_price']].sort_values('date')
            
    return pd.DataFrame()

def fetch_dividend_history(start_date_str=START_DATE):
    print("Fetching Dividend History (Ex-Dates/Amounts)...")
    
    # Extend range to include previous year's end to avoid missing year-end dividends
    start_dt = datetime.strptime(start_date_str, "%Y%m%d")
    extended_start_str = (start_dt - timedelta(days=365)).strftime("%Y%m%d")
    
    tr_id = "HHKDB669102C0"
    params = {
        "CTS": "",
        "GB1": "0", # 0: Total
        "F_DT": extended_start_str,
        "T_DT": datetime.now().strftime("%Y%m%d"),
        "SHT_CD": STOCK_CODE,
        "HIGH_GB": ""
    }
    API_URL = "/uapi/domestic-stock/v1/ksdinfo/dividend"
    
    res = kis_auth._url_fetch(API_URL, tr_id, "", params)
    if res.isOK():
        output = res.getBody().output1
        if output:
            df = pd.DataFrame(output)
            # record_date: 배당기준일
            # per_sto_divi_amt: 주당배당금
            df['date'] = pd.to_datetime(df['record_date'], format='%Y%m%d', errors='coerce')
            df['div_amt'] = pd.to_numeric(df['per_sto_divi_amt'], errors='coerce')
            
            # Approximate Ex-dividend date (배당락일 is usually 1 business day before record date)
            # For simplicity, we'll mark the record date but label it as Ex-Date/Dividend
            return df[['date', 'div_amt']].sort_values('date')
            
    return pd.DataFrame()

def visualize():
    df_price = fetch_daily_prices()
    df_investor = fetch_investor_trends()
    df_short = fetch_daily_short_sale_full()
    df_credit = fetch_daily_credit_balance_full()
    df_lending = fetch_daily_lending_balance_full()
    df_finance = fetch_financial_data()
    df_balance = fetch_balance_sheet_data()
    total_shares = fetch_stock_info()
    df_news = fetch_news_events(START_DATE)
    df_opinion = fetch_analyst_opinion(START_DATE)
    df_dividend = fetch_dividend_history(START_DATE)
    
    if df_price.empty or df_investor.empty:
        print("Data insufficient.")
        return

    # Merge Daily Data
    df_final = pd.merge(df_price, df_investor, on='date', how='inner')
    if not df_short.empty:
        df_final = pd.merge(df_final, df_short, on='date', how='left')
    if not df_credit.empty:
        df_final = pd.merge(df_final, df_credit, on='date', how='left')
    if not df_lending.empty:
        df_final = pd.merge(df_final, df_lending, on='date', how='left')

    # Add cumulative
    df_final['cum_individual'] = df_final['prsn_ntby_qty'].cumsum()
    df_final['cum_foreigner'] = df_final['frgn_ntby_qty'].cumsum()
    df_final['cum_institution'] = df_final['orgn_ntby_qty'].cumsum()
    
    # Calculate MAs
    df_final['MA20'] = df_final['price'].rolling(window=20).mean()
    df_final['MA60'] = df_final['price'].rolling(window=60).mean()
    df_final['MA120'] = df_final['price'].rolling(window=120).mean()

    # Sort
    df_final = df_final.sort_values('date')

    # Fundamentals & Valuation
    # Merge Finance (IS) and Balance (BS)
    if not df_finance.empty and not df_balance.empty and total_shares > 0:
        # Merge BS into IS based on date
        df_fund = pd.merge(df_finance, df_balance, on='date', how='outer').sort_values('date')
        
        # Merge into Daily
        df_merged = pd.merge_asof(df_final, df_fund, on='date', direction='backward')
        
        # Calculate Valuation Ratios
        # Annualize Net Income/Revenue based on Month (Quarter)
        # month 03 -> *4, 06 -> *2, 09 -> *4/3, 12 -> *1
        df_merged['month'] = df_merged['date'].dt.month
        df_merged['annual_factor'] = df_merged['month'].apply(lambda m: 12/m if m > 0 else 1)
        
        # Avoid zero division
        df_merged['annual_revenue'] = df_merged['revenue'] * df_merged['annual_factor']
        df_merged['annual_income'] = df_merged['net_income'] * df_merged['annual_factor']
        
        # EPS, BPS, SPS
        df_merged['EPS'] = df_merged['annual_income'] / total_shares
        df_merged['BPS'] = df_merged['equity'] / total_shares
        df_merged['SPS'] = df_merged['annual_revenue'] / total_shares
        
        # PER, PBR, PSR
        df_merged['PER'] = df_merged['price'] / df_merged['EPS']
        df_merged['PBR'] = df_merged['price'] / df_merged['BPS']
        df_merged['PSR'] = df_merged['price'] / df_merged['SPS']
    else:
        df_merged = df_final
        # Fill NaN
        for col in ['PER', 'PBR', 'PSR', 'revenue', 'net_income']:
            df_merged[col] = np.nan

    # Plot - 5 Panels
    # Panel 4: Valuation (PBR/PSR Left, PER Right)
    
    fig, (ax1, ax_credit, ax_short, ax_val, ax_vol) = plt.subplots(5, 1, figsize=(14, 22), gridspec_kw={'height_ratios': [3, 2, 2, 2, 1]}, sharex=True)
    
    # --- Panel 1: Price + Investor + MA ---
    color = 'black'
    ax1.set_ylabel('Price (KRW)', color=color, fontweight='bold')
    ax1.plot(df_merged['date'], df_merged['price'], color=color, linewidth=2, label='Price', zorder=1)
    
    # MAs
    ax1.plot(df_merged['date'], df_merged['MA20'], color='gold', linewidth=1.5, label='MA20')
    ax1.plot(df_merged['date'], df_merged['MA60'], color='forestgreen', linewidth=1.5, label='MA60')
    ax1.plot(df_merged['date'], df_merged['MA120'], color='gray', linewidth=1.5, label='MA120', linestyle='--')
    
    # Analyst Target Prices
    if not df_opinion.empty:
        # Filter within graph range
        valid_opinions = df_opinion[df_opinion['date'] >= df_merged['date'].min()]
        
        if not valid_opinions.empty:
            # Sort by date
            valid_opinions = valid_opinions.sort_values('date')
            
            # Plot ALL target prices as a step progression
            # Iterate to draw lines from current date to next date
            
            chart_end_date = df_merged['date'].max()
            max_target_price = 0
            
            for i in range(len(valid_opinions)):
                row = valid_opinions.iloc[i]
                t_price = row['target_price']
                s_date = row['date']
                max_target_price = max(max_target_price, t_price)
                
                # Determine end date of this line segment
                if i < len(valid_opinions) - 1:
                    e_date = valid_opinions.iloc[i+1]['date']
                else:
                    e_date = chart_end_date
                
                # Draw the line segment
                ax1.hlines(y=t_price, xmin=s_date, xmax=e_date, 
                           colors='magenta', linestyles='--', linewidth=2, zorder=7)
                
                # Mark the start of the recommendation
                ax1.scatter(s_date, t_price, color='magenta', s=20, zorder=8)
                
                # Annotation varies
                if i == len(valid_opinions) - 1:
                    # LATEST Target: Detailed Info at the END of the chart
                    current_price = df_merged.iloc[-1]['price']
                    upside = (t_price - current_price) / current_price * 100
                    date_str = s_date.strftime('%y.%m.%d')
                    
                    label_text = f"Target: {t_price:,.0f}\n({date_str})\nUpside: {upside:+.1f}%"
                    
                    ax1.annotate(label_text, 
                                 xy=(chart_end_date, t_price), 
                                 xytext=(10, 0), textcoords='offset points',
                                 color='white', fontweight='bold', fontsize=10, va='center', ha='left',
                                 bbox=dict(boxstyle="round,pad=0.3", fc="magenta", ec="magenta", alpha=1.0))
                else:
                     # Past Targets: Simple text on the line
                     date_str = s_date.strftime('%y.%m.%d')
                     ax1.annotate(f"{t_price:,.0f}", 
                                  xy=(s_date, t_price), 
                                  xytext=(0, 5), textcoords='offset points',
                                  color='magenta', fontweight='bold', fontsize=8, va='bottom', ha='left')

            # Ensure Y-axis includes all target prices
            current_ylim = ax1.get_ylim()
            new_ymax = max(current_ylim[1], max_target_price * 1.15)
            ax1.set_ylim(current_ylim[0], new_ymax)

    # News Events
    if not df_news.empty:
        # 1. Orders (수주)
        order_dates = df_news[df_news['category'] == 'Order']['date']
        order_points = df_merged[df_merged['date'].isin(order_dates)]
        if not order_points.empty:
            ax1.scatter(order_points['date'], order_points['price'], 
                        color='lime', marker='*', s=150, 
                        label='Contract/Order', zorder=6, edgecolors='black', linewidth=0.5)

        # 2. Disclosures (공시)
        discl_dates = df_news[df_news['category'] == 'Disclosure']['date']
        discl_points = df_merged[df_merged['date'].isin(discl_dates)]
        if not discl_points.empty:
            ax1.scatter(discl_points['date'], discl_points['price'], 
                        color='orange', marker='v', s=80, 
                        label='Disclosure', zorder=5, edgecolors='white')

    # Dividend Events
    if not df_dividend.empty:
        # Align with price data (mark on or nearest date)
        div_merged = pd.merge_asof(df_dividend.sort_values('date'), 
                                   df_merged[['date', 'price']].sort_values('date'), 
                                   on='date', direction='nearest')
        
        chart_start_date = df_merged['date'].min()
        chart_end_date = df_merged['date'].max()
        
        for idx, row in div_merged.iterrows():
            actual_div_date = row['date']
            
            # Filter: only show dividends close to or within chart range
            if actual_div_date < chart_start_date:
                # Catch year-end dividends (e.g. 12/31 for 01/01 chart)
                if (chart_start_date - actual_div_date).days > 5:
                    continue
            if actual_div_date > chart_end_date:
                continue
                
            if not pd.isna(row['price']):
                ax1.scatter(row['date'], row['price'], 
                            color='gold', marker='D', s=100, 
                            label='Dividend' if idx == 0 else "", zorder=9, edgecolors='black')
                
                # Annotation for amount
                ax1.annotate(f"Div: {row['div_amt']:,.0f}", 
                             xy=(row['date'], row['price']), 
                             xytext=(0, 15), textcoords='offset points',
                             color='darkgoldenrod', fontweight='bold', fontsize=9, 
                             ha='center', va='bottom',
                             bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="gold", alpha=0.9))
    
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.grid(True, alpha=0.2)
    ax1.set_title(f"{STOCK_NAME} - Detailed Analysis (2025 Full Year) including Valuation")

    ax1_twin = ax1.twinx()
    ax1_twin.set_ylabel('Cum. Net Buy (Shares)', color='tab:blue', fontweight='bold')
    l_inst = ax1_twin.plot(df_merged['date'], df_merged['cum_institution'], color='tab:red', label='Institution (Cum)', linewidth=2.5)
    l_frgn = ax1_twin.plot(df_merged['date'], df_merged['cum_foreigner'], color='tab:blue', label='Foreigner (Cum)', linestyle='--', alpha=0.7)
    l_indi = ax1_twin.plot(df_merged['date'], df_merged['cum_individual'], color='tab:green', label='Individual (Cum)', linestyle=':', alpha=0.7)
    ax1_twin.axhline(0, color='gray', linewidth=0.8, linestyle='--')
    
    # Combine legends from both axes
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax1_twin.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left', ncol=3, fontsize='small')

    # --- Panel 2: Credit Analysis ---
    color_bal = 'rebeccapurple'
    color_rate = 'mediumpurple'
    
    ax_credit.set_ylabel('Credit Balance (Shares)', color=color_bal, fontweight='bold')
    lc1 = ax_credit.plot(df_merged['date'], df_merged['credit_balance'], color=color_bal, label='Credit Balance', linewidth=2)
    ax_credit.tick_params(axis='y', labelcolor=color_bal)
    ax_credit.grid(True, alpha=0.2)
    
    ax_credit_twin = ax_credit.twinx()
    ax_credit_twin.set_ylabel('Credit Rate (%)', color=color_rate, fontweight='bold')
    lc2 = ax_credit_twin.plot(df_merged['date'], df_merged['credit_rate'], color=color_rate, label='Credit Rate', linestyle='--', alpha=0.8)
    ax_credit_twin.tick_params(axis='y', labelcolor=color_rate)
    ax_credit.legend(lc1+lc2, [l.get_label() for l in lc1+lc2], loc='upper left')

    # Calculate Cumulative flows
    if 'lending_new' in df_merged.columns:
        df_merged['cum_lending_new'] = df_merged['lending_new'].cumsum()
        df_merged['cum_lending_repaid'] = df_merged['lending_repaid'].cumsum()

    # --- Panel 3: Short/Lending Analysis (Balance vs Cumulative Flow) ---
    color_lending = 'darkorange'
    
    # Left Axis: Stocks (Balance, Cum New, Cum Repaid)
    ax_short.set_ylabel('Balance / Cumulative (Shares)', color='black', fontweight='bold')
    
    lines_s = []
    if 'lending_balance' in df_merged.columns:
        l1 = ax_short.plot(df_merged['date'], df_merged['lending_balance'], color=color_lending, label='Lending Balance (Net)', linewidth=2.5, zorder=3)
        lines_s.extend(l1)
        
    if 'lending_new' in df_merged.columns and 'lending_repaid' in df_merged.columns:
        # Calculate Net Lending Flow (Short vs Covering)
        df_merged['net_lending_flow'] = df_merged['lending_new'] - df_merged['lending_repaid']
        # Cumulative Net Flow to show trend
        df_merged['cum_net_flow'] = df_merged['net_lending_flow'].cumsum()
        
        # Plot Net Flow as a line
        l_net = ax_short.plot(df_merged['date'], df_merged['cum_net_flow'], color='darkgreen', 
                              label='Cum. Net Flow (Short - Cover)', linewidth=2, linestyle='-')
        lines_s.extend(l_net)
        
    if 'cum_lending_new' in df_merged.columns:
        l2 = ax_short.plot(df_merged['date'], df_merged['cum_lending_new'], color='firebrick', label='Cum. New Lending (Short)', linestyle='--', linewidth=1.5, alpha=0.6)
        l3 = ax_short.plot(df_merged['date'], df_merged['cum_lending_repaid'], color='royalblue', label='Cum. Repayment (Covering)', linestyle='--', linewidth=1.5, alpha=0.6)
        lines_s.extend(l2 + l3)
        
    ax_short.tick_params(axis='y', labelcolor='black')
    ax_short.grid(True, alpha=0.2)
    
    # Right Axis: Daily Net Flow (Colored Bars for Short vs Cover)
    ax_short_twin = ax_short.twinx()
    ax_short_twin.set_ylabel('Daily Net Flow (Shares)', color='gray', fontweight='bold')
    
    if 'net_lending_flow' in df_merged.columns:
        # Color bars based on whether Short (New) or Cover (Repaid) is greater
        colors = ['red' if x > 0 else 'blue' for x in df_merged['net_lending_flow']]
        b_net = ax_short_twin.bar(df_merged['date'], df_merged['net_lending_flow'], color=colors, alpha=0.3, label='Daily Net Flow')
        ax_short_twin.axhline(0, color='black', linewidth=0.8, alpha=0.5)
        
        # Combine legends
        from matplotlib.patches import Patch
        legend_elements = lines_s + [
            Patch(facecolor='red', alpha=0.5, label='Short > Cover'),
            Patch(facecolor='blue', alpha=0.5, label='Cover > Short')
        ]
        ax_short.legend(handles=legend_elements, loc='upper left', fontsize='small', ncol=2)
    
    ax_short_twin.tick_params(axis='y', labelcolor='gray')

    # --- Panel 4: Valuation (PBR/Likely PSR vs PER) ---
    color_pbr = 'navy'
    color_per = 'maroon'
    
    ax_val.set_ylabel('PBR / PSR (x)', color=color_pbr, fontweight='bold')
    l_pbr = ax_val.plot(df_merged['date'], df_merged['PBR'], color=color_pbr, label='PBR', linewidth=2)
    l_psr = ax_val.plot(df_merged['date'], df_merged['PSR'], color='teal', label='PSR', linewidth=1.5, linestyle='-.')
    
    ax_val.tick_params(axis='y', labelcolor=color_pbr)
    ax_val.grid(True, alpha=0.2)
    
    ax_val_twin = ax_val.twinx()
    ax_val_twin.set_ylabel('PER (x)', color=color_per, fontweight='bold')
    l_per = ax_val_twin.plot(df_merged['date'], df_merged['PER'], color=color_per, label='PER', linestyle='--', linewidth=1.5)
    ax_val_twin.tick_params(axis='y', labelcolor=color_per)
    
    lns_v = l_pbr + l_psr + l_per
    ax_val.legend(lns_v, [l.get_label() for l in lns_v], loc='upper left')

    # --- Panel 5: Volume ---
    ax_vol.bar(df_merged['date'], df_merged['volume'], color='gray', alpha=0.5, label='Volume')
    ax_vol.set_ylabel('Volume', color='gray', fontweight='bold')
    ax_vol.set_xlabel('Date')
    ax_vol.legend(loc='upper left')
    ax_vol.grid(True, alpha=0.2)
    
    # --- Annotate Peaks & Vertical Lines ---
    peak_dates = {}
    
    def annotate_and_line(ax, series, color, label_prefix="", draw_line=True, value_sign=1):
        if series.empty: return
        max_idx = series.idxmax()
        if pd.isna(max_idx): return
        max_val = series.loc[max_idx]
        max_date = df_merged.loc[max_idx, 'date']
        
        if draw_line:
            peak_dates[label_prefix] = (max_date, color)
        
        plot_val = max_val * value_sign
        if value_sign == 1:
            text_offset = (0, 30); va = 'bottom'
        else:
            text_offset = (0, -40); va = 'top'
            
        ax.annotate(f'{label_prefix}Peak: {max_date.strftime("%Y-%m-%d")}\n{max_val:,.1f}', 
                    xy=(max_date, plot_val), xytext=text_offset, textcoords='offset points', 
                    arrowprops=dict(facecolor=color, shrink=0.05, alpha=0.7),
                    horizontalalignment='center', verticalalignment=va,
                    color=color, fontweight='bold', fontsize=9,
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=color, alpha=0.8))

    df_merged = df_merged.reset_index(drop=True)
    
    annotate_and_line(ax1, df_merged['price'], 'black', "Price ")
    annotate_and_line(ax_credit, df_merged['credit_balance'], 'rebeccapurple', "Credit ")
    if 'lending_balance' in df_merged.columns:
        annotate_and_line(ax_short, df_merged['lending_balance'], 'darkorange', "Lending ")
    if 'lending_repaid' in df_merged.columns:
        annotate_and_line(ax_short_twin, df_merged['lending_repaid'], 'blue', "Max Repay ", value_sign=-1)

    # Draw Vertical Lines on ALL Axes
    axes_list = [ax1, ax_credit, ax_short, ax_val, ax_vol]
    for label, (p_date, p_color) in peak_dates.items():
        for ax in axes_list:
            ax.axvline(p_date, color=p_color, linestyle=':', linewidth=1.5, alpha=0.8)
    
    plt.tight_layout()
    # Sanitize STOCK_NAME for filename
    safe_name = STOCK_NAME.replace(" ", "_").replace("(", "").replace(")", "").replace("&", "")
    output_path = f"{safe_name}_comprehensive_chart_2025.png"
    plt.savefig(output_path)
    print(f"Chart saved to {output_path}")

if __name__ == "__main__":
    visualize()
