from sqlalchemy import Column, String, Integer, TIMESTAMP, func, Date, ForeignKey
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

    user_wedding_info = relationship("UserWeddingInfo", back_populates="user")

class UserWeddingInfo(Base):
    __tablename__ = "user_wedding_info"
    id = Column(Integer, primary_key=True, index=True)
    wedding_date = Column(Date, nullable=True)
    wedding_region = Column(String, nullable=True)
    expected_buget = Column(Integer, nullable=True)
    prefered_hall_type = Column(String, nullable=True)
    create_by_user_id = Column(String, ForeignKey("users.id"))

    user = relationship("User", back_populates="user_wedding_info")