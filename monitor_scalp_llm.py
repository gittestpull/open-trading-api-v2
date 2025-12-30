import sys
import os
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime
import argparse
from openai import OpenAI
from dotenv import load_dotenv

# Load OpenAI API Key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Add examples_user to path for kis_auth
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))
import kis_auth

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
    def __init__(self, ticker, budget, live_mode=False):
        self.ticker = ticker.upper()
        self.budget = budget
        self.live_mode = live_mode
        self.is_domestic = ticker.isdigit() and len(ticker) == 6
        self.market = "Domestic" if self.is_domestic else "Overseas"
        
        # State management
        self.state = "SEARCHING"
        self.avg_buy_price = 0
        self.total_qty = 0
        self.current_step = 0
        self.latest_sentiment = 0 # -5 to 5
        self.last_news_titles = []
        
        # API Auth
        kis_auth.auth()
        self.trenv = kis_auth.getTREnv()
        
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
                "FID_INPUT_DATE_1": datetime.now().strftime("%Y%m%d"),
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
                "DATA_DT": datetime.now().strftime("%Y%m%d"),
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
                    foreign = out.get('prsn_ntby_qty', '0') or '0'
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
        logger.info(f"Starting Enhanced LLM Scalper | Ticker: {self.ticker} | Budget: {self.budget:,}")
        sum_weights = sum(WEIGHTS)
        
        while True:
            # 1. Fetch Data, Index, Trend & News
            df = self.get_minute_chart()
            news_titles = self.fetch_news()
            market_context = self.get_market_context()
            self.latest_sentiment = self.get_llm_sentiment(news_titles, market_context)
            rsi, bb = self.calculate_indicators(df)
            
            if rsi is None or np.isnan(rsi):
                time.sleep(10)
                continue
                
            curr_price = df['last'].iloc[-1]
            lower_bb, upper_bb = bb
            
            logger.info(f"Price: {curr_price:.2f} | RSI: {rsi:.1f} | BB: [{lower_bb:.2f}, {upper_bb:.2f}] | GPT: {self.latest_sentiment} | State: {self.state}")
            
            if self.state == "SEARCHING":
                # BUY: Technical Signal + Non-negative Sentiment
                if rsi <= RSI_BUY_LEVEL and curr_price <= lower_bb:
                    if self.latest_sentiment >= 0:
                        step_budget = self.budget * (WEIGHTS[0] / sum_weights)
                        qty = int(step_budget / curr_price)
                        if self.place_order("buy", qty, curr_price):
                            self.avg_buy_price, self.total_qty, self.current_step, self.state = curr_price, qty, 1, "HOLDING"
                    else:
                        logger.warning(f"BUY Signal Ignored due to Bearish Sentiment ({self.latest_sentiment})")
            
            elif self.state == "HOLDING":
                profit_rate = (curr_price - self.avg_buy_price) / self.avg_buy_price
                
                # Emergency LLM Exit: Strong Bearish News/Market
                if self.latest_sentiment <= -3:
                    logger.warning(f"!!! EMERGENCY EXIT !!! Strong Bearish Score ({self.latest_sentiment})")
                    if self.place_order("sell", self.total_qty, curr_price):
                        self.state, self.avg_buy_price, self.total_qty, self.current_step = "SEARCHING", 0, 0, 0

                # Pyramiding (Averaging Down)
                elif profit_rate <= -PYRAMIDING_THRESHOLD and self.current_step < MAX_STEPS:
                    if self.latest_sentiment >= -1: # Don't average down if context is too bad
                        step_budget = self.budget * (WEIGHTS[self.current_step] / sum_weights)
                        qty = int(step_budget / curr_price)
                        if self.place_order("buy", qty, curr_price):
                            new_total_qty = self.total_qty + qty
                            self.avg_buy_price = ((self.avg_buy_price * self.total_qty) + (curr_price * qty)) / new_total_qty
                            self.total_qty, self.current_step = new_total_qty, self.current_step + 1

                # Exit Conditions
                elif curr_price >= upper_bb or profit_rate >= TARGET_PROFIT:
                    if self.place_order("sell", self.total_qty, curr_price):
                        self.state, self.avg_buy_price, self.total_qty, self.current_step = "SEARCHING", 0, 0, 0
            
            time.sleep(60) # News check every 60s is sufficient and cost-effective

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--budget", type=int, default=1000000)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    scalper = LLMScalper(args.ticker, args.budget, args.live)
    try:
        scalper.run()
    except KeyboardInterrupt:
        logger.info("Stopped by user")
