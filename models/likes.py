from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID # UUID 타입 임포트
from sqlalchemy.sql import func


from core.database import Base # 사용자님의 Base가 정의된 파일 임포트

class LikeModel(Base):
    __tablename__ = "likes" # 앞서 생성한 테이블 이름과 일치해야 합니다.

    # user_id와 wedding_company_id를 복합 기본 키로 사용
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    wedding_company_id = Column(Integer, ForeignKey('wedding_company.id', ondelete='CASCADE'), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())