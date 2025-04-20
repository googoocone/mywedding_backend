# models/estimate.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Date, Text, Enum
from core.database import Base
from models.enums import EstimateTypeEnum, MealCategoryEnum

class Estimate(Base):
    __tablename__ = "estimate"
    id = Column(Integer, primary_key=True, index=True)
    hall_id = Column(Integer, ForeignKey("hall.id"))
    hall_price = Column(Integer, nullable=True)
    type = Column(Enum(EstimateTypeEnum), nullable=True)
    date = Column(Date, nullable=True)
    created_by_user_id = Column(String, ForeignKey("users.id"))

class MealPrice(Base):
    __tablename__ = "meal_price"
    id = Column(Integer, primary_key=True, index=True, nullable=True)
    estimate_id = Column(Integer, ForeignKey("estimate.id"))
    meal_type = Column(String, nullable=True)
    category = Column(Enum(MealCategoryEnum), nullable=True)
    price = Column(Integer, nullable=True)
    extra = Column(Text, nullable=True)

class EstimateOption(Base):
    __tablename__ = "estimate_option"
    id = Column(Integer, primary_key=True, index=True)
    estimate_id = Column(Integer, ForeignKey("estimate.id"))
    name = Column(String, nullable=True)
    price = Column(Integer, nullable=True)
    is_required = Column(Boolean, nullable=True)
    description = Column(Text, nullable=True)
    reference_url = Column(String, nullable=True)

class Etc(Base):
    __tablename__ = "etc"
    id = Column(Integer, primary_key=True, index=True)
    estimate_id = Column(Integer, ForeignKey("estimate.id"))
    content = Column(Text, nullable=True)
