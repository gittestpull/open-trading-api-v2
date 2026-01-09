import sys
import os
import time
import logging
from datetime import datetime

# 1. Absolute First: Setup Logging before ANY other imports
import subprocess
LOG_DIR = os.path.join(os.getcwd(), 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

log_basename = f"trading_{datetime.now().strftime('%Y%m%d')}"
# Try to find ticker and bot_id in args for log filename
if "--ticker" in sys.argv:
    try:
        idx = sys.argv.index("--ticker")
        if idx + 1 < len(sys.argv):
            safe_ticker = sys.argv[idx + 1].replace('/', '_') # Sanitize
            log_basename = f"trading_{safe_ticker}_{datetime.now().strftime('%Y%m%d')}"
            
            # Sub-check for bot_id to make it even more specific
            if "--bot_id" in sys.argv:
                b_idx = sys.argv.index("--bot_id")
                if b_idx + 1 < len(sys.argv):
                    bot_id = sys.argv[b_idx + 1]
                    log_basename = f"trading_{safe_ticker}_{bot_id}_{datetime.now().strftime('%Y%m%d')}"
    except:
        pass

log_filename = os.path.join(LOG_DIR, f"{log_basename}.log")

# Setup Handlers
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Terminal: INFO+

# Compressed Rotating File Handler (keeps old logs as .gz)
from logging.handlers import TimedRotatingFileHandler
import gzip
import shutil

class CompressedRotatingHandler(TimedRotatingFileHandler):
    """Rotating handler that compresses old logs with gzip instead of deleting."""
    def __init__(self, filename, **kwargs):
        super().__init__(filename, when='midnight', backupCount=30, encoding='utf-8', **kwargs)
    
    def emit(self, record):
        super().emit(record)
        self.flush()  # Unbuffered for real-time log streaming
    
    def rotator(self, source, dest):
        """Compress rotated log file with gzip."""
        with open(source, 'rb') as f_in:
            with gzip.open(f'{dest}.gz', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(source)
    
    def namer(self, default_name):
        """Remove .gz from rotation target (added by rotator)."""
        return default_name  # Let rotator add .gz

file_handler = CompressedRotatingHandler(log_filename)
file_handler.setLevel(logging.DEBUG)  # File: ALL (DEBUG+)

# Configure Root Logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        file_handler,  # Compressed rotating handler
        logging.StreamHandler()  # Console handler
    ],
    force=True  # Clear any existing configuration from early imports
)
logger = logging.getLogger(__name__)

# 2. Other Imports
import pandas as pd
import numpy as np
import argparse
import json
import threading
import asyncio
import signal

class Watchdog(threading.Thread):
    """
    Monitors the main loop. If 'ping' isn't called within 'timeout' seconds,
    it assumes the bot is hung and kills the process to allow Docker/System to restart it.
    """
    def __init__(self, timeout=60, name="Watchdog"):
        super().__init__(daemon=True, name=name)
        self.timeout = timeout
        self.last_ping = time.time()
        self.running = True
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.logger.info(f"🐶 Watchdog started (Timeout: {self.timeout}s)")
        while self.running:
            time.sleep(5)
            elapsed = time.time() - self.last_ping
            if elapsed > self.timeout:
                self.logger.error(f"💀 WATCHDOG BITE: Main loop hung for {elapsed:.1f}s! Killing process...")
                # Send telegram alert before dying
                self._send_telegram_alert()
                # Flush logs before dying
                for handler in self.logger.handlers:
                    handler.flush()
                # Kill self (Force Kill to ensure we don't get stuck in shutdown hook)
                os.kill(os.getpid(), signal.SIGKILL)

    def ping(self):
        self.last_ping = time.time()

    def stop(self):
        self.running = False
    
    def _send_telegram_alert(self):
        """Send telegram alert before dying (best effort)."""
        try:
            import telegram_notifier
            # Try to get ticker from global scalper instance
            ticker = getattr(self, '_ticker', 'Unknown')
            telegram_notifier.send_watchdog_alert(ticker)
        except:
            pass  # Best effort, don't let this prevent process kill

# Add examples_user and subdirectories to path first
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))
sys.path.append(os.path.join(os.getcwd(), 'examples_user', 'domestic_stock'))
sys.path.append(os.path.join(os.getcwd(), 'examples_user', 'overseas_stock'))

import kis_auth
from stock_code_lookup import StockMaster
import trade_history
import domestic_stock_functions as d_func

def notify_user(msg, ticker=None):
    """Utility to provide audio and desktop notifications (Secure)."""
    try:
        title = f"Trading Bot ({ticker})" if ticker else "Trading Bot"
        # Sanitize to prevent AppleScript injection
        title = title.replace('"', '').replace("'", "")
        msg = msg.replace('"', '').replace("'", "")
        
        # Use subprocess to avoid shell injection
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "{title}"'], check=False)
        subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
    except Exception as e:
        logger.debug(f"Notification failed: {e}")

def check_log_health(filename, limit_minutes=5, max_errors=3):
    """Analyze recent log entries for CRITICAL failures and block startup if necessary."""
    if not os.path.exists(filename):
        return True
    
    recent_critical_errors = 0
    now = datetime.now()
    
    # Critical keywords that directly affect trading (only these will block startup)
    CRITICAL_KEYWORDS = ["Order Failed", "Insufficient balance", "Auth Failed", "Connection timeout", "Insufficient cash"]
    # Keywords to absolutely ignore (notification, websocket, etc.)
    IGNORE_KEYWORDS = ["execution notice", "WS Monitor", "WebSocket", "HEALTH CHECK"]

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in reversed(lines[-100:]): # Check last 100 lines
                if "[ERROR]" in line:
                    # 1. Ignore soft errors first
                    if any(ig.lower() in line.lower() for ig in IGNORE_KEYWORDS):
                        continue
                    
                    # 2. Check time
                    try:
                        log_time_str = line.split(',')[0]
                        log_time = datetime.strptime(log_time_str, '%Y-%m-%d %H:%M:%S')
                        if (now - log_time).total_seconds() / 60 > limit_minutes:
                            continue # Too old
                            
                        # 3. Block only if it's a critical keyword OR a generic error (not ignored)
                        # User: "매수를 잘못 할수 있는 에러만 체크해야지"
                        if any(kw.lower() in line.lower() for kw in CRITICAL_KEYWORDS):
                            recent_critical_errors += 1
                        else:
                            # If we have too many generic [ERROR]s in a short time, maybe something is wrong, 
                            # but let's be lenient as per user request.
                            pass
                    except:
                        continue
        
        if recent_critical_errors >= max_errors:
            logger.error(f"⚠️ LOG HEALTH CHECK FAILED: {recent_critical_errors} CRITICAL trading errors found in last {limit_minutes} min.")
            logger.error(f"Critical triggers: {CRITICAL_KEYWORDS}")
            return False
    except Exception as e:
        logger.warning(f"Log health check skipped: {e}")
    
    return True

# Strategy Parameters
RSI_PERIOD = 9
RSI_BUY_LEVEL = 30
BB_PERIOD = 20
BB_STD = 2
TARGET_PROFIT = 0.005  # 0.5%
PYRAMIDING_THRESHOLD = 0.01  # 1.0% drop for next buy
MAX_STEPS = 4
WEIGHTS = [1, 2, 4, 8]

class UniversalScalper:
    def __init__(self, ticker, budget, target_profit=0.005, live_mode=False, manual_buy_price=0, use_orderbook=False, use_momentum=False, args=None):
        self.args = args # Store args for flag checking
        # 0. Initial guess
        self.is_domestic = ticker.isdigit() and len(ticker) == 6
        
        # 1. If not digit, try name lookup for Domestic code
        if not self.is_domestic:
            sm = StockMaster()
            found_code = sm.get_code(ticker)
            if found_code:
                logger.info(f"Resolved Name '{ticker}' to Code '{found_code}'")
                ticker = found_code
                self.is_domestic = True

        self.ticker = ticker.upper()
        self.budget = budget
        self.target_profit = target_profit
        self.live_mode = live_mode
        self.manual_buy_price = manual_buy_price
        self.market = "Domestic" if self.is_domestic else "Overseas"
        self.current_exchange = "KRX"  # Will be updated dynamically for NXT sessions
        self.use_orderbook = use_orderbook  # Orderbook filter option
        self.use_momentum = use_momentum  # Momentum (breakout) mode
        
        # Taxes and Fees (Friction)
        if self.is_domestic:
            # Tuned Fee to match MTS BEP (8176/8160 ~= 0.20% gap)
            self.buy_fee = 0.00015  # 0.015%
            self.sell_fee = 0.00015 # 0.015%
            self.sell_tax = 0.0017  # 0.17% (Adjusted to match 0.20% total)
        else:
            self.buy_fee = 0.0004   # 0.04% (Standard Overseas)
            self.sell_fee = 0.0004  # 0.04%
            self.sell_tax = 0.0     # Tax handled separately or minimal SEC fee
        
        self.friction = self.buy_fee + self.sell_fee + self.sell_tax
        
        # State management
        self.state = "SEARCHING"
        self.avg_buy_price = 0
        self.total_qty = 0
        self.current_step = 0
        self.buy_history = []  # List of (price, qty)
        self.last_price = 0    # Track latest price for real-time dashboard
        self.daily_realized_profit = 0  # Accumulated net profit for this session
        
        # API Auth
        kis_auth.auth()
        self.trenv = kis_auth.getTREnv()
        
        # State Directory
        self.state_dir = "scalp_data"
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)
        self.state_file = os.path.join(self.state_dir, f"state_{self.ticker}.json")
        
        # Cached balance (only updated after trade execution)
        self.cached_balance = (0, 0, 0, 0)  # (cash, asset, real_avg, real_qty)
        
        # Initial Load
        self.load_state()
        
        # Initial balance fetch (once at startup)
        self.cached_balance = self.get_balance()
        
        # Supply info caching (Foreign/Institutional trends)
        self.last_supply_check = 0
        self.cached_supply = "Fetching..."
        self.supply_check_interval = 600  # 10 minutes
        if self.is_domestic:
            self.cached_supply = self.get_supply_info()
        
        # Runtime Safety
        self.consecutive_errors = 0
        self.max_allowed_errors = 3
        self.last_supply_check = time.time()
        
        # Prices
        self.prev_close = 0
        self.prev_high = 0
        
        # Websocket Monitor (Execution Notification)
        self.ws_active = False
        if self.live_mode:
            self.ws_thread = threading.Thread(target=self.start_ws_monitor, daemon=True)
            self.ws_thread.start()
            self.ws_active = True
        self.daily_high = 0
        self.krx_close_today = 0  # Today's KRX closing price for NXT reference
        self.nxt_consecutive_errors = 0 # Track NXT availability
        self.last_price_info_check = 0
        self.last_price_info_check = 0
        self.price_info_interval = 300 # 5 mins
        
        # Market Data (Investor, Credit, Short)
        self.investor_info_str = "Inv: -" 
        self.credit_trend_str = "CrdRate: - Short: -"
        self.last_market_data_check = 0
        self.market_data_interval = 600 # 10 mins (Data updates slowly)
        
        # Holiday and Session cache
        self.cached_holiday_status = None # None: not checked, True: holiday, False: business day
        self.last_holiday_check_date = ""
        
        # Unfilled orders cache
        self.unfilled_buy_qty = 0
        self.unfilled_sell_qty = 0
        self.last_unfilled_check = 0
        self.unfilled_check_interval = 30 # Check every 30 seconds
        
        if self.is_domestic:
            self.update_price_info()
            
        # Credit related states
        self.credit_cash = 0
        self.credit_type_code = "21" # Default to Self-financing
        self.credit_holdings = [] # List of dict: {"qty": int, "loan_dt": str}
        self.cash_balance = 0
        
        self.last_buy_time = 0  # To prevent rapid pyramiding
        
    def get_minute_chart(self):
        """Unified minute chart fetcher."""
        if self.is_domestic:
            # Determine Market Code based on current exchange session
            # J: KRX (Regular), NX: NXT (Nextrade)
            mrkt_code = "NX" if getattr(self, 'current_exchange', 'KRX') == "NXT" else "J"
            
            url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            tr_id = "FHKST03010200"
            params = {
                "FID_COND_MRKT_DIV_CODE": mrkt_code,
                "FID_INPUT_ISCD": self.ticker,
                "FID_INPUT_HOUR_1": datetime.now().strftime("%H%M%S"),
                "FID_PW_DATA_INCU_YN": "Y",
                "FID_ETC_CLS_CODE": ""
            }
        else:
            url = "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
            tr_id = "HHDFS76950200"
            params = {
                "AUTH": "",
                "EXCD": "NAS", # Standardizing to NASDAQ for now, could be dynamic
                "SYMB": self.ticker,
                "NMIN": "1",
                "PINC": "0",
                "NEXT": "",
                "NREC": "40",
                "FILL": "",
                "KEYB": ""
            }

        res = kis_auth._url_fetch(url, tr_id, "", params)
        if res.isOK():
            output2 = res.getBody().output2
            df = pd.DataFrame(output2)
            
            # Map column names based on market
            if self.is_domestic:
                cols_map = {'stck_prpr': 'last', 'stck_oprc': 'open', 'stck_hgpr': 'high', 'stck_lwpr': 'low', 'cntg_vol': 'vol'}
            else:
                cols_map = {'last': 'last', 'open': 'open', 'high': 'high', 'low': 'low', 'evol': 'vol'}
            
            df = df.rename(columns=cols_map)
            # Convert to numeric
            cols = ['last', 'open', 'high', 'low', 'vol']
            for col in cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Pad data if history is too short for RSI
            min_len = 20
            # Raw 'df' is currently Newest -> Oldest (from API output)
            # We need to ensure we have enough history.
            if len(df) < min_len and not df.empty:
                needed = min_len - len(df)
                # Oldest data is at the end of the raw list/df
                oldest_row = df.iloc[-1].to_dict()
                # Create padding of oldest data
                padding = pd.DataFrame([oldest_row] * needed)
                # Attach padding to the END (which represents older history in current order)
                df = pd.concat([df, padding], ignore_index=True)

            return df.iloc[::-1].reset_index(drop=True)
        else:
            logger.error(f"Failed to fetch chart: {res.getErrorMessage()}")
            return pd.DataFrame()
    
    def update_price_info(self):
        """Fetch and cache prev close and daily high from inquire-price API."""
        if not self.is_domestic:
            return
        try:
            url = "/uapi/domestic-stock/v1/quotations/inquire-price"
            tr_id = "FHKST01010100"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": self.ticker
            }
            res = kis_auth._url_fetch(url, tr_id, "", params)
            if res.isOK():
                out = res.getBody().output
                self.prev_close = float(out.get('stck_sdpr', 0))  # 전일 종가 (기준가)
                self.prev_high = float(out.get('stck_mxpr', 0))   # 전일 고가 (stck_mxpr = 전일최고가)
                self.daily_high = float(out.get('stck_hgpr', 0))  # 당일 최고가
                
                # Credit Loan Rate (Market) & Short Sale Volume
                loan_rate = float(out.get('whol_loan_rmnd_rate', 0))
                short_vol = int(out.get('last_ssts_cntg_qty', 0))
                self.credit_trend_str = f"CrdRate:{loan_rate:.2f}% Short:{short_vol:,}"
                
                self.last_price_info_check = time.time()
                logger.debug(f"Price Info Updated: prev_c={self.prev_close}, loan_rate={loan_rate}%, short={short_vol}")
        except Exception as e:
            logger.error(f"Failed to update price info: {e}")

    def update_market_data(self):
        """Fetch investor trend estimates (Real-time estimate)."""
        if not self.is_domestic: return

        try:
            # 1. Investor Trend Estimate (HHPTJ04160200) - Real-time estimate
            # Fields: frgn_fake_ntby_qty (Foreigner), orgn_fake_ntby_qty (Institution)
            # Personal data is not explicitly provided in this estimate API
            est_df = d_func.investor_trend_estimate(self.ticker)
            if not est_df.empty:
                row = est_df.iloc[0]
                
                def safe_int(val):
                    try: return int(val) if val else 0
                    except: return 0

                frgn = safe_int(row.get('frgn_fake_ntby_qty', 0))
                orgn = safe_int(row.get('orgn_fake_ntby_qty', 0))
                
                def fmt_k(n):
                    if abs(n) >= 1000: return f"{n/1000:.1f}k"
                    return str(n)
                
                # Note: 'Personal' is not in this API, so we show what we have
                self.investor_info_str = f"Est: 외인{fmt_k(frgn)} 기관{fmt_k(orgn)}"
            
            # 2. Short Sale: Daily short sale info is End-of-Day. 
            # Real-time short sale volume is not easily available via simple API.
            # We rely on 'inquire_price' -> 'whol_loan_rmnd_rate' for Credit market info instead.
                 
        except Exception as e:
            logger.error(f"Failed to update market data: {e}")
            
    def update_unfilled_orders(self):
        """Fetches unfilled buy/sell quantities from KIS."""
        if not self.live_mode:
            return
            
        now = time.time()
        if now - self.last_unfilled_check < self.unfilled_check_interval:
            return
            
        try:
            if self.is_domestic:
                # inqr_dvsn_1: 0(주문), 1(종목) | inqr_dvsn_2: 0(전체), 1(매도), 2(매수)
                df = d_func.inquire_psbl_rvsecncl(
                    cano=self.trenv.my_acct, 
                    acnt_prdt_cd=self.trenv.my_prod, 
                    inqr_dvsn_1="1", # By Stock
                    inqr_dvsn_2="0"  # All
                )
                if df is not None and not df.empty:
                    # Filter for current ticker and aggregate by buy/sell
                    # pdno: 종목코드, sll_buy_dvsn_cd: 01(매도), 02(매수), psbl_qty: 잔량
                    target_df = df[df['pdno'] == self.ticker]
                    self.unfilled_buy_qty = int(target_df[target_df['sll_buy_dvsn_cd'] == '02']['psbl_qty'].astype(float).sum())
                    self.unfilled_sell_qty = int(target_df[target_df['sll_buy_dvsn_cd'] == '01']['psbl_qty'].astype(float).sum())
                else:
                    self.unfilled_buy_qty = 0
                    self.unfilled_sell_qty = 0
            else:
                # Overseas
                import overseas_stock_functions as o_func
                # ovrs_excg_cd: NASD, NYSE, etc.
                df = o_func.inquire_nccs(
                    cano=self.trenv.my_acct,
                    acnt_prdt_cd=self.trenv.my_prod,
                    ovrs_excg_cd="NASD", # Defaulting to NASD for now
                    sort_sqn="DS",
                    FK200="", NK200=""
                )
                if df is not None and not df.empty:
                    # pdno: 종목코드, sll_buy_dvsn_cd: 01(매도), 02(매수), nccn_qty: 미체결수량
                    target_df = df[df['pdno'] == self.ticker]
                    self.unfilled_buy_qty = int(target_df[target_df['sll_buy_dvsn_cd'] == '02']['nccn_qty'].astype(float).sum())
                    self.unfilled_sell_qty = int(target_df[target_df['sll_buy_dvsn_cd'] == '01']['nccn_qty'].astype(float).sum())
                else:
                    self.unfilled_buy_qty = 0
                    self.unfilled_sell_qty = 0
                    
            self.last_unfilled_check = now
            logger.debug(f"Unfilled updated for {self.ticker}: Buy={self.unfilled_buy_qty}, Sell={self.unfilled_sell_qty}")
        except Exception as e:
            logger.warning(f"Failed to update unfilled orders: {e}")

    def sync_portfolio(self):
        """Fetch orderbook data (bid/ask totals)."""
        if not self.is_domestic:
            return 0, 0, ""
        try:
            url = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
            tr_id = "FHKST01010200"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": self.ticker
            }
            res = kis_auth._url_fetch(url, tr_id, "", params)
            if res.isOK():
                out = res.getBody().output1
                bid_total = int(out.get('total_bidp_rsqn', 0))  # 총매수잔량
                ask_total = int(out.get('total_askp_rsqn', 0))  # 총매도잔량
                ratio = bid_total / ask_total if ask_total > 0 else 0
                info_str = f"B{bid_total:,}:A{ask_total:,}({ratio:.1f})"
                return bid_total, ask_total, info_str
        except Exception as e:
            logger.error(f"Failed to fetch orderbook: {e}")
        return 0, 0, ""

    def save_state(self):
        """Save current trading state to JSON."""
        # Convert numpy types to native Python types for JSON serialization
        buy_history_native = [(float(p), int(q)) for p, q in self.buy_history]
        state_data = {
            "state": self.state,
            "avg_buy_price": float(self.avg_buy_price),
            "total_qty": int(self.total_qty),
            "current_step": int(self.current_step),
            "buy_history": buy_history_native,
            "pending_sell": getattr(self, 'pending_sell', None),
            "current_price": getattr(self, 'last_price', 0),
            "current_price": getattr(self, 'last_price', 0),
            "current_exchange": getattr(self, 'current_exchange', 'KRX'),
            "last_update": datetime.now().isoformat()
        }
        
        def default_serializer(obj):
            if isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            if isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            raise TypeError(f"Type {type(obj)} not serializable")

        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=4, default=default_serializer)
        # logger.debug(f"State saved to {self.state_file}")

    def load_state(self):
        """Load trading state from JSON if exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    self.state = state_data.get("state", "SEARCHING")
                    self.avg_buy_price = state_data.get("avg_buy_price", 0)
                    self.total_qty = state_data.get("total_qty", 0)
                    self.current_step = state_data.get("current_step", 0)
                    self.buy_history = state_data.get("buy_history", [])
                    self.pending_sell = state_data.get("pending_sell", None)
                logger.info(f"Loaded existing state for {self.ticker}: {self.state} | {self.total_qty} shares")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")

    def start_ws_monitor(self):
        """Runs the KIS WebSocket monitor in a separate event loop."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.ws_loop())
        except Exception as e:
            logger.error(f"WS Monitor Thread Error: {e}")

    async def ws_loop(self):
        """Connects to KIS WebSocket and listens for execution notifications."""
        try:
            # Need to get approval key for WS
            kis_auth.auth_ws()
            
            from kis_auth import KISWebSocket
            ws_client = KISWebSocket(api_url="/") 
            
            # Subscribe to Execution Notice
            if self.is_domestic:
                import domestic_stock_functions_ws as d_ws
                ccnl_func = d_ws.ccnl_notice
            else:
                import overseas_stock_functions_ws as o_ws
                ccnl_func = o_ws.ccnl_notice
            
            tr_key = self.trenv.my_htsid
            
            def on_ws_result(ws, res_tr_id, df, dm):
                if res_tr_id in ["H0STCNI0", "H0STCNI9", "H0GSCNI0", "H0GSCNI9"]:
                    self.handle_execution_notice(df)
            logger.info(f"WebSocket Execution Monitor Active (Key: {tr_key})")
            await ws_client._KISWebSocket__runner() 
            
        except Exception as e:
            logger.error(f"WebSocket Loop Exception: {e}")

    def handle_execution_notice(self, df):
        """Processes execution notification data from WebSocket."""
        try:
            if df.empty: return
            
            row = df.iloc[0]
            # Ensure ticker is string and clean up (handle potential float conversion from pandas)
            val = row.get('STCK_SHRN_ISCD', '')
            ticker = str(val).split('.')[0].replace('A', '').strip()
            
            # Pad with zeros ONLY for domestic tickers (short numbers)
            if self.is_domestic and ticker.isdigit() and len(ticker) < 6:
                ticker = ticker.zfill(6)
            
            cntg_yn = str(row.get('CNTG_YN', '')).split('.')[0]
            
            if ticker != self.ticker: return
            
            if cntg_yn == '2': # Execution Filled
                qty = int(row.get('CNTG_QTY', 0))
                price = float(row.get('CNTG_UNPR', 0))
                
                notify_user(f"{ticker} {qty}주 체결 완료!", ticker)
                logger.info(f"🔔 EXECUTION FILLED: {ticker} {qty} at {price}")
                
                if self.state == "PENDING_SELL":
                    self.finalize_sell(price, qty)
                else:
                    # Log as BUY if not pending sell (best guess for buy confirm)
                    trade_history.log_trade(
                        ticker=self.ticker,
                        action="BUY",
                        qty=qty,
                        price=price,
                        bot_id=getattr(self, 'bot_id', None),
                        ticker_code=getattr(self, 'ticker_code', None),
                        reason="Standard Buy"
                    )
        except Exception as e:
            logger.error(f"Error handling execution notice: {e}")

    def finalize_sell(self, sell_price, sell_qty):
        """Called when a sell fill is confirmed."""
        try:
            # Re-calculate exact profit based on fill price
            net_investment = self.avg_buy_price * sell_qty * (1 + self.buy_fee)
            net_return = sell_price * sell_qty * (1 - self.sell_fee - self.sell_tax)
            net_profit_amt = net_return - net_investment
            net_profit_rate = (net_return / net_investment) - 1
            
            self.daily_realized_profit += net_profit_amt
            
            # Summary update
            summary_path = "trade_summary.txt"
            with open(summary_path, "a", encoding="utf-8") as f:
                dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{dt_str}] {self.ticker} | FILLED | Net: {net_profit_rate:+.2%} | Profit: {net_profit_amt:+,.0f} | Qty: {sell_qty}\n")
            
            logger.info(f"💰 SELL CONFIRMED: {self.ticker} | Realized Net Profit: {net_profit_amt:,.0f}")
            
            # Log to DB
            trade_history.log_trade(
                ticker=self.ticker,
                action="SELL",
                qty=sell_qty,
                price=sell_price,
                bot_id=getattr(self, 'bot_id', None),
                ticker_code=getattr(self, 'ticker_code', None),
                avg_buy_price=self.avg_buy_price,
                profit_rate=net_profit_rate,
                profit_amt=net_profit_amt,
                reason="Standard Sell"
            )
            
            self.clear_state()
            self.cached_balance = self.get_balance() # Sync balance
        except Exception as e:
            logger.error(f"Error finalizing sell: {e}")

    def clear_state(self):
        """Clear state file after exit."""
        if os.path.exists(self.state_file):
            os.remove(self.state_file)
            # logger.debug(f"State file {self.state_file} cleared.")
        self.state = "SEARCHING"
        self.avg_buy_price = 0
        self.total_qty = 0
        self.current_step = 0
        self.buy_history = []

    def is_holiday_today(self):
        """Checks if today is a holiday using KIS API."""
        now_date = datetime.now().strftime("%Y%m%d")
        
        # Use cache if already checked today
        if self.last_holiday_check_date == now_date and self.cached_holiday_status is not None:
            return self.cached_holiday_status
        
        try:
            logger.info(f"Checking holiday status for {now_date}...")
            # Use max_depth=1 to prevent excessive recursion in holiday check
            df = d_func.chk_holiday(bass_dt=now_date, max_depth=1)
            if not df.empty:
                # opnd_yn: 개장일 여부 (Y/N)
                row = df.iloc[0]
                is_holiday = row.get('opnd_yn') == 'N'
                self.cached_holiday_status = is_holiday
                self.last_holiday_check_date = now_date
                
                status_str = "HOLIDAY (CLOSED)" if is_holiday else "BUSINESS DAY (OPEN)"
                logger.info(f"Market Status Check: Today is {status_str}")
                return is_holiday
        except Exception as e:
            logger.error(f"Failed to check holiday status: {e}")
            
        return False # Default to business day on failure to avoid blocking

    def calculate_support_level(self, df, window=60):
        """
        Calculate support level using local minima within the last 'window' candles.
        Returns the most significant support price or None.
        """
        if len(df) < window:
            return None
        
        # Use recent data
        recent_df = df.iloc[-window:].copy()
        
        # 1. Find Local Minima (Basic approach: lower than neighbors)
        # Using a rolling window approach to find points lower than 5 previous and 5 next
        # Since we are live, we use look-back mostly.
        # A simple robust way: Find price levels that were "lows" multiple times.
        
        # Binning approach: Round prices to nearest tick (approx 0.5% bins) and count frequency of lows
        lows = recent_df['low'].values
        
        # Simple Clustering:
        # 1. Sort lows
        # 2. Group lows that are within 0.5% of each other
        # 3. Find the cluster with the most points (strongest support)
        # 4. Return the average price of that cluster
        
        # Optimization: Just use the lowest price in the last hour as a hard support for now
        # or find a "double bottom" pattern.
        
        # Let's try Double/Triple Bottom detection
        # Check if the current price is near the absolute low of the window
        min_price = np.min(lows)
        
        # Check how many times price touched near min_price (+0.5% range)
        threshold = min_price * 1.005 # +0.5%
        touches = np.sum(lows <= threshold)
        
        if touches >= 2:
            return min_price
            
        return None

    def check_rsi_triple_bottom(self, df, window=60):
        """
        Detects specific 'Triple Bottom' pattern in RSI.
        Condition: RSI dips below 30 (Oversold) at least 3 distinct times within window.
        Distinct means there was a recovery (e.g. RSI > 40) between dips.
        """
        if len(df) < window:
            return False
            
        recent_rsi = df['RSI'].iloc[-window:].values
        
        dips = 0
        in_dip = False
        
        # Simple finite state machine to count dips
        # State: Normal -> Dip(RSI<30) -> Recovery(RSI>40) -> Normal
        
        for rsi_val in recent_rsi:
            if np.isnan(rsi_val): continue
            
            if not in_dip:
                if rsi_val <= 30: # Enter Dip
                    dips += 1
                    in_dip = True
            else:
                if rsi_val >= 40: # Recovered
                    in_dip = False
                    
        return dips >= 3

    def get_market_session(self):
        """Returns current market session: KRX, NXT_PRE, NXT_POST, or CLOSED."""
        now = datetime.now()
        hour, minute = now.hour, now.minute
        time_val = hour * 100 + minute  # HHMM format
        
        if self.is_domestic:
            # 1. Holiday Check
            if self.is_holiday_today():
                return "CLOSED"

            # 2. Regular and Extended Hours
            if 800 <= time_val < 850:
                return "NXT_PRE"  # NXT Pre-market
            elif 900 <= time_val < 1530:
                # Note: This is a safe range, but we could also check if live data is flowing 
                # to handle cases like 10:00 AM openings (CSAT day).
                return "KRX"  # Regular session
            elif 1540 <= time_val < 2000:
                return "NXT_POST"  # NXT After-hours (until 20:00)
            else:
                return "CLOSED"
        else:
            # Overseas market (US)
            if now.hour < 6 or (now.hour == 6 and now.minute < 10):
                return "US_OPEN"
            elif now.hour >= 22:
                return "US_OPEN"
            else:
                return "CLOSED"
    
    def check_market_hours(self):
        """Returns True if within any trading session (KRX or NXT), False otherwise."""
        session = self.get_market_session()
        return session != "CLOSED"
            
    def get_balance(self):
        """Fetches total evaluation amount, available cash, and credit details."""
        try:
            if self.is_domestic:
                # 1. Regular Balance
                url = "/uapi/domestic-stock/v1/trading/inquire-balance"
                tr_id = "TTTC8434R"
                params = {
                    "CANO": self.trenv.my_acct,
                    "ACNT_PRDT_CD": self.trenv.my_prod,
                    "AFHR_FLPR_YN": "N",
                    "OFL_YN": "",
                    "INQR_DVSN": "01", # 01: Loan Date, 02: Stock
                    "UNPR_DVSN": "01",
                    "FUND_STTL_ICLD_YN": "N",
                    "FNCG_AMT_AUTO_RDPT_YN": "N",
                    "PRCS_DVSN": "00",
                    "CTX_AREA_FK100": "",
                    "CTX_AREA_NK100": ""
                }
                res = kis_auth._url_fetch(url, tr_id, "", params)
                
                cash, asset, real_avg, real_qty = 0, 0, 0, 0
                self.credit_holdings = []
                
                if res.isOK():
                    out2 = res.getBody().output2[0]
                    cash = int(out2.get('prvs_rcdl_excc_amt', 0)) # Available Cash
                    asset = int(out2.get('tot_evlu_amt', 0))
                    self.cash_balance = cash
                    
                    out1 = res.getBody().output1
                    total_pchs_amt = 0
                    for item in out1:
                        if item.get('pdno') == self.ticker:
                            qty = int(item.get('hldg_qty', 0))
                            if qty > 0:
                                raw_avg = float(item.get('pchs_avg_pric', 0))
                                total_pchs_amt += (raw_avg * qty)
                                real_qty += qty
                                
                                loan_dt = item.get('loan_dt', "").strip()
                                if loan_dt: # Credit holding
                                    self.credit_holdings.append({"qty": qty, "loan_dt": loan_dt})
                    
                    if real_qty > 0:
                        # Combine all holdings into a weighted average price
                        avg_pchs_price = total_pchs_amt / real_qty
                        # Adjust Avg Price definition to BEP (Break-Even Price)
                        total_cost_rate = self.buy_fee + self.sell_fee + self.sell_tax
                        real_avg = avg_pchs_price * (1 + total_cost_rate)
                    
                    # 2. Credit Purchase Power (Domestic only)
                    max_credit = 0
                    best_credit_type = "21"

                    for c_type in ["21", "23"]: # Check both Self-financing and Brokerage loans
                        try:
                            cre_df = d_func.inquire_credit_psamount(
                                cano=self.trenv.my_acct,
                                acnt_prdt_cd=self.trenv.my_prod,
                                pdno=self.ticker,
                                ord_dvsn="01", # Market
                                crdt_type=c_type,
                                cma_evlu_amt_icld_yn="N",
                                ovrs_icld_yn="N",
                                ord_unpr="0"
                            )
                            if not cre_df.empty:
                                output = cre_df.iloc[0].to_dict()
                                amt = int(output.get('crdt_buy_psbl_amt', 
                                          output.get('max_buy_amt', 
                                          output.get('ord_psbl_cash', 0))))
                                
                                # Use MAX instead of SUM to prevent double counting shared limit
                                if amt > max_credit:
                                    max_credit = amt
                                    best_credit_type = c_type

                                logger.debug(f"[DEBUG] Credit Type {c_type} amt: {amt}")
                        except Exception as e:
                            logger.error(f"Credit inquiry for {c_type} failed: {e}")
                    
                    self.credit_cash = max_credit
                    self.credit_type_code = best_credit_type
                    
                    # Synchronize Internal State with Real Balance
                    if real_qty > 0:
                        self.total_qty = real_qty
                        self.avg_buy_price = real_avg
                        self.state = "HOLDING"
                    elif self.state == "HOLDING": # If we thought we were holding but aren't
                        self.total_qty = 0
                        self.avg_buy_price = 0
                        self.state = "SEARCHING"
                        self.current_step = 0
                        self.buy_history = []
                    
                    return cash, asset, real_avg, real_qty
                
                else:
                    res.printError()
                    return 0, 0, 0, 0

            else:
                # Overseas
                url = "/uapi/overseas-stock/v1/trading/inquire-balance"
                tr_id = "TTTS3012R"
                params = {
                    "CANO": self.trenv.my_acct,
                    "ACNT_PRDT_CD": self.trenv.my_prod,
                    "OVRS_EXCG_CD": "NASD",
                    "TR_CRC_CD": "USD",
                    "CTX_AREA_FK200": "",
                    "CTX_AREA_NK200": ""
                }
                res = kis_auth._url_fetch(url, tr_id, "", params)
                if res.isOK():
                    out2 = res.getBody().output2
                    cash = float(out2.get('ovrs_tot_dnca_amt', 0))
                    asset = float(out2.get('tot_evlu_Pamt', 0))
                    return cash, asset, 0, 0
                else:
                    out2 = res.getBody().output2
                    cash = float(out2.get('ovrs_tot_dnca_amt', 0)) # Overseas Cash
                    asset = float(out2.get('tot_evlu_Pamt', 0)) # Total Asset
                    return cash, asset, 0, 0
        except Exception:
            pass
        return 0, 0, 0, 0

    def has_uncleared_sell_order(self):
        """Checks if there's an existing uncleared sell order for the current ticker."""
        if not self.live_mode: return False
        
        try:
            if self.is_domestic:
                url = "/uapi/domestic-stock/v1/trading/inquire-nccs"
                tr_id = "TTTC8012R" if self.live_mode else "VTTC8012R"
                params = {
                    "CANO": self.trenv.my_acct,
                    "ACNT_PRDT_CD": self.trenv.my_prod,
                    "INQR_DVSN": "00",
                    "CB_OT_DVSN": "00",
                    "PRCS_DVSN": "00",
                    "CTX_AREA_FK100": "",
                    "CTX_AREA_NK100": ""
                }
            else:
                url = "/uapi/overseas-stock/v1/trading/inquire-ccnl"
                tr_id = "TTTS3035R" if self.live_mode else "VTTS3035R"
                today = datetime.now().strftime("%Y%m%d")
                params = {
                    "CANO": self.trenv.my_acct,
                    "ACNT_PRDT_CD": self.trenv.my_prod,
                    "PDNO": self.ticker,
                    "ORD_STRT_DT": today,
                    "ORD_END_DT": today,
                    "SLL_BUY_DVSN": "01", # Sell only
                    "CCLD_NCCS_DVSN": "02", # Uncleared only
                    "OVRS_EXCG_CD": "NASD",
                    "SORT_SQN": "DS",
                    "ORD_DT": "",
                    "ORD_GNO_BRNO": "",
                    "ODNO": "",
                    "CTX_AREA_NK200": "",
                    "CTX_AREA_FK200": ""
                }

            res = kis_auth._url_fetch(url, tr_id, "", params)
            if res.isOK():
                if self.is_domestic:
                    output = res.getBody().output
                # Code logic continues below
                if self.is_domestic:
                    output = res.getBody().output
                    for item in output:
                        # sll_buy_dvsn_cd: 01 (매도), pdno: 종목코드
                        if item.get('pdno') == self.ticker and item.get('sll_buy_dvsn_cd') == '01':
                            return True
                else:
                    output = res.getBody().output
                    if output and len(output) > 0:
                        return True # We already filtered by ticker and sell in params
        except Exception as e:
            logger.warning(f"Error checking uncleared orders: {e}")
        
        return False

    def calculate_indicators(self, df):
        if df is None or len(df) < BB_PERIOD:
            return None, None
            
        delta = df['last'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        sma = df['last'].rolling(window=BB_PERIOD).mean()
        std = df['last'].rolling(window=BB_PERIOD).std()
        upper_bb = sma + (std * BB_STD)
        lower_bb = sma - (std * BB_STD)
        
        return rsi.iloc[-1], (lower_bb.iloc[-1], upper_bb.iloc[-1])

    def calculate_rsi_target_price(self, df, target_rsi=30):
        """Estimate the price at which RSI will hit the target in the next candle."""
        if df is None or len(df) < RSI_PERIOD + 1:
            return None
        
        # 1. Get Gains and Losses for the rolling window
        delta = df['last'].diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # 2. Get the window that will shift at next step
        # Prev window: df.index[-(RSI_PERIOD):]
        # Next window: will drop index [len(df) - RSI_PERIOD] and add new step
        
        drop_idx = len(df) - RSI_PERIOD
        gain_old = gains.iloc[drop_idx]
        loss_old = losses.iloc[drop_idx]
        
        # Current Sum in the rolling window
        sum_gain = gains.tail(RSI_PERIOD).sum()
        sum_loss = losses.tail(RSI_PERIOD).sum()
        
        # 3. Target RS calculation
        # RSI = 100 - 100/(1+RS) -> Target RS = target_rsi / (100 - target_rsi)
        target_rs = target_rsi / (100 - target_rsi)
        
        # 4. Solve for NextPrice (Assuming NextPrice < CurrPrice for buy signal)
        # NextRS = (sum_gain - gain_old + 0) / (sum_loss - loss_old + (curr_price - next_price))
        curr_price = df['last'].iloc[-1]
        
        # (sum_gain - gain_old) / target_rs = sum_loss - loss_old + curr_price - next_price
        # next_price = curr_price + (sum_loss - loss_old) - (sum_gain - gain_old) / target_rs
        
        try:
            target_price = curr_price + (sum_loss - loss_old) - (sum_gain - gain_old) / target_rs
            return target_price
        except ZeroDivisionError:
            return None

    def get_supply_info(self):
        """Fetch Institutional and Foreign net buy data for domestic stocks."""
        if not self.is_domestic:
            return ""
        
        try:
            res = kis_auth._url_fetch(
                "/uapi/domestic-stock/v1/quotations/inquire-investor", 
                "FHKST01010900", "", 
                {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": self.ticker}
            )
            if res.isOK():
                out = res.getBody().output
                if isinstance(out, list): out = out[0]
                # KIS labels: frgn_ntby_qty (Foreigner), orgn_ntby_qty (Institution)
                f_qty = int(out.get('frgn_ntby_qty', 0))
                i_qty = int(out.get('orgn_ntby_qty', 0))
                
                def fmt(n):
                    if abs(n) >= 1000000: return f"{n/1000000:.1f}M"
                    if abs(n) >= 1000: return f"{n/1000:.1f}k"
                    return str(n)
                
                return f"Supply: F:{fmt(f_qty)}, I:{fmt(i_qty)}"
        except Exception:
            pass
        return ""

    def place_order(self, dv="buy", qty=0, price=0):
        if qty <= 0: return None
        
        mode_str = "LIVE" if self.live_mode else "DRY RUN"
        logger.info(f"[{mode_str}] {dv.upper()} {qty} of {self.ticker} at {price}")
        
        if not self.live_mode: 
            try:
                subprocess.run(["afplay", "/System/Library/Sounds/Ping.aiff"], check=False)
            except: pass
            
            # Simulate fill for Dry Run
            if dv == "sell":
                threading.Timer(2.0, self.finalize_sell, [price, qty]).start()
            return "DRY_RUN_ORDER_NO"
        
        try:
            if self.is_domestic:
                # NXT 세션에서는 지정가(00)만 가능, 정규장에서는 시장가(01) 사용
                current_exch = getattr(self, 'current_exchange', 'KRX')
                if current_exch == "NXT":
                    ord_dvsn = "00"  # Limit Order for NXT
                    ord_unpr = str(int(price))  # Use provided price
                    logger.debug(f"NXT Session: Using limit order @ {price}")
                else:
                    ord_dvsn = "01"  # Market Order for KRX
                    ord_unpr = "0"
                
                if dv == "buy":
                    # Hybrid Buy: Cash first, then Credit for remainder
                    unit_cost = price * (1 + self.buy_fee)
                    cash_affordable_qty = int(self.cash_balance / unit_cost) if unit_cost > 0 else 0
                    
                    df = None
                    remaining_qty = qty
                    
                    # Step 1: Buy with Cash (as much as possible)
                    if cash_affordable_qty > 0:
                        cash_buy_qty = min(cash_affordable_qty, remaining_qty)
                        logger.info(f"[LIVE] BUY {cash_buy_qty} of {self.ticker} (Cash)")
                        env_type = "demo" if kis_auth.isPaperTrading() else "real"
                        current_exch = getattr(self, 'current_exchange', 'KRX')
                        df = d_func.order_cash(env_type, "buy", self.trenv.my_acct, self.trenv.my_prod, self.ticker, ord_dvsn, str(int(cash_buy_qty)), ord_unpr, current_exch)
                        
                        # Check if cash order succeeded
                        if df is not None and not df.empty:
                            remaining_qty -= cash_buy_qty
                        else:
                            logger.warning(f"[LIVE] Cash order failed, will attempt full qty with Credit")
                            # Cash order failed, try full qty with credit below
                    
                    # Step 2: Buy remaining with Credit
                    if remaining_qty > 0 and self.credit_cash > 0:
                        logger.info(f"[LIVE] BUY {remaining_qty} of {self.ticker} (Credit {self.credit_type_code})")
                        today = datetime.now().strftime("%Y%m%d")
                        df_credit = d_func.order_credit("buy", self.trenv.my_acct, self.trenv.my_prod, self.ticker, self.credit_type_code, today, ord_dvsn, str(int(remaining_qty)), ord_unpr)
                        
                        # Use credit result as primary if no cash order was made
                        if df is None or df.empty:
                            df = df_credit
                else:
                    # Sell logic
                    rem_qty = qty
                    last_odno = None
                    
                    # 1. Sell Credit Holdings FIRST (Repayment - 이자 비용 절감)
                    for item in self.credit_holdings:
                        if rem_qty <= 0: break
                        sell_qty_part = min(rem_qty, item['qty'])
                        logger.info(f"[LIVE] SELL {sell_qty_part} (Credit 상환, 대출일:{item['loan_dt']}) of {self.ticker}")
                        df = d_func.order_credit("sell", self.trenv.my_acct, self.trenv.my_prod, self.ticker, "25", item['loan_dt'], ord_dvsn, str(int(sell_qty_part)), ord_unpr)
                        if df is not None and not df.empty:
                            last_odno = str(df.iloc[0].get('ODNO', ''))
                        rem_qty -= sell_qty_part
                    
                    # 2. Sell Cash Holdings (remaining)
                    total_credit_qty = sum(item['qty'] for item in self.credit_holdings)
                    cash_qty = max(0, self.total_qty - total_credit_qty)
                    
                    if rem_qty > 0 and cash_qty > 0:
                        sell_cash_qty = min(rem_qty, cash_qty)
                        logger.info(f"[LIVE] SELL {sell_cash_qty} (Cash) of {self.ticker}")
                        env_type = "demo" if kis_auth.isPaperTrading() else "real"
                        current_exch = getattr(self, 'current_exchange', 'KRX')
                        df = d_func.order_cash(env_type, "sell", self.trenv.my_acct, self.trenv.my_prod, self.ticker, ord_dvsn, str(int(sell_cash_qty)), ord_unpr, current_exch)
                        if df is not None and not df.empty:
                            last_odno = str(df.iloc[0].get('ODNO', ''))
                        rem_qty -= sell_cash_qty
                    
                    if last_odno:
                        self.last_buy_time = time.time() if dv == "buy" else self.last_buy_time
                        self.consecutive_errors = 0
                    return last_odno

            else:
                # Overseas
                import overseas_stock_functions as o_func
                ord_dvsn = "00"
                ord_qty_str = str(int(qty))
                ord_unpr_str = str(round(price, 2))
                df = o_func.order_stock(dv, self.trenv.my_acct, self.trenv.my_prod, "NASD", self.ticker, ord_dvsn, ord_qty_str, ord_unpr_str)
                if dv == "sell" and df is not None: df["SLL_TYPE"] = "00"

            if df is not None and not df.empty:
                odno = str(df.iloc[0].get('ODNO', '')) if self.is_domestic else str(df.iloc[0].get('odno', ''))
                logger.info(f"Order Accepted! No: {odno}")
                if dv == "buy": self.last_buy_time = time.time()
                self.consecutive_errors = 0
                return odno
                
        except Exception as e:
            logger.error(f"Order failed: {e}")
            self.consecutive_errors += 1
            notify_user(f"ORDER FAILED: {e}", self.ticker)
            
        return None

    def run(self):
        buy_price_str = f" | Buy Price: {self.manual_buy_price:,}" if self.manual_buy_price > 0 else ""
        logger.info(f"Starting Universal Scalper | Ticker: {self.ticker} ({self.market}) | Budget: {self.budget:,} | Target: {self.target_profit:.2%}{buy_price_str}")
        sum_weights = sum(WEIGHTS)
        
        # Initial Balance Check (Critical for displaying correct credit info on startup)
        self.cached_balance = self.get_balance()
        
        # Initial Market Data Update (Investor/Credit/Short)
        if self.is_domestic:
            self.update_market_data()

        # Warmup: Validate RSI data before allowing trades
        # Skip warmup during NXT sessions or CLOSED (insufficient data for RSI)
        session = self.get_market_session()
        if session in ["NXT_PRE", "NXT_POST", "CLOSED"]:
            logger.info(f"[Warmup] Non-KRX Session detected ({session}). Skipping RSI warmup. Using price-based entry only.")
        else:
            warmup_count = 0
            total_attempts = 0
            warmup_required = 3
            max_attempts = 5
            logger.info(f"[Warmup] Validating data... (need {warmup_required} valid RSI readings)")
            while warmup_count < warmup_required:
                total_attempts += 1
                df = self.get_minute_chart()
                rsi, _ = self.calculate_indicators(df)
                
                # Break after max attempts regardless of RSI state
                if total_attempts >= max_attempts:
                    logger.warning(f"[Warmup] Max attempts ({max_attempts}) reached. Proceeding anyway.")
                    break
                    
                if rsi is None or np.isnan(rsi):
                    logger.warning(f"[Warmup] RSI is None/NaN, attempt {total_attempts}/{max_attempts}...")
                elif rsi <= 10 or rsi >= 90:
                    logger.warning(f"[Warmup] RSI {rsi:.1f} looks abnormal, attempt {total_attempts}/{max_attempts}...")
                    warmup_count += 1
                else:
                    warmup_count += 1
                    logger.info(f"[Warmup] RSI {rsi:.1f} valid ({warmup_count}/{warmup_required})")
                
                if warmup_count < warmup_required:
                    time.sleep(10)
            logger.info(f"[Warmup] Starting trading loop...")
        
        # Start Watchdog
        self.watchdog = Watchdog(timeout=120) # 120s tolerance (30s sleep + buffer)
        self.watchdog.start()
        
        last_save_time = 0
        
        while True:
            try:
                self.watchdog.ping()
                current_time = time.time()
                
                # Check Runtime Safety
                if self.consecutive_errors >= self.max_allowed_errors:
                    logger.error(f"🛑 TERMINATING BOT: {self.consecutive_errors} consecutive errors detected. Check logs/ for details.")
                    break
    
                # 0. Get current market session and update exchange
                session = self.get_market_session()
                if session == "CLOSED" and not getattr(self.args, "ignore_market", False):
                    logger.info(f"Market Closed. Current Time: {datetime.now().strftime('%H:%M:%S')}. Stopping Bot...")
                    break
                
                # Update current exchange based on session
                if session in ["NXT_PRE", "NXT_POST"]:
                    self.current_exchange = "NXT"
                    # User: "NXT 먼저 체크해야하는게 정상 아닐까? ㅠㅠ"
                    # We check availability immediately for NXT sessions
                    df_initial = self.get_minute_chart()
                    if df_initial.empty or (df_initial['last'].iloc[-1] <= 0):
                        self.nxt_consecutive_errors += 1
                        if self.nxt_consecutive_errors >= 5:
                            logger.info(f"🛑 [{self.ticker}] Not an NXT target (Initial check failed 5x). Stopping for NXT session.")
                            import os
                            os._exit(0)
                        logger.warning(f"[{session}] ⚠️ NXT Data missing (Checks:{self.nxt_consecutive_errors}). Retrying...")
                        time.sleep(5)
                        continue
                    else:
                        self.nxt_consecutive_errors = 0 # Valid data received
                else:
                    self.current_exchange = "KRX"
                
                # Throttled Balance Sync (every 30 seconds) to catch manual trades/credit holdings
                if current_time - getattr(self, 'last_balance_sync', 0) > 30:
                    self.cached_balance = self.get_balance()
                    self.last_balance_sync = current_time

                session_tag = f"[{session}]"
                    
                df = self.get_minute_chart()
                rsi, bb = self.calculate_indicators(df)
                
                # During NXT sessions, don't block on RSI - use price-based entry only
                if session == "KRX" and (rsi is None or np.isnan(rsi)):
                    time.sleep(10)
                    continue
                
                # Handle None RSI/BB gracefully for NXT
                if rsi is None or np.isnan(rsi):
                    rsi = 50.0  # Neutral RSI for display purposes only
                if bb is None:
                    bb = (0, 0)  # Placeholder BB
                    
                curr_price = df['last'].iloc[-1] if not df.empty else 0
                
                # Guard against invalid data (0 price is the only absolute blocker)
                # RSI 0 is natural/possible in NXT/early sessions, shouldn't block
                invalid_data = curr_price <= 0 or rsi is None
                
                if invalid_data:
                    if session != "CLOSED":
                        logger.warning(f"{session_tag} ⚠️ Invalid data detected (Price:{curr_price}, RSI:{rsi}). Skipping iteration...")
                    time.sleep(5)
                    continue
                
                # Real-time Dashboard Update (Heartbeat)
                should_save = False
                if curr_price > 0 and curr_price != self.last_price:
                    self.last_price = curr_price
                    should_save = True
                
                if time.time() - last_save_time > 10:
                    should_save = True
                    
                if should_save:
                    self.save_state()
                    last_save_time = time.time()
                candle_low = df['low'].iloc[-1] if not df.empty else 0
                lower_bb, upper_bb = bb
                
                # Capture KRX close when first entering NXT_POST (using KRX API, not NXT price)
                if session == "NXT_POST" and self.krx_close_today == 0:
                    try:
                        # Fetch actual KRX closing price using KRX API (not NXT)
                        krx_res = kis_auth._url_fetch(
                            "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                            "FHKST03010200", "",
                            {
                                "FID_COND_MRKT_DIV_CODE": "J",  # KRX only
                                "FID_INPUT_ISCD": self.ticker,
                                "FID_INPUT_HOUR_1": "153000",  # KRX close time
                                "FID_PW_DATA_INCU_YN": "Y",
                                "FID_ETC_CLS_CODE": ""
                            }
                        )
                        if krx_res.isOK():
                            krx_out = krx_res.getBody().output2
                            if krx_out and len(krx_out) > 0:
                                self.krx_close_today = int(krx_out[0].get('stck_prpr', 0))
                    except Exception as e:
                        logger.warning(f"Failed to fetch KRX close: {e}")
                        self.krx_close_today = self.prev_close  # Fallback
                    
                    if self.krx_close_today > 0:
                        logger.info(f"📌 Captured KRX close for NXT reference: {self.krx_close_today:,.0f}")
                
                # Use cached balance (updated only after trade execution)
                cash, asset, real_avg, real_qty = self.cached_balance
                
                target_price_info = f" ({self.avg_buy_price * (1 + self.target_profit):.2f})" if self.state == "HOLDING" else ""
                step_info = " | " + ", ".join([f"B{i+1}:{p:.0f}({q})" for i, (p, q) in enumerate(self.buy_history)]) if self.buy_history else ""
                
                # 1. Calculate Expected Buy Price
                # Initialize to prevent UnboundLocalError
                next_bb_price = lower_bb if bb else curr_price
                next_rsi_price = None
                
                if self.state == "SEARCHING":
                    next_rsi_price = self.calculate_rsi_target_price(df, RSI_BUY_LEVEL)
                    
                    parts = [f"BB:{next_bb_price:.2f}"]
                    if next_rsi_price: parts.append(f"RSI{RSI_BUY_LEVEL}:{next_rsi_price:.2f}")
                    if self.manual_buy_price > 0: parts.append(f"Manual:{self.manual_buy_price:,}")
                    
                    next_buy_tag = f"B1 @ " + " / ".join(parts)
                elif self.current_step < MAX_STEPS:
                    next_buy_price = self.avg_buy_price * (1 - PYRAMIDING_THRESHOLD)
                    next_buy_tag = f"B{self.current_step+1} @ {next_buy_price:.2f}"
                else:
                    next_buy_tag = "MAX STEPS"
    
                # Throttled Supply Info (update every 10 mins)
                if self.is_domestic and (current_time - self.last_supply_check >= self.supply_check_interval):
                    new_supply = self.get_supply_info()
                    if new_supply: 
                        self.cached_supply = new_supply
                        self.last_supply_check = current_time
                
                supply_part = f" | {self.cached_supply}" if self.is_domestic else ""
    
                # Bounce info
                bounce_rate = (curr_price - candle_low) / candle_low if candle_low > 0 else 0
                bounce_str = f" | Bounce: {bounce_rate:.2%}" if self.state == "SEARCHING" else ""
                
                # Balance and Holdings info
                balance_str = f"주문가능: {cash:,} | 총자산: {asset:,}"
                holding_str = f"평단가: {real_avg:.2f} ({real_qty}주)" if real_qty > 0 else "보유없음"
                
                # Auto-Synchronization with Actual Account Balance
                if real_qty != self.total_qty:
                    logger.warning(f" [⚠️Sync] Status mismatch detected. Local: {self.total_qty}주, Account: {real_qty}주. Synchronizing...")
                    if real_qty == 0:
                        self.clear_state()
                    else:
                        self.state = "HOLDING"
                        self.total_qty = real_qty
                        self.avg_buy_price = real_avg
                        self.current_step = 1  # Reset to step 1 based on current balance
                        self.buy_history = [(real_avg, real_qty)]
                        self.save_state()
                
                # Build drop target info string
                drop_info = ""
                if self.is_domestic:
                    hour = datetime.now().hour
                    if 8 <= hour < 10 and self.prev_close > 0:
                        drop_target = self.prev_close * 0.98
                        drop_info = f" | Drop@{drop_target:,.0f}(종가{self.prev_close:,.0f})"
                    elif hour >= 10 and self.daily_high > 0:
                        drop_target = self.daily_high * 0.98
                        drop_info = f" | Drop@{drop_target:,.0f}(고가{self.daily_high:,.0f})"
                
                # Orderbook info (if enabled)
                ob_info = ""
                bid_total, ask_total = 0, 0
                if self.use_orderbook and self.is_domestic:
                    bid_total, ask_total, ob_info = self.sync_portfolio() # Renamed from get_orderbook
                    ob_info = f" | OB:{ob_info}" if ob_info else ""
                
                # Calculate Effective Budget (Cap user budget by actual available assets for this cycle)
                holding_value = self.avg_buy_price * self.total_qty if self.state == "HOLDING" else 0
                effective_budget = min(self.budget, cash + holding_value)
                budget_tag = f"Budget:{effective_budget:,.0f}" if effective_budget < self.budget else ""
                budget_part = f" | {budget_tag}" if budget_tag else ""
                
                holding_str = f"평단가: {self.avg_buy_price:.2f} ({self.total_qty}주)" if self.state == "HOLDING" else "보유없음"
                
                profit_info = ""
                profit_rate = 0
                net_profit_rate = 0
                unrealized_net_amt = 0
                if self.state == "HOLDING":
                    profit_rate = (curr_price - self.avg_buy_price) / self.avg_buy_price
                    net_profit_rate = profit_rate - self.friction
                    
                    # Unrealized Net Profit Amount
                    net_investment = self.avg_buy_price * self.total_qty * (1 + self.buy_fee)
                    net_return = curr_price * self.total_qty * (1 - self.sell_fee - self.sell_tax)
                    unrealized_net_amt = net_return - net_investment
                    
                    profit_info = f" | Profit: {profit_rate:.2%} (Net: {net_profit_rate:.2%}) | PNL: {unrealized_net_amt:,.0f}"
    
                realized_info = f" | Today: {self.daily_realized_profit:,.0f}" if self.daily_realized_profit != 0 else ""
                
                # Investor Info (Market Data)
                # mkt_info variable removed as it is handled below directly
    
                # Core Metrics
                self.update_unfilled_orders()
                unfilled_str = f"Unfilled: B:{self.unfilled_buy_qty}, S:{self.unfilled_sell_qty}"
                
                # Calculate next_buy_price for logging
                if self.state == "SEARCHING":
                    next_buy_price_for_log = next_bb_price # Or next_rsi_price, or manual_buy_price
                elif self.current_step < MAX_STEPS:
                    next_buy_price_for_log = self.avg_buy_price * (1 - PYRAMIDING_THRESHOLD)
                else:
                    next_buy_price_for_log = 0 
                
                # Prepare variables for the new log line
                asset_val = asset
                avg_price = self.avg_buy_price
                total_qty = self.total_qty
                h_str = step_info # Reusing step_info for buy history
                target_price = self.avg_buy_price * (1 + self.target_profit) if self.state == "HOLDING" else 0
                
                # Determine reference close price based on session for Change Rate calculation
                ref_close_price = self.prev_close
                ref_label = "전일대비"
    
                if session == "NXT_PRE":
                    ref_close_price = self.prev_close
                    ref_label = "전일종가"
                elif session == "NXT_POST" and self.krx_close_today > 0:
                    ref_close_price = self.krx_close_today
                    ref_label = "KRX종가"
                
                # Calculate Change Rate based on the correct reference price
                change_rate = 0
                if ref_close_price > 0:
                    change_rate = (curr_price - ref_close_price) / ref_close_price
    
                # Simplified log construction to avoid extra pipes
                price_str = f"{session_tag} Price: {curr_price:,.0f} ({change_rate:+.2%})"
                
                if ref_close_price > 0 and session in ["NXT_PRE", "NXT_POST"]:
                     price_str += f" [{ref_label}:{ref_close_price:,.0f}]"
                
                log_parts = [
                    f"{price_str}{bounce_str}",
                    f"RSI: {rsi:.1f}",
                    f"BB: [{lower_bb:.2f}, {upper_bb:.2f}]"
                ]
                if supply_part.strip(): log_parts.append(supply_part.strip())
                if ob_info.strip(): log_parts.append(ob_info.strip())
                if unfilled_str.strip(): log_parts.append(unfilled_str.strip())
                
                # Credit Info prominently displayed
                if self.is_domestic:
                    credit_qty = sum(item['qty'] for item in self.credit_holdings)
                    c_str = f"Credit: {self.credit_cash:,.0f} ({credit_qty}주)" if credit_qty > 0 else f"Credit: {self.credit_cash:,.0f}"
                    log_parts.append(c_str)
                    # Market Info (Credit Rate & Investor Est)
                    log_parts.append(f"Mkt: {self.credit_trend_str} | {self.investor_info_str}")
    
                if self.state == "HOLDING":
                    log_parts.append(f"Profit: {profit_rate:.2%} (Net: {net_profit_rate:.2%})")
                    log_parts.append(f"PNL: {unrealized_net_amt:,.0f}")
                    
                log_parts.append(f"주문가능: {cash:,.0f}")
                log_parts.append(f"총자산: {asset_val:,.0f}")
                log_parts.append(f"평단가: {avg_price:.2f} ({total_qty}주)")
                
                if h_str.strip(): log_parts.append(h_str.strip())
                if realized_info.strip(): log_parts.append(realized_info.strip())
                
                log_parts.append(f"Target: {self.target_profit:.2%} ({target_price:.2f})")
                
                if self.state == "SEARCHING":
                    # Show different target for NXT vs KRX
                    if session in ["NXT_PRE", "NXT_POST"] and ref_close_price > 0:
                        nxt_target = ref_close_price * 0.99
                        log_parts.append(f"NXT Buy@: {nxt_target:,.0f} ({ref_label}{ref_close_price:,.0f}-1%)")
                    else:
                        log_parts.append(f"Next: {next_buy_price_for_log:.2f}")
                elif self.current_step < MAX_STEPS:
                    next_step_weight = WEIGHTS[self.current_step]
                    next_step_qty = int(effective_budget * (next_step_weight / sum_weights) / next_buy_price_for_log) if next_buy_price_for_log > 0 else 0
                    log_parts.append(f"Next: B{self.current_step+1} @ {next_buy_price_for_log:.2f} ({next_step_qty}주)")
                    
                log_parts.append(f"State: {self.state}")
                
                logger.info(" | ".join(log_parts))
                
                if self.state == "SEARCHING":
                    # Time-based Priority Entry Condition (Highest Priority)
                    drop_hit = False
                    drop_reason = ""
                    hour = datetime.now().hour
                    
                    # Update price info periodically
                    if self.is_domestic and (current_time - self.last_price_info_check >= self.price_info_interval):
                        self.update_price_info()
                        self.update_market_data()
                        self.last_market_data_check = current_time
                    
                    if self.is_domestic:
                        # NXT Session: Reference Close -1% Drop Logic
                        if session in ["NXT_PRE", "NXT_POST"] and ref_close_price > 0:
                            nxt_drop_target = ref_close_price * 0.99
                            if curr_price <= nxt_drop_target or candle_low <= nxt_drop_target:
                                drop_hit = True
                                drop_reason = f"NXT({ref_label})-1%({ref_close_price:,.0f}→{nxt_drop_target:,.0f})"
                                
                        # Regular Hours Logic (existing)
                        elif 8 <= hour < 10 and self.prev_close > 0:
                            # 08:00~10:00: 전일 종가 대비 -2% 
                            drop_target = self.prev_close * 0.98
                            if curr_price <= drop_target or candle_low <= drop_target:
                                drop_hit = True
                                drop_reason = f"PrevClose-2%({self.prev_close:,.0f}→{drop_target:,.0f})"
                        elif hour >= 10 and self.daily_high > 0:
                            # 10:00 이후: 당일 최고가 대비 -2%
                            drop_target = self.daily_high * 0.98
                            if curr_price <= drop_target or candle_low <= drop_target:
                                drop_hit = True
                                drop_reason = f"DailyHigh-2%({self.daily_high:,.0f}→{drop_target:,.0f})"
                    
                    # Triple-Threat Entry Condition: Only for KRX session (RSI hit, BB hit, or Manual Price hit)
                    # NXT sessions use price-drop condition ONLY
                    rsi_hit = False
                    bb_hit = False
                    price_hit = False
                    momentum_hit = False
                    momentum_reason = ""
                    
                    if session == "KRX":
                        rsi_hit = rsi <= RSI_BUY_LEVEL
                        bb_hit = (curr_price <= lower_bb or candle_low <= lower_bb)
                        price_hit = (self.manual_buy_price > 0 and (curr_price <= self.manual_buy_price or candle_low <= self.manual_buy_price))
                        
                        # Momentum Entry Condition (Breakout: curr > prev_high)
                        if self.use_momentum and self.prev_high > 0:
                            if curr_price > self.prev_high:
                                momentum_hit = True
                                momentum_reason = f"Breakout({curr_price:,.0f}>{self.prev_high:,.0f})"
                    
                    if momentum_hit or drop_hit or rsi_hit or bb_hit or price_hit:
                        # Orderbook filter check (if enabled)
                        if self.use_orderbook and bid_total <= ask_total:
                            logger.info(f"Orderbook Filter Blocked: Bid({bid_total:,}) <= Ask({ask_total:,}). Skipping entry.")
                        else:
                            reason = []
                            if momentum_hit: reason.append(momentum_reason)  # Momentum first
                            if drop_hit: reason.append(drop_reason)
                            if rsi_hit: reason.append(f"RSI({rsi:.1f})")
                            if bb_hit: reason.append(f"BB({lower_bb:.2f})")
                            if price_hit: reason.append(f"Price({self.manual_buy_price:,})")
                            if self.use_orderbook: reason.append(f"OB({bid_total:,}>{ask_total:,})")
                            
                            logger.info(f"ENTRY Triggered: {' | '.join(reason)}")
                            
                            # Calculate Support Score for Weighting
                            support_price = self.calculate_support_level(df)
                            is_near_support = False
                            if support_price:
                                # Check if current price is within 0.5% above support
                                if support_price <= curr_price <= support_price * 1.005:
                                    is_near_support = True
                                    reason.append(f"Support({support_price:,.0f})")
                            
                            # Check RSI Triple Bottom
                            is_rsi_triple = self.check_rsi_triple_bottom(df)
                            if is_rsi_triple:
                                reason.append("RSI_3_Bottom")
                            
                            # Apply Multiplier
                            qty_multiplier = 1.0
                            
                            # Priority: Triple Bottom (2.0x) > Support (1.5x)
                            if is_rsi_triple:
                                qty_multiplier = 2.0
                                logger.info(f"💎 RSI Triple Bottom Detected! Confidence Max. Boosting buy qty by 2.0x.")
                            elif is_near_support:
                                qty_multiplier = 1.5
                                logger.info(f"Strong Support Detected @ {support_price:,.0f}. Boosting buy qty by 1.5x.")
                            
                            step_budget = effective_budget * (WEIGHTS[0] / sum_weights) * qty_multiplier
                            qty = int(step_budget / curr_price)
                            
                            # 3. Small Budget Fix: Ensure at least 1 share if budget allows
                            if qty == 0 and effective_budget >= curr_price:
                                qty = 1
                                logger.info(f"Small Budget Override: buying {qty} share(s)")
    
                            if qty > 0 and self.place_order("buy", qty, curr_price):
                                self.avg_buy_price = curr_price
                                self.total_qty = qty
                                self.current_step = 1
                                self.buy_history = [(curr_price, qty)]
                                self.state = "HOLDING"
                                self.save_state()
                                self.cached_balance = self.get_balance()  # Update balance after buy
                
                elif self.state == "HOLDING":
                    profit_rate = (curr_price - self.avg_buy_price) / self.avg_buy_price
                    net_profit_rate = profit_rate - self.friction
                    
                    # Pyramiding (Averaging Down) Logic
                    pyramiding_drop = profit_rate <= -PYRAMIDING_THRESHOLD
                    pyramiding_rsi = rsi <= 25 and rsi > 10
                    
                    # Proactive Safety: 3-minute cooldown between buys
                    time_since_buy = (time.time() - self.last_buy_time) / 60
                    cooldown_ok = time_since_buy >= 3
                    
                    # Condition selection: B1->B2 (OR), B3+ (AND) for safety
                    if self.current_step < 2:
                        is_pyramid_triggered = (pyramiding_drop or pyramiding_rsi)
                        trigger_type = "OR (Drop|RSI)"
                    else:
                        is_pyramid_triggered = (pyramiding_drop and pyramiding_rsi)
                        trigger_type = "AND (Drop&RSI)"
                    
                    if is_pyramid_triggered and self.current_step < MAX_STEPS:
                        if not cooldown_ok:
                            logger.info(f"Pyramiding Blocked: Cooldown ({time_since_buy:.1f}/3.0 min)")
                        else:
                            pyramid_reason = []
                            if pyramiding_drop: pyramid_reason.append(f"Drop({profit_rate:.1%})")
                            if pyramiding_rsi: pyramid_reason.append(f"RSI({rsi:.1f})")
                            
                            
                            # Apply Multiplier/Support Logic for Pyramiding too
                            support_price = self.calculate_support_level(df)
                            qty_multiplier = 1.0
                            if support_price and support_price <= curr_price <= support_price * 1.005:
                                 qty_multiplier = 1.5
                                 logger.info(f"Pyramiding near Support @ {support_price:,.0f}. Boosting qty by 1.5x.")
    
                            step_budget = effective_budget * (WEIGHTS[self.current_step] / sum_weights) * qty_multiplier
                            qty = int(step_budget / curr_price)
                            
                            # Small Budget Fix for Pyramiding
                            remaining_budget = effective_budget - (self.avg_buy_price * self.total_qty)
                            if qty == 0 and remaining_budget >= curr_price:
                                qty = 1
                                logger.info(f"Small Budget Pyramiding Override: buying {qty} share(s)")
    
                            if qty > 0 and self.place_order("buy", qty, curr_price):
                                new_total_qty = self.total_qty + qty
                                self.avg_buy_price = ((self.avg_buy_price * self.total_qty) + (curr_price * qty)) / new_total_qty
                                self.total_qty = new_total_qty
                                self.current_step += 1
                                self.buy_history.append((curr_price, qty))
                                self.save_state()
                                self.cached_balance = self.get_balance()  # Update balance after pyramiding
                                logger.info(f"Pyramiding B{self.current_step}: {trigger_type} [{', '.join(pyramid_reason)}] | New Avg: {self.avg_buy_price:.2f}")
    
                    # Exit Conditions: BB Upper only if in profit >= Target Profit (2%+)
                    bb_exit = curr_price >= upper_bb and profit_rate >= self.target_profit
                    target_exit = profit_rate >= self.target_profit
                    
                    if bb_exit or target_exit:
                        reason = f"BB Upper (>={self.target_profit:.1%} 익절)" if bb_exit else "Target Profit"
                        
                        # Check for existing sell order before placing a new one
                        if self.has_uncleared_sell_order():
                            logger.info(f"Existing sell order found for {self.ticker}. Skipping duplicate EXIT.")
                            continue
    
                        # Precise Net Profit Calculation
                        net_investment = self.avg_buy_price * self.total_qty * (1 + self.buy_fee)
                        net_return = curr_price * self.total_qty * (1 - self.sell_fee - self.sell_tax)
                        net_profit_amt = net_return - net_investment
                        
                        logger.info(f"EXIT Triggered: {reason} | Qty: {self.total_qty} | Avg: {self.avg_buy_price:.2f} | Sell: {curr_price:.2f} | Gross: {profit_rate:.2%} | Net Profit: {net_profit_amt:,.0f}")
                        odno = self.place_order("sell", self.total_qty, curr_price)
                        if odno:
                            self.state = "PENDING_SELL"
                            self.pending_sell = {
                                "odno": odno,
                                "qty": self.total_qty,
                                "price": curr_price,
                                "reason": reason,
                                "avg_buy_price": self.avg_buy_price
                            }
                            self.save_state()
                            # Real summary is written upon fill confirmed by WebSocket
                
                elif self.state == "PENDING_SELL":
                    # Active Fill Detection: Check if sell was executed
                    # 1. Unfilled sell qty is 0 = order was filled or cancelled
                    # 2. Actual balance shows 0 shares for this ticker
                    
                    if self.unfilled_sell_qty == 0:
                        # Re-fetch balance to confirm actual holdings
                        _, _, _, actual_qty = self.get_balance()
                        
                        if actual_qty == 0:
                            # Sell was successfully filled!
                            pending = getattr(self, 'pending_sell', {})
                            sell_price = pending.get('price', 0)
                            sell_qty = pending.get('qty', self.total_qty)
                            
                            logger.info(f"✅ SELL FILL CONFIRMED (detected via balance sync) | Qty: {sell_qty} @ {sell_price}")
                            self.finalize_sell(sell_price, sell_qty)
                        else:
                            # Still holding shares - order may have been partially filled or cancelled
                            logger.warning(f"⚠️ PENDING_SELL but still holding {actual_qty} shares. Syncing state...")
                            self.total_qty = actual_qty
                            self.state = "HOLDING"
                            self.pending_sell = None
                            self.save_state()
                
                time.sleep(3)
            
            except KeyboardInterrupt:
                logger.info("Admin stop requested.")
                break
            except Exception as e:
                logger.error(f"⚠️ Unhandled Exception in Main Loop: {e}", exc_info=True)
                time.sleep(10) # Wait before retry to prevent log spam
                continue

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", type=str, default="오리엔탈정공", help="Ticker name or code")
    parser.add_argument("--budget", type=int, default=1000000, help="Total budget in KRW")
    parser.add_argument("--target", type=float, default=0.005, help="Target profit rate (0.005 = 0.5%)")
    parser.add_argument("--live", action="store_true", help="Live trading mode")
    parser.add_argument("--buy_price", type=float, default=0, help="Manual buy price (0 for market)")
    parser.add_argument("--orderbook", action="store_true", help="Use orderbook filter")
    parser.add_argument("--momentum", action="store_true", help="Use momentum mode")
    parser.add_argument("--bot_id", type=str, help="Unique Bot ID for logging")
    parser.add_argument("--ignore_market", action="store_true", help="Ignore market close check (for testing)")
    args = parser.parse_args()
    
    # 3. Quick Market Check before heavy init
    if not args.ignore_market:
        # We check simple hours first to avoid unnecessary KIS auth if closed
        now = datetime.now()
        time_val = now.hour * 100 + now.minute
        is_weekend = now.weekday() >= 5
        
        is_domestic = args.ticker.isdigit() and len(args.ticker) == 6 or StockMaster().get_code(args.ticker)
        
        if is_domestic:
            if is_weekend or not (800 <= time_val < 2000):
                logger.info(f"🛑 Market Closed (KRX/NXT). Current Time: {now.strftime('%H:%M')}")
                logger.info("Use --ignore_market to run anyway.")
                time.sleep(1) # Give web server some time to see the process and logs
                sys.exit(0)
        else:
            # Simple US check (rough)
            if not (2200 <= time_val or time_val < 610):
                logger.info(f"🛑 US Market Closed. Current Time: {now.strftime('%H:%M')}")
                logger.info("Use --ignore_market to run anyway.")
                time.sleep(1)
                sys.exit(0)
    
    # 0. Log Health Check before starting
    if not check_log_health(log_filename):
        sys.exit(1)
    
    scalper = UniversalScalper(args.ticker, args.budget, args.target, args.live, args.buy_price, args.orderbook, args.momentum, args=args)
    try:
        scalper.run()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
