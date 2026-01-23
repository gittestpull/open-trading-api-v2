# -*- coding: utf-8 -*-
"""
LLM-Enhanced Scalper Module
Extends BaseScalper with GPT-based sentiment analysis and market context evaluation.

Features:
- Real-time news sentiment analysis using GPT-5.2
- Market context aggregation (KOSPI/KOSDAQ, SPY/QQQ)
- Investor trend monitoring (Foreign/Institutional)
- Emergency exit on strong bearish signals
"""
import os
import sys
import re
import logging
from typing import Tuple, Optional, List, Dict
from datetime import datetime
import pytz
from dotenv import load_dotenv

KST = pytz.timezone('Asia/Seoul')

import pandas as pd

# KIS API imports
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))
sys.path.append(os.path.join(os.getcwd(), 'examples_user', 'domestic_stock'))
sys.path.append(os.path.join(os.getcwd(), 'examples_user', 'overseas_stock'))

from .base import BaseScalper
from .config import ScalperConfig


logger = logging.getLogger(__name__)

# Load OpenAI API Key
load_dotenv()


def get_openai_client():
    """Lazy load OpenAI client to avoid import errors when not using LLM."""
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set. LLM features disabled.")
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        logger.warning("openai package not installed. LLM features disabled.")
        return None


class LLMScalper(BaseScalper):
    """
    LLM-enhanced scalper that uses GPT-5.2 for sentiment analysis.
    
    Key additions over BaseScalper:
    - fetch_news(): Retrieves latest news for the ticker
    - get_market_context(): Aggregates macro indicators
    - get_llm_sentiment(): GPT-based sentiment scoring (-5 to +5)
    - Emergency exit on sentiment <= -3
    """
    
    def __init__(self, config: ScalperConfig):
        self.is_domestic = self._detect_market(config.ticker)
        self.openai_client = get_openai_client()
        
        # LLM-specific state
        self.latest_sentiment: int = 0
        self.last_news_titles: List[str] = []
        self.last_input: str = ""
        
        super().__init__(config)
    
    def _detect_market(self, ticker: str) -> bool:
        """Detects if ticker is domestic (6-digit KR) or overseas."""
        from stock_code_lookup import StockMaster
        
        is_domestic = ticker.isdigit() and len(ticker) == 6
        
        if not is_domestic:
            sm = StockMaster()
            found_code = sm.get_code(ticker)
            if found_code:
                self.config.ticker = found_code
                return True
        
        return is_domestic
    
    def _initialize_api(self):
        """Initialize KIS API authentication."""
        import kis_auth
        kis_auth.auth()
        self.trenv = kis_auth.getTREnv()
        self.kis_auth = kis_auth
    
    def get_minute_chart(self) -> pd.DataFrame:
        """Fetch 1-minute OHLCV chart data."""
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
            cols_map = {
                'stck_prpr': 'last', 'stck_oprc': 'open',
                'stck_hgpr': 'high', 'stck_lwpr': 'low', 'cntg_vol': 'vol'
            }
        else:
            url = "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
            tr_id = "HHDFS76950200"
            params = {
                "AUTH": "", "EXCD": "NAS", "SYMB": self.ticker,
                "NMIN": "1", "PINC": "0", "NEXT": "",
                "NREC": "40", "FILL": "", "KEYB": ""
            }
            cols_map = {
                'last': 'last', 'open': 'open',
                'high': 'high', 'low': 'low', 'evol': 'vol'
            }
        
        res = self.kis_auth._url_fetch(url, tr_id, "", params)
        if not res.isOK():
            return pd.DataFrame()
        
        df = pd.DataFrame(res.getBody().output2)
        df = df.rename(columns=cols_map)
        
        for col in ['last', 'open', 'high', 'low', 'vol']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df.iloc[::-1].reset_index(drop=True)
    
    def get_current_price(self) -> float:
        """Get current price from latest chart data."""
        df = self.get_minute_chart()
        if df.empty:
            return 0.0
        return float(df['last'].iloc[-1])
    
    def get_balance(self) -> Tuple[float, float, float, float]:
        """Fetch account balance: (cash, total_asset, avg_price, qty)."""
        try:
            if self.is_domestic:
                url = "/uapi/domestic-stock/v1/trading/inquire-balance"
                tr_id = "TTTC8434R"
                params = {
                    "CANO": self.trenv.my_acct,
                    "ACNT_PRDT_CD": self.trenv.my_prod,
                    "AFHR_FLPR_YN": "N", "OFL_YN": "",
                    "INQR_DVSN": "01", "UNPR_DVSN": "01",
                    "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N",
                    "PRCS_DVSN": "00", "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""
                }
            else:
                url = "/uapi/overseas-stock/v1/trading/inquire-balance"
                tr_id = "TTTS3012R"
                params = {
                    "CANO": self.trenv.my_acct,
                    "ACNT_PRDT_CD": self.trenv.my_prod,
                    "OVRS_EXCG_CD": "NASD", "TR_CRC_CD": "USD",
                    "CTX_AREA_FK200": "", "CTX_AREA_NK200": ""
                }
            
            res = self.kis_auth._url_fetch(url, tr_id, "", params)
            if not res.isOK():
                return (0, 0, 0, 0)
            
            if self.is_domestic:
                out2 = res.getBody().output2[0]
                cash = int(out2.get('prvs_rcdl_excc_amt', 0))
                asset = int(out2.get('tot_evlu_amt', 0))
                
                # Find position for this ticker
                real_avg, real_qty = 0.0, 0
                for item in res.getBody().output1:
                    if item.get('pdno') == self.ticker:
                        real_qty = int(item.get('hldg_qty', 0))
                        raw_avg = float(item.get('pchs_avg_pric', 0))
                        friction = self.config.fees.get_domestic_friction()
                        real_avg = raw_avg * (1 + friction)
                        break
                
                return (cash, asset, real_avg, real_qty)
            else:
                out2 = res.getBody().output2
                cash = float(out2.get('ovrs_tot_dnca_amt', 0))
                asset = float(out2.get('tot_evlu_Pamt', 0))
                return (cash, asset, 0, 0)
                
        except Exception as e:
            logger.error(f"Failed to fetch balance: {e}")
            return (0, 0, 0, 0)
    
    def get_orderbook(self) -> Tuple[int, int, str]:
        """Fetch orderbook bid/ask totals."""
        if not self.is_domestic:
            return (0, 0, "")
        
        try:
            url = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
            tr_id = "FHKST01010200"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": self.ticker
            }
            res = self.kis_auth._url_fetch(url, tr_id, "", params)
            if res.isOK():
                out = res.getBody().output1
                bid = int(out.get('total_bidp_rsqn', 0))
                ask = int(out.get('total_askp_rsqn', 0))
                ratio = bid / ask if ask > 0 else 0
                return (bid, ask, f"B{bid:,}:A{ask:,}({ratio:.1f})")
        except Exception as e:
            logger.error(f"Failed to fetch orderbook: {e}")
        
        return (0, 0, "")
    
    def place_order(self, side: str, qty: int, price: float) -> bool:
        """Place buy or sell order."""
        if qty <= 0:
            return False
        
        mode_str = "LIVE" if self.config.live_mode else "DRY RUN"
        logger.info(f"[{mode_str}] {side.upper()} {qty} of {self.ticker} at {price}")
        
        if not self.config.live_mode:
            os.system("afplay /System/Library/Sounds/Submarine.aiff")
            return True
        
        try:
            if self.is_domestic:
                import domestic_stock_functions as d_func
                url = "/uapi/domestic-stock/v1/trading/order-cash"
                tr_id = "TTTC0012U" if side == "buy" else "TTTC0011U"
                env_type = "demo" if self.kis_auth.isPaperTrading() else "real"
                
                df = d_func.order_cash(
                    env_type, side, self.trenv.my_acct, self.trenv.my_prod,
                    self.ticker, "01", str(int(qty)), "0", "KRX"
                )
                
                if df is not None and not df.empty:
                    os.system("afplay /System/Library/Sounds/Submarine.aiff")
                    return True
            else:
                import overseas_stock_functions as o_func
                df = o_func.order_stock(
                    side, self.trenv.my_acct, self.trenv.my_prod,
                    "NASD", self.ticker, "00", str(int(qty)), str(round(price, 2))
                )
                
                if df is not None and not df.empty:
                    os.system("afplay /System/Library/Sounds/Submarine.aiff")
                    return True
                    
        except Exception as e:
            logger.error(f"Order failed: {e}")
        
        return False
    
    def check_market_hours(self) -> bool:
        """Check if market is currently open."""
        now = datetime.now()
        
        if self.is_domestic:
            close_time = now.replace(hour=15, minute=40, second=0, microsecond=0)
            return now < close_time
        else:
            close_time = now.replace(hour=6, minute=10, second=0, microsecond=0)
            if now.hour < 6 or (now.hour == 6 and now.minute < 10):
                return True
            return now.hour >= 22
    
    def _get_friction(self) -> float:
        """Get total transaction friction (fees + taxes)."""
        if self.is_domestic:
            return self.config.fees.get_domestic_friction()
        return self.config.fees.get_overseas_friction()
    
    # ========================================
    # LLM-SPECIFIC METHODS
    # ========================================
    
    def fetch_news(self) -> List[str]:
        """Fetch latest news titles for the ticker."""
        if self.is_domestic:
            url = "/uapi/domestic-stock/v1/quotations/news-title"
            tr_id = "FHKST01011800"
            params = {
                "FID_NEWS_OFER_ENTP_CODE": "2",
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
                "INFO_GB": "", "CLASS_CD": "", "NATION_CD": "US",
                "EXCHANGE_CD": "", "SYMB": self.ticker,
                "DATA_DT": datetime.now(KST).strftime("%Y%m%d"),
                "DATA_TM": "", "CTS": ""
            }
        
        res = self.kis_auth._url_fetch(url, tr_id, "", params)
        if not res.isOK():
            return []
        
        if self.is_domestic:
            output = res.getBody().output
        else:
            output = res.getBody().outblock1
        
        titles = [item.get('hts_tltl') or item.get('title') for item in output[:10] if item]
        return [t for t in titles if t]
    
    def get_market_context(self) -> Dict[str, str]:
        """Fetch macro context (indices, investor trends)."""
        context = {}
        
        try:
            if self.is_domestic:
                # KOSPI & KOSDAQ indices
                for code, name in [("0001", "KOSPI"), ("1001", "KOSDAQ")]:
                    res = self.kis_auth._url_fetch(
                        "/uapi/domestic-stock/v1/quotations/inquire-index-price",
                        "FHPUP02100000", "",
                        {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": code}
                    )
                    if res.isOK():
                        out = res.getBody().output
                        if isinstance(out, list):
                            out = out[0]
                        context[name] = f"{out['bstp_nmix_prpr']} ({out['bstp_nmix_prdy_ctrt']}%)"
                
                # Investor Trend
                res = self.kis_auth._url_fetch(
                    "/uapi/domestic-stock/v1/quotations/inquire-investor",
                    "FHKST01010900", "",
                    {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": self.ticker}
                )
                if res.isOK():
                    out = res.getBody().output
                    if isinstance(out, list):
                        out = out[0]
                    foreign = out.get('frgn_ntby_qty', '0') or '0'
                    inst = out.get('orgn_ntby_qty', '0') or '0'
                    context['Investor'] = f"Foreign: {foreign}, Inst: {inst}"
            else:
                # SPY & QQQ for overseas
                for symb, name in [("SPY", "SPY"), ("QQQ", "QQQ")]:
                    excd = "NYS" if symb == "SPY" else "NAS"
                    res = self.kis_auth._url_fetch(
                        "/uapi/overseas-price/v1/quotations/price",
                        "HHDFS00000300", "",
                        {"AUTH": "", "EXCD": excd, "SYMB": symb}
                    )
                    if res.isOK():
                        out = res.getBody().output
                        context[name] = f"{out['last']} ({out['rate']}%)"
                        
        except Exception as e:
            logger.error(f"Failed to fetch market context: {e}")
        
        return context
    
    def get_llm_sentiment(self, titles: List[str], context: Dict[str, str]) -> int:
        """
        Get GPT-based sentiment score from -5 (Strong Sell) to +5 (Strong Buy).
        Caches result if input hasn't changed.
        """
        if not titles and not context:
            return 0
        
        if self.openai_client is None:
            return 0
        
        # Check if input changed
        current_input = str(titles) + str(context)
        if current_input == self.last_input:
            return self.latest_sentiment
        
        self.last_input = current_input
        self.last_news_titles = titles
        
        market_type = "Domestic" if self.is_domestic else "Overseas"
        context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
        
        prompt = (
            f"As a pro stock analyst, evaluate the sentiment for {self.ticker} ({market_type}).\n"
            f"Market Context:\n{context_str}\n\n"
            f"Latest News:\n" + "\n".join(titles) + "\n\n"
            "Score from -5 (Strong Sell/Panic) to +5 (Strong Buy/Moon) based on both News AND Market context. "
            "Answer ONLY with the numeric score."
        )
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-5.2",
                messages=[{"role": "user", "content": prompt}]
            )
            score_str = response.choices[0].message.content.strip()
            match = re.search(r"[-+]?\d+", score_str)
            score = int(match.group()) if match else 0
            
            logger.info(
                f"GPT-5.2 Analysis -> Score: {score} | "
                f"News: {len(titles)} found | Context: {list(context.keys())}"
            )
            
            self.latest_sentiment = max(-5, min(5, score))
            return self.latest_sentiment
            
        except Exception as e:
            logger.error(f"LLM Analysis failed: {e}")
            return self.latest_sentiment
    
    def should_buy(
        self,
        current_price: float,
        rsi: float,
        bb_lower: float,
        candle_low: float
    ) -> Tuple[bool, str]:
        """Override to include sentiment check."""
        should, reason = super().should_buy(current_price, rsi, bb_lower, candle_low)
        
        if should:
            # Block buy if sentiment is negative
            if self.latest_sentiment < 0:
                logger.warning(
                    f"BUY Signal Ignored due to Bearish Sentiment ({self.latest_sentiment})"
                )
                return False, ""
            reason += f" | GPT:{self.latest_sentiment}"
        
        return should, reason
    
    def should_sell(
        self,
        current_price: float,
        rsi: float,
        bb_upper: float
    ) -> Tuple[bool, str]:
        """Override to include emergency exit on strong bearish sentiment."""
        # Emergency exit on very bearish sentiment
        if self.latest_sentiment <= -3:
            logger.warning(
                f"!!! EMERGENCY EXIT !!! Strong Bearish Score ({self.latest_sentiment})"
            )
            return True, f"EMERGENCY_EXIT(GPT:{self.latest_sentiment})"
        
        return super().should_sell(current_price, rsi, bb_upper)
    
    def run(self):
        """
        Override main loop to include LLM sentiment analysis.
        """
        logger.info(
            f"Starting LLM Scalper | Ticker: {self.ticker} | "
            f"Budget: {self.config.budget:,.0f} | "
            f"Target: {self.config.strategy.target_profit:.2%} | "
            f"LLM: {'Enabled' if self.openai_client else 'Disabled'}"
        )
        
        import time
        
        while True:
            try:
                if not self.check_market_hours():
                    logger.info("Market closed. Stopping...")
                    break
                
                if self.consecutive_errors >= self.max_allowed_errors:
                    logger.error("Too many consecutive errors. Stopping...")
                    break
                
                df = self.get_minute_chart()
                if df is None or df.empty:
                    time.sleep(10)
                    continue
                
                # Calculate indicators
                rsi, bb = self.calculate_indicators(df)
                if rsi is None or bb is None:
                    time.sleep(10)
                    continue
                
                current_price = float(df['last'].iloc[-1])
                candle_low = float(df['low'].iloc[-1]) if 'low' in df.columns else current_price
                lower_bb, upper_bb = bb
                
                # Fetch LLM context
                news_titles = self.fetch_news()
                market_context = self.get_market_context()
                self.latest_sentiment = self.get_llm_sentiment(news_titles, market_context)
                
                # Get balance
                cash, asset, _, _ = self.get_balance()
                
                # Log status
                gpt_tag = f" | GPT: {self.latest_sentiment}"
                logger.info(self.format_status_log(current_price, rsi, bb, cash, asset) + gpt_tag)
                
                # Trading logic
                if self.state == "SEARCHING":
                    should, reason = self.should_buy(current_price, rsi, lower_bb, candle_low)
                    if should:
                        logger.info(f"BUY SIGNAL: {reason}")
                        self.execute_buy(current_price, step=0)
                
                elif self.state == "HOLDING":
                    should, reason = self.should_sell(current_price, rsi, upper_bb)
                    if should:
                        logger.info(f"SELL SIGNAL: {reason}")
                        self.execute_sell(current_price)
                    elif self.should_pyramid(current_price, rsi):
                        # Don't pyramid if sentiment is bad
                        if self.latest_sentiment >= -1:
                            logger.info(f"PYRAMID SIGNAL: Step {self.current_step + 1}")
                            self.execute_buy(current_price, step=self.current_step)
                        else:
                            logger.warning(
                                f"Pyramid blocked due to sentiment ({self.latest_sentiment})"
                            )
                
                # LLM calls are expensive, use longer poll interval
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("Interrupted by user. Saving state...")
                self.state_manager.save()
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.consecutive_errors += 1
                time.sleep(10)
