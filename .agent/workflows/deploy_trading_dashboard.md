---
description: How to deploy and maintain the Trading Bot Dashboard
---

# Trading Bot Dashboard - Deploy Workflow

## Prerequisites
- `podman` and `podman-compose` installed
- KIS Open API credentials configured in `examples_user/kis_auth.py._cfg`
- UFW firewall (optional, managed by script)

## Quick Deploy
// turbo-all
```bash
cd /home/yangseungkwang/repo/open-trading-api
chmod +x run_web.sh && ./run_web.sh
```
This script:
1. Cleans stale UFW rules
2. Generates random port and password
3. Sends Telegram notification with access URL
4. Builds and starts the container

## Manual Deploy (Advanced)
```bash
export WEB_PORT=<desired_port>
export DASHBOARD_PASSWORD=<your_password>
podman-compose build --no-cache
podman-compose up -d --force-recreate
```

## Check Status
```bash
podman top trading-web           # Running processes
podman logs trading-web | tail   # Recent logs
ls -alt logs/                    # Bot log files
ls -alt scalp_data/              # Bot state files
```

## Restart Container
```bash
podman-compose restart trading-web
```

## Full Rebuild (After Code Changes)
```bash
./run_web.sh    # Or manual: podman-compose build --no-cache && up -d
```

## Troubleshooting

### Bots Stopped Unexpectedly
1. Check `podman logs trading-web` for "Authentication token fail" or "WATCHDOG BITE"
2. Verify KIS API keys are valid
3. Check `ls -alt logs/` for last update time

### Zombie Bots (Running but Not Updating)
- Watchdog (90s timeout) should auto-kill hung processes
- Check Heartbeat indicator: 🟢 Active, 🟡 Lagging, 🔴 Stalled

### Port Already in Use
```bash
podman kill trading-web && podman rm trading-web
./run_web.sh   # Generates new random port
```
