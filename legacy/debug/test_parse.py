
import re
import urllib.request

def test_parsing():
    code = "005930" # Samsung
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as response:
        html = response.read().decode('euc-kr', errors='ignore')
    
    # PER
    per_match = re.search(r'PER.*?<em>([0-9,.]+)</em>', html, re.DOTALL)
    print(f"PER Match: {per_match.group(1) if per_match else 'None'}")
    
    # Operational Rate
    op_match = re.search(r'영업이익률.*?<em[^>]*>([0-9,.-]+)%</em>', html, re.DOTALL)
    print(f"OP Rate Match: {op_match.group(1) if op_match else 'None'}")
    
    # Debt Rate
    debt_match = re.search(r'부채비율.*?<em[^>]*>([0-9,.-]+)%</em>', html, re.DOTALL)
    print(f"Debt Rate Match: {debt_match.group(1) if debt_match else 'None'}")
    
    # Reserve Rate
    rsrv_match = re.search(r'유보율.*?<em[^>]*>([0-9,.-]+)%</em>', html, re.DOTALL)
    print(f"Rsrv Rate Match: {rsrv_match.group(1) if rsrv_match else 'None'}")

if __name__ == "__main__":
    test_parsing()
