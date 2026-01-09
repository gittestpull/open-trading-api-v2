---
description: Multi-Environment Deployment (Prod, Staging, Dev) Strategy
---

# Multi-Environment Deployment Workflow

> [!IMPORTANT]
> **글로벌 원칙: 로컬 환경 절대 설치 금지**
> 모든 설치, 실행, 개발 작업은 반드시 **컨테이너 환경(Podman)**에서만 수행합니다. 호스트 로컬 환경의 오염을 방지하고 개발 환경의 일관성을 유지하기 위한 철칙입니다. 모든 작업은 `podman` 및 `podman-compose`를 기반으로 합니다.

이 workflow는 Podman을 사용하여 동일한 호스트에서 여러 환경(Production, Staging, Development)을 동시에 가동하고 관리하는 표준 방식을 정의합니다.

## Environment Definitions

| Environment | Purpose | Default Port | Storage Path |
|-------------|---------|--------------|--------------|
| **Production** | Live stable service | 30800 | `./logs/prod`, `./scalp_data/prod` |
| **Staging** | Feature testing with real data | 8080 | `./logs/staging`, `./scalp_data/staging` |
| **Development**| Raw experimentation | 30802 | `./logs/dev`, `./scalp_data/dev` |

## Deployment Strategy

### 1. Project Naming (Isolation)
Every environment must use a unique project name to prevent container name collisions.
```bash
# In docker-compose commands:
podman-compose -p myapp-staging up -d
```

### 2. Volume Separation
Volumes must be isolated by environment subdirectories to prevent data corruption between versions.
```yaml
# docker-compose.yml
services:
  myapp:
    volumes:
      - ./data/${ENV_TYPE:-prod}:/app/data
```

### 3. Port Management
Assign unique host ports for each environment.
- Prod: `8080` or `30800`
- Staging: `8081` or `30801`
- Dev: `8082` or `30802`

## Execution Guide

### Simultaneous Deployment
To run a new feature in staging without stopping production:
// turbo
```bash
./run_web.sh staging
```

### Environment-Specific Cleanup
// turbo
```bash
podman-compose -p trading-staging down
```

### Best Practices
- **Port Visibility**: Use `ufw allow <port> comment 'TradingBot-<env>'` to manage firewall rules per environment.
- **No Local Install**: `pip install` 혹은 `npm install` 등을 호스트 로컬에서 절대 수행하지 마세요. 필요한 모든 패키지 설치는 `Dockerfile` 또는 컨테이너 내부(`/app`)에서 이루어져야 합니다.
- **Mandatory Podman**: 이 프로젝트의 모든 컨테이너 런타임은 `podman`을 표준으로 합니다.
