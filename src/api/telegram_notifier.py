# -*- coding: utf-8 -*-
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import requests

from .database import Database, get_database

logger = logging.getLogger(__name__)


class TelegramNotifier:
    
    def __init__(self, bot_token: str = None, chat_id: str = None, db: Database = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.db = db or get_database()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
    
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.is_configured():
            logger.warning("[Telegram] Not configured (missing token or chat_id)")
            return False
        
        try:
            response = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("ok", False)
        except Exception as e:
            logger.error(f"[Telegram] Send failed: {e}")
            return False
    
    def format_price_alert(self, ticker: str, name: str, price: float, 
                           change_rate: float, alert_type: str) -> str:
        emoji = "🚀" if change_rate > 0 else "📉"
        direction = "상승" if change_rate > 0 else "하락"
        
        return f"""
{emoji} <b>{alert_type}</b>

<b>{name}</b> ({ticker})
현재가: {price:,.0f}원
등락률: {change_rate:+.2f}% {direction}

📊 시간: {datetime.now().strftime("%H:%M:%S")}
""".strip()
    
    def format_fomo_alert(self, stocks: List[Dict]) -> str:
        lines = ["🔥 <b>FOMO 과열 경고</b>\n"]
        
        for s in stocks[:5]:
            lines.append(
                f"• <b>{s.get('name', s['ticker'])}</b>: "
                f"FOMO {s['fomo_level']:.0f}점 | "
                f"관심도 {s['attention_score']:.0f}점"
            )
        
        lines.append(f"\n⚠️ 과열 종목 진입 주의")
        lines.append(f"📊 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        return "\n".join(lines)
    
    def format_bottom_signal(self, stocks: List[Dict]) -> str:
        lines = ["💎 <b>바닥 신호 포착</b>\n"]
        
        for s in stocks[:5]:
            lines.append(
                f"• <b>{s.get('name', s['ticker'])}</b>: "
                f"관심도 {s['attention_score']:.0f}점 | "
                f"감성 {s['crowd_sentiment']:.2f}"
            )
        
        lines.append(f"\n💡 관심 소멸 구간 - 역발상 기회")
        lines.append(f"📊 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        return "\n".join(lines)
    
    def format_trade_signal(self, ticker: str, name: str, action: str,
                            price: float, reason: str) -> str:
        emoji = "🟢" if action == "BUY" else "🔴"
        action_kr = "매수" if action == "BUY" else "매도"
        
        return f"""
{emoji} <b>{action_kr} 신호</b>

<b>{name}</b> ({ticker})
가격: {price:,.0f}원
사유: {reason}

📊 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
""".strip()
    
    def format_daily_summary(self, stats: Dict) -> str:
        return f"""
📈 <b>Daily Summary</b>

💰 총 자산: {stats.get('total_asset', 0):,.0f}원
📊 일일 수익: {stats.get('daily_pnl', 0):+,.0f}원 ({stats.get('daily_return', 0):+.2f}%)
🔢 거래 횟수: {stats.get('trade_count', 0)}회

🏆 최고 수익: {stats.get('best_stock', '-')} ({stats.get('best_return', 0):+.2f}%)
💔 최대 손실: {stats.get('worst_stock', '-')} ({stats.get('worst_return', 0):+.2f}%)

📊 {datetime.now().strftime("%Y-%m-%d")}
""".strip()
    
    async def send_price_alert(self, ticker: str, name: str, price: float,
                               change_rate: float, alert_type: str = "가격 알림") -> bool:
        message = self.format_price_alert(ticker, name, price, change_rate, alert_type)
        return self.send_message(message)
    
    async def send_fomo_alert(self, stocks: List[Dict]) -> bool:
        if not stocks:
            return False
        message = self.format_fomo_alert(stocks)
        return self.send_message(message)
    
    async def send_bottom_signal(self, stocks: List[Dict]) -> bool:
        if not stocks:
            return False
        message = self.format_bottom_signal(stocks)
        return self.send_message(message)
    
    async def send_trade_signal(self, ticker: str, name: str, action: str,
                                price: float, reason: str) -> bool:
        message = self.format_trade_signal(ticker, name, action, price, reason)
        return self.send_message(message)
    
    async def send_daily_summary(self, stats: Dict) -> bool:
        message = self.format_daily_summary(stats)
        return self.send_message(message)


class AlertRule:
    
    def __init__(self, db: Database = None):
        self.db = db or get_database()
        self.notifier = get_telegram_notifier()
    
    async def add_rule(self, name: str, condition: str, channel: str = "telegram") -> int:
        await self.db.execute("""
            INSERT INTO alert_rules (name, condition, channel, is_active)
            VALUES (?, ?, ?, 1)
        """, (name, condition, channel))
        
        result = await self.db.fetch_one(
            "SELECT id FROM alert_rules WHERE name = ? ORDER BY id DESC LIMIT 1",
            (name,)
        )
        return result['id'] if result else 0
    
    async def get_active_rules(self) -> List[Dict]:
        return await self.db.fetch_all(
            "SELECT * FROM alert_rules WHERE is_active = 1"
        )
    
    async def deactivate_rule(self, rule_id: int) -> bool:
        await self.db.execute(
            "UPDATE alert_rules SET is_active = 0 WHERE id = ?",
            (rule_id,)
        )
        return True
    
    async def check_price_alerts(self) -> List[Dict]:
        rules = await self.get_active_rules()
        triggered = []
        
        for rule in rules:
            condition = rule.get('condition', '{}')
            triggered.append(rule)
        
        return triggered


_notifier_instance: Optional[TelegramNotifier] = None

def get_telegram_notifier() -> TelegramNotifier:
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = TelegramNotifier()
    return _notifier_instance
