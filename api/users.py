from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from models.users import User

router = APIRouter(prefix="/users")

@router.get("/")
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {"users": users}

