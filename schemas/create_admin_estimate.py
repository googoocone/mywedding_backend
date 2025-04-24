# schemas.py 파일 내용

from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date
# Enum types (assuming correct import paths)
from models.enums import (
    EstimateTypeEnum,
    MealCategoryEnum,
    HallTypeEnum,
    MoodEnum,
    PackageTypeEnum,
    PackageItemTypeEnum
)

# --- JSON structure's Nested objects and array items ---

# JSON: payload.company (nested object)
# This model is correct based on the JSON structure under the 'company' key
class CompanyNestedPayload(BaseModel):
     id: Optional[int] = None
     name: str # <-- 필드들은 이 모델 안에 정의되어 있습니다.
     address: str
     phone: str
     homepage: str
     accessibility: str
     lat: Optional[float] = None
     lng: Optional[float] = None
     ceremony_times: str

# JSON: payload.hall
# This model is correct based on the JSON structure under the 'hall' key
class HallFieldsPayload(BaseModel):
    id: Optional[int] = None
    name: str
    interval_minutes: int
    guarantees: int
    parking: int
    type: HallTypeEnum
    mood: MoodEnum

# JSON: payload.etcs (array) - Note: JSON key is 'etcs', not 'etc'
# Correcting this model to match the JSON structure for each item
class EtcItemPayload(BaseModel):
    id: Optional[int] = None
    content: str

# JSON: payload.hall_includes (array)
class HallIncludeItemPayload(BaseModel):
    id: Optional[int] = None
    hall_id: Optional[int] = None
    category: str
    subcategory: str

# JSON: payload.hall_photos (array)
class HallPhotoItemPayload(BaseModel):
    id: Optional[int] = None
    hall_id: Optional[int] = None
    url: str
    order_num: int
    caption: str
    is_visible: bool

# JSON: payload.meal_prices (array)
class MealPriceItemPayload(BaseModel):
    id: Optional[int] = None
    estimate_id: Optional[int] = None
    meal_type: str
    category: MealCategoryEnum
    price: int
    extra: str

# JSON: payload.estimate_options (array)
class EstimateOptionItemPayload(BaseModel):
    id: Optional[int] = None
    estimate_id: Optional[int] = None
    name: str
    price: int
    is_required: bool
    description: str
    reference_url: str

# JSON: payload.wedding_package_items (array) - Nested within wedding_package AND at top level in JSON
# This model is correct for items
class WeddingPackageItemPayload(BaseModel):
     id: Optional[int] = None
     wedding_package_id: Optional[int] = None
     type: PackageItemTypeEnum
     company_name: str
     price: int
     description: str
     url: str

# JSON: payload.wedding_package (single object or null)
# This model is correct for the nested wedding_package object
class WeddingPackagePayload(BaseModel):
     id: Optional[int] = None
     estimate_id: Optional[int] = None
     type: PackageTypeEnum
     name: str
     total_price: int
     is_total_price: bool
     # Nested items array using the JSON key 'wedding_package_items'
     wedding_package_items: List[WeddingPackageItemPayload] = []


# --- Top-level Payload Schema (Matching Provided JSON Example Exactly) ---
class AdminEstimateCreateRequestPayload(BaseModel):
    # Top-level IDs present in JSON example (likely ignored for create)
    id: Optional[int] = None # Estimate ID
    hall_id: Optional[int] = None # Hall ID
    wedding_company_id: Optional[int] = None # Company ID

    # Top-level fields present in JSON example (that were expected nested in original Pydantic)
    hall_price: Optional[int] = None # <-- Present at top level in JSON
    type: Optional[EstimateTypeEnum] = None # <-- Present at top level in JSON.
    date: date # <-- Present at top level in JSON. date 문자열 파싱은 Pydantic이 처리합니다.

    # Lists at top level in JSON example
    etcs: List[EtcItemPayload] = [] # <-- JSON에 'etcs' (리스트)로 있습니다.
    meal_prices: List[MealPriceItemPayload] = []
    estimate_options: List[EstimateOptionItemPayload] = []
    hall_includes: List[HallIncludeItemPayload] = []
    hall_photos: List[HallPhotoItemPayload] = []
    # JSON 예시에서 최상위 레벨 리스트로 있습니다. (wedding_package 내부에도 있습니다)
    wedding_package_items: List[WeddingPackageItemPayload] = []

    # Top-level nested objects present in JSON example
    company: CompanyNestedPayload # <-- JSON에 중첩된 'company' 객체가 있습니다. 이 모델 정의는 정확합니다.
    hall: HallFieldsPayload # <-- JSON에 중첩된 'hall' 객체가 있습니다. 이 모델 정의는 정확합니다.
    wedding_package: Optional[WeddingPackagePayload] = None # <-- JSON에 중첩된 'wedding_package' 객체가 있습니다 (null일 수 있음). 이 모델 정의는 정확합니다.

    # JSON에 없는 최상위 estimate 객체 요구사항은 이전 수정에서 이미 제거되었습니다.
    # estimate: EstimateFieldsPayload # 제거됨

    # Add ConfigDict if needed, but not strictly necessary for this fix
    # model_config = ConfigDict(arbitrary_types_allowed=True)