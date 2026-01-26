import sys
import os
import pandas as pd
import numpy as np

# Add path to reuse existing modules
sys.path.append(os.getcwd())
# Import fetching functions from the visualization script
# We assume visualize_investor_trends.py is in the current directory
from visualize_investor_trends import (
    fetch_daily_prices,
    fetch_daily_credit_balance_full,
    fetch_daily_lending_balance_full,
    fetch_financial_data,
    fetch_investor_trends,
    fetch_balance_sheet_data,
    fetch_stock_info
)
import visualize_investor_trends as vit

def analyze_data():
    if len(sys.argv) > 1:
        stock_code = sys.argv[1]
        vit.STOCK_CODE = stock_code
        print(f"Set target stock to: {stock_code}")
        
    print("--- [Interpreting Chart Data including Valuation] ---")
    
    # 1. Fetch Data
    df_price = fetch_daily_prices()
    df_finance = fetch_financial_data()
    df_balance = fetch_balance_sheet_data()
    total_shares = fetch_stock_info()
    df_investor = fetch_investor_trends()
    df_credit = fetch_daily_credit_balance_full()
    df_lending = fetch_daily_lending_balance_full()
    
    if df_price.empty or total_shares == 0:
        print("Error: No price data or shares info found.")
        return

    # Merge
    df_merged = pd.merge_asof(
        df_price.sort_values('date'), 
        pd.merge(df_finance, df_balance, on='date', how='outer').sort_values('date'),
        on='date', direction='backward'
    )
    
    # Calculate Ratios
    df_merged['month'] = df_merged['date'].dt.month
    df_merged['annual_factor'] = df_merged['month'].apply(lambda m: 12/m if m > 0 else 1)
    df_merged['BPS'] = df_merged['equity'] / total_shares
    df_merged['EPS'] = (df_merged['net_income'] * df_merged['annual_factor']) / total_shares
    df_merged['PBR'] = df_merged['price'] / df_merged['BPS']
    df_merged['PER'] = df_merged['price'] / df_merged['EPS']
    
    latest = df_merged.iloc[-1]
    peak_pbr_idx = df_merged['PBR'].idxmax()
    peak_pbr_date = df_merged.loc[peak_pbr_idx, 'date']
    peak_pbr_val = df_merged.loc[peak_pbr_idx, 'PBR']
    
    print(f"\n7. Valuation Analysis (Relationship Check)")
    print(f"   - Current PBR: {latest['PBR']:.2f}x (Based on {latest['equity']/1e8:,.0f} 100M KRW Equity)")
    print(f"   - Current PER: {latest['PER']:.1f}x")
    print(f"   - Peak PBR: {peak_pbr_val:.2f}x on {peak_pbr_date.strftime('%Y-%m-%d')}")
    print(f"   - PBR Low: {df_merged['PBR'].min():.2f}x")
    
    # Check Price vs Valuation Correlation (Correlation Coeff)
    corr_pbr = df_merged['price'].corr(df_merged['PBR'])
    print(f"   - Price-PBR Correlation: {corr_pbr:.2f} (Close to 1.0 means Price aligns with Valuation, which is expected for PBR if Equity is stable)")
    
    if latest['PBR'] < 1.0:
        print("   -> PBR is below 1.0, indicating UNDERVALUATION relative to Net Assets.")

    # 2. Merge Data
    df = pd.merge(df_price, df_investor, on='date', how='inner')
    if not df_credit.empty:
        df = pd.merge(df, df_credit, on='date', how='left')
    if not df_lending.empty:
        df = pd.merge(df, df_lending, on='date', how='left')
        
    # Sort
    df = df.sort_values('date').reset_index(drop=True)
    
    # 3. Analyze Peaks (Meaningful Values)
    price_peak_idx = df['price'].idxmax()
    price_peak_date = df.loc[price_peak_idx, 'date']
    price_peak_val = df.loc[price_peak_idx, 'price']
    
    print(f"\n1. Stock Price Peak")
    print(f"   - Date: {price_peak_date.strftime('%Y-%m-%d')}")
    print(f"   - Price: {price_peak_val:,.0f} KRW")
    
    if 'credit_balance' in df.columns:
        credit_peak_idx = df['credit_balance'].idxmax()
        credit_peak_date = df.loc[credit_peak_idx, 'date']
        credit_peak_val = df.loc[credit_peak_idx, 'credit_balance']
        
        print(f"\n2. Credit Balance Peak (Individual Debt)")
        print(f"   - Date: {credit_peak_date.strftime('%Y-%m-%d')}")
        print(f"   - Qty: {credit_peak_val:,.0f} Shares")
        
        # Time lag analysis
        lag_days = (price_peak_date - credit_peak_date).days
        print(f"   - Correlation: Credit Peak was {abs(lag_days)} days {'before' if lag_days > 0 else 'after'} Price Peak.")

    if 'lending_balance' in df.columns:
        lending_peak_idx = df['lending_balance'].idxmax()
        lending_peak_date = df.loc[lending_peak_idx, 'date']
        lending_peak_val = df.loc[lending_peak_idx, 'lending_balance']
        
        print(f"\n3. Lending Balance Peak (Short Potential)")
        print(f"   - Date: {lending_peak_date.strftime('%Y-%m-%d')}")
        print(f"   - Qty: {lending_peak_val:,.0f} Shares")
        
    if 'lending_repaid' in df.columns:
        repay_peak_idx = df['lending_repaid'].idxmax()
        repay_peak_date = df.loc[repay_peak_idx, 'date']
        repay_peak_val = df.loc[repay_peak_idx, 'lending_repaid']
        
        print(f"\n4. Max Short Covering (Repayment) Date")
        print(f"   - Date: {repay_peak_date.strftime('%Y-%m-%d')}")
        print(f"   - Qty: {repay_peak_val:,.0f} Shares")
        
        # Check price action around repayment
        repay_price = df.loc[repay_peak_idx, 'price']
        print(f"   - Price on Repay Day: {repay_price:,.0f} KRW")

    # 4. Investor Trends (Accumulated)
    df['cum_foreigner'] = df['frgn_ntby_qty'].cumsum()
    df['cum_individual'] = df['prsn_ntby_qty'].cumsum()
    
    latest = df.iloc[-1]
    print(f"\n5. YTD Investor Position (As of {latest['date'].strftime('%Y-%m-%d')})")
    print(f"   - Foreigner: {latest['cum_foreigner']:,.0f} Shares")
    print(f"   - Individual: {latest['cum_individual']:,.0f} Shares")
    
    # 5. Financials
    if not df_finance.empty:
        latest_fin = df_finance.iloc[0] # Sorted by date desc usually? No, check simplified fetch
        # The fetch function sorts by date asc
        latest_fin = df_finance.iloc[-1]
        print(f"\n6. Latest Financials (Accumulated till {latest_fin['date'].strftime('%Y-%m')})")
        print(f"   - Revenue: {latest_fin['revenue'] / 100000000:,.1f} 100M KRW")
        print(f"   - Net Income: {latest_fin['net_income'] / 100000000:,.1f} 100M KRW")

if __name__ == "__main__":
    analyze_data()
