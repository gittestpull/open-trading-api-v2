import os
import re
from datetime import datetime
import pandas as pd

# Use basic ANSI colors if supported, else empty strings
class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def analyze_logs(log_dir='logs'):
    print(f"\n{Color.BOLD}📊 Scalping Trade Analyzer v2.0{Color.END}")
    print(f"Reading logs from: {os.path.abspath(log_dir)}")
    
    if not os.path.exists(log_dir):
        print(f"Error: {log_dir} directory not found.")
        return

    log_files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')])
    if not log_files:
        print("No log files found.")
        return

    all_trades = []
    active_trade = None
    last_asset_val = 0
    first_asset_val = None
    last_update_time = ""
    
    # regex patterns
    entry_pat = re.compile(r"ENTRY Triggered: (.*)")
    load_state_pat = re.compile(r"Loaded existing state for (\w+): HOLDING \| (\d+) shares @ ([\d.]+)")
    exit_pat = re.compile(r"EXIT Triggered: (.*?) \| (?:Qty: (\d+) \| Avg: ([\d.-]+) \| Sell: ([\d.-]+) \| )?Gross: ([\d.-]+)% \| Net: ([\d.-]+)%(?: \| Net Profit: ([\d,.-]+))?")
    pyramid_pat = re.compile(r"Pyramiding (B\d): (.*) \| New Avg: ([\d.]+)")
    status_pat = re.compile(r"Price: ([\d.]+) \| .* \| Profit: ([\d.-]+)% \(Net: ([\d.-]+)%\) \| PNL: ([\d,.-]+)")
    asset_pat = re.compile(r"총자산: ([\d,]+)")
    ticker_pat = re.compile(r"Ticker: (\w+)")

    for log_file in log_files:
        path = os.path.join(log_dir, log_file)
        current_ticker = "Unknown"
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                # Update last known time
                try: last_update_time = line.split(' ')[1].split(',')[0]
                except: pass

                # Ticker Detection
                m_tick = ticker_pat.search(line)
                if m_tick: current_ticker = m_tick.group(1)

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
                    ticker = current_ticker if not m_load else m_load.group(1)
                    active_trade = {
                        'date': line.split(' ')[0],
                        'entry_time': line.split(' ')[1].split(',')[0],
                        'ticker': ticker,
                        'entry_reason': reason,
                        'steps': 1,
                        'net_profit': 0.0,
                        'net_profit_amt': 0.0,
                        'status': 'OPEN'
                    }
                
                # Find Pyramiding
                m_pyr = pyramid_pat.search(line)
                if m_pyr and active_trade:
                    active_trade['steps'] += 1
                
                # Update Active Trade PNL from status logs
                m_status = status_pat.search(line)
                if m_status and active_trade and active_trade['status'] == 'OPEN':
                    active_trade['net_profit'] = float(m_status.group(3))
                    active_trade['net_profit_amt'] = float(m_status.group(4).replace(',', ''))

                # Find Exit
                m_exit = exit_pat.search(line)
                if m_exit and active_trade:
                    active_trade['exit_time'] = line.split(' ')[1].split(',')[0]
                    active_trade['exit_reason'] = m_exit.group(1)
                    active_trade['status'] = 'CLOSED'
                    
                    net_pct = m_exit.group(6)
                    if net_pct: active_trade['net_profit'] = float(net_pct)
                    net_amt = m_exit.group(7)
                    if net_amt: active_trade['net_profit_amt'] = float(net_amt.replace(',', ''))
                    
                    all_trades.append(active_trade)
                    active_trade = None

    if active_trade:
        all_trades.append(active_trade)

    if not all_trades and not first_asset_val:
        print(f"\n{Color.RED}No trading activity found yet.{Color.END}")
        print("Tip: Run the scalper for a few minutes to generate enough log data.")
        return

    df = pd.DataFrame(all_trades) if all_trades else pd.DataFrame()
    
    print(f"\n{Color.BLUE}--- 💰 Financial Summary ---{Color.END}")
    if first_asset_val and last_asset_val:
        diff = last_asset_val - first_asset_val
        c = Color.GREEN if diff >= 0 else Color.RED
        print(f"Start Asset: {first_asset_val:,.0f}")
        print(f"End Asset:   {last_asset_val:,.0f} (at {last_update_time})")
        print(f"Day's PNL:   {c}{diff:+,.0f} ({diff/first_asset_val:+.2%}){Color.END}")
    else:
        print("Asset data insufficient.")

    if not df.empty:
        closed_df = df[df['status'] == 'CLOSED']
        open_df = df[df['status'] == 'OPEN']

        if not open_df.empty:
            print(f"\n{Color.BLUE}--- ⏳ Active Positions (Real-time PNL) ---{Color.END}")
            for _, row in open_df.iterrows():
                c = Color.GREEN if row['net_profit'] >= 0 else Color.RED
                print(f"{row['ticker']} | {row['entry_reason']} | Step {row['steps']} | {c}{row['net_profit']:+.2%}% ({row['net_profit_amt']:+,.0f}){Color.END}")

        print(f"\n--- 📝 Recent Activity Log ---")
        display_df = df.tail(10).copy()
        # Formatting for display
        def style_pnl(val):
            return f"{Color.GREEN}{val:+,.0f}{Color.END}" if val > 0 else f"{Color.RED}{val:+,.0f}{Color.END}" if val < 0 else f"{val:,.0f}"

        print(f"{'Time':<10} | {'Ticker':<8} | {'Step':<4} | {'Net %':<8} | {'Net Amt':<10} | {'Status'}")
        print("-" * 65)
        for _, row in display_df.iterrows():
            c_pct = Color.GREEN if row['net_profit'] > 0 else Color.RED if row['net_profit'] < 0 else ""
            status_c = Color.BOLD if row['status'] == 'OPEN' else ""
            print(f"{row['entry_time']:<10} | {row['ticker']:<8} | {row['steps']:<4} | {c_pct}{row['net_profit']:>7.2%}{Color.END} | {style_pnl(row['net_profit_amt']):>20} | {status_c}{row['status']:<6}{Color.END}")
    
    print(f"\n{Color.BOLD}Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Color.END}")

if __name__ == "__main__":
    analyze_logs()
