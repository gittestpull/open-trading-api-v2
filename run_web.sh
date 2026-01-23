#!/bin/bash

# Trading Bot Web Dashboard - Multi-Env Run Script
# Usage: ./run_web.sh [prod|staging|dev]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 0. Environment Setup
ENV_TYPE=${1:-prod} # Default to prod if no arg provided
case $ENV_TYPE in
    prod)
        DEFAULT_PORT=30800
        PROJECT_NAME="trading-prod"
        ;;
    staging)
        DEFAULT_PORT=8080
        PROJECT_NAME="trading-staging"
        ;;
    dev)
        DEFAULT_PORT=30802
        PROJECT_NAME="trading-dev"
        ;;
    *)
        echo "❌ Invalid environment: $ENV_TYPE. Use prod, staging, or dev."
        exit 1
        ;;
esac

echo "🌐 Environment: $ENV_TYPE"
echo "📂 Project Name: $PROJECT_NAME"

# --- Function: Cleanup Old Firewall Rules ---
cleanup_firewall() {
    echo "🧹 Checking for stale UFW rules for $ENV_TYPE..."
    # format of 'ufw status': 12345/tcp ALLOW Anywhere # TradingBot-prod
    STALE_PORTS=$(sudo ufw status | grep "TradingBot-$ENV_TYPE" | awk '{print $1}' | cut -d'/' -f1)
    
    if [ -n "$STALE_PORTS" ]; then
        for PORT in $STALE_PORTS; do
            echo "🔒 Closing stale UFW port: $PORT"
            sudo ufw delete allow $PORT/tcp >/dev/null 2>&1 || true
        done
    fi
}

# 0.1 Cleanup Old Rules (Skip for staging to keep it static)
if [ "$ENV_TYPE" != "staging" ]; then
    cleanup_firewall
fi

# 1. Generate Credentials
RANDOM_PORT=$DEFAULT_PORT
RANDOM_PASS=$(date +%s%N | sha256sum | head -c 16)

# Open new port (Only if not already open or for non-staging)
if [ "$ENV_TYPE" != "staging" ]; then
    echo "🛡️ Opening UFW port: $RANDOM_PORT"
    sudo ufw allow $RANDOM_PORT/tcp comment "TradingBot-$ENV_TYPE" || true
else
    echo "ℹ️ Staging environment: Skipping UFW port opening (Static 8080 assumed open)"
fi

# Get Public IP
PUBLIC_IP=$(curl -s --max-time 3 ifconfig.me || echo "External_IP_Check_Failed")

echo "🎲 Port: $RANDOM_PORT"
echo "🔐 Password: $RANDOM_PASS"

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
    env = '$ENV_TYPE'
    
    message = (
        f'🚀 *Trading Bot Started ({env.upper()})*\\n\\n'
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
# Ensure directory isolation
mkdir -p logs/$ENV_TYPE scalp_data/$ENV_TYPE data/$ENV_TYPE web/config/$ENV_TYPE

if [ ! -f "web/config/$ENV_TYPE/bots_config.json" ]; then
    echo "{}" > web/config/$ENV_TYPE/bots_config.json
fi

if [ ! -f "web/config/$ENV_TYPE/blocked_ips.json" ]; then
    echo "{}" > web/config/$ENV_TYPE/blocked_ips.json
fi

echo "🔨 Building trading web dashboard [$ENV_TYPE]..."
ENV_TYPE=$ENV_TYPE \
WEB_PORT=$RANDOM_PORT \
DASHBOARD_PASSWORD="$RANDOM_PASS" \
TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID" \
PUBLIC_IP="$PUBLIC_IP" \
podman-compose -p "$PROJECT_NAME" up --build -d

echo ""
echo "✅ Trading Bot Dashboard [$ENV_TYPE] started!"
echo ""
echo "🌐 Global: http://$PUBLIC_IP:$RANDOM_PORT"
echo "🌐 Local:  http://localhost:$RANDOM_PORT"
echo "🔑 Password: $RANDOM_PASS"
echo ""
