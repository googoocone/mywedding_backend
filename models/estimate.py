# models/estimate.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Date, Text, Enum, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from core.database import Base
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from models.enums import EstimateTypeEnum, MealCategoryEnum

class Estimate(Base):
    __tablename__ = "estimate"
    id = Column(Integer, primary_key=True, index=True)
    hall_id = Column(Integer, ForeignKey("hall.id"))
    hall_price = Column(Integer, nullable=True)
    type = Column(Enum(EstimateTypeEnum), nullable=True)
    date = Column(Date, nullable=True)
    time = Column(Time, nullable=True)
    guarantees = Column(Integer, nullable=True)
    penalty_amount = Column(Integer, nullable=True)
    penalty_detail = Column(String, nullable=True)
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    hall = relationship("Hall", back_populates="estimates")
    wedding_packages = relationship("WeddingPackage",cascade="all", back_populates="estimate")
    meal_prices = relationship("MealPrice",cascade="all", back_populates="estimate")
    estimate_options = relationship("EstimateOption",cascade="all", back_populates="estimate")
    etcs = relationship("Etc",cascade="all", back_populates="estimate")


class MealPrice(Base):
    __tablename__ = "meal_price"
    id = Column(Integer, primary_key=True, index=True)
    estimate_id = Column(Integer, ForeignKey("estimate.id"))
    meal_type = Column(String, nullable=True)
    category = Column(
        PGEnum(MealCategoryEnum, name="meal_category", create_type=False), # <-- 수정된 Enum 정의
        nullable=True # 실제 스키마에 맞게 Null 허용 여부 설정
    )
    price = Column(Integer, nullable=True)
    extra = Column(Text, nullable=True)

    estimate = relationship("Estimate", back_populates="meal_prices")

class EstimateOption(Base):
    __tablename__ = "estimate_option"
    id = Column(Integer, primary_key=True, index=True)
    estimate_id = Column(Integer, ForeignKey("estimate.id"))
    name = Column(String, nullable=True)
    price = Column(Integer, nullable=True)
    is_required = Column(Boolean, nullable=True)
    description = Column(Text, nullable=True)
    reference_url = Column(String, nullable=True)

    estimate = relationship("Estimate", back_populates="estimate_options")

class Etc(Base):
    __tablename__ = "etc"
    id = Column(Integer, primary_key=True, index=True)
    estimate_id = Column(Integer, ForeignKey("estimate.id"))
    content = Column(Text, nullable=True)

    estimate = relationship("Estimate", back_populates="etcs")