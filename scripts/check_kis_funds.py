import sys
import os
import json
from datetime import datetime

# OpenClaw workspace path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src', 'core'))
import kis_auth as ka

def check_funds():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] KIS 계좌 자금 조회 시작...")
    print("=" * 50)

    try:
        # Check if token is loaded (kis_auth usually loads config and token on import)
        # If not, we might need to ensure we are in 'prod' mode
        
        # 1. Balance Inquiry (예수금, D+1, D+2)
        # TR: TTTC8434R
        # URL: /uapi/domestic-stock/v1/trading/inquire-balance
        print("\n[1] 잔고 조회 (예수금/정산금)...")
        
        # Config values are usually loaded by kis_auth from ~/KIS/config/
        # We just need to call the API.
        
        tr_id = "TTTC8434R"
        api_url = "/uapi/domestic-stock/v1/trading/inquire-balance"
        
        params = {
            "CANO": "",  # Account number is usually auto-filled from config if empty? Or needs to be passed.
            "ACNT_PRDT_CD": "01",
            "AFHR_FLPR_YN": "N",
            "FUND_STTL_ICLD_YN": "N",
            "FUND_RSLT_CFYN": "N",
            "PRCS_DT": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        # Try to call the API
        try:
            # Use _url_fetch. It might need arguments. 
            # Based on examples, it takes (api_url, tr_id, tr_cont, params)
            # We need to check if we need '0' for tr_cont (no continuation)
            res = ka._url_fetch(api_url, tr_id, "0", params)
            
            print(f"Response Code: {res.get('rt_cd')}")
            
            if res.get('rt_cd') == '0':
                output1 = res.get('output1', [])
                if output1:
                    data = output1[0]
                    print("--- 자산현황 ---")
                    print(f"  예탁증거금: {data.get('dps_crnt_bal_amt', 'N/A')} 원")
                    print(f"  취득원금합계: {data.get('pchs_amnt_sum', 'N/A')} 원")
                    print(f"  손익합계: {data.get('evlu_pfls_sum', 'N/A')} 원")
                    print(f"  자산총액: {data.get('tot_asts', 'N/A')} 원")
                    
                    print("\n--- 증거금현황 ---")
                    print(f"  주문가능금액(현금): {data.get('ord_psbl_cash', 'N/A')} 원")
                    print(f"  증거금: {data.get('crdt_plcy_rvomny', 'N/A')} 원")
                    print(f"  대용금: {data.get('substamt', 'N/A')} 원")
                else:
                    print("  (output1 데이터 없음)")
            else:
                print(f"  실패: {res.get('msg1')}")
                
        except Exception as e:
            print(f"  API 호출 실패: {e}")

        # 2. Order Possible Amount (매수가능금액)
        # TR: TTTC8908R
        print("\n[2] 매수가능금액 조회...")
        
        tr_id2 = "TTTC8908R"
        api_url2 = "/uapi/domestic-stock/v1/trading/inquire-order-possible"
        
        # Similar params usually
        res2 = ka._url_fetch(api_url2, tr_id2, "0", params)
        
        if res2.get('rt_cd') == '0':
            output2 = res2.get('output2', {})
            if output2:
                print("--- 주문가능현황 ---")
                print(f"  총주문가능금액: {output2.get('ord_psbl_cash_amt', 'N/A')} 원")
                print(f"  인출가능금액: {output2.get('wdrwl_psbl_amt', 'N/A')} 원")
                # More fields...
        else:
            print(f"  실패: {res2.get('msg1')}")

    except Exception as e:
        print(f"스크립트 실행 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_funds()
