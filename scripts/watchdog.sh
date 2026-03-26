#!/bin/bash
# Trading Web Watchdog — 컨테이너 상태 확인 및 자동 복구
# cron 또는 launchd로 매 2분 실행

CONTAINER="open-trading-api-v2_trading-web_1"
COMPOSE_DIR="/Users/darkkwang/.openclaw/workspace-taekwang/stock/open-trading-api-v2"
LOG="/tmp/trading-watchdog.log"
HEALTH_URL="http://localhost:30802/"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

# 1. Podman 머신 확인
if ! podman machine list --format '{{.Running}}' 2>/dev/null | grep -q "true"; then
    log "⚠ Podman machine not running. Starting..."
    podman machine start 2>&1 >> "$LOG"
    sleep 10
fi

# 2. 컨테이너 상태 확인
STATUS=$(podman inspect "$CONTAINER" --format '{{.State.Status}}' 2>/dev/null)

if [ "$STATUS" != "running" ]; then
    log "⚠ Container status: $STATUS. Restarting..."
    cd "$COMPOSE_DIR" && podman-compose up -d trading-web 2>&1 >> "$LOG"
    sleep 5
    log "✅ Container restarted"
    exit 0
fi

# 3. 헬스체크 (HTTP 응답 확인)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>/dev/null)

if [ "$HTTP_CODE" != "200" ]; then
    log "⚠ Health check failed (HTTP $HTTP_CODE). Restarting container..."
    cd "$COMPOSE_DIR" && podman-compose restart trading-web 2>&1 >> "$LOG"
    sleep 5
    log "✅ Container restarted after health check failure"
    exit 0
fi

# 4. 정상
# log "✅ All healthy (HTTP $HTTP_CODE)"
