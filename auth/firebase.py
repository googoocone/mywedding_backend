# auth/firebase.py

import firebase_admin
# auth 모듈 외에 credentials 와 storage 모듈도 필요합니다.
from firebase_admin import credentials, auth, storage # ✅ storage 모듈 임포트

from datetime import datetime, timedelta
from jose import jwt
import os
from typing import Optional # Optional 임포트 (타입 힌트용)
from urllib.parse import urlparse, unquote # URL 파싱 및 디코딩 임포트

# Firebase Admin SDK 초기화 데이터 구성
# 환경 변수에서 직접 읽어오도록 설정 (앱 시작 전 환경 변수가 로드되어 있어야 함)
firebase_config = {
    "type": os.environ.get("FIREBASE_TYPE"),
    "project_id": os.environ.get("FIREBASE_PROJECT_ID"),
    "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
    # private_key는 줄바꿈 문자(\n)를 실제 줄바꿈으로 변환해야 합니다.
    "private_key": os.environ.get("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n"),
    "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
    "auth_uri": os.environ.get("FIREBASE_AUTH_URI"),
    "token_uri": os.environ.get("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.environ.get("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_X509_CERT_URL"),
    "universe_domain": os.environ.get("FIREBASE_UNIVERSE_DOMAIN"),
    "storageBucket" : os.environ.get("FIREBASE_STORAGE_BUCKET")
}

# STORAGE_BUCKET_NAME은 project_id + ".appspot.com" 형태가 일반적입니다.
FIREBASE_STORAGE_BUCKET = os.environ.get("FIREBASE_STORAGE_BUCKET", f"{firebase_config.get('project_id')}.appspot.com")


# 최초 1회 초기화 (app 시작 시)
if not firebase_admin._apps:
    print("Firebase Admin SDK 초기화 시도...")
    try:
        # credentials.Certificate.from_service_account_info 함수 사용 권장
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred, {
            'storageBucket': FIREBASE_STORAGE_BUCKET # ✅ Storage 버킷 이름 설정 추가
        })
        print("Firebase Admin SDK 초기화 성공")
    except Exception as e:
        print(f"Firebase Admin SDK 초기화 실패: {e}")
        # TODO: 로깅 강화 또는 앱 시작 중단 처리

# ✅ Firebase Storage 버킷 객체 가져오는 함수 추가
def get_firebase_bucket():
    """초기화된 Firebase 앱에서 Storage 버킷 객체를 반환합니다."""
    if not firebase_admin._apps:
        # 초기화되지 않았다면 (예상치 못한 경우) 에러 처리
        print("오류: Firebase Admin SDK가 초기화되지 않았습니다. 버킷을 가져올 수 없습니다.")
        # 초기화 실패 시 명확히 None 반환 또는 에러 발생
        return None

    try:
        # 초기화 시 설정된 기본 버킷 객체 반환
        return storage.bucket()
    except Exception as e:
        print(f"Firebase Storage 버킷 가져오기 실패: {e}")
        return None

# ✅ Firebase Storage URL에서 파일 경로 추출 함수 추가
def extract_firebase_path_from_url(url: str) -> Optional[str]:
    """Firebase Storage URL에서 파일 경로 부분을 추출합니다."""
    if not url:
        return None
    try:
        parsed_url = urlparse(url)
        path_with_o = parsed_url.path

        if '/o/' in path_with_o:
            firebase_path = unquote(path_with_o.split('/o/', 1)[-1])
            return firebase_path
        else:
            print(f"경고: URL에서 '/o/' 경로를 찾을 수 없습니다: {url}")
            return None

    except Exception as e:
        print(f"경고: Firebase URL 파싱 중 오류 발생: {e}, URL: {url}")
        return None


# verify_firebase_token 함수 (기존 코드)
def verify_firebase_token(id_token: str) -> dict:
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token  # { uid, email, ... }
    except Exception as e:
        raise ValueError("Invalid Firebase ID token") from e