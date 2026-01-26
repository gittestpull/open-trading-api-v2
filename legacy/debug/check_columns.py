
import urllib.request
import re

url = "https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page=1&fieldIds=market_sum&fieldIds=per&fieldIds=pbr&fieldIds=quant"

req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

print(f"Fetching {url}...")
try:
    with urllib.request.urlopen(req, timeout=10) as response:
        # Try EUC-KR first
        raw = response.read()
        try:
            html = raw.decode('euc-kr')
            print("Decoded with EUC-KR")
        except:
            html = raw.decode('utf-8', errors='ignore')
            print("Decoded with UTF-8")
        
        # Find table headers
        headers_match = re.search(r'<thead>(.*?)</thead>', html, re.DOTALL)
        if headers_match:
            headers = re.findall(r'<th[^>]*>(.*?)</th>', headers_match.group(1))
            print("Headers:", headers)
        
        # Find first row
        rows = re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL)
        for row in rows:
            if "item/main.naver" in row:
                tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
                cleaned_tds = [re.sub(r'<[^>]+>', '', td).strip() for td in tds]
                print("First Row Data:", cleaned_tds)
                break

except Exception as e:
    print(f"Error: {e}")
