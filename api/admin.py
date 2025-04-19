from fastapi import FastAPI, Form, Request, APIRouter, Depends, HTTPException
from pydantic import BaseModel

from utils.hash import hash_password, verify_password
from utils.security import create_admin_token, verify_jwt_token
from starlette.responses import Response
from sqlalchemy.orm import Session
from core.database import get_db
from models.admin import Admin


class CodeRequest(BaseModel):
  id : str
  password : str

router = APIRouter(prefix="/admin")

@router.post('/')
def admin_home(reponse:Response) :
  return {"message" : "hello"}

@router.post('/signin')
def admin_signin(body: CodeRequest, response: Response,  db:Session=Depends(get_db)):
    try:
        name = body.id

        admin = db.query(Admin).filter(Admin.name == name).first()
        if not admin : 
           raise HTTPException(status_code=500, detail=f"관리자 계정 존재하지 않음")
        
        result = verify_password(body.password,admin.password)

        if result == True:

          admin_token = create_admin_token(admin)

          response.set_cookie(
          key="admin_token",
          value=admin_token,
          httponly=True,
          secure=False,           # ✅ 로컬 개발에서는 False
          samesite="lax",         # ✅ 기본값으로
          max_age=86400,
          path='/'
          )

          return {"message": "login", "status": 200}
        else : 
           return {"message" : "암호 틀림", "status" : 401} 

    except Exception as e:
        print("❌ 예외 발생:", e)
        raise
    


@router.get("/me")
def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("admin_token")
    print("admin token", token)
    if not token:
        raise HTTPException(status_code=401, detail="Access token missing")

    result = verify_jwt_token(token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    print("result", result)
    return {
       "message" : "good"
    }
    # payload = result["payload"]
    # new_access_token = result.get("new_access_token")

    # if new_access_token:
    #     response.set_cookie(
    #         key="access_cookie",
    #         value=new_access_token,
    #         httponly=True,
    #         secure=False,
    #         samesite="lax",
    #         max_age=86400,
    #         path="/"
    #     )

    # user_id = payload.get("sub")
    # if not user_id:
    #     raise HTTPException(status_code=401, detail="Invalid token payload")

    # user = db.query(Admin).filter(Admin.uid == user_id).first()
    # if not user:
    #     raise HTTPException(status_code=404, detail="User not found")

    # return {
    #     "user": {
    #         "name": user.name,
    #         "profile_image": user.profile_image,
    #     }
    # }