from sqlalchemy import Boolean, Column, String, Integer, TIMESTAMP, func, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base
from sqlalchemy.orm import relationship

class User(Base) :
    __tablename__ = 'users'

    id= Column(String, primary_key=True, index=True)
    uid=Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    profile_image = Column(String, nullable=True)
    type = Column(String)
    created_at = Column(TIMESTAMP, server_default=func.now())
    phone = Column(String, nullable= True)

    user_wedding_info = relationship("UserWeddingInfo", back_populates="user")

class UserWeddingInfo(Base):
    __tablename__ = "user_wedding_info"
    id = Column(Integer, primary_key=True, index=True)
    wedding_date = Column(Date, nullable=True)
    wedding_region = Column(String, nullable=True) # DB ENUM 타입이라면 해당 값들이 ENUM에 정의되어 있어야 함
    expected_budget = Column(Integer, nullable=True) # 컬럼명 오타 수정 (buget -> budget)
   
    attendance = Column(Integer, nullable=True)
    nickname = Column(String, nullable=True)
    create_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False) # unique=True 추가 (한 유저는 하나의 웨딩 정보만 가진다고 가정)
    email = Column(String, nullable=True) # 웨딩 정보용 이메일

    agreed_to_privacy_policy = Column(Boolean, nullable=True, default=False)
    agreed_to_terms_of_service = Column(Boolean, nullable=True, default=False)
    agreed_to_marketing = Column(Boolean, nullable=True, default=False)

    user = relationship("User", back_populates="user_wedding_info") # User 모델에 user_wedding_info 관계 설정 필요