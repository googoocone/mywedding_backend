# app/utils/security.py
from fastapi import Depends
from datetime import datetime
import jwt
import os
import dotenv
from models.users import User
from datetime import datetime, timedelta
from sqlalchemy.orm import Session


from core.database import get_db
from core.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

dotenv.load_dotenv()

SECRET_KEY = os.getenv('JWT_SECRET_KEY')
ALGORITHM = "HS256"



def verify_jwt_token(token: str, db: Session = Depends(get_db)) -> dict | None:
    print("검증합니다....", token)
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        return {
            "payload": payload,
            "new_access_token": None
        }
    except jwt.ExpiredSignatureError:
        try:
            print("토큰 만료")
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
            uid = payload.get("sub")

            db = next(get_db())
            user = db.query(User).filter(User.uid == uid).first()
            if not user:
                print("유저 없음")
                return None

            refresh_token = user.refresh_token
            if not refresh_token:
                print("리프레시 토큰 없음")
                return None

            try:
                refresh_payload = jwt.decode(refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
                if refresh_payload["type"] != "refresh":
                    return None

                new_access_token = create_access_token(user)
                return {
                    "payload": payload,
                    "new_access_token": new_access_token
                }
            except jwt.PyJWTError as e:
                print("리프레시 토큰 문제", e)
                return None
        except Exception as e:
            print("❌ 만료된 토큰 디코딩 실패", e)
            return None
    except jwt.InvalidTokenError:

        print("❌ 유효하지 않은 토큰")
        return None


def create_access_token(user: dict | object) -> str:
    """
    access token 발급
    """
    uid = user["uid"] if isinstance(user, dict) else user.uid
    print("uid", uid, type(uid))

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


def get_new_access_token(payload: dict, db:Session = Depends(get_db)):
    try:
        print("payload", payload)
        try: 
            user = db.query(User).filter(User.uid == payload["sub"]).first()
        except:
            print("안되네? ")
        if user : 
            print("good")
        refresh_token = user.refresh_token
        print("refreshToken", refresh_token)
        print("실행")
        if payload.get("type") == "refresh":
            # 데이터베이스에서 해당 리프레시 토큰이 유효한지 확인 (예: 만료되지 않았는지, 사용자가 존재하는지 등)
            # ...

            user_id = payload.get("sub")
            # 새로운 액세스 토큰 발급
            access_token = create_access_token({"uid": user_id})
            return access_token
        else:
            print("유효하지 않은 리프레시 토큰 타입")
            return None
    except jwt.ExpiredSignatureError:
        print("리프레시 토큰 만료")
        return None
    except jwt.InvalidTokenError:
        print("유효하지 않은 리프레시 토큰")
        return None
    
def create_admin_token(admin: dict | object) -> str:
    """
    admin access token 발급
    """

    uid = str(admin.id)
    print("uid", uid, type(uid))
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": uid,
        "exp": expire,
        "type": "access",
        "role" : "admin"
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token