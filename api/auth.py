from fastapi import APIRouter, Request, Depends, HTTPException, Response
import requests
from sqlalchemy.orm import Session
from core.database import get_db
from auth.firebase import create_access_token, create_refresh_token
from models.users import User
from utils.security import verify_jwt_token
from firebase_admin import auth
from crud.user import get_user_by_uid
import uuid
from fastapi.responses import JSONResponse
import jwt
from datetime import datetime, timedelta
from pydantic import BaseModel
import os
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/auth")


@router.post('/firebase-login') 
async def firebase_login(request: Request, db: Session = Depends(get_db)):
    # ✅ 헤더에서 Authorization 토큰 꺼내기
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token provided")

    kakao_token = token.split(" ")[1]

    # ✅ 카카오 유저 정보 요청
    kakao_user_info_res = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {kakao_token}"}
    )
    
    if kakao_user_info_res.status_code != 200:
        raise HTTPException(status_code=400, detail="카카오 유저 정보 조회 실패")

    kakao_user = kakao_user_info_res.json()
    print("kakao USer", kakao_user)
    kakao_id = kakao_user.get("id")
    kakao_name = kakao_user.get("properties", {}).get('nickname', "")
    kakao_profile_image = kakao_user.get("properties", {}).get("profile_image", "")

    if not kakao_id:
        raise HTTPException(status_code=400, detail="카카오 ID 누락")

    # ✅ Firebase 커스텀 토큰 생성
    uid = f"kakao:{kakao_id}"
    try:
        firebase_custom_token = auth.create_custom_token(uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Firebase 토큰 생성 실패: {str(e)}")
    

    return {
        "firebase_token" : firebase_custom_token,
        "kakao_user": {
            "name": kakao_name,
            "profile_image":  kakao_profile_image
        }
    }
    
@router.post('/server-login')
async def server_login(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="토큰 없음")
    
    id_token = token.split(" ")[1]

    body = await request.json()
    kakao_user = body.get("kakao_user", {})
    user_name = kakao_user.get("name", "")
    user_profile_image = kakao_user.get("profile_image", "")

    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]

        # Firebase에 유저 있는지 확인
        try:
            firebase_user = auth.get_user(uid)
        except auth.UserNotFoundError:
            firebase_user = auth.create_user(uid=uid)

        # 서버 DB에서 유저 조회 (먼저 실행)
        user = db.query(User).filter(User.uid == uid).first()
        
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                uid=uid,
                name=user_name,
                profile_image=user_profile_image
            )
            db.add(user)
            db.commit()
        
        # 토큰 발급 (유저 정보가 있는 후에)
        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)
        
        # 리프레시 토큰 DB에 저장
        user.refresh_token = refresh_token
        db.commit()
        
        print(f"액세스 토큰 설정: {access_token}...")
        print(f"리프레시 토큰 설정: {refresh_token}...")
        
        # HttpOnly 쿠키에 액세스 토큰 설정
        response.set_cookie(key="access_cookie", value=access_token, httponly=True,secure=True, samesite="none", max_age=86400, path='/')
        
        # 리프레시 토큰도 쿠키에 설정 (더 긴 수명)


        print("쿠키 설정 완료")

        # 응답에는 토큰을 포함하지 않고 사용자 정보만 반환
        return {
                "user": {
                    "name": user_name,
                    "profile_image": user_profile_image
                },
                "status_code":200,
            }
 
    
    except Exception as e:
        print("인증 에러:", str(e))
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
async def get_me(request: Request):
    print("실행된다")
    access_cookie = request.cookies.get("access_cookie")
    if not access_cookie:
        raise HTTPException(status_code=401, detail="쿠키 없음")

    # 여기선 간단히 토큰 디코딩 없이 쿠키 존재 여부만 반환해도 됨
    return JSONResponse(content={"message": "인증됨", "token": access_cookie})


# @router.post('/refresh')
# async def refresh_access_token(request: Request, response: Response, db: Session = Depends(get_db)):
#     # 요청 헤더와 쿠키 디버깅
#     print("요청 헤더:", request.headers)
#     print("요청 쿠키:", request.cookies)
    
#     refresh_token = request.cookies.get("refresh_token")
    
#     if not refresh_token:
#         print("리프레시 토큰 쿠키가 없습니다.")
#         raise HTTPException(status_code=401, detail="리프레시 토큰이 없습니다")
    
#     try:
#         # 리프레시 토큰 검증
#         print(f"리프레시 토큰 검증 시도: {refresh_token[:10]}...")
        
#         secret_key = os.environ.get("JWT_REFRESH_SECRET_KEY", "your_refresh_secret_key")
#         print(f"사용 중인 시크릿 키: {secret_key[:5]}...")
        
#         payload = jwt.decode(
#             refresh_token, 
#             key=secret_key, 
#             algorithms=["HS256"]
#         )
#         user_id = payload.get("sub")
        
#         user = db.query(User).filter(User.id == user_id).first()
#         if not user:
#             print(f"ID가 {user_id}인 사용자를 찾을 수 없습니다.")
#             raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다")
            
#         if user.refresh_token != refresh_token:
#             print("저장된 리프레시 토큰과 일치하지 않습니다.")
#             raise HTTPException(status_code=401, detail="리프레시 토큰이 만료되었습니다")
        
#         # 새 액세스 토큰 발급
#         new_access_token = create_access_token(user)
#         print(f"새 액세스 토큰 발급: {new_access_token[:10]}...")
        
#         # 쿠키에 새 액세스 토큰 설정
#         response.set_cookie(
#             key="access_token",
#             value=new_access_token,
#             httponly=True,
#             secure=False,  # SameSite=None에는 Secure=True가 필요함
#             samesite="lax",
#             max_age=86400,
#             domain="localhost",  # 도메인을 명시적으로 설정
#             path="/"            # 모든 경로에서 쿠키 접근 가능
#         )
        
#         # CORS 헤더 추가
#         response.headers["Access-Control-Allow-Origin"] = "http://localhost:3000"
#         response.headers["Access-Control-Allow-Credentials"] = "true"
        
#         print("새 액세스 토큰 쿠키 설정 완료")
        
#         return {
#             "code": 200,
#             "message": "토큰이 갱신되었습니다"
#         }
#     except jwt.ExpiredSignatureError:
#         print("리프레시 토큰이 만료되었습니다.")
#         raise HTTPException(status_code=401, detail="리프레시 토큰이 만료되었습니다")
#     except jwt.InvalidTokenError as e:
#         print(f"유효하지 않은 토큰: {str(e)}")
#         raise HTTPException(status_code=401, detail=f"유효하지 않은 토큰: {str(e)}")
#     except Exception as e:
#         print(f"예상치 못한 오류: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


@router.post('/logout')
async def logout(response: Response):
    # 쿠키 삭제
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    
    return {
        "code": 200,
        "message": "로그아웃 성공"
    }