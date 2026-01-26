
import os
import sys
import asyncio
from dotenv import load_dotenv

# Load .env if exists
load_dotenv()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath("."))

from src.api.ai_analyst import AIAnalyst

async def test_sector_analysis():
    print(f"Checking OPENAI_API_KEY: {'Found' if os.getenv('OPENAI_API_KEY') else 'MISSING'}")
    
    analyst = AIAnalyst()
    if not analyst.client:
        print("ERROR: OpenAI Client not initialized. API Key missing?")
        return

    print("Requesting sector analysis for 'Shipbuilding'...")
    try:
        result = await analyst.get_global_sector_leaders("Shipbuilding")
        print("Result:", result)
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(test_sector_analysis())
