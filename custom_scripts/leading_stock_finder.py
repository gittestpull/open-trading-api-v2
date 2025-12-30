import os
import sys
import pandas as pd
import logging
from typing import Optional

# Path configuration to import kis_auth
script_path = os.path.abspath(__file__)
custom_scripts_dir = os.path.dirname(script_path)
project_root = os.path.dirname(custom_scripts_dir)

# Add both root and examples_user to sys.path
if project_root not in sys.path:
    sys.path.insert(0, project_root)
examples_user_path = os.path.join(project_root, 'examples_user')
if examples_user_path not in sys.path:
    sys.path.insert(0, examples_user_path)

try:
    import kis_auth as ka
except ImportError as e:
    print(f"Import Error: {e}")
    print(f"Current Working Directory: {os.getcwd()}")
    print(f"Project Root: {project_root}")
    print(f"Search Paths: {sys.path[:5]}...") # Show first few paths
    print("Could not import kis_auth.py. Please ensure you are running from the project root.")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for KIS API
FLUCTUATION_URL = "/uapi/domestic-stock/v1/ranking/fluctuation"
VOLUME_RANK_URL = "/uapi/domestic-stock/v1/quotations/volume-rank"
VOLUME_POWER_URL = "/uapi/domestic-stock/v1/ranking/volume-power"

def fetch_fluctuation() -> pd.DataFrame:
    """Fetch top gainers."""
    logger.info("Fetching price fluctuation ranking...")
    tr_id = "FHPST01700000"
    params = {
        "fid_rsfl_rate2": "30",
        "fid_cond_mrkt_div_code": "J", 
        "fid_cond_scr_div_code": "20170",
        "fid_input_iscd": "0000",
        "fid_rank_sort_cls_code": "0000",
        "fid_input_cnt_1": "100",
        "fid_prc_cls_code": "0",
        "fid_input_price_1": "0",
        "fid_input_price_2": "10000000",
        "fid_vol_cnt": "0",
        "fid_trgt_cls_code": "0",
        "fid_trgt_exls_cls_code": "0",
        "fid_div_cls_code": "0",
        "fid_rsfl_rate1": "0" 
    }
    res = ka._url_fetch(FLUCTUATION_URL, tr_id, "", params)
    if res.isOK() and hasattr(res.getBody(), 'output'):
        return pd.DataFrame(res.getBody().output)
    return pd.DataFrame()

def fetch_volume_rank() -> pd.DataFrame:
    """Fetch top trading amount items."""
    logger.info("Fetching trading amount ranking...")
    tr_id = "FHPST01710000"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "20171",
        "FID_INPUT_ISCD": "0000",
        "FID_DIV_CLS_CODE": "0",
        "FID_BLNG_CLS_CODE": "3", # Trading Amount
        "FID_TRGT_CLS_CODE": "111111111",
        "FID_TRGT_EXLS_CLS_CODE": "0000000000",
        "FID_INPUT_PRICE_1": "",
        "FID_INPUT_PRICE_2": "",
        "FID_VOL_CNT": "",
        "FID_INPUT_DATE_1": ""
    }
    res = ka._url_fetch(VOLUME_RANK_URL, tr_id, "", params)
    if res.isOK() and hasattr(res.getBody(), 'output'):
        return pd.DataFrame(res.getBody().output)
    return pd.DataFrame()

def fetch_volume_power() -> pd.DataFrame:
    """Fetch top volume power items."""
    logger.info("Fetching volume power ranking...")
    tr_id = "FHPST01680000"
    params = {
        "fid_trgt_exls_cls_code": "0",
        "fid_cond_mrkt_div_code": "J",
        "fid_cond_scr_div_code": "20168",
        "fid_input_iscd": "0000",
        "fid_div_cls_code": "0",
        "fid_input_price_1": "",
        "fid_input_price_2": "",
        "fid_vol_cnt": "",
        "fid_trgt_cls_code": "0"
    }
    res = ka._url_fetch(VOLUME_POWER_URL, tr_id, "", params)
    if res.isOK() and hasattr(res.getBody(), 'output'):
        return pd.DataFrame(res.getBody().output)
    return pd.DataFrame()

def main():
    # 1. Auth
    ka.auth(svr="prod", product="01")
    
    # 2. Fetch Data
    df_gainers = fetch_fluctuation()
    df_volume = fetch_volume_rank()
    df_power = fetch_volume_power()
    
    logger.info(f"Results: Gainers({len(df_gainers)}), Volume({len(df_volume)}), Power({len(df_power)})")

    if df_volume.empty:
        logger.error("No trading volume/amount data available. Exiting.")
        return

    # Use df_volume as the base
    base_df = df_volume.copy()
    base_df = base_df.rename(columns={'mksc_shrn_iscd': 'stck_shrn_iscd'})
    
    # Ranks
    base_df['volume_rank'] = range(1, len(base_df) + 1)
    
    if not df_gainers.empty:
        df_gainers['gainer_rank'] = range(1, len(df_gainers) + 1)
        # In fluctuation output: stck_shrn_iscd
        base_df = pd.merge(base_df, df_gainers[['stck_shrn_iscd', 'gainer_rank']], on='stck_shrn_iscd', how='left')
    else:
        base_df['gainer_rank'] = 101
        
    if not df_power.empty:
        # In power output: stck_shrn_iscd, tday_rltv (Volume Power)
        df_power['power_rank'] = range(1, len(df_power) + 1)
        base_df = pd.merge(base_df, df_power[['stck_shrn_iscd', 'tday_rltv', 'power_rank']], on='stck_shrn_iscd', how='left')
    else:
        base_df['tday_rltv'] = 0
        base_df['power_rank'] = 101
    
    # Clean up NaNs
    base_df['prdy_ctrt'] = pd.to_numeric(base_df['prdy_ctrt'], errors='coerce').fillna(0)
    base_df['acml_tr_pbmn'] = pd.to_numeric(base_df['acml_tr_pbmn'], errors='coerce').fillna(0)
    base_df['tday_rltv'] = pd.to_numeric(base_df['tday_rltv'], errors='coerce').fillna(0)
    base_df['gainer_rank'] = base_df['gainer_rank'].fillna(101)
    base_df['power_rank'] = base_df['power_rank'].fillna(101)
    
    # Scoring
    # Volume Amount is very important for leading stocks
    # Score = (101 - volume_rank) * 2.0 + (101 - gainer_rank) * 1.0 + (tday_rltv / 2.0)
    base_df['leader_score'] = (101 - base_df['volume_rank']) * 2.0 + \
                              (101 - base_df['gainer_rank']) * 1.0 + \
                              (base_df['tday_rltv'] / 2.0)
    
    # Sort and Display
    result = base_df.sort_values(by='leader_score', ascending=False).head(20)
    
    print("\n" + "="*90)
    print(f"{'주도주 검색 결과 (Leading Stock Finder)':^90}")
    print(f"{'Current Time: ' + pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'):^90}")
    if df_gainers.empty:
        print(f"{'*** Note: Gainers data might be empty during pre-market/after-market hours. ***':^90}")
    print("="*90)
    print(f"{'Rank':<5} {'Code':<8} {'Stock Name':<20} {'Price':<10} {'Change%':<10} {'Amount(M)':<12} {'VolPower':<10}")
    print("-"*90)
    
    for i, row in enumerate(result.itertuples(), 1):
        print(f"{i:<5} {row.stck_shrn_iscd:<8} {row.hts_kor_isnm:<20} {row.stck_prpr:>8} {row.prdy_ctrt:>8.2f}% {row.acml_tr_pbmn:>12,.0f} {row.tday_rltv:>10.2f}")
    
    print("="*90)

if __name__ == "__main__":
    main()
