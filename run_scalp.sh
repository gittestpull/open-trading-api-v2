#!/bin/bash

# Trading Bot Podman Runner
# Usage: ./run_scalp.sh [ticker] [budget] [target] [--live]
#
# Example:
#   ./run_scalp.sh "오리엔탈정공" 1300000 0.02 --live

TICKER="${1:-오리엔탈정공}"
BUDGET="${2:-1300000}"
TARGET="${3:-0.02}"
LIVE_FLAG="${4:---live}"

# Container name
CONTAINER_NAME="trading-scalp-$(echo $TICKER | tr -cd '[:alnum:]')"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Stop existing container if running
podman stop "$CONTAINER_NAME" 2>/dev/null
podman rm "$CONTAINER_NAME" 2>/dev/null

# Build the image
echo "🔨 Building trading bot image..."
podman build -t trading-scalp:latest "$SCRIPT_DIR"

# Create directories if not exists
mkdir -p "$HOME/KIS/config"
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/scalp_data"

# Check if kis_devlp.yaml exists
CONFIG_FOUND=false
VOLUME_ARGS=""

if [ -f "$SCRIPT_DIR/kis_devlp.yaml" ]; then
    CONFIG_FOUND=true
    VOLUME_ARGS="$VOLUME_ARGS -v $SCRIPT_DIR/kis_devlp.yaml:/app/kis_devlp.yaml:ro"
    echo "✅ Found config: $SCRIPT_DIR/kis_devlp.yaml"
fi

if [ -f "$HOME/KIS/config/kis_devlp.yaml" ]; then
    CONFIG_FOUND=true
    VOLUME_ARGS="$VOLUME_ARGS -v $HOME/KIS/config:/root/KIS/config:ro"
    echo "✅ Found config: $HOME/KIS/config/kis_devlp.yaml"
fi

if [ "$CONFIG_FOUND" = false ]; then
    echo ""
    echo "⚠️  Warning: kis_devlp.yaml not found!"
    echo "   Please create the config file at one of:"
    echo "   1. $SCRIPT_DIR/kis_devlp.yaml (local)"
    echo "   2. $HOME/KIS/config/kis_devlp.yaml (global)"
    echo ""
    echo "   Or use environment variables KIS_APP_KEY and KIS_APP_SECRET"
    echo ""
    exit 1
fi

# Run the container
echo ""
echo "🚀 Starting trading bot..."
echo "   Ticker: $TICKER"
echo "   Budget: $BUDGET"
echo "   Target: $TARGET"
echo "   Live Mode: $LIVE_FLAG"
echo ""

podman run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    $VOLUME_ARGS \
    -v "$SCRIPT_DIR/logs:/app/logs:rw" \
    -v "$SCRIPT_DIR/scalp_data:/app/scalp_data:rw" \
    -e TZ=Asia/Seoul \
    trading-scalp:latest \
    --ticker "$TICKER" \
    --budget "$BUDGET" \
    --target "$TARGET" \
    $LIVE_FLAG

echo ""
echo "✅ Container '$CONTAINER_NAME' started!"
echo ""
echo "📋 Useful commands:"
echo "   View logs:   podman logs -f $CONTAINER_NAME"
echo "   Stop bot:    podman stop $CONTAINER_NAME"
echo "   Remove:      podman rm $CONTAINER_NAME"
