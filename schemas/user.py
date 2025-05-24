# schemas/user.py (또는 profile.py)
from pydantic import BaseModel, Field, validator, EmailStr 
from typing import Optional, List
from datetime import date

class NicknameAvailabilityResponse(BaseModel):
    isAvailable: bool
    message: Optional[str] = None

class UserWeddingInfoBase(BaseModel):
    wedding_date: Optional[date] = None # "미정"일 경우 null 허용
    wedding_region: str = Field(..., min_length=1)
    expected_budget: int = Field(..., ge=0)
    preferred_hall_type: str = Field(..., min_length=1)
    estimated_guests: int = Field(..., ge=0) # attendance 필드명과 일치시킴

class UserProfileUpdate(UserWeddingInfoBase):
    nickname: str = Field(..., min_length=1, max_length=9)

class UserProfileResponse(UserWeddingInfoBase):
    nickname: str
    # 여기에 UserWeddingInfo의 다른 필드들도 필요하다면 추가 (예: id)
    
    class Config:
        orm_mode = True # SQLAlchemy 모델과 자동 매핑

class WeddingInfoCreate(BaseModel):
    nickname: str
    weddingDate: Optional[date]
    weddingRegion: str
    weddingBudget: Optional[int]
    estimatedGuests: Optional[int]

class NicknameCheckPayload(BaseModel):
    nickname: str

class NicknameCheckResp(BaseModel):
    available: bool

class WeddingInfoSchema(BaseModel):
    nickname: Optional[str] = None
    email: Optional[EmailStr] = None # 웨딩 정보용 이메일
    phoneNumber:Optional[str] = None
    weddingDate: Optional[date] = None
    weddingRegion: Optional[str] = None
    weddingBudget: Optional[int] = None
    estimatedGuests: Optional[int] = None
    agreedToPrivacyPolicy: Optional[bool] = None
    agreedToTermsOfService: Optional[bool] = None
    agreedToMarketing: Optional[bool] = None
    privacy_policy_agreed_at: Optional[date] = None
    agreed_privacy_policy_version : Optional[str] = None

    class Config:
        from_attributes = True 