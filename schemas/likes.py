# --- Pydantic 모델 정의 (요청/응답 데이터 유효성 검사) ---
from typing import List, Optional

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