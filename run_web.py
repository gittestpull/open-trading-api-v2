#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from src.web import create_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = create_app(base_dir)
    
    print(\"=\" * 50)
    print(\"  Deep Dive Investment Platform\")
    print(\"=\" * 50)
    print(f\"  URL: http://localhost:8080\")
    print(\"=\" * 50)
    
    uvicorn.run(app, host=\"0.0.0.0\", port=8080, log_level=\"info\")


if __name__ == "__main__":
    main()
