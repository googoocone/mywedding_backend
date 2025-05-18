# schemas/admin.py

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from datetime import date, time as times
import enum

class HallTypeEnum(str, enum.Enum):
    야외 = "야외"
    호텔 = "호텔"
    가든 = "가든"
    스몰 = "스몰"
    하우스 = "하우스"
    컨벤션 = "컨벤션"
    채플 = "채플"

class MoodEnum(str, enum.Enum): # HallSchema에 mood가 str로 되어있으므로, Enum 사용 권장
    밝은 = "밝은"
    어두운 = "어두운"

class CodeRequest(BaseModel):
    id: str
    password: str

class HallPhotoSchema(BaseModel):
    url: str
    order_num: int
    caption: str
    is_visible: bool

class HallIncludeSchema(BaseModel):
    category: str
    subcategory: str

class HallSchema(BaseModel): # 제공해주신 스키마
    name: str
    interval_minutes: int
    guarantees: int
    parking: int
    # ✨ [수정됨] type 필드를 HallTypeEnum 리스트로 변경, 기본값 빈 리스트
    type: Optional[List[HallTypeEnum]]
    mood: MoodEnum # 문자열 대신 정의된 Enum 사용 권장, Optional 여부 확인 필요 (현재는 필수로 가정)

    class Config:
        orm_mode = True
        use_enum_values = True # Enum 값을 실제 문자열 값으로 사용

class MealTypeSchema(BaseModel):
    meal_type: str
    category: str
    price: int
    extra: Optional[str] = None

class EstimateOptionSchema(BaseModel):
    name: str
    price: int
    is_required: bool
    description: str
    reference_url: str = None

class EstimateSchema(BaseModel):
    hall_price: int
    type: str
    date: date
    time : Optional[times] = None
    penalty_amount: Optional[int] = None
    penalty_detail: Optional[str] = None

class WeddingPackageSchema(BaseModel):
    type: str
    name: str
    total_price: int
    is_total_price: bool

class PackageItemSchema(BaseModel):
    type: str
    company_name: str
    price: int
    description: str
    url: str = None

class EtcSchema(BaseModel):
    content: str

class WeddingCompanyCreate(BaseModel):
    name: str
    address: str
    phone: str
    homepage: str = None
    accessibility: Optional[str] = None
    mapx: Optional[str] = None
    mapy: Optional[str] = None
    ceremony_times: Optional[str] = None
    meal_price : List[MealTypeSchema]

    hall: HallSchema
    hall_includes: List[HallIncludeSchema]
    hall_photos: List[HallPhotoSchema]

    estimate: EstimateSchema
    estimate_options: Optional[List[EstimateOptionSchema]] = []

    # wedding_package: WeddingPackageSchema
    # package_items: Optional[List[PackageItemSchema]] = []

    etc: Optional[EtcSchema] = None
