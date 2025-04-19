from sqlalchemy import Column, String, TIMESTAMP, func
from core.database import Base

class Admin(Base) :
    __tablename__ = 'admin'

    id= Column(String, primary_key=True, index=True)
    name= Column(String, nullable=False)
    password=Column(String, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())