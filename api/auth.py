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
    # print("firebase_data", firebase_data["idToken"])

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
    secure=True,           
    samesite="None",         
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
            secure=True,
            samesite="None",
            max_age=86400,
            path="/"
        )

    user_id = payload.get("sub")
    print('user_id', user_id)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": {
            "name": user.name,
            "profile_image": user.profile_image,
            "id" : user.id,
            "phone" : bool(user.phone)
        }
    }



@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_cookie", path='/')
    return {"message": "로그아웃 완료"}


