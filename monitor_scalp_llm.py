import sys
import os
import time
import logging
import warnings
import pandas as pd
import numpy as np
from datetime import datetime
import pytz

KST = pytz.timezone('Asia/Seoul')
import argparse
from openai import OpenAI
from dotenv import load_dotenv
import json

warnings.warn(
    "monitor_scalp_llm.py is deprecated. "
    "Use 'from src.scalper import LLMScalper' or 'python run_scalper.py --llm' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Load OpenAI API Key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
        logging.FileHandler("llm_scalp.log", encoding='utf-8')
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

class LLMScalper:
    def __init__(self, ticker, budget, target_profit=0.005, live_mode=False, manual_buy_price=0):
        # 0. Initial guess
        self.is_domestic = ticker.isdigit() and len(ticker) == 6
        
        # 1. If not digit, try name lookup for Domestic code
        if not self.is_domestic:
            sm = StockMaster()
            found_code = sm.get_code(ticker)
            if found_code:
                ticker = found_code
                self.is_domestic = True

        self.ticker = ticker.upper()
        self.budget = budget
        self.target_profit = target_profit
        self.live_mode = live_mode
        self.manual_buy_price = manual_buy_price
        self.market = "Domestic" if self.is_domestic else "Overseas"
        
        # State management
        self.state = "SEARCHING"
        self.avg_buy_price = 0
        self.total_qty = 0
        self.current_step = 0
        self.buy_history = []  # List of (price, qty)
        self.latest_sentiment = 0 # -5 to 5
        self.last_news_titles = []
        
        # API Auth
        kis_auth.auth()
        self.trenv = kis_auth.getTREnv()
        
        # State Directory
        self.state_dir = "scalp_data"
        if not os.path.exists(self.state_dir):
            os.makedirs(self.state_dir)
        self.state_file = os.path.join(self.state_dir, f"state_{self.ticker}.json")
        
        # Initial Load
        self.load_state()
        
    def get_minute_chart(self):
        """Unified minute chart fetcher."""
        if self.is_domestic:
            url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            tr_id = "FHKST03010200"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": self.ticker,
                "FID_INPUT_HOUR_1": datetime.now(KST).strftime("%H%M%S"),
                "FID_PW_DATA_INCU_YN": "Y",
                "FID_ETC_CLS_CODE": ""
            }
        else:
            url = "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
            tr_id = "HHDFS76950200"
            params = {
                "AUTH": "",
                "EXCD": "NAS",
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
            if self.is_domestic:
                cols_map = {'stck_prpr': 'last', 'stck_oprc': 'open', 'stck_hgpr': 'high', 'stck_lwpr': 'low', 'cntg_vol': 'vol'}
            else:
                cols_map = {'last': 'last', 'open': 'open', 'high': 'high', 'low': 'low', 'evol': 'vol'}
            df = df.rename(columns=cols_map)
            cols = ['last', 'open', 'high', 'low', 'vol']
            for col in cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df.iloc[::-1].reset_index(drop=True)
        return None

    def check_market_hours(self):
        """Returns True if within trading hours, False otherwise."""
        now = datetime.now(KST)
        if self.is_domestic:
            close_time = now.replace(hour=15, minute=40, second=0, microsecond=0)
            return now < close_time
        else:
            close_time = now.replace(hour=6, minute=10, second=0, microsecond=0)
            if now.hour < 6 or (now.hour == 6 and now.minute < 10):
                return True
            return now.hour >= 22

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
        self.state = "SEARCHING"
        self.avg_buy_price = 0
        self.total_qty = 0
        self.current_step = 0
        self.buy_history = []

    def fetch_news(self):
        """Fetches latest news titles for the ticker."""
        if self.is_domestic:
            url = "/uapi/domestic-stock/v1/quotations/news-title"
            tr_id = "FHKST01011800"
            params = {
                "FID_NEWS_OFER_ENTP_CODE": "2", # 종합
                "FID_COND_MRKT_CLS_CODE": "00",
                "FID_INPUT_ISCD": self.ticker,
                "FID_TITL_CNTT": "",
                "FID_INPUT_DATE_1": datetime.now(KST).strftime("%Y%m%d"),
                "FID_INPUT_HOUR_1": "090000",
                "FID_RANK_SORT_CLS_CODE": "01",
                "FID_INPUT_SRNO": "1"
            }
        else:
            url = "/uapi/overseas-price/v1/quotations/news-title"
            tr_id = "HHPSTH60100C1"
            params = {
                "INFO_GB": "",
                "CLASS_CD": "",
                "NATION_CD": "US",
                "EXCHANGE_CD": "",
                "SYMB": self.ticker,
                "DATA_DT": datetime.now(KST).strftime("%Y%m%d"),
                "DATA_TM": "",
                "CTS": ""
            }

        res = kis_auth._url_fetch(url, tr_id, "", params)
        if res.isOK():
            output = res.getBody().output if self.is_domestic else res.getBody().outblock1
            titles = [item.get('hts_tltl') or item.get('title') for item in output[:10] if item]
            return [t for t in titles if t]
        return []

    def get_market_context(self):
        """Fetches Macro context (Indices, Investor Trends)."""
        context = {}
        try:
            if self.is_domestic:
                # 1. KOSPI & KOSDAQ Indices
                for code, name in [("0001", "KOSPI"), ("1001", "KOSDAQ")]:
                    res_idx = kis_auth._url_fetch("/uapi/domestic-stock/v1/quotations/inquire-index-price", "FHPUP02100000", "", {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code})
                    if res_idx.isOK():
                        out = res_idx.getBody().output
                        if isinstance(out, list): out = out[0]
                        context[name] = f"{out['bstp_nmix_prpr']} ({out['bstp_nmix_prdy_ctrt']}%)"
                
                # 2. Investor Trend (Stock specific)
                res_inv = kis_auth._url_fetch("/uapi/domestic-stock/v1/quotations/inquire-investor", "FHKST01010900", "", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": self.ticker})
                if res_inv.isOK():
                    out = res_inv.getBody().output
                    if isinstance(out, list): out = out[0]
                    foreign = out.get('frgn_ntby_qty', '0') or '0'
                    inst = out.get('orgn_ntby_qty', '0') or '0'
                    context['Investor'] = f"Foreign: {foreign}, Inst: {inst}"
            else:
                # 1. S&P 500 & Nasdaq (Approx via proxy)
                for symb, name in [("SPY", "SPY"), ("QQQ", "QQQ")]:
                    excd = "NYS" if symb == "SPY" else "NAS"
                    res_idx = kis_auth._url_fetch("/uapi/overseas-price/v1/quotations/price", "HHDFS00000300", "", {"AUTH": "", "EXCD": excd, "SYMB": symb})
                    if res_idx.isOK():
                        out = res_idx.getBody().output
                        context[name] = f"{out['last']} ({out['rate']}%)"
        except Exception as e:
            logger.error(f"Failed to fetch market context: {e}")
        return context

    def get_llm_sentiment(self, titles, context):
        """Judgment with News + Macro Context."""
        if not titles and not context: return 0
        
        # Check if anything changed
        current_input = str(titles) + str(context)
        if hasattr(self, 'last_input') and current_input == self.last_input:
            return self.latest_sentiment
            
        self.last_input = current_input
        self.last_news_titles = titles
        
        context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
        prompt = (
            f"As a pro stock analyst, evaluate the sentiment for {self.ticker} ({self.market}).\n"
            f"Market Context:\n{context_str}\n\n"
            f"Latest News:\n" + "\n".join(titles) + "\n\n"
            "Score from -5 (Strong Sell/Panic) to +5 (Strong Buy/Moon) based on both News AND Market context. "
            "Answer ONLY with the numeric score."
        )
        
        try:
            response = client.chat.completions.create(
                model="gpt-5.2",
                messages=[{"role": "user", "content": prompt}]
            )
            score_str = response.choices[0].message.content.strip()
            import re
            match = re.search(r"[-+]?\d+", score_str)
            score = int(match.group()) if match else 0
            logger.info(f"GPT-5.2 Analysis -> Score: {score} | News: {len(titles)} found | Context: {list(context.keys())}")
            self.latest_sentiment = max(-5, min(5, score))
            return self.latest_sentiment
        except Exception as e:
            logger.error(f"LLM Analysis failed: {e}")
            return self.latest_sentiment

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
                    cash = int(out2.get('prvs_rcdl_excc_amt', 0))
                    asset = int(out2.get('tot_evlu_amt', 0))
                    return cash, asset
                else:
                    out2 = res.getBody().output2
                    cash = float(out2.get('ovrs_tot_dnca_amt', 0))
                    asset = float(out2.get('tot_evlu_Pamt', 0))
                    return cash, asset
        except Exception:
            pass
        return 0, 0

    def calculate_indicators(self, df):
        if df is None or len(df) < BB_PERIOD: return None, None
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
        
        delta = df['last'].diff()
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        drop_idx = len(df) - RSI_PERIOD
        gain_old = gains.iloc[drop_idx]
        loss_old = losses.iloc[drop_idx]
        
        sum_gain = gains.tail(RSI_PERIOD).sum()
        sum_loss = losses.tail(RSI_PERIOD).sum()
        
        target_rs = target_rsi / (100 - target_rsi)
        curr_price = df['last'].iloc[-1]
        
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
            res = kis_auth._url_fetch("/uapi/domestic-stock/v1/quotations/inquire-investor", "FHKST01010900", "", {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": self.ticker})
            if res.isOK():
                out = res.getBody().output
                if isinstance(out, list): out = out[0]
                f_qty = int(out.get('frgn_ntby_qty', 0))
                i_qty = int(out.get('orgn_ntby_qty', 0))
                def fmt(n):
                    if abs(n) >= 1000000: return f"{n/1000000:.1f}M"
                    if abs(n) >= 1000: return f"{n/1000:.1f}k"
                    return str(n)
                return f"Supply: F:{fmt(f_qty)}, I:{fmt(i_qty)}"
        except Exception: pass
        return ""

    def place_order(self, dv="buy", qty=0, price=0):
        if qty <= 0: return False
        mode_str = "LIVE" if self.live_mode else "DRY RUN"
        logger.info(f"[{mode_str}] {dv.upper()} {qty} of {self.ticker} at {price}")
        if not self.live_mode: 
            # Play a distinct sound for LLM bot even in dry run
            os.system("afplay /System/Library/Sounds/Submarine.aiff")
            return True
        
        if self.is_domestic:
            url, tr_id = "/uapi/domestic-stock/v1/trading/order-cash", ("TTTC0012U" if dv == "buy" else "TTTC0011U")
            params = {"CANO": self.trenv.my_acct, "ACNT_PRDT_CD": self.trenv.my_prod, "PDNO": self.ticker, "ORD_DVSN": "00", "ORD_QTY": str(int(qty)), "ORD_UNPR": str(int(price)), "EXCG_ID_DVSN_CD": "KRX"}
        else:
            url, tr_id = "/uapi/overseas-stock/v1/trading/order", ("TTTT1002U" if dv == "buy" else "TTTT1006U")
            params = {"CANO": self.trenv.my_acct, "ACNT_PRDT_CD": self.trenv.my_prod, "OVRS_EXCG_CD": "NASD", "PDNO": self.ticker, "ORD_QTY": str(int(qty)), "OVRS_ORD_UNPR": str(round(price, 2)), "ORD_DVSN": "00"}
            if dv == "sell": params["SLL_TYPE"] = "00"

        res = kis_auth._url_fetch(url, tr_id, "", params, postFlag=True)
        if res.isOK():
            os.system("afplay /System/Library/Sounds/Submarine.aiff")
            return True
        return False

    def run(self):
        buy_price_str = f" | Buy Price: {self.manual_buy_price:,}" if self.manual_buy_price > 0 else ""
        logger.info(f"Starting Enhanced LLM Scalper | Ticker: {self.ticker} | Budget: {self.budget:,} | Target: {self.target_profit:.2%}{buy_price_str}")
        sum_weights = sum(WEIGHTS)
        
        while True:
            # 0. Check Market Hours
            if not self.check_market_hours():
                logger.info(f"Market Closed. Current Time: {datetime.now(KST).strftime('%H:%M:%S')}. Stopping Bot...")
                break

            # 1. Fetch Data, Index, Trend & News
            df = self.get_minute_chart()
            news_titles = self.fetch_news()
            market_context = self.get_market_context()
            self.latest_sentiment = self.get_llm_sentiment(news_titles, market_context)
            rsi, bb = self.calculate_indicators(df)
            balance = self.get_balance()
            
            if rsi is None or np.isnan(rsi):
                time.sleep(10)
                continue
                
            curr_price = df['last'].iloc[-1]
            candle_low = df['low'].iloc[-1]
            lower_bb, upper_bb = bb
            cash, asset = self.get_balance()
            
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

            # 2. Fetch Supply (Investor) Info
            supply_str = self.get_supply_info()
            supply_part = f" | {supply_str}" if supply_str else ""

            # Bounce info (logged for insight but no longer used to skip)
            bounce_rate = (curr_price - candle_low) / candle_low if candle_low > 0 else 0
            bounce_str = f" | Bounce: {bounce_rate:.2%}" if self.state == "SEARCHING" else ""
            
            balance_str = f"주문가능: {cash:,} | 총자산: {asset:,}"
            logger.info(f"Price: {curr_price:.2f}{bounce_str} | RSI: {rsi:.1f} | BB: [{lower_bb:.2f}, {upper_bb:.2f}]{supply_part} | {balance_str} | GPT: {self.latest_sentiment} | Target: {self.target_profit:.2%}{target_price_info}{step_info} | Next Buy: {next_buy_tag} | State: {self.state}")
            
            if self.state == "SEARCHING":
                # Triple-Threat Entry Condition: Any of (RSI hit, BB hit, or Manual Price hit)
                rsi_hit = rsi <= RSI_BUY_LEVEL
                bb_hit = (curr_price <= lower_bb or candle_low <= lower_bb)
                price_hit = (self.manual_buy_price > 0 and (curr_price <= self.manual_buy_price or candle_low <= self.manual_buy_price))
                
                if rsi_hit or bb_hit or price_hit:
                    if self.latest_sentiment >= 0:
                        reason = []
                        if rsi_hit: reason.append(f"RSI({rsi:.1f})")
                        if bb_hit: reason.append(f"BB({lower_bb:.2f})")
                        if price_hit: reason.append(f"Price({self.manual_buy_price:,})")
                        
                        logger.info(f"ENTRY Triggered: {' | '.join(reason)}")
                        
                        step_budget = self.budget * (WEIGHTS[0] / sum_weights)
                        qty = int(step_budget / curr_price)
                        
                        # 3. Small Budget Fix
                        if qty == 0 and self.budget >= curr_price:
                            qty = 1
                            logger.info(f"Small Budget Override: buying {qty} share(s)")

                        if qty > 0 and self.place_order("buy", qty, curr_price):
                            self.avg_buy_price, self.total_qty, self.current_step, self.buy_history, self.state = curr_price, qty, 1, [(curr_price, qty)], "HOLDING"
                            self.save_state()
                    else:
                        logger.warning(f"BUY Signal Ignored due to Bearish Sentiment ({self.latest_sentiment})")
            
            elif self.state == "HOLDING":
                profit_rate = (curr_price - self.avg_buy_price) / self.avg_buy_price
                
                # Emergency LLM Exit: Strong Bearish News/Market
                if self.latest_sentiment <= -3:
                    logger.warning(f"!!! EMERGENCY EXIT !!! Strong Bearish Score ({self.latest_sentiment})")
                    if self.place_order("sell", self.total_qty, curr_price):
                        self.clear_state()

                # Pyramiding (Averaging Down)
                elif profit_rate <= -PYRAMIDING_THRESHOLD and self.current_step < MAX_STEPS:
                    if self.latest_sentiment >= -1: # Don't average down if context is too bad
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
                            self.total_qty, self.current_step = new_total_qty, self.current_step + 1
                            self.buy_history.append((curr_price, qty))
                            self.save_state()

                # Exit Conditions: BB Upper only if in profit >= 0.5%, or Target Profit reached
                elif curr_price >= upper_bb or profit_rate >= self.target_profit:
                    bb_exit = curr_price >= upper_bb and profit_rate >= 0.005
                    target_exit = profit_rate >= self.target_profit
                    
                    if bb_exit or target_exit:
                        if self.place_order("sell", self.total_qty, curr_price):
                            self.clear_state()
            
            time.sleep(60) # News check every 60s is sufficient and cost-effective

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--budget", type=int, default=1000000)
    parser.add_argument("--target", type=float, default=0.005, help="Target profit rate (default: 0.005 for 0.5%)")
    parser.add_argument("--buy_price", type=float, default=0, help="Manual buy price (triggers B1)")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    scalper = LLMScalper(args.ticker, args.budget, args.target, args.live, args.buy_price)
    try:
        scalper.run()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
