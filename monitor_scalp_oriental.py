"""
⚠️ DEPRECATED - 이 파일은 더 이상 사용되지 않습니다.

대신 다음을 사용하세요:
    python run_scalper.py --ticker 014940 --budget 1000000 --live

이 파일은 하위 호환성을 위해 유지되지만, 새로운 기능은 추가되지 않습니다.
새 프로젝트에서는 src/scalper/ 모듈을 직접 사용하세요.

마이그레이션 방법:
    # 기존 (deprecated)
    python monitor_scalp_oriental.py --dry_run --budget 1000000

    # 새로운 방식
    python run_scalper.py --ticker 014940 --budget 1000000
    python run_scalper.py --ticker 014940 --budget 1000000 --live  # 실전
"""
import warnings
warnings.warn(
    "monitor_scalp_oriental.py is deprecated. Use 'python run_scalper.py --ticker 014940' instead.",
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
    parser.add_argument("--dry_run", action="store_true", default=True)
    parser.add_argument("--budget", type=int, default=1000000)
    args = parser.parse_args()
    
    setup_logging(name="oriental_scalp")
    
    config = ScalperConfig(
        ticker="014940",
        budget=args.budget,
        live_mode=not args.dry_run
    )
    
    scalper = UniversalScalper(config)
    scalper.run()

if __name__ == "__main__":
    main()
