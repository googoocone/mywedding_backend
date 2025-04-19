from fastapi import APIRouter, Request, Depends, HTTPException, Response, Body
import requests
from sqlalchemy.orm import Session
from core.database import get_db
from utils.security import create_access_token, create_refresh_token
from models.users import User
from utils.security import verify_jwt_token
from firebase_admin import auth
from crud.user import get_user_by_uid
import uuid
from fastapi.responses import JSONResponse
from auth import firebase 
from pydantic import BaseModel
import os
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

class CodeRequest(BaseModel):
    code: str

router = APIRouter(prefix="/auth")

@router.post("/kakao/token")
def kakao_login(body: CodeRequest, response : Response,db: Session = Depends(get_db)):
    code = body.code
    client_id = os.getenv("KAKAO_CLIENT_ID")
    redirect_uri = os.getenv("KAKAO_REDIRECT_URI")
    client_secret = os.getenv("KAKAO_CLIENT_SECRET")

    # 카카오 인증
    token_response = requests.post(
        "https://kauth.kakao.com/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "client_secret" : client_secret,
            "code": code,
        },
    )

    token_json = token_response.json()
    kakao_access_token = token_json.get("access_token")
    print("kakao_token", token_json)
    # 카카오 유저 정보 획득
    kakao_user_info_res = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={"Authorization": f"Bearer {kakao_access_token}"}
    )
    user_info = kakao_user_info_res.json()

    user_id = user_info["id"]
    user_name = user_info["properties"]["nickname"]
    user_profile_image = user_info["properties"]["profile_image"]

    uid = f"kakao:{user_id}"
    try:
        firebase_custom_token = auth.create_custom_token(uid)
    except Exception as e:
        # --- 상세 에러 확인을 위한 코드 추가 ---
        print(f"!!!!!!!! Firebase Custom Token 생성 중 오류 발생 !!!!!!!!!!")
        print(f"오류 타입: {type(e)}")
        print(f"오류 메시지: {e}")
        import traceback # Traceback 모듈 import
        traceback.print_exc() # 전체 Traceback 출력 (어디서 오류났는지 상세히 보여줌)
        raise HTTPException(status_code=500, detail=f"Firebase 토큰 생성 실패: {str(e)}")
    

    firebase_res = requests.post(
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken",
        params={"key": os.getenv("FIREBASE_API_KEY")},
        json={
            "token": firebase_custom_token.decode("utf-8"),
            "returnSecureToken": True
            }
    )
    
    if firebase_res.status_code != 200:
        raise HTTPException(status_code=500, detail="Firebase 인증 실패")

    firebase_data = firebase_res.json()
    print("firebase_data", firebase_data["idToken"])

    if firebase_data["isNewUser"] == True:
        user = User(
                    id=str(uuid.uuid4()),
                    uid=uid,
                    name=user_name,
                    profile_image=user_profile_image,
                    
                )
        db.add(user)
        db.commit()
    else : 
        user = db.query(User).filter(User.uid == uid).first()

    # 토큰 발급 (유저 정보가 있는 후에)
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    response.set_cookie(
    key="access_cookie",
    value=access_token,
    httponly=True,
    secure=False,           # ✅ 로컬 개발에서는 False
    samesite="lax",         # ✅ 기본값으로
    max_age=86400,
    path='/'
    )

    user.refresh_token = refresh_token
    db.commit()


    return {"access_token": user_info}

    
# 

@router.get("/me")
def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("access_cookie")
    if not token:
        raise HTTPException(status_code=401, detail="Access token missing")

    result = verify_jwt_token(token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    payload = result["payload"]
    new_access_token = result.get("new_access_token")

    if new_access_token:
        response.set_cookie(
            key="access_cookie",
            value=new_access_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=86400,
            path="/"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.uid == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": {
            "name": user.name,
            "profile_image": user.profile_image,
        }
    }



@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_cookie")
    return {"message": "로그아웃 완료"}

# @router.post('/firebase-login') 
# async def firebase_login(request: Request, db: Session = Depends(get_db)):
#     # ✅ 헤더에서 Authorization 토큰 꺼내기
#     token = request.headers.get("Authorization")
#     if not token or not token.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="No token provided")

#     kakao_token = token.split(" ")[1]

#     # ✅ 카카오 유저 정보 요청
#     kakao_user_info_res = requests.get(
#         "https://kapi.kakao.com/v2/user/me",
#         headers={"Authorization": f"Bearer {kakao_token}"}
#     )
    
#     if kakao_user_info_res.status_code != 200:
#         raise HTTPException(status_code=400, detail="카카오 유저 정보 조회 실패")

#     kakao_user = kakao_user_info_res.json()
#     print("kakao USer", kakao_user)
#     kakao_id = kakao_user.get("id")
#     kakao_name = kakao_user.get("properties", {}).get('nickname', "")
#     kakao_profile_image = kakao_user.get("properties", {}).get("profile_image", "")

#     if not kakao_id:
#         raise HTTPException(status_code=400, detail="카카오 ID 누락")

#     # ✅ Firebase 커스텀 토큰 생성
#     uid = f"kakao:{kakao_id}"
#     try:
#         firebase_custom_token = auth.create_custom_token(uid)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Firebase 토큰 생성 실패: {str(e)}")
    

#     return {
#         "firebase_token" : firebase_custom_token,
#         "kakao_user": {
#             "name": kakao_name,
#             "profile_image":  kakao_profile_image
#         }
#     }


@router.post('/server-login')
# async def server_login(request: Request, response: Response, db: Session = Depends(get_db)):
#     token = request.headers.get("Authorization")
#     if not token or not token.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="토큰 없음")
    
#     id_token = token.split(" ")[1]

#     body = await request.json()
#     kakao_user = body.get("kakao_user", {})
#     user_name = kakao_user.get("name", "")
#     user_profile_image = kakao_user.get("profile_image", "")

#     try:
#         decoded_token = auth.verify_id_token(id_token)
#         uid = decoded_token["uid"]

#         # Firebase에 유저 있는지 확인
#         try:
#             firebase_user = auth.get_user(uid)
#         except auth.UserNotFoundError:
#             firebase_user = auth.create_user(uid=uid)

#         # 서버 DB에서 유저 조회 (먼저 실행)
#         user = db.query(User).filter(User.uid == uid).first()
        
#         if not user:
#             user = User(
#                 id=str(uuid.uuid4()),
#                 uid=uid,
#                 name=user_name,
#                 profile_image=user_profile_image
#             )
#             db.add(user)
#             db.commit()
        
#         # 토큰 발급 (유저 정보가 있는 후에)
#         access_token = create_access_token(user)
#         refresh_token = create_refresh_token(user)
        
#         # 리프레시 토큰 DB에 저장
#         user.refresh_token = refresh_token
#         db.commit()
        
#         print(f"액세스 토큰 설정: {access_token}...")
#         print(f"리프레시 토큰 설정: {refresh_token}...")
        
#         # HttpOnly 쿠키에 액세스 토큰 설정
#         response.set_cookie(key="access_cookie", value=access_token, httponly=True,secure=True, samesite="none", max_age=86400, path='/')
        
#         # 리프레시 토큰도 쿠키에 설정 (더 긴 수명)


#         print("쿠키 설정 완료")

#         # 응답에는 토큰을 포함하지 않고 사용자 정보만 반환
#         return {
#                 "user": {
#                     "name": user_name,
#                     "profile_image": user_profile_image
#                 },
#                 "status_code":200,
#             }
 
    
#     except Exception as e:
#         print("인증 에러:", str(e))
#         raise HTTPException(status_code=401, detail=str(e))




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