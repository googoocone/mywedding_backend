from sqlalchemy.orm import Session
from models.users import User
import uuid

def get_user_by_uid(uid : str, db:Session) -> User | None:
    return db.query(User).filter(User.uid == uid).first()

def create_user(uid:str, email:str, name:str, db:Session, refresh_token : str = None) -> User:
    new_user = User(
        id = str(uuid.uuid4()), uid=uid, name= name, email=email, refresh_token = refresh_token
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user