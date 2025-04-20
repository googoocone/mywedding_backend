# models/package.py
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Enum
from core.database import Base
from models.enums import PackageTypeEnum, PackageItemTypeEnum

class WeddingPackage(Base):
    __tablename__ = "wedding_package"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(PackageTypeEnum), nullable=True)
    name = Column(String, nullable=True)
    total_price = Column(Integer, nullable=True)
    is_total_price = Column(Boolean, nullable=True)
    estimate_id = Column(Integer, ForeignKey("estimate.id"))

class WeddingPackageItem(Base):
    __tablename__ = "wedding_package_item"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(PackageItemTypeEnum), nullable=True)
    company_name = Column(String, nullable=True)
    price = Column(Integer, nullable=True)
    description = Column(String, nullable=True)
    url = Column(String, nullable=True)
    wedding_package_id = Column(Integer, ForeignKey("wedding_package.id"))
