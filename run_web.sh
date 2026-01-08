#!/bin/bash

# Trading Bot Web Dashboard - Run Script
# Usage: ./run_web.sh
# Automates: Random Port, Random Password, Telegram Notification, Robust Firewall

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Function: Cleanup Old Firewall Rules ---
# This removes ANY UFW rule tagged with 'TradingBot' to prevent zombies.
cleanup_firewall() {
    echo "🧹 Checking for stale UFW rules..."
    # Get list of ports with our comment
    # format of 'ufw status': 12345/tcp ALLOW Anywhere # TradingBot
    STALE_PORTS=$(sudo ufw status | grep "TradingBot" | awk '{print $1}' | cut -d'/' -f1)
    
    if [ -n "$STALE_PORTS" ]; then
        for PORT in $STALE_PORTS; do
            echo "🔒 Closing stale UFW port: $PORT"
            sudo ufw delete allow $PORT/tcp >/dev/null 2>&1 || true
        done
    fi
}

# 0. Cleanup Old Rules
cleanup_firewall

# 1. Generate Random Credentials
RANDOM_PORT=$(( ( RANDOM % 40000 ) + 20000 ))
RANDOM_PASS=$(date +%s%N | sha256sum | head -c 16)

# Open new port with comment for tracking
echo "🛡️ Opening UFW port: $RANDOM_PORT"
sudo ufw allow $RANDOM_PORT/tcp comment 'TradingBot'

# Get Public IP (with short timeout)
PUBLIC_IP=$(curl -s --max-time 3 ifconfig.me || echo "External_IP_Check_Failed")

echo "🎲 Generated Port: $RANDOM_PORT"
echo "🔐 Generated Password: $RANDOM_PASS"

# 2. Extract Credentials & Send Notification (Python)
PYTHON_OUT=$(python3 - <<EOF
import yaml
import sys
import urllib.request
import urllib.parse
import ssl

try:
    with open('kis_devlp.yaml', 'r') as f:
        data = yaml.safe_load(f)
        token = data.get('telegram_token', '')
        chat_id = data.get('telegram_chat_id', '')

    if not token or not chat_id:
        print('⚠️  Telegram credentials not found.')
        sys.exit(0)

    port = '$RANDOM_PORT'
    password = '$RANDOM_PASS'
    public_ip = '$PUBLIC_IP'
    
    message = (
        f'🚀 *Trading Bot Started*\\n\\n'
        f'🌐 URL: http://{public_ip}:{port}\\n'
        f'🔐 PW: \`{password}\`\\n'
        f'(Local: http://localhost:{port})'
    )

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown'
    }
    data = urllib.parse.urlencode(payload).encode('utf-8')
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, context=ctx) as response:
        print('📨 Telegram notification sent!')

    # Export for shell use
    print(f'__EXPORT_TOKEN__={token}')
    print(f'__EXPORT_CHAT_ID__={chat_id}')

except Exception as e:
    print(f'❌ Telegram Notification Failed: {e}')
EOF
)

# Print python output (except the export lines)
echo "$PYTHON_OUT" | grep -v "__EXPORT_"

# 2.1 Parse Exported Vars
TELEGRAM_BOT_TOKEN=$(echo "$PYTHON_OUT" | grep "__EXPORT_TOKEN__" | cut -d'=' -f2)
TELEGRAM_CHAT_ID=$(echo "$PYTHON_OUT" | grep "__EXPORT_CHAT_ID__" | cut -d'=' -f2)


# 3. Prepare Environment & Run
mkdir -p logs scalp_data data

if [ ! -f "web/bots_config.json" ]; then
    echo "{}" > web/bots_config.json
fi

# Stop existing container
podman-compose down 2>/dev/null || podman stop trading-web 2>/dev/null

echo "🔨 Building trading web dashboard..."
WEB_PORT=$RANDOM_PORT \
DASHBOARD_PASSWORD="$RANDOM_PASS" \
TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
podman-compose up --build -d

echo ""
echo "✅ Trading Bot Dashboard started!"
echo ""
echo "🌐 Global: http://$PUBLIC_IP:$RANDOM_PORT"
echo "🌐 Local:  http://localhost:$RANDOM_PORT"
echo "🔑 Password: $RANDOM_PASS"
echo ""
