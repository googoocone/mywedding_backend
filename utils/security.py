# app/utils/security.py
import uuid
from fastapi import Depends, HTTPException, Request
from datetime import datetime
from grpc import Status
import jwt
import os
import dotenv
from models.users import User
from datetime import datetime, timedelta
from sqlalchemy.orm import Session


from core.database import get_db
from core.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,ADMIN_TOKEN_EXPIRE_MINUTES
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
            
            user = db.query(User).filter(User.id == uid).first()
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

def verify_jwt_token_from_cookie(
    request: Request, # HTTP 요청 객체를 직접 받음
    db: Session = Depends(get_db)
) -> dict:
    """
    쿠키에서 JWT 액세스 토큰을 검증하고, 만료된 경우 리프레시 토큰을 사용하여 갱신합니다.
    성공 시: {"payload": access_token_payload, "new_access_token": new_access_token_or_none}
    실패 시: HTTPException 발생
    """
    token = request.cookies.get("access_cookie")

    if not token:
        # print("❌ 쿠키에 액세스 토큰이 없습니다.")
        raise HTTPException(
            status_code=Status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 쿠키에 없습니다. 로그인이 필요합니다.",
            # headers={"WWW-Authenticate": "Bearer"}, # 쿠키 인증이므로 WWW-Authenticate 헤더는 선택적
        )

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return {
            "payload": payload,
            "new_access_token": None  # 기존 토큰이 유효하므로 새 토큰 없음
        }
    except jwt.ExpiredSignatureError:
        # print("🔶 액세스 토큰 만료됨. 리프레시 시도...")
        try:
            # 만료된 토큰에서 사용자 식별자(sub) 추출 (만료 검증 없이 디코딩)
            expired_payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
            uid = expired_payload.get("sub")
            if not uid:
                # print("❌ 만료된 토큰에서 사용자 식별자(sub)를 찾을 수 없음")
                raise HTTPException(
                    status_code=Status.HTTP_401_UNAUTHORIZED,
                    detail="만료된 토큰의 형식이 올바르지 않습니다."
                )

            # print(f"사용자 UID ({uid})의 리프레시 토큰 조회 중...")
            user = db.query(User).filter(User.uid == uid).first()
            if not user:
                # print(f"❌ UID ({uid})에 해당하는 사용자를 찾을 수 없음")
                raise HTTPException(
                    status_code=Status.HTTP_401_UNAUTHORIZED,
                    detail="사용자 정보를 찾을 수 없습니다 (토큰 갱신 실패)."
                )

            if not user.refresh_token:
                # print(f"❌ 사용자 ({uid})에게 저장된 리프레시 토큰이 없음")
                raise HTTPException(
                    status_code=Status.HTTP_401_UNAUTHORIZED,
                    detail="로그인 세션이 만료되었습니다 (리프레시 토큰 없음)."
                )

            # print("리프레시 토큰 검증 시도...")
            refresh_payload = jwt.decode(user.refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

            # 리프레시 토큰의 타입이 'refresh'인지, sub가 일치하는지 등 추가 검증 가능
            if refresh_payload.get("type") != "refresh":
                # print("❌ 유효하지 않은 리프레시 토큰 타입")
                raise HTTPException(
                    status_code=Status.HTTP_401_UNAUTHORIZED,
                    detail="리프레시 토큰이 올바르지 않습니다."
                )
            if refresh_payload.get("sub") != uid:
                # print("❌ 리프레시 토큰의 사용자 식별자가 일치하지 않음")
                raise HTTPException(
                    status_code=Status.HTTP_401_UNAUTHORIZED,
                    detail="리프레시 토큰 정보가 일치하지 않습니다."
                )
            new_access_token = create_access_token(user) # create_access_token 함수는 User 객체를 인자로 받는다고 가정
            
            return {
                "payload": expired_payload, # 이전 토큰의 페이로드 (사용자 식별용)
                "new_access_token": new_access_token
            }

        except jwt.ExpiredSignatureError: # 리프레시 토큰 자체도 만료된 경우
            # print("❌ 리프레시 토큰도 만료됨. 재로그인 필요.")
            raise HTTPException(
                status_code=Status.HTTP_401_UNAUTHORIZED,
                detail="세션이 완전히 만료되었습니다. 다시 로그인해주세요 (리프레시 토큰 만료)."
            )
        except jwt.PyJWTError as e: # 리프레시 토큰 검증 실패 (유효하지 않은 형식 등)
            # print(f"❌ 리프레시 토큰 검증 실패: {e}")
            raise HTTPException(
                status_code=Status.HTTP_401_UNAUTHORIZED,
                detail=f"세션 갱신에 실패했습니다: {str(e)}"
            )
        except Exception as e: # 그 외 예외 (DB 조회 실패 등)
            # print(f"❌ 토큰 갱신 중 예상치 못한 오류: {e}")
            # 로깅을 통해 상세 오류 확인 필요
            raise HTTPException(
                status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="토큰 갱신 처리 중 서버 오류가 발생했습니다."
            )

    except jwt.InvalidTokenError as e: # 액세스 토큰 자체가 유효하지 않은 경우 (만료 외의 문제)
        # print(f"❌ 유효하지 않은 액세스 토큰: {e}")
        raise HTTPException(
            status_code=Status.HTTP_401_UNAUTHORIZED,
            detail=f"제공된 인증 토큰이 유효하지 않습니다: {str(e)}"
        )
    except Exception as e: # 그 외 JWT 디코딩 관련 오류

        raise HTTPException(
            status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="인증 처리 중 서버 오류가 발생했습니다."
        )



def verify_admin_jwt_token(token: str) -> dict | None:
    """
    Admin JWT 토큰을 검증합니다.
    만료되었거나 유효하지 않은 경우 None을 반환합니다.
    리프레시 토큰 로직은 없습니다.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        # 여기서 payload에 admin 역할이나 특정 클레임이 있는지 추가 검증을 할 수도 있습니다.
        # 예: if payload.get("role") != "admin": return None
        return {"payload": payload}
    except jwt.ExpiredSignatureError:
        print("❌ Admin token has expired.")
        return None  # 토큰 만료 시 None 반환
    except jwt.InvalidTokenError:
        print("❌ Invalid admin token.")
        return None  # 유효하지 않은 토큰(서명 오류, 형식 오류 등) 시 None 반환
    except Exception as e:
        # 기타 예상치 못한 오류 발생 시 로깅하고 None 반환
        print(f"❌ An unexpected error occurred during admin token validation: {str(e)}")
        return None

def create_access_token(user: object) -> str: # user 타입을 더 구체적으로 명시하는 것이 좋습니다 (예: User)
    """
    access token 발급 시 'sub' 클레임에 user.id (UUID)를 사용합니다.
    """

    # print("user 객체 정보:", user.__dict__) # 디버깅용

    subject_id_str: str

    print("user create_access_token", user)
    if hasattr(user, 'id') and isinstance(getattr(user, 'id'), uuid.UUID):
        # SQLAlchemy 모델 객체 또는 'id' 속성으로 UUID를 가진 객체일 경우
        subject_id_str = str(user.id)
        # print(f"SQLAlchemy User 객체에서 id (UUID) 사용: {subject_id_str}")
    elif isinstance(user, dict) and 'id' in user and isinstance(user['id'], uuid.UUID):
        # 딕셔너리이고 'id' 키에 UUID가 있는 경우
        subject_id_str = str(user['id'])
        # print(f"딕셔너리에서 id (UUID) 사용: {subject_id_str}")
    elif isinstance(user, dict) and 'id' in user and isinstance(user['id'], str):
        try:
            uuid.UUID(user['id']) # 문자열이 유효한 UUID 형식인지 확인
            subject_id_str = user['id']
            # print(f"딕셔널이에서 id (문자열 UUID) 사용: {subject_id_str}")
        except ValueError:
            # print(f"오류: 딕셔너리의 'id' 필드가 유효한 UUID 문자열이 아님: {user['id']}")
            raise ValueError("제공된 user 딕셔너리의 'id' 필드가 유효한 UUID 문자열이 아닙니다.")
    elif hasattr(user, 'uid'): # 만약 id가 없고 uid만 있다면 uid를 fallback으로 사용 (선택적)

        subject_id_str = str(user.uid) # 또는 여기서 에러를 발생시킬 수도 있습니다.
    else:
        # print("오류: user 객체에서 'id'(UUID) 또는 'uid'를 추출할 수 없습니다.")
        raise TypeError("토큰 생성을 위한 사용자 ID(UUID)를 user 객체에서 찾을 수 없습니다.")

    
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject_id_str,  # user.id (UUID)를 문자열로 변환하여 sub 클레임에 사용
        "exp": expire,
        "type": "access",
        "role": "user", # 필요에 따라 다른 정보도 추가 가능
        # "uid": str(user.uid) if hasattr(user, 'uid') else None # 기존 uid도 필요하면 추가
    }
    print("payload", payload)
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
    expire = datetime.utcnow() + timedelta(minutes=ADMIN_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": uid,
        "exp": expire,
        "type": "access",
        "role" : "admin"
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token