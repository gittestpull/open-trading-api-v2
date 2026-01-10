#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from src.web import create_app


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = create_app(base_dir)
    
    print("=" * 50)
    print("  Scalper Dashboard")
    print("=" * 50)
    print(f"  URL: http://localhost:8000")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
