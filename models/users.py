from sqlalchemy import Column, String, Integer, TIMESTAMP, func
from core.database import Base

class User(Base) :
    __tablename__ = 'users'

    id= Column(String, primary_key=True, index=True)
    uid=Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    refresh_token = Column(String, nullable=True)
    profile_image = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())