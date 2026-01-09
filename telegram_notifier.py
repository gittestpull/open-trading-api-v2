"""
Telegram Notifier for Trading Bot Dashboard
Sends alerts for errors, crashes, and important events.
"""

import os
import requests
import logging
from typing import List

logger = logging.getLogger(__name__)

# Configuration from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def is_configured() -> bool:
    """Check if Telegram notifications are configured."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

def send_alert(message: str, level: str = "INFO", ticker: str = None, buttons: List[List[dict]] = None) -> bool:
    """
    Send a Telegram alert message.
    
    Args:
        message: The message to send
        level: Alert level (INFO, WARNING, ERROR, CRITICAL)
        ticker: Optional ticker name for context
        buttons: Optional list of lists of dicts for inline keyboard
                 e.g. [[{"text": "Button", "callback_data": "data"}]]
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not is_configured():
        logger.debug("Telegram not configured, skipping alert")
        return False
    
    # Format message with emoji based on level
    emoji_map = {
        "INFO": "ℹ️",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "CRITICAL": "🚨"
    }
    emoji = emoji_map.get(level, "📌")
    
    ticker_tag = f"[{ticker}] " if ticker else ""
    formatted_message = f"{emoji} {ticker_tag}{message}"
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": formatted_message,
            "parse_mode": "HTML"
        }
        
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}
            
        response = requests.post(url, json=payload, timeout=5)
        
        if response.status_code == 200:
            logger.debug(f"Telegram alert sent: {formatted_message[:50]}...")
            return True
        else:
            logger.warning(f"Telegram API error: {response.status_code}")
            return False
            
    except Exception as e:
        logger.warning(f"Failed to send Telegram alert: {e}")
        return False

def send_crash_alert(ticker: str, exit_code: int, restart_count: int):
    """Send alert when a bot crashes."""
    message = f"Bot crashed (exit code: {exit_code})\nAuto-restart: {restart_count}/3"
    return send_alert(message, level="ERROR", ticker=ticker)

def send_watchdog_alert(ticker: str):
    """Send alert when Watchdog bites (process hung)."""
    message = "Watchdog bite! Process hung and was killed."
    return send_alert(message, level="CRITICAL", ticker=ticker)

def send_max_restart_alert(ticker: str):
    """Send alert when max restarts reached."""
    message = "Max restarts (3) reached! Manual intervention required."
    return send_alert(message, level="CRITICAL", ticker=ticker)

def send_trade_alert(ticker: str, action: str, qty: int, price: float, profit_rate: float = None):
    """Send alert for successful trades."""
    if action.upper() == "SELL" and profit_rate is not None:
        profit_str = f" ({profit_rate:+.2%})" if profit_rate else ""
        message = f"SELL {qty}주 @ {price:,.0f}원{profit_str}"
    else:
        message = f"BUY {qty}주 @ {price:,.0f}원"
    
    return send_alert(message, level="INFO", ticker=ticker)
