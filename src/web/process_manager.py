# -*- coding: utf-8 -*-
import subprocess
import threading
import time
import os
import signal
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque


@dataclass
class ScalperProcess:
    pid: int
    ticker: str
    budget: float
    live_mode: bool
    llm_mode: bool
    started_at: datetime
    process: subprocess.Popen
    log_buffer: deque = field(default_factory=lambda: deque(maxlen=500))
    
    def to_dict(self) -> dict:
        return {
            "pid": self.pid,
            "ticker": self.ticker,
            "budget": self.budget,
            "live_mode": self.live_mode,
            "llm_mode": self.llm_mode,
            "started_at": self.started_at.isoformat(),
            "running": self.process.poll() is None,
            "uptime_seconds": (datetime.now() - self.started_at).total_seconds(),
        }


class ProcessManager:
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.processes: Dict[str, ScalperProcess] = {}
        self._lock = threading.Lock()
        self._log_threads: Dict[str, threading.Thread] = {}
    
    def start_scalper(
        self,
        ticker: str,
        budget: float = 1000000,
        target: float = 0.005,
        live_mode: bool = False,
        llm_mode: bool = False,
        orderbook: bool = False,
        momentum: bool = False,
        buy_price: float = 0,
    ) -> dict:
        ticker_key = ticker.upper()
        
        with self._lock:
            if ticker_key in self.processes:
                existing = self.processes[ticker_key]
                if existing.process.poll() is None:
                    return {"error": f"Scalper for {ticker_key} is already running (PID: {existing.pid})"}
        
        cmd = [
            "uv", "run", "python", "run_scalper.py",
            "--ticker", ticker,
            "--budget", str(int(budget)),
            "--target", str(target),
        ]
        
        if live_mode:
            cmd.append("--live")
        if llm_mode:
            cmd.append("--llm")
        if orderbook:
            cmd.append("--orderbook")
        if momentum:
            cmd.append("--momentum")
        if buy_price > 0:
            cmd.extend(["--buy_price", str(buy_price)])
        
        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.base_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            
            scalper_proc = ScalperProcess(
                pid=process.pid,
                ticker=ticker_key,
                budget=budget,
                live_mode=live_mode,
                llm_mode=llm_mode,
                started_at=datetime.now(),
                process=process,
            )
            
            with self._lock:
                self.processes[ticker_key] = scalper_proc
            
            log_thread = threading.Thread(
                target=self._read_output,
                args=(ticker_key,),
                daemon=True
            )
            log_thread.start()
            self._log_threads[ticker_key] = log_thread
            
            return {
                "success": True,
                "message": f"Started scalper for {ticker_key}",
                "pid": process.pid,
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _read_output(self, ticker_key: str):
        proc = self.processes.get(ticker_key)
        if not proc:
            return
        
        try:
            for line in iter(proc.process.stdout.readline, ''):
                if not line:
                    break
                timestamp = datetime.now().strftime("%H:%M:%S")
                log_entry = f"[{timestamp}] {line.rstrip()}"
                proc.log_buffer.append(log_entry)
        except Exception:
            pass
    
    def stop_scalper(self, ticker: str) -> dict:
        ticker_key = ticker.upper()
        
        with self._lock:
            if ticker_key not in self.processes:
                return {"error": f"No running scalper for {ticker_key}"}
            
            proc = self.processes[ticker_key]
            
            if proc.process.poll() is not None:
                del self.processes[ticker_key]
                return {"error": f"Scalper for {ticker_key} already stopped"}
            
            try:
                proc.process.terminate()
                proc.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.process.kill()
                proc.process.wait()
            
            del self.processes[ticker_key]
            
            return {
                "success": True,
                "message": f"Stopped scalper for {ticker_key}",
            }
    
    def get_status(self, ticker: Optional[str] = None) -> List[dict]:
        with self._lock:
            if ticker:
                ticker_key = ticker.upper()
                if ticker_key in self.processes:
                    return [self.processes[ticker_key].to_dict()]
                return []
            
            result = []
            dead_tickers = []
            
            for key, proc in self.processes.items():
                if proc.process.poll() is not None:
                    dead_tickers.append(key)
                else:
                    result.append(proc.to_dict())
            
            for key in dead_tickers:
                del self.processes[key]
            
            return result
    
    def get_logs(self, ticker: str, lines: int = 100) -> List[str]:
        ticker_key = ticker.upper()
        
        with self._lock:
            if ticker_key not in self.processes:
                return []
            
            proc = self.processes[ticker_key]
            return list(proc.log_buffer)[-lines:]
    
    def get_state_files(self) -> List[dict]:
        state_dir = os.path.join(self.base_dir, "scalp_data")
        if not os.path.exists(state_dir):
            return []
        
        import json
        states = []
        
        for filename in os.listdir(state_dir):
            if filename.startswith("state_") and filename.endswith(".json"):
                filepath = os.path.join(state_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        ticker = filename.replace("state_", "").replace(".json", "")
                        data["ticker"] = ticker
                        data["file"] = filename
                        states.append(data)
                except Exception:
                    pass
        
        return states
    
    def reset_state(self, ticker: str) -> dict:
        ticker_key = ticker.upper()
        
        # 실행 중이면 먼저 중지
        with self._lock:
            if ticker_key in self.processes:
                return {"error": f"Cannot reset state while scalper is running. Stop {ticker_key} first."}
        
        state_file = os.path.join(self.base_dir, "scalp_data", f"state_{ticker_key}.json")
        if os.path.exists(state_file):
            try:
                os.remove(state_file)
                return {"success": True, "message": f"Reset state for {ticker_key}"}
            except Exception as e:
                return {"error": f"Failed to delete state file: {str(e)}"}
        else:
            return {"error": f"No state file found for {ticker_key}"}
    
    def cleanup(self):
        with self._lock:
            for ticker_key, proc in list(self.processes.items()):
                if proc.process.poll() is None:
                    proc.process.terminate()
                    try:
                        proc.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.process.kill()
            self.processes.clear()
