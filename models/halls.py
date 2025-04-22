# models/hall.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Text, Enum
from sqlalchemy.orm import relationship
from core.database import Base
from models.enums import HallTypeEnum, MoodEnum

class Hall(Base):
    __tablename__ = "hall"
    id = Column(Integer, primary_key=True, index=True)
    wedding_company_id = Column(Integer, ForeignKey("wedding_company.id"))
    name = Column(String, nullable=True)
    interval_minutes = Column(Integer, nullable=True)
    guarantees = Column(Integer, nullable=True)
    parking = Column(Integer, nullable=True)
    type = Column(Enum(HallTypeEnum), nullable=True)
    mood = Column(Enum(MoodEnum), nullable=True)
    estimates = relationship("Estimate", back_populates="hall")

class HallPhoto(Base):
    __tablename__ = "hall_photos"
    id = Column(Integer, primary_key=True, index=True)
    hall_id = Column(Integer, ForeignKey("hall.id"))
    url = Column(Text, nullable=True)
    order_num = Column(Integer, nullable=True)
    caption = Column(String, nullable=True)
    is_visible = Column(Boolean, nullable=True)

class HallInclude(Base):
    __tablename__ = "hall_include"
    id = Column(Integer, primary_key=True, index=True, nullable=True)
    hall_id = Column(Integer, ForeignKey("hall.id"))
    category = Column(String, nullable=True)
    subcategory = Column(String, nullable=True)