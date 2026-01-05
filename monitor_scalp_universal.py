import sys
import os
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime
import argparse
import json

# Add examples_user to path for kis_auth
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))
import kis_auth
from stock_code_lookup import StockMaster

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("universal_scalp.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

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
    def __init__(self, ticker, budget, target_profit=0.005, live_mode=False, manual_buy_price=0):
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
        
        # State management
        self.state = "SEARCHING"
        self.avg_buy_price = 0
        self.total_qty = 0
        self.current_step = 0
        self.buy_history = []  # List of (price, qty)
        
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
            self.last_supply_check = time.time()
        
    def get_minute_chart(self):
        """Unified minute chart fetcher."""
        if self.is_domestic:
            url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            tr_id = "FHKST03010200"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
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
            
            return df.iloc[::-1].reset_index(drop=True)
        else:
            logger.error(f"Failed to fetch chart: {res.getErrorMessage()}")
            return None

    def save_state(self):
        """Save current trading state to JSON."""
        # Convert numpy types to native Python types for JSON serialization
        buy_history_native = [(float(p), int(q)) for p, q in self.buy_history]
        state_data = {
            "state": self.state,
            "avg_buy_price": float(self.avg_buy_price),
            "total_qty": int(self.total_qty),
            "current_step": int(self.current_step),
            "buy_history": buy_history_native
        }
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=4)
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
                logger.info(f"Loaded existing state for {self.ticker}: {self.state} | {self.total_qty} shares @ {self.avg_buy_price:.2f}")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")

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

    def get_market_session(self):
        """Returns current market session: KRX, NXT_PRE, NXT_POST, or CLOSED."""
        now = datetime.now()
        hour, minute = now.hour, now.minute
        time_val = hour * 100 + minute  # HHMM format
        
        if self.is_domestic:
            if 800 <= time_val < 850:
                return "NXT_PRE"  # NXT Pre-market
            elif 900 <= time_val < 1530:
                return "KRX"  # Regular session
            elif 1540 <= time_val < 1800:
                return "NXT_POST"  # NXT After-hours
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
        """Fetches total evaluation amount and available cash."""
        try:
            if self.is_domestic:
                url = "/uapi/domestic-stock/v1/trading/inquire-balance"
                tr_id = "TTTC8434R"
                params = {
                    "CANO": self.trenv.my_acct,
                    "ACNT_PRDT_CD": self.trenv.my_prod,
                    "AFHR_FLPR_YN": "N",
                    "OFL_YN": "",
                    "INQR_DVSN": "02",
                    "UNPR_DVSN": "01",
                    "FUND_STTL_ICLD_YN": "N",
                    "FNCG_AMT_AUTO_RDPT_YN": "N",
                    "PRCS_DVSN": "00",
                    "CTX_AREA_FK100": "",
                    "CTX_AREA_NK100": ""
                }
            else:
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
                if self.is_domestic:
                    out2 = res.getBody().output2[0]
                    cash = int(out2.get('prvs_rcdl_excc_amt', 0)) # 주문가능금액
                    asset = int(out2.get('tot_evlu_amt', 0)) # Total Asset
                    
                    # Get holding info for current ticker
                    out1 = res.getBody().output1
                    real_avg, real_qty = 0, 0
                    for item in out1:
                        if item.get('pdno') == self.ticker:
                            real_avg = float(item.get('pchs_avg_pric', 0))
                            real_qty = int(item.get('hldg_qty', 0))
                            break
                    return cash, asset, real_avg, real_qty
                else:
                    out2 = res.getBody().output2
                    cash = float(out2.get('ovrs_tot_dnca_amt', 0)) # Overseas Cash
                    asset = float(out2.get('tot_evlu_Pamt', 0)) # Total Asset
                    return cash, asset, 0, 0
        except Exception:
            pass
        return 0, 0, 0, 0

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
        if qty <= 0: return False
        
        mode_str = "LIVE" if self.live_mode else "DRY RUN"
        logger.info(f"[{mode_str}] {dv.upper()} {qty} of {self.ticker} at {price}")
        
        if not self.live_mode: 
            # Play a distinct sound for Universal bot even in dry run
            os.system("afplay /System/Library/Sounds/Ping.aiff")
            return True
        
        if self.is_domestic:
            url = "/uapi/domestic-stock/v1/trading/order-cash"
            tr_id = "TTTC0012U" if dv == "buy" else "TTTC0011U"
            params = {
                "CANO": self.trenv.my_acct,
                "ACNT_PRDT_CD": self.trenv.my_prod,
                "PDNO": self.ticker,
                "ORD_DVSN": "00",
                "ORD_QTY": str(int(qty)),
                "ORD_UNPR": str(int(price)),
                "EXCG_ID_DVSN_CD": self.current_exchange  # Dynamic: KRX or NXT
            }
        else:
            url = "/uapi/overseas-stock/v1/trading/order"
            tr_id = "TTTT1002U" if dv == "buy" else "TTTT1006U"
            params = {
                "CANO": self.trenv.my_acct,
                "ACNT_PRDT_CD": self.trenv.my_prod,
                "OVRS_EXCG_CD": "NASD", # Hardcoded for NASDAQ
                "PDNO": self.ticker,
                "ORD_QTY": str(int(qty)),
                "OVRS_ORD_UNPR": str(round(price, 2)), # Overseas has decimals
                "ORD_DVSN": "00"
            }
            if dv == "sell": params["SLL_TYPE"] = "00"

        res = kis_auth._url_fetch(url, tr_id, "", params, postFlag=True)
        if res.isOK():
            os.system("afplay /System/Library/Sounds/Ping.aiff")
            logger.info(f"Order Success! No: {res.getBody().output.get('ODNO')}")
            return True
        else:
            logger.error(f"Order Failed: {res.getErrorMessage()}")
            return False

    def run(self):
        buy_price_str = f" | Buy Price: {self.manual_buy_price:,}" if self.manual_buy_price > 0 else ""
        logger.info(f"Starting Universal Scalper | Ticker: {self.ticker} ({self.market}) | Budget: {self.budget:,} | Target: {self.target_profit:.2%}{buy_price_str}")
        sum_weights = sum(WEIGHTS)
        
        while True:
            # 0. Get current market session and update exchange
            current_time = time.time()
            session = self.get_market_session()
            if session == "CLOSED":
                logger.info(f"Market Closed. Current Time: {datetime.now().strftime('%H:%M:%S')}. Stopping Bot...")
                break
            
            # Update current exchange based on session
            if session in ["NXT_PRE", "NXT_POST"]:
                self.current_exchange = "NXT"
            else:
                self.current_exchange = "KRX"
            
            session_tag = f"[{session}]"
                
            df = self.get_minute_chart()
            rsi, bb = self.calculate_indicators(df)
            
            if rsi is None or np.isnan(rsi):
                time.sleep(10)
                continue
                
            curr_price = df['last'].iloc[-1]
            candle_low = df['low'].iloc[-1]
            lower_bb, upper_bb = bb
            
            # Use cached balance (updated only after trade execution)
            cash, asset, real_avg, real_qty = self.cached_balance
            
            target_price_info = f" ({self.avg_buy_price * (1 + self.target_profit):.2f})" if self.state == "HOLDING" else ""
            step_info = " | " + ", ".join([f"B{i+1}:{p:.0f}({q})" for i, (p, q) in enumerate(self.buy_history)]) if self.buy_history else ""
            
            # 1. Calculate Expected Buy Price
            if self.state == "SEARCHING":
                next_bb_price = lower_bb
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
            
            # Inventory Mismatch Alert
            mismatch_alert = ""
            if self.state == "HOLDING" and self.total_qty > 0 and real_qty == 0:
                mismatch_alert = " [⚠️수량불일치: 계좌에 주식 없음!]"
            
            logger.info(f"{session_tag} Price: {curr_price:.2f}{bounce_str} | RSI: {rsi:.1f} | BB: [{lower_bb:.2f}, {upper_bb:.2f}]{supply_part} | {balance_str} | {holding_str}{mismatch_alert}{step_info} | Target: {self.target_profit:.2%}{target_price_info} | Next Buy: {next_buy_tag} | EXCG: {self.current_exchange} | State: {self.state}")
            
            if self.state == "SEARCHING":
                # Triple-Threat Entry Condition: Any of (RSI hit, BB hit, or Manual Price hit)
                rsi_hit = rsi <= RSI_BUY_LEVEL
                bb_hit = (curr_price <= lower_bb or candle_low <= lower_bb)
                price_hit = (self.manual_buy_price > 0 and (curr_price <= self.manual_buy_price or candle_low <= self.manual_buy_price))
                
                if rsi_hit or bb_hit or price_hit:
                    reason = []
                    if rsi_hit: reason.append(f"RSI({rsi:.1f})")
                    if bb_hit: reason.append(f"BB({lower_bb:.2f})")
                    if price_hit: reason.append(f"Price({self.manual_buy_price:,})")
                    
                    logger.info(f"ENTRY Triggered: {' | '.join(reason)}")
                    
                    step_budget = self.budget * (WEIGHTS[0] / sum_weights)
                    qty = int(step_budget / curr_price)
                    
                    # 3. Small Budget Fix: Ensure at least 1 share if budget allows
                    if qty == 0 and self.budget >= curr_price:
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
                
                # Pyramiding (Averaging Down)
                if profit_rate <= -PYRAMIDING_THRESHOLD and self.current_step < MAX_STEPS:
                    step_budget = self.budget * (WEIGHTS[self.current_step] / sum_weights)
                    qty = int(step_budget / curr_price)
                    
                    # Small Budget Fix for Pyramiding
                    remaining_budget = self.budget - (self.avg_buy_price * self.total_qty)
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
                        logger.info(f"Averaged Down. New Avg Price: {self.avg_buy_price:.2f}")

                # Exit Conditions: BB Upper only if in profit >= 0.5%, or Target Profit reached
                bb_exit = curr_price >= upper_bb and profit_rate >= 0.005
                target_exit = profit_rate >= self.target_profit
                
                if bb_exit or target_exit:
                    reason = "BB Upper (>=0.5% 익절)" if bb_exit else "Target Profit"
                    logger.info(f"EXIT Triggered: {reason} | Profit: {profit_rate:.2%}")
                    if self.place_order("sell", self.total_qty, curr_price):
                        self.cached_balance = self.get_balance()  # Update balance after sell
                        self.clear_state()
            
            time.sleep(30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True, help="Ticker symbol (e.g., 014940, TSLA)")
    parser.add_argument("--budget", type=int, default=1000000, help="Total budget in KRW (default: 1M)")
    parser.add_argument("--target", type=float, default=0.005, help="Target profit rate (default: 0.005 for 0.5%)")
    parser.add_argument("--buy_price", type=float, default=0, help="Manual buy price (triggers B1)")
    parser.add_argument("--live", action="store_true", help="Execute real orders")
    args = parser.parse_args()
    
    scalper = UniversalScalper(args.ticker, args.budget, args.target, args.live, args.buy_price)
    try:
        scalper.run()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
