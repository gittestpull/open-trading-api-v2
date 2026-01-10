# -*- coding: utf-8 -*-
"""
Open Trading API - 한국투자증권 트레이딩 봇 패키지

이 패키지는 한국투자증권 Open API를 활용한 자동매매 시스템을 제공합니다.

Modules:
    scalper: 스캘핑 전략 관련 모듈
    utils: 유틸리티 함수들
    api: API 래퍼 및 인증
"""

__version__ = "2.0.0"
__author__ = "Korea Investment & Securities"

from .scalper import UniversalScalper, LLMScalper
from .utils import setup_logging

__all__ = [
    "UniversalScalper",
    "LLMScalper", 
    "setup_logging",
]
