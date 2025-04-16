# app/utils/security.py
from datetime import datetime
import jwt
import os
import dotenv
from datetime import datetime, timedelta
from core.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

dotenv.load_dotenv()

SECRET_KEY = os.getenv('JWT_SECRET_KEY')
ALGORITHM = "HS256"

def verify_jwt_token(token: str):
    print("검증합니다....", token)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(payload)
        return payload
    except jwt.ExpiredSignatureError:
        print("토큰 만료")
        refresh_access_token(payload)
        return None
    except jwt.InvalidTokenError:
        print("유효하지 않는 토큰")
        return None

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

def refresh_access_token(payload:dict) : 
    """
    엑세스 토큰 재발급
    """

    print("실행이 되니?")
    