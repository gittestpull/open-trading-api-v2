import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from visualize_investor_trends import (
    fetch_daily_prices,
    fetch_investor_trends,
    fetch_daily_credit_balance_full,
    fetch_daily_lending_balance_full,
    STOCK_NAME
)

def analyze_timing():
    print(f"Analyzing Trading Signals for {STOCK_NAME} (2025)...")
    
    # 1. Fetch & Merge Data
    df_price = fetch_daily_prices()
    df_investor = fetch_investor_trends()
    df_credit = fetch_daily_credit_balance_full()
    df_lending = fetch_daily_lending_balance_full()
    
    df = pd.merge(df_price, df_investor, on='date', how='inner')
    if not df_credit.empty:
        df = pd.merge(df, df_credit, on='date', how='left')
    if not df_lending.empty:
        df = pd.merge(df, df_lending, on='date', how='left')
        
    df = df.sort_values('date').reset_index(drop=True)
    
    # 2. Define Signals
    
    # Signal A: Credit Balance Peak (Contrarian Sell)
    # Rationale: High credit means potential overhang. If it starts dropping, forced selling might occur.
    # Logic: Sell if Credit Correlation is high AND Credit Balance drops > 2% from recent 20-day high.
    df['credit_20d_max'] = df['credit_balance'].rolling(window=20).max()
    df['signal_sell_credit'] = np.where(
        (df['credit_balance'] < df['credit_20d_max'] * 0.98) & (df['price'] > df['price'].shift(20)), 
        -1, 0
    )
    
    # Signal B: Foreigner Accumulation (Smart Money Buy)
    # Rationale: Foreigners are picking bottoms vs Individuals.
    # Logic: Buy if Foreigner Cumulative Net Buy increases for 3 consecutive days after a monthly low.
    df['cum_foreigner'] = df['frgn_ntby_qty'].cumsum()
    df['frgn_3d_trend'] = df['cum_foreigner'].diff(3)
    df['signal_buy_frgn'] = np.where(df['frgn_3d_trend'] > 0, 1, 0)
    
    # Signal C: Short Covering (Lending Balance Drop)
    # Logic: Buy if Lending Balance drops significantly (Shorts are covering).
    if 'lending_balance' in df.columns:
        df['lending_20d_max'] = df['lending_balance'].rolling(window=20).max()
        df['signal_buy_short_cover'] = np.where(
            df['lending_balance'] < df['lending_20d_max'] * 0.90, # 10% drop from peak
            1, 0
        )
    else:
        df['signal_buy_short_cover'] = 0

    # 3. Simulate Trades (Simplified)
    position = 0
    cash = 10000000 # 10M KRW
    shares = 0
    history = []
    
    for i, row in df.iterrows():
        if i < 20: continue
        
        price = row['price']
        date = row['date']
        
        # BUY Logic (Or)
        buy_signal = row['signal_buy_frgn'] == 1 or row['signal_buy_short_cover'] == 1
        
        # SELL Logic
        sell_signal = row['signal_sell_credit'] == -1
        
        # Execute
        if position == 0 and buy_signal:
            shares = cash // price
            cash -= shares * price
            position = 1
            history.append(f"{date.date()}: BUY at {price} (Signal: Frgn/Short)")
            
        elif position == 1 and sell_signal:
            cash += shares * price
            shares = 0
            position = 0
            history.append(f"{date.date()}: SELL at {price} (Signal: Credit Drop)")
            
        # Stop Loss (-5%)
        # if position == 1 and price < ...
    
    # Final Value
    if position == 1:
        cash += shares * df.iloc[-1]['price']
        
    print(f"\n--- Backtest Result ---")
    print(f"Initial: 10,000,000 KRW")
    print(f"Final:   {cash:,.0f} KRW")
    print(f"Return:  {((cash - 10000000)/10000000)*100:.2f}%")
    print(f"Buy/Hold Return: {((df.iloc[-1]['price'] - df.iloc[0]['price']) / df.iloc[0]['price'])*100:.2f}%")
    
    print("\n--- Trade Logs ---")
    for log in history[-10:]:
        print(log)
        
    # Analyze Peaks relationship
    print("\n--- Peak Analysis ---")
    price_peak_idx = df['price'].idxmax()
    credit_peak_idx = df['credit_balance'].idxmax()
    
    print(f"Price Peak: {df.iloc[price_peak_idx]['date'].date()} ({df.iloc[price_peak_idx]['price']} KRW)")
    print(f"Credit Peak: {df.iloc[credit_peak_idx]['date'].date()}")
    days_diff = (df.iloc[price_peak_idx]['date'] - df.iloc[credit_peak_idx]['date']).days
    print(f"-> Credit Peak was {abs(days_diff)} days {'before' if days_diff > 0 else 'after'} Price Peak.")

if __name__ == "__main__":
    analyze_timing()
