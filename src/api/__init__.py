# -*- coding: utf-8 -*-
# Phase 1 - Core
from .database import Database, get_database
from .stock_master import StockMasterService, get_stock_master_service
from .collector import DataCollector, get_collector
from .scheduler import CollectionScheduler, get_scheduler

# Phase 2 - Human Index
from .youtube import YouTubeCollector, get_youtube_collector
from .naver import NaverCollector, get_naver_collector
from .dart import DartCollector, get_dart_collector
from .human_index import HumanIndexCalculator, get_human_index_calculator

# Phase 3 - Notifications
from .telegram_notifier import TelegramNotifier, get_telegram_notifier, AlertRule

# Phase 4 - AI Analysis
from .ai_analyst import AIAnalyst, get_ai_analyst

# Phase 5 - Backtest & Global Market
from .backtest import BacktestEngine, BacktestResult, get_backtest_engine
from .global_market import GlobalMarketCollector, get_global_market_collector

# Phase 6 - Journal & Simulator
from .journal import TradeJournal, get_trade_journal
from .simulator import TradingSimulator, SimulationState, get_trading_simulator

__all__ = [
    # Phase 1
    'Database',
    'get_database',
    'StockMasterService',
    'get_stock_master_service',
    'DataCollector',
    'get_collector',
    'CollectionScheduler',
    'get_scheduler',
    # Phase 2
    'YouTubeCollector',
    'get_youtube_collector',
    'NaverCollector',
    'get_naver_collector',
    'DartCollector',
    'get_dart_collector',
    'HumanIndexCalculator',
    'get_human_index_calculator',
    # Phase 3
    'TelegramNotifier',
    'get_telegram_notifier',
    'AlertRule',
    # Phase 4
    'AIAnalyst',
    'get_ai_analyst',
    # Phase 5
    'BacktestEngine',
    'BacktestResult',
    'get_backtest_engine',
    'GlobalMarketCollector',
    'get_global_market_collector',
    # Phase 6
    'TradeJournal',
    'get_trade_journal',
    'TradingSimulator',
    'SimulationState',
    'get_trading_simulator',
]
