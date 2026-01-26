import sys
import os
import pandas as pd
import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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
API_URL_NEWS = "/uapi/domestic-stock/v1/quotations/news-title"

STOCK_CODE = "014940"
STOCK_NAME = "Oriental Precision (014940)"
START_DATE = "20250901"
END_DATE = datetime.now().strftime("%Y%m%d")

# -- Reusing Check Functions from analyze_correlation_oriental.py --
def fetch_weekly_prices():
    # ... (same logic, adapted for daily if needed for graph smoothness, but weekly is fine)
    # Actually for graph, Daily Price is better.
    print(f"Fetching daily prices from {START_DATE}...")
    kis_auth.auth()
    tr_id = "FHKST03010100"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": STOCK_CODE,
        "FID_INPUT_DATE_1": START_DATE,
        "FID_INPUT_DATE_2": END_DATE,
        "FID_PERIOD_DIV_CODE": "D", # Daily for smoother graph
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

def fetch_daily_short_sale_full():
    # Same logic as analyze_correlation
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
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": STOCK_CODE,
            "FID_INPUT_DATE_1": s_date, "FID_INPUT_DATE_2": e_date
        }
        res = kis_auth._url_fetch(API_URL_SHORT, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output2)
            if not chunk.empty: all_data.append(chunk)
        current_start = current_end + timedelta(days=1)
        
    if not all_data: return pd.DataFrame()
    df = pd.concat(all_data, ignore_index=True)
    df = df.drop_duplicates(subset=['stck_bsop_date'])
    df['date'] = pd.to_datetime(df['stck_bsop_date'])
    df['short_ratio'] = pd.to_numeric(df['ssts_vol_rlim'])
    return df[['date', 'short_ratio']].sort_values('date')

def fetch_daily_credit_balance_full():
    print("Fetching credit balance data...")
    all_data = []
    curr_date_str = END_DATE
    target_start_dt = datetime.strptime(START_DATE, "%Y%m%d")
    
    for _ in range(10): 
        tr_id = "FHPST04760000"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J", "FID_COND_SCR_DIV_CODE": "20476",
            "FID_INPUT_ISCD": STOCK_CODE, "FID_INPUT_DATE_1": curr_date_str
        }
        res = kis_auth._url_fetch(API_URL_CREDIT, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output)
            if chunk.empty: break
            all_data.append(chunk)
            
            if 'deal_date' in chunk.columns: oldest = chunk['deal_date'].min()
            elif 'stck_bsop_date' in chunk.columns: oldest = chunk['stck_bsop_date'].min()
            else: oldest = chunk.iloc[-1, 0]
            
            if datetime.strptime(oldest, "%Y%m%d") <= target_start_dt: break
            curr_date_str = (datetime.strptime(oldest, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
        else: break
            
    if not all_data: return pd.DataFrame()
    df = pd.concat(all_data, ignore_index=True).drop_duplicates()
    date_key = 'deal_date' if 'deal_date' in df.columns else 'stck_bsop_date'
    df['date'] = pd.to_datetime(df[date_key])
    df['credit_rate'] = pd.to_numeric(df['whol_loan_rmnd_rate'])
    df = df[df['date'] >= target_start_dt]
    return df[['date', 'credit_rate']].sort_values('date')

def fetch_news_data():
    """Fetch recent news titles"""
    print("Fetching news data...")
    all_news = []
    # News API doesn't support date range well in one go, usually paginate by date or seq
    # Params: FID_INPUT_DATE_1 (Date), FID_INPUT_HOUR_1 (Time)
    
    # We will fetch news around the major price drop events or just generally for the period? 
    # Fetching ALL news for 4 months might be too much API calling if not paginated efficiently
    # Let's try to fetch last 30 days or iterate a bit.
    
    curr_date = END_DATE
    target_start = datetime.strptime(START_DATE, "%Y%m%d")
    
    for _ in range(5): # Limit pages
        tr_id = "FHKST01011800"
        params = {
            "FID_NEWS_OFER_ENTP_CODE": "2", # e.g. Yonhap
            "FID_COND_MRKT_CLS_CODE": "00",
            "FID_INPUT_ISCD": STOCK_CODE,
            "FID_TITL_CNTT": "",
            "FID_INPUT_DATE_1": curr_date,
            "FID_INPUT_HOUR_1": "235959",
            "FID_RANK_SORT_CLS_CODE": "1", # Recent order
            "FID_INPUT_SRNO": ""
        }
        
        res = kis_auth._url_fetch(API_URL_NEWS, tr_id, "", params)
        if res.isOK():
            chunk = pd.DataFrame(res.getBody().output)
            if chunk.empty: break
            
            # chunk columns: cntg_time, dorg, news_titl, etc.
            # no date column in output? usually mixed in or logic implies 'today' of input?
            # actually output has 'data_dt' or similar commonly.
            
            # Let's check columns if we can. Assuming standard output.
            # Output fields: hts_pbnt_titl_cntt (Title), data_dt (Date)
            
            all_news.append(chunk)
            
            # Pagination logic for news is usually via Date/Time of last item
            last_row = chunk.iloc[-1]
            last_date = last_row.get('data_dt')
            last_time = last_row.get('cntg_time')
            
            if last_date:
                curr_date = last_date
                if datetime.strptime(last_date, "%Y%m%d") < target_start:
                    break
            else:
                break
        else:
            break
            
    if not all_news: return pd.DataFrame()
    df = pd.concat(all_news, ignore_index=True)
    df = df.drop_duplicates()
    
    # Clean up
    if 'data_dt' in df.columns:
        df['date'] = pd.to_datetime(df['data_dt'])
        df['title'] = df['hts_pbnt_titl_cntt']
        return df[['date', 'title']].sort_values('date')
    return pd.DataFrame()

def visualize():
    df_price = fetch_weekly_prices() # Daily data actually
    df_short = fetch_daily_short_sale_full()
    df_credit = fetch_daily_credit_balance_full()
    df_news = fetch_news_data()
    
    # Merge for Plotting
    # We want a continuous daily axis
    df_chart = df_price.set_index('date')
    df_chart = df_chart.join(df_short.set_index('date'), how='left')
    df_chart = df_chart.join(df_credit.set_index('date'), how='left')
    
    # Fill NAs for continuous line (ffill)
    df_chart = df_chart.ffill()
    
    # Plot
    fig, ax1 = plt.subplots(figsize=(14, 8))
    
    # Axis 1: Price
    color = 'tab:blue'
    ax1.set_xlabel('Date')
    ax1.set_ylabel('Price (KRW)', color=color)
    ax1.plot(df_chart.index, df_chart['price'], color=color, label='Price')
    ax1.tick_params(axis='y', labelcolor=color)
    
    # Axis 2: Short Ratio & Credit Rate
    ax2 = ax1.twinx()  
    color_s = 'tab:red'
    color_c = 'tab:green'
    ax2.set_ylabel('Ratio (%)', color='black') 
    
    ax2.plot(df_chart.index, df_chart['short_ratio'], color=color_s, linestyle='--', alpha=0.7, label='Short Sale Ratio')
    ax2.plot(df_chart.index, df_chart['credit_rate'], color=color_c, linestyle=':', alpha=0.7, label='Credit Rate')
    ax2.tick_params(axis='y', labelcolor='black')
    
    # Add News Annotations
    # Filter news to significant ones or just plot dots
    if not df_news.empty:
        # Filter news within range
        df_news = df_news[df_news['date'] >= df_chart.index.min()]
        
        for idx, row in df_news.iterrows():
            date = row['date']
            title = row['title']
            
            if date in df_chart.index:
                price = df_chart.loc[date, 'price']
                # Annotate
                # Only show short title or just a marker
                ax1.scatter(date, price, color='orange', marker='^', zorder=5)
    
    # Title and Legend
    plt.title(f"{STOCK_NAME} Analysis (Price vs Short/Credit) with News")
    
    # Combine legends
    lines_1, labels_1 = ax1.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')
    
    plt.grid(True, alpha=0.3)
    
    # Save
    output_path = "oriental_precision_chart.png"
    plt.savefig(output_path)
    print(f"Chart saved to {output_path}")

if __name__ == "__main__":
    visualize()
