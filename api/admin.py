from fastapi import FastAPI, Form, Request, APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

from utils.hash import hash_password, verify_password
from utils.security import create_admin_token, verify_jwt_token
from starlette.responses import Response
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError
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

from models.enums import EstimateTypeEnum

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
    
@router.post('/get_standard_estimate')
async def get_standard_estimate(request : Request, db: Session = Depends(get_db)):
    """
    특정 업체의 표준 견적서와 모든 상세 정보를 가져옵니다.
    """
    try:
        data = await request.json()
        company_name = data.get("companyName")

        if not company_name:
             # 회사 이름이 없을 경우 Bad Request 반환
             raise HTTPException(status_code=400, detail="회사 이름이 제공되지 않았습니다.")

        # SQLAlchemy 쿼리 작성: Estimate를 기준으로 조인 및 관계된 모든 데이터를 로딩
        estimates = db.query(EstimateModel).options(
            # Estimate -> Hall (단일 객체)
            # Hall 모델에 WeddingCompany, HallPhoto, HallInclude 관계가 로드되도록 설정합니다.
            joinedload(EstimateModel.hall).options(
                 joinedload(HallModel.wedding_company), # Hall -> WeddingCompany 로딩
                 selectinload(HallModel.hall_photos),       # Hall -> HallPhoto 로딩 (1:N)
                 selectinload(HallModel.hall_includes)      # Hall -> HallInclude 로딩 (1:N)
            ),
            # Estimate -> MealPrice (여러 객체, 1:N)
            selectinload(EstimateModel.meal_prices),
            # Estimate -> EstimateOption (여러 객체, 1:N)
            selectinload(EstimateModel.estimate_options),
            # Estimate -> Etc (여러 객체, 1:N)
            selectinload(EstimateModel.etcs),
            # Estimate -> WeddingPackage (여러 객체, 1:N), 그리고 Package 하위 Item 로딩
            selectinload(EstimateModel.wedding_packages).selectinload(
                # WeddingPackage -> WeddingPackageItem 로딩 (1:N)
                WeddingPackageModel.wedding_package_items
            )
            # Estimate -> User 관계도 필요하다면 추가: selectinload(EstimateModel.created_by_user)
        ).join(EstimateModel.hall).join(HallModel.wedding_company).filter(
            WeddingCompanyModel.name == company_name,
            EstimateModel.type == EstimateTypeEnum.standard # 표준 견적만 필터링
        ).all()

        # Pydantic 모델 (EstimatesResponse)의 data 필드에 SQLAlchemy 결과 리스트를 담아 반환합니다.
        # response_model 설정과 from_attributes=True (또는 orm_mode=True) 설정 덕분에
        # Pydantic이 SQLAlchemy 객체를 자동으로 DetailedEstimateSchema 리스트로 변환합니다.
        return {"message" : "성공", "data" : estimates}

    except SQLAlchemyError as e:
        # 데이터베이스 쿼리 중 발생한 에러 처리
        print(f"데이터베이스 쿼리 오류: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except HTTPException as e:
        # 이미 HTTPException으로 처리된 예외는 다시 발생
        raise e
    except Exception as e:
        # 예상치 못한 다른 예외 발생 시 로깅 및 500 에러 반환
        print(f"표준 견적 정보를 가져오는 중 서버 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="표준 견적 정보를 가져오는 중 서버 오류가 발생했습니다.")
