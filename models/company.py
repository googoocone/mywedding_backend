# models/company.py
from sqlalchemy import Column, Integer, String, Text, JSON
from sqlalchemy.orm import relationship
from core.database import Base

class WeddingCompany(Base):
    __tablename__ = "wedding_company"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    homepage = Column(String, nullable=True)
    accessibility = Column(Text, nullable=True)
    lat = Column(Integer, nullable=True)
    lng = Column(Integer, nullable=True)
    ceremony_times = Column(String, nullable=True)

    halls = relationship("Hall", back_populates="wedding_company")