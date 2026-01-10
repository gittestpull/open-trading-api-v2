"""
⚠️ DEPRECATED - 이 파일은 더 이상 사용되지 않습니다.

대신 다음을 사용하세요:
    python run_scalper.py --ticker TSLA --budget 5000 --live

이 파일은 하위 호환성을 위해 유지되지만, 새로운 기능은 추가되지 않습니다.
"""
import warnings
warnings.warn(
    "monitor_scalp_tesla.py is deprecated. Use 'python run_scalper.py --ticker TSLA' instead.",
    DeprecationWarning,
    stacklevel=2
)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.logging_config import setup_logging
from src.scalper.config import ScalperConfig
from src.scalper.universal import UniversalScalper

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", default=False)
    args = parser.parse_args()
    
    setup_logging(name="tesla_scalp")
    
    config = ScalperConfig(
        ticker="TSLA",
        budget=5000,
        live_mode=args.live
    )
    
    scalper = UniversalScalper(config)
    scalper.run()

if __name__ == "__main__":
    main()
