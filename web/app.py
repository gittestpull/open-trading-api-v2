
"""
Trading Bot Web Dashboard - FastAPI Backend
"""
import os
import json
import asyncio
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
import secrets
import sys
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Project paths
BASE_DIR = Path(__file__).parent.parent
LOGS_DIR = BASE_DIR / "logs"
SCALP_DATA_DIR = BASE_DIR / "scalp_data"

# Add project root and examples_user to path
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "examples_user"))

try:
    import kis_auth
    from stock_code_lookup import StockMaster
    import telegram_notifier
    import trade_history
    from stock_screener import StockScreener
except ImportError as e:
    logging.error(f"Failed to import core modules: {e}")

# Initialize Stock Screener
try:
    stock_screener = StockScreener()
except Exception as e:
    logging.error(f"Failed to initialize StockScreener: {e}")
    stock_screener = None


# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
SCALP_DATA_DIR.mkdir(exist_ok=True)

# Password Configuration
# Generate a random secure password if not provided in ENV
DEFAULT_SECURE_PASS = secrets.token_urlsafe(16)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", DEFAULT_SECURE_PASS)
HONEYPOT_PASSWORD = "trading123"

if DASHBOARD_PASSWORD == DEFAULT_SECURE_PASS:
    logger.warning(f"⚠️  NO PASSWORD SET! Generated secure password: {DASHBOARD_PASSWORD}")
    logger.warning("Please set DASHBOARD_PASSWORD environment variable for persistence.")

# Security
security = HTTPBasic()

# Blocked IPs file (persisted)
BLOCKED_IPS_FILE = BASE_DIR / "web" / "blocked_ips.json"
MAX_LOGIN_ATTEMPTS = 2

def load_blocked_ips() -> Dict[str, dict]:
    """Load blocked IPs from file"""
    if BLOCKED_IPS_FILE.exists():
        try:
            with open(BLOCKED_IPS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_blocked_ips(blocked: Dict[str, dict]):
    """Save blocked IPs to file"""
    try:
        with open(BLOCKED_IPS_FILE, "w") as f:
            json.dump(blocked, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save blocked IPs: {e}")


# Login attempt tracking
login_attempts: Dict[str, int] = {}
blocked_ips: Dict[str, dict] = load_blocked_ips()

def get_client_ip(request: Request) -> str:
    """
    Get client IP. 
    SECURITY NOTE: Trusted Proxy is not configured. 
    To prevent spoofing via X-Forwarded-For, we imply direct connection by default.
    Only use X-Forwarded-For if you are sure you are behind a trusted reverse proxy (Nginx).
    """
    # For this setup (Host Networking or Direct Docker Port Mapping), request.client.host is safer.
    # checking 'X-Forwarded-For' blindly is dangerous.
    # If user wants to use proxy, they should enable a flag. For now, we prefer safety.
    return request.client.host if request.client else "unknown"

def check_rate_limit(request: Request):
    """Check if IP is permanently blocked"""
    ip = get_client_ip(request)
    if ip in blocked_ips:
        logger.warning(f"Blocked IP {ip} attempted access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="🚫 IP 영구 차단됨. 관리자에게 문의하세요."
        )
    return ip

# Telegram Notification Helpers
def send_telegram_alert(message: str, buttons: List[List[dict]] = None):
    """Send security alert via Telegram"""
    try:
        config_path = BASE_DIR / "kis_devlp.yaml"
        if not config_path.exists():
            return
            
        import yaml
        import urllib.request
        import json
        import ssl

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            token = config.get("telegram_token")
            chat_id = config.get("telegram_chat_id")
            
        if not token or not chat_id:
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}
            
        json_data = json.dumps(payload).encode("utf-8")
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, context=ctx) as response:
            pass
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")

def record_failed_attempt(ip: str):
    """Record a failed login attempt - permanent ban after MAX attempts"""
    if ip not in login_attempts:
        login_attempts[ip] = 0
    
    login_attempts[ip] += 1
    logger.warning(f"Failed login attempt from {ip} ({login_attempts[ip]}/{MAX_LOGIN_ATTEMPTS})")
    
    if login_attempts[ip] >= MAX_LOGIN_ATTEMPTS:
        blocked_ips[ip] = {
            "blocked_at": datetime.now().isoformat(),
            "attempts": login_attempts[ip]
        }
        save_blocked_ips(blocked_ips)
        logger.warning(f"🚫 IP {ip} PERMANENTLY BLOCKED")
        
        # Build Blocked List Summary
        blocked_list_str = "\n".join([f"- `{b_ip}` ({data['blocked_at']})" for b_ip, data in blocked_ips.items()])
        
        msg = (
            f"🚨 **SECURITY ALERT**\n\n"
            f"🚫 **IP BLOCKED**: `{ip}`\n"
            f"Reason: Excessive Login Failures ({MAX_LOGIN_ATTEMPTS} attempts)\n\n"
            f"📋 **Current Blocked IPs**:\n{blocked_list_str}"
        )
        
        buttons = [
            [{"text": f"✅ IP {ip} 차단 해제", "callback_data": f"unblock_ip:{ip}"}],
            [{"text": "🧹 전체 차단 해제", "callback_data": "unblock_all"}]
        ]
        send_telegram_alert(msg, buttons=buttons)


def clear_failed_attempts(ip: str):
    """Clear failed attempts on successful login"""
    if ip in login_attempts:
        del login_attempts[ip]

def verify_password(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    """Password verification with rate limiting"""
    ip = check_rate_limit(request)
    
    # HONEYPOT CHECK
    # Check for the known vulnerable password "trading123"
    if secrets.compare_digest(credentials.password, HONEYPOT_PASSWORD):
        logger.critical(f"🚨 HONEYPOT TRIGGERED! IP {ip} used known vulnerable password '{HONEYPOT_PASSWORD}'. Blocking immediately.")
        
        # Immediate Permanent Block
        blocked_ips[ip] = {
            "blocked_at": datetime.now().isoformat(),
            "attempts": 999,
            "reason": "HONEYPOT_TRIGGERED"
        }
        save_blocked_ips(blocked_ips)
        
        # Send Alert
        blocked_list_str = "\n".join([f"- `{b_ip}`" for b_ip in blocked_ips.keys()])
        msg = (
            f"🚨 **HONEYPOT TRIGGERED!** 🐝\n\n"
            f"🚫 **IP BLOCKED**: `{ip}`\n"
            f"Reason: Used vulnerable password 'trading123'\n\n"
            f"📋 **Current Blocked IPs**:\n{blocked_list_str}"
        )
        
        buttons = [[{"text": f"✅ IP {ip} 차단 해제 (Unblock)", "callback_data": f"unblock_ip:{ip}"}]]
        send_telegram_alert(msg, buttons=buttons)
        
        # Return fake 401 to confuse or standard 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Basic"},
        )

    correct_password = secrets.compare_digest(credentials.password, DASHBOARD_PASSWORD)
    
    if not correct_password:
        record_failed_attempt(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    clear_failed_attempts(ip)
    return credentials.username

def validate_ticker(ticker: str) -> str:
    """Validate ticker to prevent command injection"""
    # Allow alphanumeric, Korean characters, and simple separators like dot or dash
    # Reject shell metacharacters: ; | & $ > < ` \ !
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")
        
    # Regex: Alphanumeric (English/Korean) + simple dash/dot
    # Used for filenames and display, so keep it strict.
    pattern = re.compile(r'^[a-zA-Z0-9가-힣\-\.]+$')
    if not pattern.match(ticker):
        logger.warning(f"Invalid ticker format rejected: {ticker}")
        raise HTTPException(status_code=400, detail="Invalid ticker format. Use letters, numbers, or Korean only.")
    
    return ticker


# Pydantic Models
class BotConfig(BaseModel):
    ticker: str
    budget: int
    target: float = 0.02
    live: bool = True
    buy_price: float = 0 # Deprecated, kept for backward compatibility during transition
    buy_prices: List[float] = [] # New: Support multiple prices
    orderbook: bool = False
    momentum: bool = False
    ignore_market: bool = False


class BotStatus(BaseModel):
    id: str
    ticker: str
    ticker_code: Optional[str] = None
    budget: int
    target: float
    live: bool
    status: str  # STOPPED, RUNNING, SEARCHING, HOLDING, etc.
    pid: Optional[int] = None
    avg_price: float = 0
    total_qty: int = 0
    current_price: float = 0
    profit_rate: float = 0
    buy_price: float = 0 # Deprecated
    buy_prices: List[float] = [] # New
    orderbook: bool = False
    momentum: bool = False
    ignore_market: bool = False
    current_exchange: Optional[str] = "KRX"
    last_update: Optional[str] = None
    created_at: str


class SellRequest(BaseModel):
    price: int = 0  # 0 = Market Price
    skip_trade: bool = False # If True, only reset local state without selling


# Bot Manager
class BotManager:
    def __init__(self):
        self.bots: Dict[str, dict] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.sm = StockMaster()  # Initialize StockMaster
        try:
            kis_auth.auth() # Ensure KIS API is authorized for price fetching
        except Exception as e:
            logger.error(f"Failed to auth KIS: {e}")
        self._load_saved_bots()
        
        # Auto-Restart Recovery
        try:
            running_bots = [b_id for b_id, b in self.bots.items() if b.get("status") == "RUNNING"]
            if running_bots:
                logger.info(f"🔄 Found {len(running_bots)} bots to recover: {running_bots}")
                for bot_id in running_bots:
                    logger.info(f"🚀 Auto-restarting bot {bot_id}...")
                    try:
                        self.start_bot(bot_id)
                        import time
                        time.sleep(1) # Prevent CPU spike
                    except Exception as e:
                        logger.error(f"❌ Failed to auto-recover bot {bot_id}: {e}")
        except Exception as e:
            logger.error(f"Critical error during auto-recovery: {e}")
    
    def _load_saved_bots(self):
        """Load bots from saved config"""
        config_file = BASE_DIR / "web" / "bots_config.json"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    self.bots = json.load(f)
                
                # Migration: Convert target profit from percentage to decimal if >= 0.1
                # Migration 2: Support multiple buy prices
                migrated = False
                for bot in self.bots.values():
                    if bot.get("target", 0) >= 0.1:
                        bot["target"] = bot["target"] / 100.0
                        migrated = True
                    
                    if "buy_prices" not in bot:
                        # Migrate single buy_price to list
                        old_price = bot.get("buy_price", 0)
                        bot["buy_prices"] = [old_price] if old_price > 0 else []
                        migrated = True
                
                if migrated:
                    self._save_bots()
                    logger.info("Migrated bot targets from percentage to decimal")
                    
                logger.info(f"Loaded {len(self.bots)} bots from config")
            except Exception as e:
                logger.error(f"Failed to load bots config: {e}")
    
    def _save_bots(self):
        """Save bots config to file"""
        config_file = BASE_DIR / "web" / "bots_config.json"
        try:
            with open(config_file, "w") as f:
                # Don't save process-related info
                save_data = {}
                for bot_id, bot in self.bots.items():
                    save_data[bot_id] = {k: v for k, v in bot.items() if k != 'pid'}
                json.dump(save_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save bots config: {e}")
    
    def add_bot(self, config: BotConfig) -> str:
        """Add a new bot configuration"""
        # Validate Input
        validate_ticker(config.ticker)
        
        bot_id = f"bot_{config.ticker}_{datetime.now().strftime('%H%M%S')}"
        self.bots[bot_id] = {
            "id": bot_id,
            "ticker": config.ticker,
            "ticker_code": None,
            "budget": config.budget,
            "target": config.target / 100.0 if config.target >= 0.1 else config.target,
            "live": config.live,
            "buy_price": getattr(config, "buy_price", 0),
            "orderbook": getattr(config, "orderbook", False),
            "momentum": getattr(config, "momentum", False),
            "ignore_market": getattr(config, "ignore_market", False),
            "status": "STOPPED",
            "pid": None,
            "avg_price": 0,
            "total_qty": 0,
            "current_price": 0,
            "profit_rate": 0,
            "created_at": datetime.now().isoformat()
        }
        self._save_bots()
        return bot_id
    
    def remove_bot(self, bot_id: str) -> bool:
        """Remove a bot"""
        if bot_id in self.bots:
            self.stop_bot(bot_id)
            del self.bots[bot_id]
            self._save_bots()
            return True
        return False
    
    def update_bot(self, bot_id: str, config: BotConfig) -> bool:
        """Update a bot configuration (only properly works if stopped)"""
        if bot_id not in self.bots:
            return False
            
        # Validate Input
        validate_ticker(config.ticker)
        
        # Don't allow changing running bots for safety (or implement dynamic reload later)
        if self.bots[bot_id]["status"] == "RUNNING":
            # For now, just block update or warn. Let's allow update but user must restart.
            pass

        bot = self.bots[bot_id]
        bot["ticker"] = config.ticker
        bot["budget"] = config.budget
        bot["target"] = config.target / 100.0 if config.target >= 0.1 else config.target
        bot["live"] = config.live
        bot["buy_price"] = config.buy_price
        bot["momentum"] = config.momentum
        bot["ignore_market"] = config.ignore_market
        
        self._save_bots()
        logger.info(f"Updated bot {bot_id}")
        return True

    def start_bot(self, bot_id: str) -> bool:
        """Start a trading bot process"""
        if bot_id not in self.bots:
            return False
        
        bot = self.bots[bot_id]
        if bot_id in self.processes and self.processes[bot_id].poll() is None:
            logger.info(f"Bot {bot_id} is already running")
            return True
            
        # Prevent multiple bots for the same ticker
        target_code = self.sm.get_code(bot['ticker'])
        for other_id, other_bot in self.bots.items():
            if other_id == bot_id: continue
            
            # Check if running
            if other_bot.get("status") == "RUNNING" or (other_id in self.processes and self.processes[other_id].poll() is None):
                other_code = other_bot.get("ticker_code") or self.sm.get_code(other_bot.get("ticker"))
                if other_code and other_code == target_code:
                    logger.warning(f"🚫 Prevented start: Bot {other_id} is already running for {target_code}")
                    return False
        
        if bot.get("strategy") == "LLM":
            script = "monitor_scalp_llm.py"
        else:
            script = "monitor_scalp_universal.py"
            
        cmd = [
            "uv", "run", "python", script,
            "--ticker", bot["ticker"],
            "--budget", str(bot["budget"]),
            "--target", str(bot["target"]),
            "--bot_id", bot_id
        ]
        
        # Extended options
        buy_prices = bot.get("buy_prices", [])
        # Support legacy buy_price if list is empty
        if not buy_prices and bot.get("buy_price", 0) > 0:
            buy_prices = [bot["buy_price"]]
            
        for bp in buy_prices:
            if bp > 0:
                cmd.extend(["--buy_price", str(bp)])
        
        if bot.get("orderbook", False):
            cmd.append("--orderbook")
            
        if bot.get("momentum", False):
            cmd.append("--momentum")

        if bot.get("ignore_market", False):
            cmd.append("--ignore_market")

        if bot["live"]:
            cmd.append("--live")
        
        try:
            # Start process
            process = subprocess.Popen(
                cmd,
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1
            )
            self.processes[bot_id] = process
            bot["pid"] = process.pid
            bot["status"] = "RUNNING"
            self._save_bots()
            logger.info(f"Started bot {bot_id} with PID {process.pid}")
            return True
        except Exception as e:
            logger.error(f"Failed to start bot {bot_id}: {e}")
            bot["status"] = "ERROR"
            return False
    
    def stop_bot(self, bot_id: str) -> bool:
        """Stop a trading bot process"""
        if bot_id not in self.bots:
            return False
        
        bot = self.bots[bot_id]
        
        if bot_id in self.processes:
            process = self.processes[bot_id]
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            del self.processes[bot_id]
        
        bot["status"] = "STOPPED"
        bot["pid"] = None
        self._save_bots()
        logger.info(f"Stopped bot {bot_id}")
        return True

    def perform_sell(self, bot: dict, price: int = 0) -> bool:
        """Perform sell order (Market or Limit) with NXT session support"""
        try:
            qty = bot.get("total_qty", 0)
            if qty <= 0:
                return True
                
            code = bot.get("ticker_code")
            if not code:
                return False

            # Detect Session / Exchange
            # current_exchange is synced in get_bot_status from state file
            current_exch = bot.get("current_exchange", "KRX")
            
            # Construct Order Payload
            tr_id = "VTTC0801U" if not bot["live"] else "TTTC0801U"
            
            # Get Account Config
            import yaml
            with open(BASE_DIR / "kis_devlp.yaml", "r") as f:
                cfg = yaml.safe_load(f)
                
            account_num = cfg.get("my_paper_stock") if not bot["live"] else cfg.get("my_acct_stock")
            if not account_num: 
                logger.error("Account number missing for sell")
                return False

            # API Endpoint
            url = "/uapi/domestic-stock/v1/trading/order-cash"
            
            # Determine Order Division and Price
            # NXT only supports Limit Order (00)
            if current_exch == "NXT":
                ord_dvsn = "00"
                # If Market Sell (price=0) requested during NXT, use current_price as limit
                ord_unpr = str(int(price)) if price > 0 else str(int(bot.get("current_price", 0)))
                if ord_unpr == "0":
                    logger.error(f"Cannot sell {code} on NXT: Price is missing")
                    return False
            else:
                ord_dvsn = "01" if price == 0 else "00"
                ord_unpr = "0" if price == 0 else str(price)
            
            params = {
                "CANO": account_num,
                "ACNT_PRDT_CD": "01",
                "PDNO": code,
                "ORD_DVSN": ord_dvsn,
                "ORD_QTY": str(qty),
                "ORD_UNPR": ord_unpr,
                "EXCG_ID_DVSN_CD": current_exch  # Pass "NXT" or "KRX"
            }
            
            res = kis_auth._url_fetch(url, tr_id, "", params, postFlag=True)
            
            if res.isOK():
                type_str = "Market" if ord_dvsn == "01" else f"Limit({ord_unpr})"
                logger.info(f"✅ Emergency Sell Success [{current_exch}]: {code} {qty}ea [{type_str}]")
                return True
            else:
                logger.error(f"❌ Emergency Sell Failed [{current_exch}]: {res.getBody()}")
                return False
                
        except Exception as e:
            logger.error(f"Emergency sell error: {e}")
            return False



    
    def get_bot_status(self, bot_id: str) -> Optional[dict]:
        """Get current status of a bot with robust state syncing"""
        if bot_id not in self.bots:
            return None
        
        bot = self.bots[bot_id]
        
        # Check if process is still running
        if bot_id in self.processes:
            process = self.processes[bot_id]
            if process.poll() is not None:
                bot["status"] = "STOPPED"
                bot["pid"] = None
                del self.processes[bot_id]
        
        # Resolve Ticker Code if missing or needed for verification
        resolved_code = None
        if bot["ticker"].isdigit():
            resolved_code = bot["ticker"]
        else:
            # Try to resolve code using StockMaster if we haven't already or to verify
            code = self.sm.get_code(bot["ticker"])
            if code:
                resolved_code = code
        
        # SELF-HEALING: If we resolved a code, ensure bot config matches
        # This fixes the 'Inospace' -> '014940' contamination issue
        if resolved_code and bot.get("ticker_code") != resolved_code:
            logger.warning(f"Bot {bot_id} ticker_code mismatch! {bot.get('ticker_code')} != {resolved_code}. Fixing...")
            bot["ticker_code"] = resolved_code
            # Reset potentially contaminated data
            bot["avg_price"] = 0
            bot["total_qty"] = 0
            bot["current_price"] = 0
            bot["profit_rate"] = 0
            self._save_bots()

        # Now try to read the CORRECT state file
        target_code = resolved_code if resolved_code else bot.get("ticker_code")
        
        if target_code:
            state_file = SCALP_DATA_DIR / f"state_{target_code}.json"
            if state_file.exists():
                try:
                    with open(state_file, "r") as f:
                        state = json.load(f)
                    
                    # Update bot state from file
                    bot["avg_price"] = round(state.get("avg_buy_price", 0))
                    bot["total_qty"] = state.get("total_qty", 0)
                    
                    # Read real-time price if available
                    if state.get("current_price", 0) > 0:
                        bot["current_price"] = state.get("current_price")
                        
                    bot["current_exchange"] = state.get("current_exchange", "KRX")
                    bot["last_update"] = state.get("last_update", "")
                    
                    if bot["status"] == "RUNNING":
                        bot["status"] = state.get("state", "RUNNING")
                        
                except Exception as e:
                    logger.debug(f"Failed to read state file {state_file}: {e}")
        
        # Proactive price fetching for stopped bots or if current_price is 0
        should_fetch = (bot.get("status") == "STOPPED") or (bot.get("current_price", 0) == 0)
        
        if should_fetch and target_code:
            live_price = self._fetch_current_price(target_code)
            if live_price > 0:
                bot["current_price"] = live_price
            
        # Ensure profit rate is calculated if we have price and avg_price
        if bot["current_price"] > 0 and bot["avg_price"] > 0:
            bot["profit_rate"] = (bot["current_price"] / bot["avg_price"]) - 1
            
        return bot

    def _fetch_current_price(self, ticker_code: str) -> float:
        """Fetch current price from KIS API for domestic stocks"""
        try:
            url = "/uapi/domestic-stock/v1/quotations/inquire-price"
            tr_id = "FHKST01010100"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": ticker_code
            }
            res = kis_auth._url_fetch(url, tr_id, "", params)
            if res.isOK():
                return float(res.getBody().output.get('stck_prpr', 0))
        except Exception:
            pass
        return 0
    
    def get_all_bots(self) -> List[dict]:
        """Get status of all bots"""
        return [self.get_bot_status(bot_id) for bot_id in self.bots]
    
    async def monitor_processes(self):
        """Background task to monitor and restart crashed bots (Keep-Alive)"""
        import asyncio
        restart_counts = {}  # bot_id -> (count, first_restart_time)
        MAX_RESTARTS = 3
        COOLDOWN_PERIOD = 300  # 5 minutes
        
        while True:
            await asyncio.sleep(5)  # Check every 5 seconds
            
            for bot_id in list(self.processes.keys()):
                process = self.processes.get(bot_id)
                if process is None:
                    continue
                    
                exit_code = process.poll()
                if exit_code is not None:
                    # Process has died
                    bot = self.bots.get(bot_id, {})
                    ticker = bot.get("ticker", "Unknown")
                    
                    # 1. Check for normal exit (exit code 0)
                    if exit_code == 0:
                        logger.info(f"👋 [{ticker}] Bot finished normally (exit code 0). Stopping.")
                        bot["status"] = "STOPPED"
                        self._save_bots()
                        del self.processes[bot_id]
                        if bot_id in restart_counts:
                            del restart_counts[bot_id]
                        continue

                    # 2. Check restart cooldown
                    now = time.time()
                    count, first_time = restart_counts.get(bot_id, (0, now))
                    
                    # Reset counter if cooldown period passed
                    if now - first_time > COOLDOWN_PERIOD:
                        count = 0
                        first_time = now
                    
                    if count >= MAX_RESTARTS:
                        logger.error(f"🛑 [{ticker}] Max restarts ({MAX_RESTARTS}) reached. Manual intervention required.")
                        telegram_notifier.send_max_restart_alert(ticker)
                        bot["status"] = "ERROR"
                        self._save_bots()
                        del self.processes[bot_id]
                        continue
                    
                    logger.warning(f"💀 [{ticker}] Bot crashed with exit code {exit_code}. Auto-restarting... ({count+1}/{MAX_RESTARTS})")
                    telegram_notifier.send_crash_alert(ticker, exit_code, count + 1)
                    
                    # Clean up old process
                    del self.processes[bot_id]
                    
                    # Restart
                    try:
                        self.start_bot(bot_id)
                        restart_counts[bot_id] = (count + 1, first_time)
                        logger.info(f"✅ [{ticker}] Bot restarted successfully.")
                    except Exception as e:
                        logger.error(f"❌ [{ticker}] Failed to restart: {e}")
                        restart_counts[bot_id] = (count + 1, first_time)
    
    def get_bot_logs(self, bot_id: str, lines: int = 50) -> List[str]:
        """Get recent log lines for a specific bot (from ticker-specific log file)"""
        if bot_id not in self.bots:
            return []
        
        bot = self.bots[bot_id]
        ticker = bot.get("ticker", "")
        ticker_code = bot.get("ticker_code", "")
        
        today = datetime.now().strftime("%Y%m%d")
        
        # Priority order for log files: 
        # 1. Ticker Code + Bot ID (Most specific)
        # 2. Ticker Name + Bot ID
        # 3. Ticker Code only (Backward compatibility)
        # 4. Ticker Name only
        # 5. Fallback generic log
        
        log_files = []
        if ticker_code:
            log_files.append(LOGS_DIR / f"trading_{ticker_code}_{bot_id}_{today}.log")
        if ticker:
            log_files.append(LOGS_DIR / f"trading_{ticker}_{bot_id}_{today}.log")
        
        # Backward compatibility fallbacks
        if ticker_code:
            log_files.append(LOGS_DIR / f"trading_{ticker_code}_{today}.log")
        if ticker:
            log_files.append(LOGS_DIR / f"trading_{ticker}_{today}.log")
            
        log_files.append(LOGS_DIR / f"trading_{today}.log")

        target_file = None
        for f in log_files:
            if f.exists():
                target_file = f
                break
        
        if not target_file:
             return [f"[{ticker}] 로그 파일 없음: {log_files[0].name}"]

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                return [line.strip() for line in f.readlines()[-lines:]]
        except Exception as e:
            return [f"Error reading logs: {e}"]


# Global bot manager
bot_manager = BotManager()


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"WS send error: {e}")
                self.disconnect(connection)


ws_manager = ConnectionManager()


# Log Tailing and Streaming
class LogStreamer:
    def __init__(self, manager: BotManager, ws: ConnectionManager):
        self.manager = manager
        self.ws = ws
        self.last_offsets: Dict[str, int] = {} # bot_id -> last read offset

    async def stream_logs(self):
        """Poll log files for all running bots and broadcast new lines"""
        while True:
            try:
                # Status check is relatively cheap, but let's not spam
                all_bots = self.manager.bots
                # Include all active states for log streaming
                active_states = ["RUNNING", "HOLDING", "SEARCHING", "BUYING", "SELLING"]
                active_bids = [bid for bid, bot in all_bots.items() if bot["status"] in active_states]
                
                for bot_id in active_bids:
                    bot = self.manager.bots[bot_id]
                    ticker = bot.get("ticker", "")
                    ticker_code = bot.get("ticker_code", "")
                    today = datetime.now().strftime("%Y%m%d")
                    
                    log_candidates = []
                    if ticker_code:
                        log_candidates.append(LOGS_DIR / f"trading_{ticker_code}_{bot_id}_{today}.log")
                    if ticker:
                        log_candidates.append(LOGS_DIR / f"trading_{ticker}_{bot_id}_{today}.log")
                    
                    target_file = None
                    for f in log_candidates:
                        if f.exists():
                            target_file = f
                            break
                    
                    if not target_file:
                        # Log once per minute to avoid spam if file not yet created
                        if datetime.now().second == 0:
                            logger.warning(f"Log not found for {bot_id}. Searched: {[f.name for f in log_candidates]}")
                        continue

                    # Read new lines if file exists
                    file_size = target_file.stat().st_size
                    # Initial load logic: ensure we start tracking and broadcast historical tail if fresh
                    is_new = bot_id not in self.last_offsets
                    if is_new:
                        # For first-time discovery, read only the last 5kb to avoid jumbo messages
                        last_offset = max(0, file_size - 8000)
                        self.last_offsets[bot_id] = last_offset
                    else:
                        last_offset = self.last_offsets.get(bot_id, 0)

                    if file_size < last_offset:
                        last_offset = 0  # Reset offset if file shrank (rotation or reset)
                        
                    if file_size > last_offset:
                        try:
                            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                                f.seek(last_offset)
                                # Limit to 200 lines per tick to avoid WS buffer issues
                                raw_lines = f.readlines(10000) # Read approx 10kb worth of lines
                                new_lines = [line.strip() for line in raw_lines if line.strip()]
                                
                                if new_lines:
                                    logger.info(f"Broadcasting {len(new_lines)} lines for {bot_id}")
                                    await self.ws.broadcast({
                                        "type": "log",
                                        "bot_id": bot_id,
                                        "lines": new_lines
                                    })
                                
                                self.last_offsets[bot_id] = f.tell()
                        except Exception as e:
                            logger.error(f"Error reading log for {bot_id}: {e}")
                    # else:
                    #    logger.debug(f"No growth for {bot_id}: {file_size} == {last_offset}")
                
            except Exception as e:
                logger.error(f"Log streaming error: {e}")
            
            await asyncio.sleep(0.5) # Poll logs every 0.5s for better responsiveness

log_streamer = LogStreamer(bot_manager, ws_manager)


# Background task for status updates
async def status_broadcast_task():
    """Broadcast bot status to all connected clients"""
    while True:
        try:
            bots = bot_manager.get_all_bots()
            await ws_manager.broadcast({"type": "status", "bots": bots})
        except Exception as e:
            logger.error(f"Status broadcast error: {e}")
        await asyncio.sleep(3)  # Update every 3 seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    status_task = asyncio.create_task(status_broadcast_task())
    log_task = asyncio.create_task(log_streamer.stream_logs())
    keepalive_task = asyncio.create_task(bot_manager.monitor_processes())
    
    # Start Stock Cache background refresh
    stock_cache_task = None
    try:
        from stock_cache import get_stock_cache, start_cache_refresh_task
        stock_cache_task = asyncio.create_task(start_cache_refresh_task(interval_minutes=5))
        logger.info("📊 Stock Cache background refresh started")
    except Exception as e:
        logger.error(f"Failed to start stock cache: {e}")
    
    # Start Telegram Polling (webhooks require HTTPS, so we use long polling instead)
    telegram_polling_task = None
    try:
        config_path = BASE_DIR / "kis_devlp.yaml"
        if config_path.exists():
            import yaml
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                tg_token = config.get("telegram_token")
            
            if tg_token:
                async def telegram_polling():
                    """Long polling to receive Telegram button callbacks"""
                    import urllib.request
                    import json
                    import ssl
                    
                    last_update_id = 0
                    poll_url = f"https://api.telegram.org/bot{tg_token}/getUpdates"
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    
                    def do_poll(offset):
                        """Synchronous polling function to run in thread"""
                        params = f"?offset={offset}&timeout=30"
                        req = urllib.request.Request(poll_url + params)
                        with urllib.request.urlopen(req, context=ctx, timeout=35) as response:
                            return json.loads(response.read().decode())
                    
                    def answer_callback(callback_id):
                        """Answer callback query to remove loading state"""
                        answer_url = f"https://api.telegram.org/bot{tg_token}/answerCallbackQuery"
                        answer_payload = json.dumps({"callback_query_id": callback_id}).encode("utf-8")
                        answer_req = urllib.request.Request(answer_url, data=answer_payload, headers={'Content-Type': 'application/json'})
                        urllib.request.urlopen(answer_req, context=ctx, timeout=10)
                    
                    logger.info("🤖 Telegram Polling started")
                    
                    while True:
                        try:
                            # Run blocking call in thread pool
                            data = await asyncio.to_thread(do_poll, last_update_id + 1)
                            
                            if data.get("ok") and data.get("result"):
                                for update in data["result"]:
                                    last_update_id = update["update_id"]
                                    
                                    # Handle callback_query (button press)
                                    if "callback_query" in update:
                                        callback = update["callback_query"]
                                        callback_data = callback.get("data", "")
                                        callback_id = callback.get("id")
                                        
                                        # Process: Unblock IP
                                        if callback_data.startswith("unblock_ip:"):
                                            ip = callback_data.split(":")[1]
                                            if ip in blocked_ips:
                                                del blocked_ips[ip]
                                                save_blocked_ips(blocked_ips)
                                                if ip in login_attempts:
                                                    del login_attempts[ip]
                                                logger.info(f"IP {ip} unblocked via Telegram")
                                                send_telegram_alert(f"✅ IP `{ip}` 차단 해제 완료!")
                                            else:
                                                send_telegram_alert(f"ℹ️ IP `{ip}` 는 이미 차단 목록에 없습니다.")
                                        
                                        # Process: Unblock ALL IPs
                                        elif callback_data == "unblock_all":
                                            count = len(blocked_ips)
                                            blocked_ips.clear()
                                            login_attempts.clear()
                                            save_blocked_ips(blocked_ips)
                                            logger.info(f"All {count} IPs unblocked via Telegram")
                                            send_telegram_alert(f"🧹 전체 차단 해제 완료! ({count}개 IP 해제됨)")
                                        
                                        # Process: Stop Bot
                                        elif callback_data.startswith("stop_bot:"):
                                            bot_id = callback_data.split(":")[1]
                                            if bot_manager.stop_bot(bot_id):
                                                logger.info(f"Bot {bot_id} stopped via Telegram")
                                                send_telegram_alert(f"🛑 봇 `{bot_id}` 정지 완료!")
                                            else:
                                                send_telegram_alert(f"⚠️ 봇 `{bot_id}` 를 찾을 수 없습니다.")

                                        
                                        # Answer callback in background
                                        try:
                                            await asyncio.to_thread(answer_callback, callback_id)
                                        except:
                                            pass
                        
                        except Exception as e:
                            if "timed out" not in str(e).lower():
                                logger.warning(f"Telegram polling error: {e}")
                            await asyncio.sleep(5)
                        
                        await asyncio.sleep(0.1)

                
                telegram_polling_task = asyncio.create_task(telegram_polling())
                logger.info("✅ Telegram Polling task started")
    except Exception as e:
        logger.error(f"Failed to start Telegram polling: {e}")


    logger.info("Trading Bot Dashboard started (Keep-Alive enabled)")
    yield
    # Shutdown
    status_task.cancel()
    log_task.cancel()
    keepalive_task.cancel()
    # Stop all running bots
    for bot_id in list(bot_manager.processes.keys()):
        bot_manager.stop_bot(bot_id)
    logger.info("Trading Bot Dashboard stopped")


# FastAPI App
app = FastAPI(
    title="Trading Bot Dashboard",
    description="Web dashboard for monitoring and controlling trading bots",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


# Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve dashboard HTML"""
    check_rate_limit(request)
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/bots")
async def get_bots(_: str = Depends(verify_password)):
    """Get all bots status"""
    return bot_manager.get_all_bots()


@app.post("/api/bots")
async def add_bot(config: BotConfig, _: str = Depends(verify_password)):
    """Add a new bot"""
    bot_id = bot_manager.add_bot(config)
    return {"id": bot_id, "message": "Bot added successfully"}


@app.post("/api/bots/{bot_id}/start")
async def start_bot(bot_id: str, _: str = Depends(verify_password)):
    """Start a bot"""
    if bot_manager.start_bot(bot_id):
        return {"message": "Bot started"}
    raise HTTPException(status_code=404, detail="Bot not found")


@app.post("/api/bots/{bot_id}/stop")
async def stop_bot(bot_id: str, _: str = Depends(verify_password)):
    """Stop a bot"""
    if bot_manager.stop_bot(bot_id):
        return {"message": "Bot stopped"}
    raise HTTPException(status_code=404, detail="Bot not found")


@app.put("/api/bots/{bot_id}")
async def update_bot(bot_id: str, config: BotConfig, _: str = Depends(verify_password)):
    """Update a bot"""
    if bot_manager.update_bot(bot_id, config):
        return {"message": "Bot updated successfully"}
    raise HTTPException(status_code=404, detail="Bot not found")


@app.post("/api/bots/{bot_id}/panic-sell")
async def panic_sell_bot(bot_id: str, req: Optional[SellRequest] = None, _: str = Depends(verify_password)):
    """
    PANIC SELL: Stop bot, Sell all (Market or Limit), Reset state.
    """
    if bot_id not in bot_manager.bots:
        raise HTTPException(status_code=404, detail="Bot not found")
        
    bot = bot_manager.bots[bot_id]
    price = req.price if req else 0
    
    logger.warning(f"🚨 PANIC SELL TRIGGERED for {bot['ticker']} (Price: {price})")
    
    # 1. Stop Bot
    bot_manager.stop_bot(bot_id)
    
    # 2. Sell All
    qty = bot.get("total_qty", 0)
    sell_success = False
    skip_trade = req.skip_trade if req else False
    
    if skip_trade:
        logger.info(f"Local Reset Only requested for {bot['ticker']}. Skipping perform_sell.")
        sell_success = True # Consider it successful as no action was needed
    elif qty > 0:
        sell_success = bot_manager.perform_sell(bot, price)
        if sell_success:
            logger.info(f"Panic sell successful for {bot['ticker']}")
        else:
            logger.error(f"Panic sell failed for {bot['ticker']}")
    else:
        logger.info(f"No quantity to sell for {bot['ticker']}")
        sell_success = True 
        
    # 3. Reset State (Clean Slate)
    bot["total_qty"] = 0
    bot["avg_price"] = 0
    bot["current_price"] = 0
    bot["profit_rate"] = 0
    bot_manager._save_bots()
    
    # 4. Delete State File
    ticker_code = bot.get("ticker_code")
    if ticker_code:
        state_file = SCALP_DATA_DIR / f"state_{ticker_code}.json"
        if state_file.exists():
            try:
                state_file.unlink()
                logger.info(f"Deleted state file: {state_file}")
            except Exception as e:
                logger.error(f"Failed to delete state file: {e}")
                
    return {
        "message": f"Bot {bot['ticker']} stopped and reset.",
        "sold": qty if sell_success else 0,
        "success": sell_success,
        "price_type": "Market" if price == 0 else "Limit"
    }


@app.get("/api/blocked-ips")
async def get_blocked_ips(_: str = Depends(verify_password)):
    """Get list of blocked IPs"""
    return blocked_ips

@app.delete("/api/blocked-ips/{ip}")
async def unblock_ip(ip: str, _: str = Depends(verify_password)):
    """Unblock an IP address"""
    if ip in blocked_ips:
        del blocked_ips[ip]
        save_blocked_ips(blocked_ips)
    
    # Also clear login attempts
    if ip in login_attempts:
        del login_attempts[ip]
        
    logger.info(f"Unblocked IP: {ip}")
    return {"message": f"IP {ip} unblocked"}


@app.get("/api/trades")
async def get_trades(
    ticker: str = None,
    bot_id: str = None,
    action: str = None,
    limit: int = 100,
    _: str = Depends(verify_password)
):
    """Get trade history from database."""
    return trade_history.get_trades(ticker=ticker, bot_id=bot_id, action=action, limit=limit)


@app.get("/api/trades/summary")
async def get_trade_summary(days: int = 7, _: str = Depends(verify_password)):
    """Get daily profit/loss summary."""
    return trade_history.get_daily_summary(days)


@app.delete("/api/bots/{bot_id}")
async def delete_bot(bot_id: str, _: str = Depends(verify_password)):
    """Delete a bot"""
    if bot_manager.remove_bot(bot_id):
        return {"message": "Bot deleted"}
    raise HTTPException(status_code=404, detail="Bot not found")


@app.get("/api/bots/{bot_id}/logs")
async def get_bot_logs(bot_id: str, lines: int = 50, _: str = Depends(verify_password)):
    """Get bot logs"""
    logs = bot_manager.get_bot_logs(bot_id, lines)
    return {"logs": logs}


@app.post("/api/factory-reset")
async def factory_reset(_: str = Depends(verify_password)):
    """
    EMERGENCY RESET: Stop all, Sell all, Delete all.
    """
    logger.critical("🚨 FACTORY RESET TRIGGERED 🚨")
    
    # 1. Stop all bots
    for bot_id in list(bot_manager.bots.keys()):
        bot_manager.stop_bot(bot_id)
        
    # 2. Sell all holdings (Market Sell)
    results = []
    for bot_id, bot in bot_manager.bots.items():
        if bot.get("total_qty", 0) > 0:
            logger.info(f"Selling all for {bot['ticker']} ({bot['total_qty']} qty)")
            success = bot_manager.perform_sell(bot, price=0) # Market Sell
            results.append(f"{bot['ticker']}: {'Sold' if success else 'Fail'}")
            
    # 3. Clear Data
    bot_manager.bots = {}
    bot_manager._save_bots()
    
    # Delete logs and state files
    try:
        for f in SCALP_DATA_DIR.glob("*.json"):
            f.unlink()
        for f in LOGS_DIR.glob("*.log"):
            f.unlink()
    except Exception as e:
        logger.error(f"Failed to clear files: {e}")
        
    logger.info("Factory reset complete.")
    return {"message": "All bots stopped, holdings sold, and data reset.", "results": results}


@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram Callback Queries"""
    try:
        data = await request.json()
        logger.info(f"Telegram Webhook received: {data}")
        
        # Handle Callback Query
        if "callback_query" in data:
            callback = data["callback_query"]
            callback_data = callback.get("data", "")
            callback_id = callback.get("id")
            message = callback.get("message", {})
            chat_id = message.get("chat", {}).get("id")
            
            # Action: Unblock IP
            if callback_data.startswith("unblock_ip:"):
                ip = callback_data.split(":")[1]
                if ip in blocked_ips:
                    del blocked_ips[ip]
                    save_blocked_ips(blocked_ips)
                    if ip in login_attempts:
                        del login_attempts[ip]
                    logger.info(f"IP {ip} unblocked via Telegram")
                    
                    # Answer callback
                    send_telegram_alert(f"✅ IP `{ip}` has been unblocked.")
                else:
                    send_telegram_alert(f"ℹ️ IP `{ip}` is not in the blocked list.")
            
            # Action: Stop Bot
            elif callback_data.startswith("stop_bot:"):
                bot_id = callback_data.split(":")[1]
                if bot_manager.stop_bot(bot_id):
                    logger.info(f"Bot {bot_id} stopped via Telegram")
                    send_telegram_alert(f"🛑 Bot `{bot_id}` has been stopped.")
                else:
                    send_telegram_alert(f"❌ Bot `{bot_id}` not found or already stopped.")

            # Answer Callback Query (to remove loading state in Telegram)
            config_path = BASE_DIR / "kis_devlp.yaml"
            if config_path.exists():
                import yaml
                import urllib.request
                import json
                import ssl
                
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f)
                    token = config.get("telegram_token")
                
                if token:
                    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
                    payload = {"callback_query_id": callback_id, "text": "조치가 완료되었습니다."}
                    json_payload = json.dumps(payload).encode("utf-8")
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = urllib.request.Request(url, data=json_payload, headers={'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, context=ctx) as response:
                        pass

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error handling Telegram webhook: {e}")
        return {"status": "error", "message": str(e)}


# ============ Stock Screener API Endpoints ============

@app.get("/api/screener/scan")
async def screener_scan(minVolume: int = 500000,  # 50만으로 완화
                        maxPer: float = 30.0,     # 30으로 완화
                        requireDoubleBottom: bool = False,  # 기본 비활성화
                        requireInvestorFlow: bool = False,  # 기본 비활성화
                        minOpRate: float = 0.0,   # 0으로 완화 (모든 종목 포함)
                        maxDebtRate: float = 200.0,  # 200%로 완화
                        maxRsrvRate: float = 5000.0,  # 5000%로 완화
                        optimalMode: bool = False,
                        _: str = Depends(verify_password)):
    """주식 스캔 시작"""
    if stock_screener is None:
        raise HTTPException(status_code=503, detail="Stock Screener 초기화 실패")
    
    # Applied filter summary for UI display
    filters_applied = {
        "minVolume": minVolume,
        "maxPer": maxPer,
        "requireDoubleBottom": requireDoubleBottom,
        "requireInvestorFlow": requireInvestorFlow,
        "minOpRate": minOpRate,
        "maxDebtRate": maxDebtRate,
        "maxRsrvRate": maxRsrvRate,
        "optimalMode": optimalMode,
        "description": "Antigravity Optimal (RSI 30~70, 추세 OR 모멘텀)" if optimalMode else "Standard (쌍바닥/수급)"
    }
    
    try:
        # 백그라운드에서 실행하지 않고 즉시 실행
        results = await asyncio.to_thread(
            stock_screener.scan_all,
            min_volume=minVolume,
            max_per=maxPer,
            require_double_bottom=requireDoubleBottom,
            require_investor_flow=requireInvestorFlow,
            min_op_rate=minOpRate,
            max_debt_rate=maxDebtRate,
            max_rsrv_rate=maxRsrvRate,
            optimal_mode=optimalMode
        )
        return {
            "status": "success", 
            "count": len(results), 
            "items": results,
            "filters": filters_applied
        }
    except Exception as e:
        logger.error(f"Screener scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/screener/lookup")
async def screener_lookup(query: str, _: str = Depends(verify_password)):
    """수동 종목 조회 - 종목코드 또는 종목명으로 검색"""
    if stock_screener is None:
        raise HTTPException(status_code=503, detail="Stock Screener 초기화 실패")
    
    query = query.strip()
    ticker = None
    
    # 숫자만 있으면 종목코드로 처리
    if query.isdigit():
        ticker = query.zfill(6)
    else:
        # 종목명으로 코드 검색
        from stock_code_lookup import StockMaster
        stock_master = StockMaster()
        ticker = stock_master.get_code(query)
        if not ticker:
            raise HTTPException(status_code=404, detail=f"'{query}' 종목을 찾을 수 없습니다. 정확한 종목명이나 코드를 입력하세요.")
    
    try:
        info = await asyncio.to_thread(stock_screener.get_stock_price_info, ticker)
        if not info:
            raise HTTPException(status_code=404, detail=f"종목 {ticker}를 찾을 수 없습니다")
        
        # 추가 정보 조회
        per_ok, per_value = await asyncio.to_thread(stock_screener.check_per, ticker, 9999)
        fin_ok, fin_data = await asyncio.to_thread(stock_screener.check_financials, ticker, -9999, 9999, 99999)
        opt_ok, opt_data = await asyncio.to_thread(stock_screener.check_momentum_and_trend, ticker)
        
        result = {
            "ticker": ticker,
            "name": info.get("name", ticker),
            "price": info.get("price", 0),
            "volume": info.get("volume", 0),
            "sector": info.get("sector", "-"),
            "per": per_value,
            **fin_data,
            **opt_data,
            "score": 0
        }
        
        return {"status": "success", "item": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stock lookup failed for {query}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/screener/raw")
async def screener_raw(minVolume: int = 0, _: str = Depends(verify_password)):
    """필터 없이 거래량 상위 종목만 조회 (RAW 모드)"""
    if stock_screener is None:
        raise HTTPException(status_code=503, detail="Stock Screener 초기화 실패")
    
    try:
        # 거래량 상위 종목 조회
        volume_df = await asyncio.to_thread(stock_screener.get_high_volume_stocks, minVolume)
        
        if volume_df.empty:
            return {"status": "success", "count": 0, "items": [], "message": "거래량 조건 충족 종목 없음"}
        
        # 종목 코드 추출
        tickers = volume_df['mksc_shrn_iscd'].tolist() if 'mksc_shrn_iscd' in volume_df.columns else []
        
        results = []
        for ticker in tickers[:30]:  # 최대 30개
            info = await asyncio.to_thread(stock_screener.get_stock_price_info, ticker)
            if info:
                results.append({
                    "ticker": ticker,
                    "name": info.get("name", ticker),
                    "price": info.get("price", 0),
                    "volume": info.get("volume", 0),
                    "sector": info.get("sector", "-"),
                    "per": None,
                    "op_rate": None,
                    "debt_rate": None,
                    "rsrv_rate": None,
                    "rsi": None,
                    "trend_ok": False,
                    "score": 0
                })
        
        return {
            "status": "success", 
            "count": len(results), 
            "items": results,
            "message": f"거래량 상위 {len(results)}개 종목 (필터 없음)"
        }
    except Exception as e:
        logger.error(f"Raw screener failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/screener/cached")
async def screener_cached(
    minVolume: int = 0,
    maxPer: float = 9999,
    market: str = None,
    limit: int = 100,
    _: str = Depends(verify_password)
):
    """캐시된 전체 종목 데이터에서 필터링 (KOSPI + KOSDAQ ~3,700개)"""
    try:
        from stock_cache import get_stock_cache
        cache = get_stock_cache()
        
        if not cache.stocks:
            return {
                "status": "error",
                "message": "캐시가 아직 로드되지 않았습니다. 잠시 후 다시 시도하세요.",
                "count": 0,
                "items": []
            }
        
        # 필터링
        results = cache.filter_stocks(
            min_volume=minVolume,
            max_per=maxPer if maxPer < 9999 else 9999,
            market=market,
            limit=limit
        )
        
        stats = cache.get_stats()
        
        return {
            "status": "success",
            "count": len(results),
            "total_stocks": stats['total_stocks'],
            "last_update": stats['last_update'],
            "items": results,
            "filters": {
                "minVolume": minVolume,
                "maxPer": maxPer,
                "market": market,
                "limit": limit
            }
        }
    except Exception as e:
        logger.error(f"Cached screener failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/screener/cache-stats")
async def screener_cache_stats(_: str = Depends(verify_password)):
    """캐시 통계 조회"""
    try:
        from stock_cache import get_stock_cache
        cache = get_stock_cache()
        return {
            "status": "success",
            **cache.get_stats()
        }
    except Exception as e:
        logger.error(f"Cache stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/screener/status")
async def screener_status(_: str = Depends(verify_password)):
    """마지막 스캔 결과 조회"""
    if stock_screener is None:
        raise HTTPException(status_code=503, detail="Stock Screener 초기화 실패")
    
    return {
        "status": "ok",
        "last_scan_time": stock_screener.last_scan_time,
        "result_count": len(stock_screener.last_results),
        "stocks": stock_screener.last_results
    }


@app.get("/api/screener/analyze/{ticker}")
async def screener_analyze(ticker: str, _: str = Depends(verify_password)):
    """특정 종목 상세 분석"""
    if stock_screener is None:
        raise HTTPException(status_code=503, detail="Stock Screener 초기화 실패")
    
    validate_ticker(ticker)
    
    try:
        # 종목 코드 확인
        if not ticker.isdigit():
            sm = StockMaster()
            code = sm.get_code(ticker)
            if code:
                ticker = code
        
        result = {
            "ticker": ticker,
            "price_info": stock_screener.get_stock_price_info(ticker),
            "per_check": {},
            "double_bottom": {},
            "investor_flow": {}
        }
        
        # PER 체크
        per_ok, per_value = stock_screener.check_per(ticker)
        result["per_check"] = {"passed": per_ok, "value": per_value}
        
        # 쌍바닥 체크
        db_ok, db_msg = stock_screener.check_double_bottom(ticker)
        result["double_bottom"] = {"passed": db_ok, "message": db_msg}
        
        # 수급 체크
        flow = stock_screener.check_investor_flow(ticker)
        result["investor_flow"] = flow
        
        return result
    except Exception as e:
        logger.error(f"Screener analyze failed for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/screener/volume-stocks")
async def get_volume_stocks(min_volume: int = 1000000, _: str = Depends(verify_password)):
    """거래량 상위 종목 조회 (빠른 필터)"""
    if stock_screener is None:
        raise HTTPException(status_code=503, detail="Stock Screener 초기화 실패")
    
    try:
        df = await asyncio.to_thread(stock_screener.get_high_volume_stocks, min_volume)
        if df.empty:
            return {"status": "ok", "count": 0, "stocks": []}
        
        return {
            "status": "ok",
            "count": len(df),
            "stocks": df.to_dict(orient="records")
        }
    except Exception as e:
        logger.error(f"Volume stocks fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ End of Stock Screener API ============


@app.websocket("/ws")

async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    ip = get_client_ip(websocket)
    if ip in blocked_ips:
        logger.warning(f"WS connection rejected from blocked IP: {ip}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
        
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive any client messages
            data = await websocket.receive_text()
            # Echo back or handle commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
