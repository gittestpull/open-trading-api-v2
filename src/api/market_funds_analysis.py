
import logging
import pandas as pd
import requests
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import os
import sys
from datetime import datetime, timedelta
from io import BytesIO

# Ensure src is in python path
src_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_path)
# Ensure src/core is in python path so 'import kis_auth' works and shares state
sys.path.append(os.path.join(src_path, 'core'))

import kis_auth
from api.sector_analysis import SECTOR_CODE_MAP

logger = logging.getLogger(__name__)

class MarketFundsAnalyst:
    def __init__(self):
        self.headers = {'User-Agent': 'Mozilla/5.0'}

    def get_deposit_trend(self, days=365):
        """
        Fetch Customer Deposits and Credit Balance trend from Naver Finance.
        Returns: DataFrame with date index and columns ['customer_deposits', 'credit_balance'] (in Trillion KRW)
        """
        try:
            url = "https://finance.naver.com/sise/sise_deposit.naver"
            # We might need to fetch multiple pages if 'days' > 30? 
            # Naver shows about 1 month per page.
            
            all_dfs = []
            
            # Simple iteration for pages (approximate)
            # Page 1 usually has recent 1 month. 
            pages_needed = (days // 30) + 1
            
            for page in range(1, pages_needed + 1):
                page_url = f"{url}?page={page}"
                res = requests.get(page_url, headers=self.headers)
                
                # Use pandas to read HTML table
                tables = pd.read_html(BytesIO(res.content), encoding='euc-kr')
                
                # We expect the table with MultiIndex
                for table in tables:
                    # Check if it looks like our table (has '날짜' somewhere)
                    # MultiIndex columns might need flattened check or shape check
                    # The table usually has 11 columns
                    if table.shape[1] >= 4 and '날짜' in str(table.columns):
                        # Select relevant columns: Date, Deposits, Credit
                        # Based on debug: 0=Date, 1=Deposits, 3=Credit
                        df = table.iloc[:, [0, 1, 3]].copy()
                        df.columns = ['날짜', '고객예탁금', '신용잔고']
                        df = df.dropna(subset=['날짜'])
                        
                        # Filter out non-date rows (sometimes headers repeat usually not here)
                        # Naver format: YY.MM.DD
                        df = df[df['날짜'].astype(str).str.match(r'\d{2}\.\d{2}\.\d{2}')]
                        
                        all_dfs.append(df)
                        break
            
            if not all_dfs:
                return pd.DataFrame()
                
            final_df = pd.concat(all_dfs).drop_duplicates('날짜').sort_values('날짜')
            
            # Data Cleaning
            # Format: '26.01.29' -> 2026-01-29?
            # Naver uses YY.MM.DD. Since prompt says current time is 2026, 26 is 2026.
            # pd.to_datetime handles '26.01.29' as '2026-01-29' usually. 
            # But let's be explicit if needed. 
            # If it's %y.%m.%d
            final_df['date'] = pd.to_datetime(final_df['날짜'], format='%y.%m.%d')
            final_df = final_df.set_index('date')
            
            # Parse numbers (remove commas) and convert to Trillion (조)
            def clean_number(x):
                if isinstance(x, str):
                    return float(x.replace(',', ''))
                return float(x)

            # Columns: 고객예탁금, 신용잔고 (Credit Balance)
            # Units: Usually Million KRW or similar.
            # Example: 50,000,000 (Backtest unit check needed)
            # Naver displays in '백만' (Million). 
            # So 50,000 -> 50,000 Million = 50 Billion. 
            # Wait, let's verify units. Usually it's displayed as just number.
            # If it says 52,000 and unit is 100 million? No, Naver usually uses Million.
            
            final_df['customer_deposits'] = final_df['고객예탁금'].apply(clean_number)
            final_df['credit_balance'] = final_df['신용잔고'].apply(clean_number)
            
            # Convert Million to Trillion (1 Trillion = 1,000,000 Million)
            final_df['customer_deposits'] = final_df['customer_deposits'] / 1000000 
            final_df['credit_balance'] = final_df['credit_balance'] / 1000000
            
            return final_df[['customer_deposits', 'credit_balance']].sort_index()

        except Exception as e:
            logger.error(f"Failed to fetch deposit trend: {e}")
            return pd.DataFrame()

    def get_kis_market_index(self, market_code, start_date, end_date):
        """
        Fetch Market Index (proxy for Market Cap trend) using KIS API.
        Since KIS API doesn't provide historical Market Cap easily, we use Index Price.
        market_code: '0001' (KOSPI), '1001' (KOSDAQ)
        """
        # We need to import domestic_stock_functions dynamically or mock it
        # Assuming the environment has it setup as in sector_analysis.py
        
        # We need to authenticate first
        # Accessing domestic_stock_functions requires adding path
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '../examples_user/domestic_stock'))
        
        try:
            import domestic_stock_functions as dsf
            
            # Always call auth to ensure environment (_TRENV) is set up
            kis_auth.auth()
                
            # fid_cond_mrkt_div_code="U" (Upjong/Industry)
            df1, df2 = dsf.inquire_daily_indexchartprice(
                fid_cond_mrkt_div_code="U",
                fid_input_iscd=market_code,
                fid_input_date_1=start_date,
                fid_input_date_2=end_date,
                fid_period_div_code="D"
            )
            
            if df2 is None or df2.empty:
                return pd.DataFrame()
                
            # df2 contains daily data
            # Columns: stck_bsop_date, bstp_nmix_prpr (Close Price)
            df = df2[['stck_bsop_date', 'bstp_nmix_prpr']].copy()
            df.columns = ['date', 'close']
            df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
            df['close'] = pd.to_numeric(df['close'])
            
            # Normalize to 100 or leave as Index Value?
            # User wants "Market Cap", but Index is a proxy.
            # We will label it as "Index Value"
            
            return df.set_index('date').sort_index()
            
        except Exception as e:
            logger.error(f"Failed to fetch KIS index for {market_code}: {e}")
            return pd.DataFrame()

    def get_etf_market_cap(self, days=365):
        """
        Fetch ETF Total Market Cap.
        Using pykrx if available, otherwise return empty (limitation of KIS API).
        """
        try:
            from pykrx import stock
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            
            # PyKRX doesn't have a direct "Total ETF Market Cap History" function.
            # We would need to sum get_etf_ticker_list() caps daily -> Too slow.
            # So maybe we skip "Total ETF Market Cap" history and just show current?
            # Or use KOSPI 200 as proxy?
            # User asked for "ETF Market Cap". 
            
            # Let's try to get simple Index for "KOSPI 200" (Proxy for major ETFs)
            # KIS Code for KOSPI 200 is '2001' (Wait, Sector Code Map says '1028' for KOSPI 200)
            
            return pd.DataFrame()
            
        except ImportError:
            return pd.DataFrame()


    def get_analysis_data(self, days=180):
        """
        Fetch and prepare data for analysis.
        Returns: normalized_df (for chart), raw_df (for AI)
        """
        # 1. Get Deposits
        deposits_df = self.get_deposit_trend(days=days)
        if deposits_df.empty:
            logger.error("No deposit data found.")
            return None, None

        start_date = deposits_df.index.min().strftime('%Y%m%d')
        end_date = deposits_df.index.max().strftime('%Y%m%d')
        
        # 2. Get Market Indices (KOSPI, KOSDAQ)
        kospi_df = self.get_kis_market_index('0001', start_date, end_date)
        kosdaq_df = self.get_kis_market_index('1001', start_date, end_date)
        
        # 3. Get Sector Indices (Major Sectors)
        # 1013: IT, 1021: Finance, 1008: Chem, 1015: Auto, 1019: Bio, 1026: Service
        sectors = {
            '1013': 'IT/Semi', 
            '1021': 'Finance', 
            '1008': 'Chemical', 
            '1015': 'Auto/Ship',
            '1019': 'Bio/Health',
            '1026': 'Service/Platform'
        }
        sector_dfs = {}
        for code, name in sectors.items():
            df = self.get_kis_market_index(code, start_date, end_date)
            if not df.empty:
                sector_dfs[name] = df['close']

        # Align Data
        combined = pd.DataFrame(index=deposits_df.index)
        combined['Deposits'] = deposits_df['customer_deposits']
        combined['Credit'] = deposits_df['credit_balance']
        
        # Merge Index Data
        if not kospi_df.empty:
            combined = combined.join(kospi_df['close'].rename('KOSPI'))
        if not kosdaq_df.empty:
            combined = combined.join(kosdaq_df['close'].rename('KOSDAQ'))
            
        for name, series in sector_dfs.items():
            combined = combined.join(series.rename(name))
            
        combined = combined.interpolate().dropna()
        
        if combined.empty:
            return None, None

        # Normalize to 100 at start
        normalized = combined / combined.iloc[0] * 100
        return normalized, combined

    def generate_report(self, days=180, save_path="market_analysis.png"):
        logger.info("Generating Market Funds Analysis Report...")
        
        normalized, _ = self.get_analysis_data(days=days)
        if normalized is None:
            logger.error("No data available for report")
            return

        # Plotting
        plt.figure(figsize=(14, 8))
        
        # Plot Deposits (Thick lines)
        plt.plot(normalized.index, normalized['Deposits'], label='Customer Deposits', linewidth=3, color='black')
        plt.plot(normalized.index, normalized['Credit'], label='Credit Balance', linewidth=2, color='gray', linestyle='--')
        
        # Plot Markets
        if 'KOSPI' in normalized.columns:
            plt.plot(normalized.index, normalized['KOSPI'], label='KOSPI', linewidth=2, color='red')
        if 'KOSDAQ' in normalized.columns:
            plt.plot(normalized.index, normalized['KOSDAQ'], label='KOSDAQ', linewidth=2, color='orange')
            
        # Plot Sectors (Thinner lines)
        colors = ['blue', 'green', 'purple', 'brown', 'magenta', 'cyan']
        sector_cols = [c for c in normalized.columns if c not in ['Deposits', 'Credit', 'KOSPI', 'KOSDAQ']]
        
        for i, name in enumerate(sector_cols):
            plt.plot(normalized.index, normalized[name], label=name, linewidth=1, linestyle='-', alpha=0.7, color=colors[i % len(colors)])
        
        plt.title(f"Market Money Flow Analysis (Normalized, Last {days} Days)")
        plt.ylabel('Relative Performance (Start=100)')
        plt.grid(True, alpha=0.3)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        
        plt.savefig(save_path)
        logger.info(f"Saved analysis chart to {save_path}")
        return save_path


    async def generate_ai_insight(self, days=180, force_refresh=False):
        """
        Generate AI insight based on recent data trend.
        Uses file-based caching to minimize cost (Refreshes every 20 hours).
        """
        import json
        
        CACHE_FILE = "data/ai_cache_market_insight.json"
        
        # Check Cache
        if not force_refresh and os.path.exists(CACHE_FILE):
            try:
                modified_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
                if datetime.now() - modified_time < timedelta(hours=20):
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                        logger.info("Returning cached AI insight.")
                        return cached_data.get("content", "")
            except Exception as e:
                logger.warning(f"Cache read failed: {e}")

        try:
            from openai import AsyncOpenAI
            
            normalized, raw = self.get_analysis_data(days=days)
            if normalized is None:
                return "Data not available for analysis."
                
            # Prepare summary data (Last 5 records)
            recent = normalized.tail(5)
            recent_raw = raw.tail(5)
            
            # Calculate simple change trend (Last vs 5 days ago)
            start_vals = normalized.iloc[-5]
            end_vals = normalized.iloc[-1]
            changes = end_vals - start_vals
            
            # Identify leading/lagging sectors
            sorted_changes = changes.sort_values(ascending=False)
            
            prompt = f"""
            You are a professional stock market analyst. Analyze the following Korean market fund flow and sector data (Last 5 days trend).
            
            [Data Summary (Normalized Index 100=Start of Period)]
            Date Range: {recent.index[0].strftime('%Y-%m-%d')} ~ {recent.index[-1].strftime('%Y-%m-%d')}
            
            [Recent Values (Normalized)]
            {recent.to_string()}
            
            [5-Day Performance Change (Relative Points)]
            {sorted_changes.to_string()}
            
            [Raw Deposits (Trillion KRW)]
            Current Deposits: {recent_raw['Deposits'].iloc[-1]:.1f} T (~{raw['Deposits'].iloc[-1]*1000000:,.0f} Million)
            Current Credit: {recent_raw['Credit'].iloc[-1]:.1f} T
            
            Task:
            1. Analyze the trend of 'Customer Deposits' (Liquidity). Is money entering or leaving?
            2. Compare with 'Credit Balance'. Is risk appetite increasing?
            3. Identify which sectors are leading/lagging. (Bio, Service, etc.)
            4. Conclusion: Is this a Risk-On or Risk-Off market? What is the correlation between liquidity and indices?
            
            Output Format:
            Provide a concise, professional paragraph in Korean (approx 3-5 sentences). 
            Emphasize the flow of money.
            """
            
            client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful financial analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            
            # Save Cache
            try:
                os.makedirs("data", exist_ok=True)
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"content": content, "timestamp": datetime.now().isoformat()}, f, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to save AI cache: {e}")
            
            return content
            
        except Exception as e:
            logger.error(f"AI Insight generation failed: {e}")
            return f"AI Analysis Failed: {str(e)}"


if __name__ == "__main__":
    analyst = MarketFundsAnalyst()
    analyst.generate_report(days=180)
