# app/utils/security.py
import jwt
import os
import dotenv

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
        return None
    except jwt.InvalidTokenError:
        print("유효하지 않는 토큰")
        return None
