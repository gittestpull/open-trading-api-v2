import sys
import os

# Add examples_user to path to import kis_auth
sys.path.append(os.path.join(os.getcwd(), 'examples_user'))

try:
    import kis_auth
    print(">>> kis_auth 모듈을 성공적으로 불러왔습니다.")
except ImportError as e:
    print(f">>> 모듈 불러오기 실패: {e}")
    sys.exit(1)

print(">>> 토큰 발급을 시도합니다...")
try:
    # auth() 함수 호출
    kis_auth.auth()
    
    # 토큰이 잘 생성되었는지 확인
    token = kis_auth.read_token()
    if token:
        print(f">>> [성공] 토큰이 정상적으로 발급되었습니다!")
        print(f">>> 발급된 토큰(일부): {token[:20]}...")
        
        # 적용된 환경 변수 키 확인 (보안상 일부만 출력)
        env = kis_auth.getEnv()
        app_key = env.get('my_app', 'N/A')
        print(f">>> 적용된 App Key: {app_key[:5]}... ****")
    else:
        print(">>> [실패] 토큰 발급에 실패했거나 토큰을 읽을 수 없습니다.")

except Exception as e:
    print(f">>> [오류 발생] {e}")
