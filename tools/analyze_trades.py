import os
import re
from datetime import datetime
import pandas as pd

def analyze_logs(log_dir='logs'):
    print(f"📊 Analyzing trading logs in '{log_dir}'...")
    
    if not os.path.exists(log_dir):
        print(f"Error: {log_dir} directory not found.")
        return

    log_files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
    if not log_files:
        print("No log files found.")
        return

    all_trades = []
    active_trade = None
    last_asset_val = None
    first_asset_val = None
    
    # regex patterns
    entry_pat = re.compile(r"ENTRY Triggered: (.*)")
    # Pattern to catch entry from state load
    load_state_pat = re.compile(r"Loaded existing state for \w+: HOLDING \| (\d+) shares @ ([\d.]+)")
    
    exit_pat = re.compile(r"EXIT Triggered: (.*?) \| (?:Qty: (\d+) \| Avg: ([\d.-]+) \| Sell: ([\d.-]+) \| )?Gross: ([\d.-]+)% \| Net: ([\d.-]+)%(?: \| Net Profit: ([\d,.-]+))?")
    pyramid_pat = re.compile(r"Pyramiding (B\d): (.*) \| New Avg: ([\d.]+)")
    status_pat = re.compile(r"Price: ([\d.]+) \| .* \| Profit: ([\d.-]+)% \(Net: ([\d.-]+)%\) \| PNL: ([\d,.-]+)")
    asset_pat = re.compile(r"총자산: ([\d,]+)")

    for log_file in log_files:
        path = os.path.join(log_dir, log_file)
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                # Track Asset Value
                m_asset = asset_pat.search(line)
                if m_asset:
                    val = int(m_asset.group(1).replace(',', ''))
                    if first_asset_val is None: first_asset_val = val
                    last_asset_val = val

                # Find Entry (Normal or Load)
                m_entry = entry_pat.search(line)
                m_load = load_state_pat.search(line)
                
                if (m_entry or m_load) and not active_trade:
                    reason = m_entry.group(1) if m_entry else "Manual/Loaded"
                    active_trade = {
                        'date': line.split(' ')[0],
                        'entry_time': line.split(' ')[1],
                        'entry_reason': reason,
                        'steps': 1,
                        'pyramid_reasons': [],
                        'qty': int(m_load.group(1)) if m_load else 0,
                        'entry_price': float(m_load.group(2)) if m_load else 0,
                        'net_profit_amt': 0,
                        'status': 'OPEN'
                    }
                
                # Find Pyramiding
                m_pyr = pyramid_pat.search(line)
                if m_pyr and active_trade:
                    active_trade['steps'] += 1
                    active_trade['pyramid_reasons'].append(m_pyr.group(2))
                
                # Update Active Trade PNL from status logs
                m_status = status_pat.search(line)
                if m_status and active_trade and active_trade['status'] == 'OPEN':
                    active_trade['current_price'] = float(m_status.group(1))
                    active_trade['gross_profit'] = float(m_status.group(2))
                    active_trade['net_profit'] = float(m_status.group(3))
                    active_trade['net_profit_amt'] = float(m_status.group(4).replace(',', ''))

                # Find Exit
                m_exit = exit_pat.search(line)
                if m_exit and active_trade:
                    active_trade['exit_time'] = line.split(' ')[1]
                    active_trade['exit_reason'] = m_exit.group(1)
                    active_trade['status'] = 'CLOSED'
                    
                    qty = m_exit.group(2)
                    if qty: active_trade['qty'] = int(qty)
                    gross_pct = m_exit.group(5)
                    if gross_pct: active_trade['gross_profit'] = float(gross_pct)
                    net_pct = m_exit.group(6)
                    if net_pct: active_trade['net_profit'] = float(net_pct)
                    net_amt = m_exit.group(7)
                    if net_amt: active_trade['net_profit_amt'] = float(net_amt.replace(',', ''))
                    
                    all_trades.append(active_trade)
                    active_trade = None

    if active_trade:
        all_trades.append(active_trade)

    if not all_trades:
        print("No trading activity found in logs.")
        return

    df = pd.DataFrame(all_trades)
    closed_df = df[df['status'] == 'CLOSED']
    open_df = df[df['status'] == 'OPEN']
    
    print("\n--- 💰 Financial Summary ---")
    if first_asset_val and last_asset_val:
        diff = last_asset_val - first_asset_val
        print(f"Start Asset: {first_asset_val:,.0f}")
        print(f"End Asset:   {last_asset_val:,.0f}")
        print(f"Total Change: {diff:+,.0f} ({diff/first_asset_val:.2%})")
    
    print("\n--- 📈 Trading Performance (Closed) ---")
    if not closed_df.empty:
        print(f"Total Trades: {len(closed_df)}")
        print(f"Win Rate: {(closed_df['net_profit'] > 0).mean():.1%}")
        # Only show mean if count > 0 to avoid error
        print(f"Avg Net Profit: {closed_df['net_profit'].mean():.2f}%")
        print(f"Total Realized: {closed_df['net_profit_amt'].sum():,.0f}")
    else:
        print("No closed trades yet.")

    if not open_df.empty:
        print("\n--- ⏳ Active Positions ---")
        # Ensure columns exist
        for col in ['net_profit', 'net_profit_amt']:
            if col not in open_df.columns: open_df[col] = 0
        print(open_df[['date', 'entry_time', 'entry_reason', 'steps', 'net_profit', 'net_profit_amt']].to_string(index=False))

    print("\n--- 📝 Recent Activity Log ---")
    relevant_cols = ['date', 'entry_time', 'entry_reason', 'steps', 'net_profit', 'net_profit_amt', 'status']
    print(df[relevant_cols].tail(15).to_string(index=False))

if __name__ == "__main__":
    analyze_logs()
