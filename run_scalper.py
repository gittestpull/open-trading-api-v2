#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.logging_config import setup_logging
from src.scalper.config import ScalperConfig, StrategyConfig, FeeConfig


def main():
    parser = argparse.ArgumentParser(description="Universal Scalping Bot v2.0")
    parser.add_argument("--ticker", required=True, help="Stock code or name")
    parser.add_argument("--budget", type=float, default=1000000, help="Trading budget")
    parser.add_argument("--target", type=float, default=0.005, help="Target profit rate")
    parser.add_argument("--buy_price", type=float, default=0, help="Manual buy price trigger")
    parser.add_argument("--orderbook", action="store_true", help="Enable orderbook filter")
    parser.add_argument("--momentum", action="store_true", help="Enable momentum mode")
    parser.add_argument("--llm", action="store_true", help="Enable LLM (GPT) sentiment analysis")
    parser.add_argument("--live", action="store_true", help="Enable live trading")
    
    args = parser.parse_args()
    
    setup_logging(name="scalper")
    
    strategy = StrategyConfig(target_profit=args.target)
    fees = FeeConfig()
    
    config = ScalperConfig(
        ticker=args.ticker,
        budget=args.budget,
        live_mode=args.live,
        manual_buy_price=args.buy_price,
        use_orderbook=args.orderbook,
        use_momentum=args.momentum,
        strategy=strategy,
        fees=fees
    )
    
    if args.llm:
        from src.scalper.llm import LLMScalper
        scalper = LLMScalper(config)
    else:
        from src.scalper.universal import UniversalScalper
        scalper = UniversalScalper(config)
    
    scalper.run()


if __name__ == "__main__":
    main()
