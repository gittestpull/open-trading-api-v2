import requests
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Config Paths
KIS_CONFIG_DIR = os.path.expanduser("~/KIS/config")
LATEST_TOKEN_FILE = os.path.join(KIS_CONFIG_DIR, "KIS" + datetime.now().strftime("%Y%m%d"))
CONFIG_FILE = os.path.join(KIS_CONFIG_DIR, "kis_devlp.yaml")

def load_token():
    # Find latest non-empty token file
    import glob
    files = sorted(glob.glob(os.path.join(KIS_CONFIG_DIR, "KIS*")), reverse=True)
    for f in files:
        if os.path.getsize(f) > 0:
            with open(f, 'r') as file:
                for line in file:
                    if line.startswith("token:"):
                        return line.split(":", 1)[1].strip()
    return None

def load_config():
    # Simple YAML parser or just extract key values manually if needed
    # For now we assume the YAML structure from before
    import yaml
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)
    return config

def check_funds():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KIS 계좌 자금 조회 (Standalone)...")
    
    token = load_token()
    if not token:
        print("오류: 토큰을 찾을 수 없습니다. KIS 로그인이 필요할 수 있습니다.")
        return

    config = load_config()
    
    # API Headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": token,
        "appkey": config['my_app'],
        "appsecret": config['my_sec'],
        "tr_id": "TTTC8434R", # Balance
        "custtype": "P"
    }
    
    # Params
    params = {
        "CANO": config['my_acct_stock'],
        "ACNT_PRDT_CD": config['my_prod'],
        "AFHR_FLPR_YN": "N",
        "FUND_STTL_ICLD_YN": "N",
        "FUND_RSLT_CFYN": "N",
        "PRCS_DT": "",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": ""
    }
    
    # URL
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/trading/inquire-balance"
    
    try:
        resp = requests.post(url, headers=headers, data=json.dumps(params), verify=False)
        data = resp.json()
        
        print(f"Response Status: {resp.status_code}")
        
        if data.get('rt_cd') == '0':
            output1 = data.get('output1', [])
            if output1:
                d = output1[0]
                print("\n=== 계좌 자금 현황 ===")
                print(f"예탁증거금: {d.get('dps_crnt_bal_amt', 'N/A')} 원")
                print(f"주문가능현금: {d.get('ord_psbl_cash', 'N/A')} 원")
                print(f"증거금: {d.get('crdt_plcy_rvomny', 'N/A')} 원")
                print(f"대용금: {d.get('substamt', 'N/A')} 원")
            else:
                print("데이터 없음")
        else:
            print(f"API 오류: {data.get('msg1')}")
            
    except Exception as e:
        print(f"실행 오류: {e}")

if __name__ == '__main__':
    check_funds()
