import pandas as pd
import numpy as np
from visualize_investor_trends import (
    fetch_daily_prices,
    fetch_investor_trends,
    fetch_daily_credit_balance_full,
    fetch_daily_lending_balance_full,
    fetch_daily_short_sale_full,
    STOCK_NAME
)

def analyze():
    print(f"Analyzing {STOCK_NAME} (Full Year 2025)...")
    
    # 1. Fetch Data
    df_price = fetch_daily_prices()
    df_investor = fetch_investor_trends()
    df_credit = fetch_daily_credit_balance_full()
    df_lending = fetch_daily_lending_balance_full()
    df_short = fetch_daily_short_sale_full()
    
    # 2. Merge
    df = pd.merge(df_price, df_investor, on='date', how='inner')
    if not df_credit.empty:
        df = pd.merge(df, df_credit, on='date', how='left')
    if not df_lending.empty:
        df = pd.merge(df, df_lending, on='date', how='left')
    if not df_short.empty:
        df = pd.merge(df, df_short[['date', 'short_ratio']], on='date', how='left')
        
    df = df.sort_values('date')
    
    # 3. Calculate Cumulative Trends
    df['cum_individual'] = df['prsn_ntby_qty'].cumsum()
    df['cum_foreigner'] = df['frgn_ntby_qty'].cumsum()
    df['cum_institution'] = df['orgn_ntby_qty'].cumsum()
    
    # 4. Correlation Analysis
    # We want to know what drives the Price.
    target = 'price'
    candidates = [
        'cum_institution', 'cum_foreigner', 'cum_individual',
        'credit_balance', 'credit_rate', 
        'lending_balance', 'short_ratio'
    ]
    
    # Filter only existing columns
    candidates = [c for c in candidates if c in df.columns]
    
    print("\n--- Correlation with Price ---")
    correlations = df[[target] + candidates].corr()[target].sort_values(ascending=False)
    print(correlations)
    
    # 5. Recent Trends (Last 30 Days)
    recent_df = df.tail(30)
    print("\n--- Recent 30 Days Trend (Slope) ---")
    # Simple linear slope (normalized)
    for col in [target] + candidates:
        if col in recent_df.columns:
            y = recent_df[col].values
            x = np.arange(len(y))
            # Normalize to compare slopes
            y_norm = (y - np.min(y)) / (np.max(y) - np.min(y) + 1e-9)
            slope, _ = np.polyfit(x, y_norm, 1)
            direction = "UP" if slope > 0.01 else "DOWN" if slope < -0.01 else "FLAT"
            print(f"{col}: {direction} (Slope: {slope:.4f})")

    # 6. Key Insights Generation
    print("\n--- Key Analysis ---")
    
    # Investor Influence
    top_driver = correlations.index[1] if len(correlations) > 1 else "None"
    driver_corr = correlations[top_driver]
    print(f"1. Primary Price Driver: {top_driver} (Corr: {driver_corr:.2f})")
    
    # Short/Lending Signal
    if 'lending_balance' in df.columns:
        lending_corr = df['price'].corr(df['lending_balance'])
        print(f"2. Lending Balance (Short Potential): Correlation with Price is {lending_corr:.2f}")
        if lending_corr > 0.5:
             print("   -> Price rises as Lending Balance increases (Counter-intuitive: Short squeeze or hedging?)")
        elif lending_corr < -0.5:
             print("   -> Price falls as Lending Balance increases (Typical Short Selling pressure)")
        else:
             print("   -> No strong linear relationship.")

    # Credit Signal
    if 'credit_balance' in df.columns:
        credit_corr = df['price'].corr(df['credit_balance'])
        print(f"3. Credit Balance (Individual Leverage): Correlation with Price is {credit_corr:.2f}")

if __name__ == "__main__":
    analyze()
