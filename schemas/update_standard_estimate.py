from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union

from models.enums import EstimateTypeEnum

class CompanyUpdateSchema(BaseModel):
    id: int # 업데이트 대상 ID
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    homepage: Optional[str] = None
    accessibility: Optional[str] = None
    lat: Optional[float] = None # WeddingCompanyData는 number지만, DB는 float/int일 수 있음
    lng: Optional[float] = None
    ceremony_times: Optional[str] = None

    class Config:
        from_attributes = True


class HallIncludeUpdateSchema(BaseModel):
    id: Optional[int] = None # 기존 항목 업데이트 시 ID 포함
    category: Optional[str] = None
    subcategory: Optional[str] = None
    # hall_id는 상위 Hall 객체에서 설정됨

    class Config:
        from_attributes = True


class HallUpdateSchema(BaseModel):
    id: int # 업데이트 대상 ID
    name: Optional[str] = None
    interval_minutes: Optional[int] = None
    guarantees: Optional[int] = None
    parking: Optional[int] = None
    type: Optional[str] = None # 실제로는 HallType Enum 사용 권장
    mood: Optional[str] = None # 실제로는 MoodType Enum 사용 권장
    # wedding_company_id는 변경하지 않거나, 별도 로직으로 처리
    hall_includes: Optional[List[HallIncludeUpdateSchema]] = [] # 프론트에서 hall_includes_update_data로 보냄

    class Config:
        from_attributes = True

class MealPriceUpdateSchema(BaseModel):
    id: Optional[int] = None
    meal_type: Optional[str] = None
    category: Optional[str] = None # MealCategory Enum
    price: Optional[int] = None
    extra: Optional[str] = None
    # estimate_id는 상위에서 설정

    class Config:
        from_attributes = True

class EstimateOptionUpdateSchema(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    price: Optional[int] = None
    is_required: Optional[bool] = None
    description: Optional[str] = None
    reference_url: Optional[str] = None
    # estimate_id는 상위에서 설정

    class Config:
        from_attributes = True

class EtcUpdateSchema(BaseModel):
    id: Optional[int] = None
    content: Optional[str] = None
    # estimate_id는 상위에서 설정

    class Config:
        from_attributes = True

class WeddingPackageItemUpdateSchema(BaseModel):
    id: Optional[int] = None
    type: Optional[str] = None # PackageItemType Enum
    company_name: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    url: Optional[str] = None
    # wedding_package_id는 상위에서 설정

    class Config:
        from_attributes = True

class WeddingPackageUpdateSchema(BaseModel):
    id: Optional[int] = None
    type: Optional[str] = None # PackageType Enum
    name: Optional[str] = None
    total_price: Optional[int] = None
    is_total_price: Optional[bool] = None
    wedding_package_items: Optional[List[WeddingPackageItemUpdateSchema]] = []
    # estimate_id는 상위에서 설정

    class Config:
        from_attributes = True

class HallPhotoProcessSchema(BaseModel):
    id: Optional[int] = None # 기존 사진 업데이트 시 사용
    url: str
    order_num: int
    caption: Optional[str] = None
    is_visible: Optional[bool] = True
    # hall_id는 상위에서 설정

    class Config:
        from_attributes = True


class StandardEstimateUpdateRequestSchema(BaseModel): # 요청 본문 전체 스키마
    # DetailedEstimate 직접 필드
    hall_price: Optional[int] = None
    type: Optional[str] = Field(default=EstimateTypeEnum.standard.value) # 표준 견적서 타입
    date: Optional[str] = None # YYYY-MM-DD 형식의 문자열
    time: Optional[str] = None # HH:MM 형식의 문자열
    penalty_amount: Optional[int] = None
    penalty_detail: Optional[str] = None

    # 업데이트할 중첩 객체/배열 정보 (프론트 payload 필드명과 일치시킴)
    wedding_company_update_data: Optional[CompanyUpdateSchema] = None
    hall_update_data: Optional[HallUpdateSchema] = None # 여기에는 hall_includes가 포함될 수 있음
    # hall_includes_update_data: Optional[List[HallIncludeUpdateSchema]] = None # hall_update_data에 포함되거나 별도로. 프론트는 별도로 보냄.

    meal_prices: Optional[List[MealPriceUpdateSchema]] = None
    estimate_options: Optional[List[EstimateOptionUpdateSchema]] = None
    etcs: Optional[List[EtcUpdateSchema]] = None # 프론트는 단일 객체를 배열로 보냄
    wedding_packages: Optional[List[WeddingPackageUpdateSchema]] = None # 프론트는 단일 객체를 배열로 보냄

    # 사진 처리 정보
    photos_to_process: Optional[List[HallPhotoProcessSchema]] = None # 생성/업데이트할 사진 목록
    photo_ids_to_delete: Optional[List[int]] = None # 삭제할 사진 ID 목록

    @validator('date', pre=True, allow_reuse=True)
    def empty_str_to_none_date(cls, v):
        if v == "":
            return None
        return v # 실제 날짜 유효성 검사는 추가 필요

    @validator('time', pre=True, allow_reuse=True)
    def empty_str_to_none_time(cls, v):
        if v == "":
            return None
        return v # 실제 시간 유효성 검사는 추가 필요

    class Config:
        from_attributes = True

class HallIncludeUpdateSchema(BaseModel): # 이 스키마도 정의되어 있어야 함
    id: Optional[int] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    class Config:
        from_attributes = True # Pydantic v1 orm_mode = True / Pydantic v2 from_attributes = True


class FinalHallPhotoSchema(BaseModel): # 프론트의 finalPhotosForPayload 항목에 해당
    id: Optional[int] = None # ✅ 프론트의 dbId를 받을 필드. 기존 사진 업데이트 시 사용.
    url: str
    order_num: int
    caption: Optional[str] = None
    is_visible: Optional[bool] = True

    class Config:
        from_attributes = True

class StandardEstimateUpdateRequestSchemaV2(BaseModel):
    # ... (hall_price, type, date 등 다른 필드들은 이전 답변 참고) ...
    hall_price: Optional[int] = None
    type: Optional[str] = None 
    date: Optional[str] = None 
    time: Optional[str] = None 
    penalty_amount: Optional[int] = None
    penalty_detail: Optional[str] = None

    wedding_company_update_data: Optional[CompanyUpdateSchema] = None # 예시
    hall_update_data: Optional[HallUpdateSchema] = None # 예시. 여기에 hall_includes를 넣을 수도 있음

    # ✅ 이 필드가 문제의 원인일 가능성이 큼!
    # payload에서 'hall_includes_update_data'로 보내고 있으니, 스키마에도 이 이름으로 필드가 있어야 함.
    hall_includes_update_data: Optional[List[HallIncludeUpdateSchema]] = None 

    meal_prices: Optional[List[MealPriceUpdateSchema]] = None
    estimate_options: Optional[List[EstimateOptionUpdateSchema]] = None
    etcs: Optional[List[EtcUpdateSchema]] = None
    wedding_packages: Optional[List[WeddingPackageUpdateSchema]] = None

    photos_data: Optional[List[FinalHallPhotoSchema]] = [] # ✅ 수정된 스키마 사용
    photo_ids_to_delete: Optional[List[int]] = []

    class Config:
        from_attributes = True