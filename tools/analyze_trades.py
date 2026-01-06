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
    
    # regex patterns
    entry_pat = re.compile(r"ENTRY Triggered: (.*)")
    # New pattern includes Qty, Avg, Sell, Net Profit
    exit_pat = re.compile(r"EXIT Triggered: (.*?) \| (?:Qty: (\d+) \| Avg: ([\d.-]+) \| Sell: ([\d.-]+) \| )?Gross: ([\d.-]+)% \| Net: ([\d.-]+)%(?: \| Net Profit: ([\d,.-]+))?")
    pyramid_pat = re.compile(r"Pyramiding (B\d): (.*) \| New Avg: ([\d.]+)")
    
    for log_file in log_files:
        path = os.path.join(log_dir, log_file)
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            active_trade = None
            
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
                        'net_profit_amt': 0
                    }
                
                # Find Pyramiding
                m_pyr = pyramid_pat.search(line)
                if m_pyr and active_trade:
                    active_trade['steps'] += 1
                    active_trade['pyramid_reasons'].append(m_pyr.group(2))
                
                # Find Exit
                m_exit = exit_pat.search(line)
                if m_exit and active_trade:
                    active_trade['exit_time'] = line.split(' ')[1]
                    active_trade['exit_reason'] = m_exit.group(1)
                    
                    # Capture optional fields
                    qty = m_exit.group(2)
                    avg_p = m_exit.group(3)
                    sell_p = m_exit.group(4)
                    gross_pct = m_exit.group(5)
                    net_pct = m_exit.group(6)
                    net_amt = m_exit.group(7)
                    
                    active_trade['qty'] = int(qty) if qty else 0
                    active_trade['gross_profit'] = float(gross_pct)
                    active_trade['net_profit'] = float(net_pct)
                    active_trade['net_profit_amt'] = float(net_amt.replace(',', '')) if net_amt else 0
                    
                    all_trades.append(active_trade)
                    active_trade = None

    if not all_trades:
        print("No completed trades found in logs.")
        print("Tip: Trade analysis requires an 'EXIT Triggered' line in the log.")
        return

    df = pd.DataFrame(all_trades)
    
    print("\n--- 📈 Overall Statistics ---")
    print(f"Total Trades: {len(df)}")
    print(f"Win Rate: {(df['net_profit'] > 0).mean():.1%}")
    print(f"Avg Net Profit: {df['net_profit'].mean():.2f}%")
    print(f"Total Net Profit Amt: {df['net_profit_amt'].sum():,.0f}")
    print(f"Max Profit Amt: {df['net_profit_amt'].max():,.0f}")
    print(f"Min Profit Amt: {df['net_profit_amt'].min():,.0f}")

    print("\n--- 🏁 Performance by Entry Reason ---")
    reason_stats = df.groupby('entry_reason')['net_profit_amt'].agg(['count', 'sum', 'mean']).sort_values(by='mean', ascending=False)
    print(reason_stats)

    print("\n--- 🪜 Pyramiding Stats ---")
    print(df['steps'].value_counts().sort_index().rename(lambda x: f"Step {x} Target").to_string())

    print("\n--- 📝 Recent Trades ---")
    cols = ['date', 'entry_reason', 'steps', 'net_profit', 'net_profit_amt', 'exit_reason']
    print(df[cols].tail(10).to_string(index=False))

if __name__ == "__main__":
    analyze_logs()
