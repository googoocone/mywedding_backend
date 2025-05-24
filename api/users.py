import base64
from datetime import date, datetime, time, timedelta
import time
import hashlib
import hmac
import os
import random
from typing import Optional
import uuid
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response, requests, status
from fastapi.responses import JSONResponse
from grpc import Status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from models.users import User, UserWeddingInfo
from schemas.user import NicknameAvailabilityResponse, NicknameCheckPayload, NicknameCheckResp, UserProfileResponse, UserProfileUpdate, UserWeddingInfoBase, WeddingInfoSchema
from utils.security import verify_jwt_token, verify_jwt_token_from_cookie
import requests 

router = APIRouter(prefix="/users")

@router.get("/wedding-info", response_model=WeddingInfoSchema)
def get_wedding_info(
    response: Response, # 새 토큰 쿠키 설정을 위해 (선택적)
    current_user_data: dict = Depends(verify_jwt_token_from_cookie),
    db: Session = Depends(get_db)
):
    user_id_from_token_str = current_user_data["payload"]["sub"]
    try:
        user_id_uuid = uuid.UUID(user_id_from_token_str)
    except ValueError:
        raise HTTPException(
            status_code=Status.HTTP_400_BAD_REQUEST, # 대문자 Status -> 소문자 status
            detail="Invalid user ID format in token."
        )
    
    new_access_token = current_user_data.get("new_access_token")
    if new_access_token:
        response.set_cookie(
            key="access_token", # ACCESS_TOKEN_COOKIE_NAME 사용 권장
            value=new_access_token,
            httponly=True,
            samesite="lax",
            secure=True,
        )

    # User 테이블은 사용자 존재 확인을 위해 필요할 수 있음
    db_user = db.query(User).filter(User.id == user_id_uuid).first()
    if not db_user:
        raise HTTPException(status_code=Status.HTTP_404_NOT_FOUND, detail="User not found") # 대문자 Status -> 소문자 status

    info = db.query(UserWeddingInfo).filter(UserWeddingInfo.create_by_user_id == user_id_uuid).first()
    if not info:

        return WeddingInfoSchema(
            nickname=None, # 또는 db_user.name 등을 기본값으로 사용할 수 있음
            email=None,    # 또는 db_user.email 등을 기본값으로 사용할 수 있음
            weddingDate=None,
            weddingRegion=None,
            weddingBudget=None,
            phone = None,
            estimatedGuests=None,
            agreedToPrivacyPolicy=False, # 정보가 없으면 기본적으로 False
            agreedToTermsOfService=False,
            agreedToMarketing=False,
        )

    return WeddingInfoSchema(
        nickname=info.nickname,
        email=info.email,
        weddingDate=info.wedding_date,
        weddingRegion=info.wedding_region,
        weddingBudget=info.expected_budget, # DB 컬럼명 확인
        estimatedGuests=info.attendance,
        phoneNumber=db_user.phone,
        agreedToPrivacyPolicy=info.agreed_to_privacy_policy,
        agreedToTermsOfService=info.agreed_to_terms_of_service,
        agreedToMarketing=info.agreed_to_marketing,
    )


@router.post("/wedding-info", response_model=WeddingInfoSchema)
def update_or_create_wedding_info(
    response: Response,
    payload: WeddingInfoSchema, 
    current_user_data: dict = Depends(verify_jwt_token_from_cookie),
    db: Session = Depends(get_db)
):
    user_id_from_token_str = current_user_data["payload"]["sub"]
    try:
        user_id_uuid = uuid.UUID(user_id_from_token_str)
    except ValueError:
        raise HTTPException(
            status_code=Status.HTTP_400_BAD_REQUEST, 
            detail="Invalid user ID format in token."
        )

    new_access_token = current_user_data.get("new_access_token")
    if new_access_token:
        response.set_cookie(
            key="access_token", # ACCESS_TOKEN_COOKIE_NAME 사용 권장
            value=new_access_token,
            httponly=True,
            samesite="lax",
            secure=True, # HTTPS 환경에서만
        )

    db_user = db.query(User).filter(User.id == user_id_uuid).first()
    if not db_user:
        raise HTTPException(status_code=Status.HTTP_404_NOT_FOUND, detail="User not found") # 대문자 Status -> 소문자 status

    wedding_info = db.query(UserWeddingInfo).filter(UserWeddingInfo.create_by_user_id == user_id_uuid).first()

    if not wedding_info:
        wedding_info = UserWeddingInfo(create_by_user_id=user_id_uuid)
        db.add(wedding_info)

    # UserWeddingInfo 필드 업데이트
    wedding_info.nickname = payload.nickname
    wedding_info.email = payload.email # 웨딩 정보용 이메일
    wedding_info.wedding_date = payload.weddingDate
    wedding_info.wedding_region = payload.weddingRegion
    wedding_info.expected_budget = payload.weddingBudget       # DB 컬럼명 확인 (budget)
    wedding_info.attendance = payload.estimatedGuests

    # 🔽 약관 동의 정보 저장 (SQLAlchemy 모델 필드명은 snake_case)
    wedding_info.agreed_to_privacy_policy = payload.agreedToPrivacyPolicy
    wedding_info.agreed_to_terms_of_service = payload.agreedToTermsOfService
    wedding_info.agreed_to_marketing = payload.agreedToMarketing

    if payload.agreedToPrivacyPolicy:
        wedding_info.privacy_policy_agreed_at = datetime.utcnow()
        wedding_info.agreed_privacy_policy_version = "1.0" # 현재 약관 버전

    try:
        db.commit()
        db.refresh(wedding_info)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR, # 대문자 Status -> 소문자 status
            detail=f"정보 저장에 실패했습니다: {str(e)}"
        )

    # 응답 데이터 구성 (WeddingInfoSchema에 맞게)
    return WeddingInfoSchema(
        nickname=wedding_info.nickname,
        email=wedding_info.email,
        weddingDate=wedding_info.wedding_date,
        weddingRegion=wedding_info.wedding_region,
        weddingBudget=wedding_info.expected_budget, # DB 컬럼명 확인
        estimatedGuests=wedding_info.attendance,

        agreedToPrivacyPolicy=wedding_info.agreed_to_privacy_policy,
        agreedToTermsOfService=wedding_info.agreed_to_terms_of_service,
        agreedToMarketing=wedding_info.agreed_to_marketing,
    )

@router.post("/check-nickname", response_model=NicknameCheckResp) # URL 경로도 확인해주세요.
def check_nickname(
    data: NicknameCheckPayload = Body(...), # 명시적으로 Body에서 온다고 지정할 수도 있습니다.
    db: Session = Depends(get_db)
):
    print('data received from body:', data.nickname) # 이제 data.nickname으로 접근
    # user_id = current_user["payload"]["sub"]
    
    existing = (
        db.query(UserWeddingInfo)
        .filter(UserWeddingInfo.nickname == data.nickname)
        .first()
    )

    available = not existing 
    return {"available": available}


NCP_ACCESS_KEY = os.getenv("NCP_ACCESS_KEY")
NCP_SECRET_KEY = os.getenv("NCP_SECRET_KEY")
NCP_SERVICE_ID = os.getenv("NCP_SERVICE_ID")
NCP_SENS_CALLING_NUMBER = os.getenv("NCP_SENS_CALLING_NUMBER")

if not all([NCP_ACCESS_KEY, NCP_SECRET_KEY, NCP_SERVICE_ID, NCP_SENS_CALLING_NUMBER]):
    raise ValueError("네이버 클라우드 플랫폼 SENS 관련 환경 변수가 설정되지 않았습니다.")

# --- SENS API 호출을 위한 헬퍼 함수 (직접 구현) ---
# Naver Cloud Platform API Gateway Signature 생성 함수
def make_sens_signature(timestamp_str, method, url, secret_key):
    secret_key_bytes = bytes(secret_key, 'UTF-8')

    # <<< 여기가 핵심 변경 부분입니다. NCP_ACCESS_KEY 뒤의 '\n'을 제거했습니다. >>>
    message = method + " " + url + "\n" + \
              timestamp_str + "\n" + \
              NCP_ACCESS_KEY
    # <<< 변경 끝 >>>

    message_bytes = bytes(message, 'UTF-8')
    
    hmac_key = hmac.new(secret_key_bytes, message_bytes, digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(hmac_key).decode('UTF-8') # 이 부분은 일단 그대로 둡니다.

    return signature

# --- In-memory (임시) 인증 코드 저장소 ---
# 실제 프로덕션에서는 Redis, 데이터베이스 등을 사용해야 합니다.
# key: phone_number, value: {"code": "123456", "expires_at": datetime_object}
verification_codes = {}

class PhoneNumberRequest(BaseModel):
    phone_number: str

class VerifyCodeRequest(BaseModel):
    phone_number: str
    code: str



# --- SMS 인증 관련 엔드포인트 ---
@router.post("/send-sms-code")
async def send_sms_code(phone_request: PhoneNumberRequest):
    phone_number = phone_request.phone_number

    # 휴대폰 번호 유효성 검사 (서버에서도 다시 검증)
    if not phone_number or not phone_number.startswith("010") or len(phone_number) != 11 or not phone_number.isdigit():
        raise HTTPException(
            status_code=Status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 휴대폰 번호입니다."
        )

    # 6자리 랜덤 인증 코드 생성
    verification_code = str(random.randint(100000, 999999))
    
    # 인증 코드 유효 시간 설정 (예: 3분)
    expires_at = datetime.now() + timedelta(minutes=3)

    # In-memory 저장 (실제로는 데이터베이스나 Redis 사용)
    verification_codes[phone_number] = {
        "code": verification_code,
        "expires_at": expires_at
    }
    print(f"Generated code for {phone_number}: {verification_code}, expires at: {expires_at}")

    # --- 네이버 SENS API 호출 ---
    # 실제 SENS API 호출 로직은 NaverCloudPlatformClient 라이브러리를 사용하거나
    # 직접 requests 라이브러리로 HTTP 요청을 구성해야 합니다.
    # 여기서는 requests를 이용한 기본적인 예시를 보여줍니다.

    url = f"https://sens.apigw.ntruss.com/sms/v2/services/{NCP_SERVICE_ID}/messages"
    timestamp = str(int(time.time() * 1000))
    
    headers = {
        "Content-Type": "application/json; charset=utf-8", # <--- 여기가 문제의 지점일 가능성
        "x-ncp-apigw-timestamp": timestamp,
        "x-ncp-iam-access-key": NCP_ACCESS_KEY,
        "x-ncp-apigw-signature-v2": make_sens_signature(
            timestamp, "POST", f"/sms/v2/services/{NCP_SERVICE_ID}/messages", NCP_SECRET_KEY
        )
    }
    body = {
        "type": "SMS",
        "contentType": "COMM", # COMM: 일반 메시지, AD: 광고 메시지
        "countryCode": "82",
        "from": NCP_SENS_CALLING_NUMBER, # 사전에 등록된 발신번호
        "content": f"[MyWeddingDiary] 인증번호 [{verification_code}]를 입력해주세요.", # 실제 발송 메시지
        "messages": [
            {
                "to": phone_number,
                "content": f"[MyWeddingDiary] 인증번호 [{verification_code}]를 입력해주세요."
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=body) 
        response.raise_for_status() # HTTP 에러 발생 시 예외 발생

        sens_response_data = response.json()
        print(f"SENS API Response: {sens_response_data}")

        if sens_response_data.get("statusCode") == "202":
            return {"message": "인증번호가 성공적으로 전송되었습니다."}
        else:
            print(f"SENS API Error: {sens_response_data.get('statusName')}, {sens_response_data.get('statusMessage')}")
            raise HTTPException(
                status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"인증번호 전송 실패: {sens_response_data.get('statusMessage', '알 수 없는 오류')}"
            )

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="인증번호 전송 서버 통신 오류."
        )


@router.post("/verify-sms-code")
async def verify_sms_code(
    verify_request: VerifyCodeRequest, 
    current_user_data: dict = Depends(verify_jwt_token_from_cookie),
    db:Session=Depends(get_db)
    ):


    phone_number = verify_request.phone_number
    entered_code = verify_request.code

    stored_info = verification_codes.get(phone_number)

    user_id_from_token_str = current_user_data["payload"]["sub"]

    try:
        user_id_uuid = uuid.UUID(user_id_from_token_str)
    except ValueError:
        raise HTTPException(
            status_code=Status.HTTP_400_BAD_REQUEST, # 대문자 Status -> 소문자 status
            detail="Invalid user ID format in token."
        )
    
    db_user = db.query(User).filter(User.id == user_id_uuid).first()

    if not stored_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="인증번호를 요청하지 않았거나 만료되었습니다."
        )

    stored_code = stored_info["code"]
    expires_at = stored_info["expires_at"]

    print('current', current_user_data)

    if datetime.now() > expires_at:
        del verification_codes[phone_number] # 만료된 코드 삭제
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="인증번호 유효 시간이 만료되었습니다. 다시 요청해주세요."
        )

    if entered_code == stored_code:
        # 인증 성공 시 코드 삭제 (한 번 사용 후 재사용 방지)
        del verification_codes[phone_number]
        db_user.phone = phone_number

        try : 
            db.commit()
        except Exception as e: 
            raise HTTPException(
                status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR, # 대문자 Status -> 소문자 status
                detail=f"정보 저장에 실패했습니다: {str(e)}"
        )

        
        return {"verified": True, "message": "휴대폰 인증이 완료되었습니다."}
    else:
        return {"verified": False, "message": "인증번호가 일치하지 않습니다."}

