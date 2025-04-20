from fastapi import FastAPI, Form, Request, APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

from utils.hash import hash_password, verify_password
from utils.security import create_admin_token, verify_jwt_token
from starlette.responses import Response
from sqlalchemy.orm import Session
from core.database import get_db
from models.admin import Admin
from typing import List, Optional

from models.company import WeddingCompany as WeddingCompanyModel
from models.halls import Hall as HallModel, HallInclude as HallIncludeModel, HallPhoto as HallPhotoModel

from models.estimate import Estimate         as EstimateModel
from models.estimate import MealPrice       as MealPriceModel
from models.estimate import EstimateOption  as EstimateOptionModel
from models.estimate import Etc             as EtcModel

from models.package  import WeddingPackage     as WeddingPackageModel
from models.package  import WeddingPackageItem as WeddingPackageItemModel

from schemas.admin import (
    CodeRequest,
    HallSchema, HallPhotoSchema, HallIncludeSchema,
    EstimateSchema, EstimateOptionSchema, MealTypeSchema,
    WeddingPackageSchema, PackageItemSchema, EtcSchema, MealTypeSchema,
    WeddingCompanyCreate,
)




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
    
    
@router.post("/create-standard-estimate")
def create_standard_estimate(
    payload: WeddingCompanyCreate,
    db: Session = Depends(get_db),
):
    try:
        # --- ORM으로만 생성 ---
        company = WeddingCompanyModel(
            name=payload.name,
            address=payload.address,
            phone=payload.phone,
            homepage=str(payload.homepage) if payload.homepage else None,
            accessibility=payload.accessibility,
            lat=payload.mapx,
            lng = payload.mapy,
            ceremony_times=payload.ceremony_times,
        )
        db.add(company); db.flush()

        hall = HallModel(
            wedding_company_id=company.id,
            **payload.hall.dict()
        )
        db.add(hall); db.flush()

        for inc in payload.hall_includes:
            db.add(HallIncludeModel(hall_id=hall.id, **inc.dict()))

        for photo in payload.hall_photos:
            db.add(HallPhotoModel(hall_id=hall.id, **photo.dict()))

        estimate = EstimateModel(
            hall_id=hall.id,
            hall_price=payload.estimate.hall_price,
            type=payload.estimate.type,
            date=payload.estimate.date,
            created_by_user_id="131da9a7-6b64-4a0e-a75d-8cd798d698bd",
        )
        db.add(estimate); db.flush()

        for m in payload.meal_price:
            db.add(MealPriceModel(estimate_id=estimate.id, **m.dict()))

        for opt in payload.estimate_options:
            db.add(EstimateOptionModel(estimate_id=estimate.id, **opt.dict()))

        if payload.etc:
            db.add(EtcModel(estimate_id=estimate.id, **payload.etc.dict()))

        wp = WeddingPackageModel(
            estimate_id=estimate.id,
            **payload.wedding_package.dict()
        )
        db.add(wp); db.flush()

        for item in payload.package_items:
            db.add(WeddingPackageItemModel(wedding_package_id=wp.id, **item.dict()))

        db.commit()
        return {"message": "업체 등록 완료", "company_id": company.id}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB 저장 실패: {e}")