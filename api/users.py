from datetime import date
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from grpc import Status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from models.users import User, UserWeddingInfo
from schemas.user import NicknameAvailabilityResponse, UserProfileResponse, UserProfileUpdate, UserWeddingInfoBase
from utils.security import verify_jwt_token

router = APIRouter(prefix="/users")

@router.get("/")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {"users": users}


class WeddingInfoSchema(BaseModel):
    nickname: str
    weddingDate: Optional[date]
    weddingRegion: str
    weddingBudget: Optional[int]
    estimatedGuests: Optional[int]
    preferredHallType: Optional[str]

    class Config:
        orm_mode = True

@router.get("/wedding-info", response_model=WeddingInfoSchema)
def get_wedding_info(
    current_user: dict = Depends(verify_jwt_token),
    db: Session = Depends(get_db)
):
    user_id = current_user["payload"]["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    info = db.query(UserWeddingInfo).filter(
        UserWeddingInfo.create_by_user_id == user_id
    ).first()
    return {
        "nickname": user.name,
        "weddingDate": info.wedding_date if info else None,
        "weddingRegion": info.wedding_region if info else "",
        "weddingBudget": info.expected_buget if info else None,
        "estimatedGuests": info.attendance if info else None,
        "preferredHallType": info.prefered_hall_type if info else None,
    }

class WeddingInfoCreate(BaseModel):
    nickname: str
    weddingDate: Optional[date]
    weddingRegion: str
    weddingBudget: Optional[int]
    estimatedGuests: Optional[int]
    preferredHallType: Optional[str]

@router.post("/wedding-info", response_model=WeddingInfoSchema)
def upsert_wedding_info(
    data: WeddingInfoCreate,
    current_user: dict = Depends(verify_jwt_token),
    db: Session = Depends(get_db)
):
    user_id = current_user["payload"]["sub"]
    print('user_id', user_id)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Update nickname
    user.name = data.nickname
    db.add(user)
    info = db.query(UserWeddingInfo).filter(
        UserWeddingInfo.create_by_user_id == user_id
    ).first()
    if info:
        info.wedding_date = data.weddingDate
        info.wedding_region = data.weddingRegion
        info.expected_buget = data.weddingBudget
        info.attendance = data.estimatedGuests
        info.prefered_hall_type = data.preferredHallType
    else:
        info = UserWeddingInfo(
            wedding_date = data.weddingDate,
            wedding_region = data.weddingRegion,
            expected_buget = data.weddingBudget,
            attendance = data.estimatedGuests,
            prefered_hall_type = data.preferredHallType,
            create_by_user_id = user_id
        )
        db.add(info)
    db.commit()
    return data

# Nickname Duplication Check

class NicknameCheckPayload(BaseModel):
    nickname: str

class NicknameCheckResp(BaseModel):
    available: bool

@router.post("/check-nickname", response_model=NicknameCheckResp) # URL 경로도 확인해주세요.
def check_nickname(
    # data: NicknameCheckPayload, # 이렇게만 해도 FastAPI는 보통 본문으로 인식합니다.
    data: NicknameCheckPayload = Body(...), # 명시적으로 Body에서 온다고 지정할 수도 있습니다.
    # current_user: dict = Depends(verify_jwt_token),
    db: Session = Depends(get_db)
):
    print('data received from body:', data.nickname) # 이제 data.nickname으로 접근
    # user_id = current_user["payload"]["sub"]
    
    existing = (
        db.query(UserWeddingInfo)
        .filter(UserWeddingInfo.nickname == data.nickname)
        .first()
    )
    
    # available = not existing or str(existing.create_by_user_id) == user_id
    
    available = not existing 
    return {"available": available}

# In main.py:
# app.include_router(router)