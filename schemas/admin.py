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

class HallSchema(BaseModel): # 사용자 제공 스키마
    name: str
    interval_minutes: int
    guarantees: int
    parking: int
    # ✨ type: Optional[List[HallTypeEnum]]은 이미 올바르게 되어 있습니다. 기본값만 명시적으로 추가.
    type: Optional[List[HallTypeEnum]] = Field(default_factory=list) 
    mood: MoodEnum 

    class Config:
        orm_mode = True
        use_enum_values = True

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
