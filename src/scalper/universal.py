# -*- coding: utf-8 -*-
import sys
import os
from datetime import datetime
import pytz
from typing import Tuple
import logging

KST = pytz.timezone('Asia/Seoul')
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'examples_user'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'examples_user', 'domestic_stock'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'examples_user', 'overseas_stock'))

import kis_auth
from stock_code_lookup import StockMaster

from .base import BaseScalper
from .config import ScalperConfig, NXT_PRE_START, NXT_PRE_END, NXT_POST_START, NXT_POST_END, KRX_START, KRX_END


logger = logging.getLogger(__name__)


class UniversalScalper(BaseScalper):
    
    def __init__(self, config: ScalperConfig):
        self._resolve_ticker(config)
        self.is_domestic = self._is_domestic_ticker(config.ticker)
        self.current_exchange = "KRX"
        
        if self.is_domestic:
            self.friction = config.fees.get_domestic_friction()
        else:
            self.friction = config.fees.get_overseas_friction()
        
        super().__init__(config)
    
    def _resolve_ticker(self, config: ScalperConfig):
        ticker = config.ticker
        if not ticker.isdigit():
            sm = StockMaster()
            found_code = sm.get_code(ticker)
            if found_code:
                logger.info(f"Resolved '{ticker}' to '{found_code}'")
                config.ticker = found_code
    
    def _is_domestic_ticker(self, ticker: str) -> bool:
        return ticker.isdigit() and len(ticker) == 6
    
    def _initialize_api(self):
        kis_auth.auth()
        self.trenv = kis_auth.getTREnv()
    
    def _get_friction(self) -> float:
        return self.friction
    
    def get_minute_chart(self) -> pd.DataFrame:
        if self.is_domestic:
            mrkt_code = "NX" if self.current_exchange == "NXT" else "J"
            url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
            tr_id = "FHKST03010200"
            params = {
                "FID_COND_MRKT_DIV_CODE": mrkt_code,
                "FID_INPUT_ISCD": self.ticker,
                "FID_INPUT_HOUR_1": datetime.now(KST).strftime("%H%M%S"),
                "FID_PW_DATA_INCU_YN": "Y",
                "FID_ETC_CLS_CODE": ""
            }
            cols_map = {
                'stck_prpr': 'last', 
                'stck_oprc': 'open', 
                'stck_hgpr': 'high', 
                'stck_lwpr': 'low', 
                'cntg_vol': 'vol'
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
            cols_map = {
                'last': 'last', 
                'open': 'open', 
                'high': 'high', 
                'low': 'low', 
                'evol': 'vol'
            }
        
        res = kis_auth._url_fetch(url, tr_id, "", params)
        if not res.isOK():
            logger.error(f"Chart fetch failed: {res.getErrorMessage()}")
            return pd.DataFrame()
        
        output2 = res.getBody().output2
        df = pd.DataFrame(output2)
        df = df.rename(columns=cols_map)
        
        for col in ['last', 'open', 'high', 'low', 'vol']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        min_len = 20
        if len(df) < min_len and not df.empty:
            needed = min_len - len(df)
            oldest_row = df.iloc[-1].to_dict()
            padding = pd.DataFrame([oldest_row] * needed)
            df = pd.concat([df, padding], ignore_index=True)
        
        return df.iloc[::-1].reset_index(drop=True)
    
    def get_current_price(self) -> float:
        df = self.get_minute_chart()
        if df.empty:
            return 0
        return df['last'].iloc[-1]
    
    def get_balance(self) -> Tuple[float, float, float, float]:
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
                    "TR_CRCY_CD": "USD",
                    "CTX_AREA_FK200": "",
                    "CTX_AREA_NK200": ""
                }
            
            res = kis_auth._url_fetch(url, tr_id, "", params)
            if not res.isOK():
                return self.cached_balance
            
            if self.is_domestic:
                out2 = res.getBody().output2[0]
                cash = int(out2.get('prvs_rcdl_excc_amt', 0))
                asset = int(out2.get('tot_evlu_amt', 0))
                
                out1 = res.getBody().output1
                real_avg = 0
                real_qty = 0
                for item in out1:
                    if item.get('pdno') == self.ticker:
                        real_avg = float(item.get('pchs_avg_pric', 0))
                        real_qty = int(item.get('hldg_qty', 0))
                        break
            else:
                out2 = res.getBody().output2
                cash = float(out2.get('ovrs_tot_dnca_amt', 0))
                asset = float(out2.get('tot_evlu_amt', 0))
                
                out1 = res.getBody().output1
                real_avg = 0
                real_qty = 0
                for item in out1:
                    if item.get('ovrs_pdno') == self.ticker:
                        real_avg = float(item.get('pchs_avg_pric', 0))
                        real_qty = int(float(item.get('ovrs_cblc_qty', 0)))
                        break
            
            self.cached_balance = (cash, asset, real_avg, real_qty)
            return self.cached_balance
            
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")
            return self.cached_balance
    
    def place_order(self, side: str, qty: int, price: float) -> bool:
        if qty <= 0:
            return False
        
        mode_str = "LIVE" if self.config.live_mode else "DRY RUN"
        logger.info(f"[{mode_str}] {side.upper()} {qty} x {self.ticker} @ {price:.2f}")
        
        if not self.config.live_mode:
            self._play_sound()
            return True
        
        try:
            if self.is_domestic:
                url = "/uapi/domestic-stock/v1/trading/order-cash"
                tr_id = "TTTC0012U" if side == "buy" else "TTTC0011U"
                params = {
                    "CANO": self.trenv.my_acct,
                    "ACNT_PRDT_CD": self.trenv.my_prod,
                    "PDNO": self.ticker,
                    "ORD_DVSN": "00",
                    "ORD_QTY": str(int(qty)),
                    "ORD_UNPR": str(int(price)),
                    "EXCG_ID_DVSN_CD": "KRX" if self.current_exchange != "NXT" else "NXT"
                }
            else:
                url = "/uapi/overseas-stock/v1/trading/order"
                tr_id = "TTTT1002U" if side == "buy" else "TTTT1006U"
                params = {
                    "CANO": self.trenv.my_acct,
                    "ACNT_PRDT_CD": self.trenv.my_prod,
                    "OVRS_EXCG_CD": "NASD",
                    "PDNO": self.ticker,
                    "ORD_QTY": str(int(qty)),
                    "OVRS_ORD_UNPR": str(round(price, 2)),
                    "ORD_DVSN": "00"
                }
                if side == "sell":
                    params["SLL_TYPE"] = "00"
            
            res = kis_auth._url_fetch(url, tr_id, "", params, postFlag=True)
            
            if res.isOK():
                self._play_sound()
                logger.info(f"Order success: {res.getBody().output}")
                return True
            else:
                logger.error(f"Order failed: {res.getErrorMessage()}")
                return False
                
        except Exception as e:
            logger.error(f"Order error: {e}")
            return False
    
    def get_orderbook(self) -> Tuple[int, int, str]:
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
                bid_total = int(out.get('total_bidp_rsqn', 0))
                ask_total = int(out.get('total_askp_rsqn', 0))
                ratio = bid_total / ask_total if ask_total > 0 else 0
                info_str = f"B{bid_total:,}:A{ask_total:,}({ratio:.1f})"
                return bid_total, ask_total, info_str
        except Exception as e:
            logger.error(f"Orderbook error: {e}")
        
        return 0, 0, ""
    
    def check_market_hours(self) -> bool:
        now = datetime.now(KST)
        current_time = now.strftime("%H:%M")
        
        if self.is_domestic:
            if NXT_PRE_START <= current_time < NXT_PRE_END:
                self.current_exchange = "NXT"
                return True
            elif KRX_START <= current_time <= KRX_END:
                self.current_exchange = "KRX"
                return True
            elif NXT_POST_START <= current_time <= NXT_POST_END:
                self.current_exchange = "NXT"
                return True
            return False
        else:
            hour = now.hour
            if hour < 6 or (hour == 6 and now.minute < 10):
                return True
            return hour >= 22
    
    def _play_sound(self):
        try:
            os.system("afplay /System/Library/Sounds/Glass.aiff 2>/dev/null &")
        except:
            pass
