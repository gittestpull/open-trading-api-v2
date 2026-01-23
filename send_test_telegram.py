
import os
import sys
from pathlib import Path
import logging

# Add project root to path
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))

# Mock basic setup to import from app.py
os.environ["DASHBOARD_PASSWORD"] = "test"

from web.app import send_telegram_alert

def send_test_alert():
    logging.basicConfig(level=logging.INFO)
    test_ip = "1.2.3.4"
    msg = (
        f"🚨 **TEST SECURITY ALERT**\n\n"
        f"🚫 **IP BLOCKED**: `{test_ip}`\n"
        f"Reason: This is a test message to verify the unblock button functionality."
    )
    
    buttons = [[{"text": f"✅ TEST: IP {test_ip} 차단 해제", "callback_data": f"unblock_ip:{test_ip}"}]]
    
    print("Sending test telegram alert...")
    send_telegram_alert(msg, buttons=buttons)
    print("Done. Please check your Telegram and click the button!")

if __name__ == "__main__":
    send_test_alert()
