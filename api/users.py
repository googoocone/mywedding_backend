from datetime import date, datetime
from typing import Optional
import uuid
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from grpc import Status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from models.users import User, UserWeddingInfo
from schemas.user import NicknameAvailabilityResponse, NicknameCheckPayload, NicknameCheckResp, UserProfileResponse, UserProfileUpdate, UserWeddingInfoBase, WeddingInfoSchema
from utils.security import verify_jwt_token, verify_jwt_token_from_cookie

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
        # preferredHallType=info.preferred_hall_type, # 제거됨
        # 🔽 약관 동의 정보 응답에 포함 (SQLAlchemy 모델 필드명은 snake_case)
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

# In main.py:
# app.include_router(router)