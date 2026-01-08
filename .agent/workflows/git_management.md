---
description: Git Versioning & Security Policy (버전 관리 및 보안 정책)
---

# Git 버전 관리 및 보안 정책

이 워크플로우는 `open-trading-api` 프로젝트의 코드 안정성과 보안을 유지하기 위한 핵심 지침을 담고 있습니다.

## 1. 커밋 전 보안 체크 (Critical)
다음 파일들은 보안 및 개인화된 상태 정보를 포함하고 있으므로 **절대 커밋하거나 푸시하지 않습니다.**

- `kis_devlp.yaml`: KIS API 키 및 시크릿 (매우 중요)
- `logs/`: 거래 로그 및 에러 내역
- `scalp_data/`: 종목별 트레이딩 상태 정보 (JSON)
- `data/`: SQLite 거래 내역 데이터베이스
- `web/bots_config.json`: 사용자 정의 봇 설정
- `web/blocked_ips.json`: 차단된 IP 리스트
- `.env`: 환경 변수 파일

> [!IMPORTANT]
> 새로운 상태 파일이나 민감한 설정 파일을 추가할 경우 반드시 `.gitignore`에 먼저 등록하세요.

## 2. 버전 관리 및 롤백 전략
중요한 업데이트(안정성 패치, 대규모 기능 추가 등)를 진행할 때는 항상 태그를 활용합니다.

### 업데이트 전 (Rollback Point)
작업 시작 전 현재의 안정된 상태를 태그로 남깁니다.
```bash
git tag pre-update-$(date +%Y%m%d_%H%M)
```

### 업데이트 후 (New Version)
기능 구현 및 검증이 완료되면 새로운 버전 태그를 생성합니다.
```bash
git tag stability-v1.x
git push origin main --tags
```

## 3. 롤백 방법
문제가 발생하여 이전 버전으로 돌아가야 할 경우:
```bash
# 특정 태그로 강제 이동
git reset --hard [태그명]
# 원격 브랜치에도 반영이 필요한 경우 (주의 필요)
git push origin main --force
```

## 4. 환경 배포 프로세스
1. 코드 수정 및 로컬 테스트
2. `git commit` & `git push`
3. `./run_web.sh` 실행 (Podman 컨테이너 빌드 및 UFW 설정 자동화)
4. 대시보드 및 서비스 상태 확인
