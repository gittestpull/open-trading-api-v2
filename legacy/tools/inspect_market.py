
import urllib.request
import re

def inspect_market():
    url = "https://finance.naver.com/sise/sise_market_sum.naver?sosok=1&page=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=5) as response:
        html = response.read().decode('euc-kr', errors='ignore')
    
    # Find the table header
    header_raw = re.search(r'<thead>.*?</thead>', html, re.DOTALL)
    if header_raw:
        headers = re.findall(r'<th[^>]*>(.*?)</th>', header_raw.group(0), re.DOTALL)
        print("Headers:", [h.strip() for h in headers])
    
    # Find the first data row (more flexible)
    rows = re.findall(r'<tr[^>]*>.*?</tr>', html, re.DOTALL)
    for row in rows:
        if 'mouseOver' in row:
            all_tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            print(f"TD Count: {len(all_tds)}")
            for i, td in enumerate(all_tds):
                print(f"Index {i}: {td.strip() if td else ''}")
            break

if __name__ == "__main__":
    inspect_market()
