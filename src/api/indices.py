# -*- coding: utf-8 -*-
import httpx
import asyncio
from typing import Dict, Any

async def fetch_indices() -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        # 1. KOSPI & KOSDAQ & USD (Naver)
        urls = {
            "KOSPI": "https://m.stock.naver.com/api/index/KOSPI/basic",
            "KOSDAQ": "https://m.stock.naver.com/api/index/KOSDAQ/basic",
            "USD": "https://m.stock.naver.com/api/index/FX_USDKRW/basic"
        }
        
        results = {}
        
        for name, url in urls.items():
            try:
                resp = await client.get(url, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    results[name] = {
                        "now": data.get("now"),
                        "change": data.get("compareToPreviousClosePrice"),
                        "rate": data.get("fluctuationsRatio"),
                        "status": data.get("compareToPreviousPrice", {}).get("text")
                    }
            except Exception as e:
                print(f"Error fetching {name}: {e}")
        
        # 2. Bitcoin (Upbit)
        try:
            resp = await client.get("https://api.upbit.com/v1/ticker?markets=KRW-BTC", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()[0]
                results["BTC"] = {
                    "now": data.get("trade_price"),
                    "change": data.get("signed_change_price"),
                    "rate": data.get("signed_change_rate") * 100,
                    "status": "RISE" if data.get("change") == "RISE" else "FALL" if data.get("change") == "FALL" else "EVEN"
                }
        except Exception as e:
            print(f"Error fetching BTC: {e}")
            
    return results

if __name__ == "__main__":
    import asyncio
    print(asyncio.run(fetch_indices()))
