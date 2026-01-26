#!/bin/bash
# Stop Trading Bot & Cleanup Firewall
# Usage: ./stop_web.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Stop Container
echo "🛑 Stopping Trading Bot..."
podman-compose down 2>/dev/null || podman stop trading-web 2>/dev/null

# 2. Cleanup Firewall Rules (Stateless)
# Removes any rule tagged with 'TradingBot'
echo "🧹 Cleaning up firewall rules..."
STALE_PORTS=$(sudo ufw status | grep "TradingBot" | awk '{print $1}' | cut -d'/' -f1)

if [ -n "$STALE_PORTS" ]; then
    for PORT in $STALE_PORTS; do
        echo "🔒 Closing UFW port: $PORT"
        sudo ufw delete allow $PORT/tcp >/dev/null 2>&1 || true
    done
    echo "✅ All TradingBot ports closed."
else
    echo "ℹ️  No active ports found."
fi

echo "✅ Shutdown complete."
