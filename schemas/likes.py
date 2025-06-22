# --- Pydantic 모델 정의 (요청/응답 데이터 유효성 검사) ---
import enum
from typing import Dict, List, Optional

from pydantic import BaseModel


class LikeRequest(BaseModel):
    wedding_company_id: int

class LikeStatusResponse(BaseModel):
    is_liked: bool

class WeddingHallPhoto(BaseModel):
    url: str

class HallInfo(BaseModel):
    name: str
    hall_photos: List[WeddingHallPhoto]
    
class LikeBatchRequest(BaseModel):
    hall_ids: List[int]

class LikeBatchResponse(BaseModel):
    like_statuses: Dict[int, bool] # {wedding_company_id: is_liked}

class WeddingCompany(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    halls: List[HallInfo] # Halls 정보 포함
    liked_at: Optional[str] = None # 찜한 시간 (조회 시 추가될 필드)

class HallInfoResponse(BaseModel):
    name: str
    hall_photos: List[WeddingHallPhoto] # HallPhoto 모델로부터

class LikedWeddingCompanyResponse(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    halls: List[HallInfoResponse] # HallModel로부터
    liked_at: str # DateTime 필드는 문자열로 변환 (ISO 8601)
    
class MoodEnum(str, enum.Enum):
    밝은 = "밝은"
    어두운 = "어두운"

# HallPhoto 스키마 (기존과 동일하지만, is_visible 등 다른 필드를 포함하고 싶다면 추가)
class HallPhotoOut(BaseModel):
    id: int
    hall_id: int # 외래키도 포함시킬 수 있습니다.
    url: str
    order_num: Optional[int] = None # nullable = True 이므로 Optional
    caption: Optional[str] = None
    is_visible: Optional[bool] = None

    class Config:
        from_attributes = True

# 홀 스키마 (Hall SQLAlchemy 모델에 맞게 수정)
class HallOut(BaseModel):
    id: int
    wedding_company_id: int # ✅ SQLAlchemy 모델과 동일하게 이름 변경
    name: Optional[str] = None # nullable = True 이므로 Optional
    interval_minutes: Optional[int] = None # ✅ 추가
    guarantees: Optional[int] = None # ✅ 추가
    parking: Optional[int] = None # ✅ 추가
    type: Optional[str] = None # ✅ 추가 (또는 HallTypeEnum 사용)
    mood: Optional[MoodEnum] = None # ✅ 추가 (MoodEnum 사용)

    hall_photos: List[HallPhotoOut] = [] # 홀에 속한 사진 목록

    class Config:
        from_attributes = True

# 웨딩 업체(회사) 스키마 (기존과 동일하지만, 주소 필드에 대한 처리 방식도 고려)
class WeddingCompanyOut(BaseModel):
    id: int
    name: str
    address: Optional[str] = None # address도 nullable=True일 가능성 고려
    # 필요한 다른 필드들 추가 (예: contact_info, description 등)
    halls: List[HallOut] = [] # 해당 업체에 속한 홀 목록

    class Config:
        from_attributes = True