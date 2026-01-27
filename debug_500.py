
import os
import sys
import asyncio

# Setup path
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

from src.web.app import create_app
from fastapi.testclient import TestClient

app = create_app(base_dir)
client = TestClient(app)

print("Calling /api/deepdive/005930 ...")
try:
    response = client.get("/api/deepdive/005930")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    import traceback
    traceback.print_exc()
