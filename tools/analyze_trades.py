import os
import re
from datetime import datetime
import pandas as pd

def analyze_logs(log_dir='logs'):
    print(f"📊 Analyzing trading logs in '{log_dir}'...")
    
    if not os.path.exists(log_dir):
        print("Error: logs directory not found.")
        return

    log_files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
    if not log_files:
        print("No log files found.")
        return

    all_trades = []
    active_trade = None
    
    # regex patterns
    entry_pat = re.compile(r"ENTRY Triggered: (.*)")
    exit_pat = re.compile(r"EXIT Triggered: (.*?) \| (?:Qty: (\d+) \| Avg: ([\d.-]+) \| Sell: ([\d.-]+) \| )?Gross: ([\d.-]+)% \| Net: ([\d.-]+)%(?: \| Net Profit: ([\d,.-]+))?")
    pyramid_pat = re.compile(r"Pyramiding (B\d): (.*) \| New Avg: ([\d.]+)")
    # Real-time status to catch current HOLDING state
    status_pat = re.compile(r"Price: ([\d.]+) \| .* \| Profit: ([\d.-]+)% \(Net: ([\d.-]+)%\) \| PNL: ([\d,.-]+)")
    
    for log_file in log_files:
        path = os.path.join(log_dir, log_file)
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            for line in lines:
                # Find Entry
                m_entry = entry_pat.search(line)
                if m_entry:
                    active_trade = {
                        'date': line.split(' ')[0],
                        'entry_time': line.split(' ')[1],
                        'entry_reason': m_entry.group(1),
                        'steps': 1,
                        'pyramid_reasons': [],
                        'qty': 0,
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

    # Add currently active trade if exists
    if active_trade:
        all_trades.append(active_trade)

    if not all_trades:
        print("No trading activity found in logs.")
        return

    df = pd.DataFrame(all_trades)
    closed_df = df[df['status'] == 'CLOSED']
    open_df = df[df['status'] == 'OPEN']
    
    print("\n--- 📈 Overall Statistics (Closed Trades) ---")
    if not closed_df.empty:
        print(f"Total Trades: {len(closed_df)}")
        print(f"Win Rate: {(closed_df['net_profit'] > 0).mean():.1%}")
        print(f"Avg Net Profit: {closed_df['net_profit'].mean():.2f}%")
        print(f"Total Realized Profit: {closed_df['net_profit_amt'].sum():,.0f}")
    else:
        print("No closed trades yet.")

    if not open_df.empty:
        print("\n--- ⏳ Currently Active Trades ---")
        print(open_df[['date', 'entry_reason', 'steps', 'net_profit', 'net_profit_amt']].to_string(index=False))

    if not closed_df.empty:
        print("\n--- 🏁 Performance by Entry Reason (Closed) ---")
        reason_stats = closed_df.groupby('entry_reason')['net_profit_amt'].agg(['count', 'sum', 'mean']).sort_values(by='mean', ascending=False)
        print(reason_stats)

    print("\n--- 📝 All Recent Activity ---")
    cols = ['date', 'entry_reason', 'steps', 'net_profit', 'net_profit_amt', 'status']
    print(df[cols].tail(10).to_string(index=False))

if __name__ == "__main__":
    analyze_logs()
