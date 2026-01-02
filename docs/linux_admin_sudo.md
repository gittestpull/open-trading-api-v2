# Linux Sudo 권한 부여 가이드

이 문서는 Linux 시스템에서 일반 사용자에게 `sudo` 권한을 부여하는 방법을 설명합니다. 제공해주신 `/etc/sudoers` 설정을 바탕으로 가장 안전하고 권장되는 방법들을 정리했습니다.

## 1. `sudo` 그룹을 이용한 권한 부여 (가장 권장됨)

가장 간단하고 표준적인 방법은 사용자를 시스템의 `sudo` 그룹에 추가하는 것입니다. `/etc/sudoers` 설정에 이미 `%sudo ALL=(ALL:ALL) ALL` 항목이 있으므로, 이 그룹에 속한 사용자는 모든 명령을 sudo로 실행할 수 있습니다.

### 방법:
```bash
# 사용자(username)를 sudo 그룹에 추가
sudo usermod -aG sudo <username>
```
> [!NOTE]
> 설정을 적용하려면 해당 사용자가 로그아웃 후 다시 로그인해야 합니다.

---

## 2. `/etc/sudoers.d/`를 이용한 개별 설정 (관리 용이)

메인 `/etc/sudoers` 파일을 직접 수정하는 대신, `/etc/sudoers.d/` 디렉토리에 개별 설정 파일을 만드는 방식입니다. 이는 설정이 꼬이는 것을 방지하고 관리가 편리합니다.

### 방법:
1. `visudo -f` 명령을 사용하여 새 설정 파일을 생성합니다.
   ```bash
   sudo visudo -f /etc/sudoers.d/<filename>
   ```
2. 파일 내용에 다음 중 하나를 추가합니다:

   - **모든 권한 부여 (비밀번호 확인 필요):**
     ```text
     <username> ALL=(ALL:ALL) ALL
     ```
   - **비밀번호 없이 모든 권한 부여:**
     ```text
     <username> ALL=(ALL:ALL) NOPASSWD: ALL
     ```

---

## 3. 특정 명령만 sudo 허용하기

사용자에게 전체 root 권한이 아닌, 특정 서비스 재시작이나 로그 확인 명령만 허용하고 싶을 때 유용합니다.

### 예시:
`/etc/sudoers.d/deploy-user` 파일 내용:
```text
# deploy-user에게 nginx 서비스 관리 권한만 부여
deploy-user ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart nginx, /usr/bin/systemctl reload nginx
```

---

## ⚠️ 주의사항 (Best Practices)

1. **`visudo` 사용 필수**: `/etc/sudoers`나 `/etc/sudoers.d/` 파일을 수정할 때는 반드시 `visudo` 명령을 사용하세요. `visudo`는 저장 전 문법 오류를 체크하여, 잘못된 설정으로 인해 아예 sudo를 못 쓰게 되는 상황을 방지합니다.
2. **`@includedir` 확인**: 메인 `/etc/sudoers` 하단에 `@includedir /etc/sudoers.d` 문구가 있는지 확인하세요 (제공해주신 파일에는 포함되어 있습니다).
3. **최소 권한 원칙**: 꼭 필요한 경우가 아니라면 `NOPASSWD` 설정은 지양하고, 가능한 특정 명령으로 권한을 제한하는 것이 보안상 안전합니다.
