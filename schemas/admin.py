# schemas/admin.py

from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import date, time as times

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

class HallSchema(BaseModel):
    name: str
    interval_minutes: int
    guarantees: int
    parking: int
    type: str
    mood: str

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

    wedding_package: WeddingPackageSchema
    package_items: Optional[List[PackageItemSchema]] = []

    etc: Optional[EtcSchema] = None
