import firebase_admin
from firebase_admin import credentials, auth
from datetime import datetime, timedelta
from jose import jwt
from core.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

# 최초 1회 초기화 (app 시작 시)
cred = credentials.Certificate("mywedding-136d8-firebase-adminsdk-fbsvc-bf78e895ba.json")
firebase_admin.initialize_app(cred)

def verify_firebase_token(id_token: str) -> dict:
    try:
        
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token  # { uid, email, ... }
    except Exception as e:
        raise ValueError("Invalid Firebase ID token") from e

def create_access_token(user: dict | object) -> str:
    """
    access token 발급
    """
    uid = user["uid"] if isinstance(user, dict) else user.uid

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": uid,
        "exp": expire,
        "type": "access",
        "role" : "user"
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def create_refresh_token(user: dict | object) -> str:
    """
    refresh token 발급
    """
    uid = user["uid"] if isinstance(user, dict) else user.uid

    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": uid,
        "exp": expire,
        "type": "refresh"
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token