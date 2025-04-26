from fastapi import FastAPI, Form, Request, APIRouter, Depends, HTTPException, Path
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

from schemas.create_admin_estimate import (
    AdminEstimateCreateRequestPayload,
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
    
    
@router.post("/create-standard-estimate")
def create_standard_estimate(
    payload: WeddingCompanyCreate,
    db: Session = Depends(get_db),
):
    print("payload", payload)
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
    
@router.post('/create_admin_estimate')
async def create_admin_estimate(
    payload: AdminEstimateCreateRequestPayload, # Request Body를 Pydantic 모델로 받음
    db: Session = Depends(get_db)
):
    """
    프론트엔드에서 보낸 데이터를 기반으로 새로운 관리자 견적서와 관련 정보를 생성합니다.
    수신된 데이터의 ID는 무시하고 새로운 레코드를 생성합니다.
    """

    print("paylaod", payload)

    try:
        
        for inc_payload in payload.hall_includes:
            include = HallIncludeModel(
                hall_id=payload.hall_id, # 새로 생성된 hall의 ID 사용
                category=inc_payload.category,
                subcategory=inc_payload.subcategory,
            )
            db.add(include)


        for photo_payload in payload.hall_photos:
             # URL이 null이 아니어야 저장 (프론트엔드에서 null을 보낼 수도 있으므로)
             if photo_payload.url:
                photo = HallPhotoModel(
                    hall_id=payload.hall_id, # 새로 생성된 hall의 ID 사용
                    url=photo_payload.url,
                    order_num=photo_payload.order_num,
                    caption=photo_payload.caption,
                    is_visible=photo_payload.is_visible,
                )
                db.add(photo)

        estimate = EstimateModel(
            hall_id=payload.hall_id,
            # 최상위 레벨 페이로드에서 필드를 직접 사용
            hall_price=payload.hall_price,
            type=EstimateTypeEnum.admin, # 여전히 admin으로 하드코딩됨
            date=payload.date, # <-- 이제 이게 최상위 레벨에 있습니다
            created_by_user_id="131da9a7-6b64-4a0e-a75d-8cd798d698bd", # 사용자 ID 로직
        )
        print("--- 디버그 정보 ---")
        print(f"created_by_user_id 값: {estimate.created_by_user_id}")
        print(f"created_by_user_id 타입: {type(estimate.created_by_user_id)}")
        print("---------------")
        db.add(estimate)
        db.flush() # ID를 얻기 위해 flush

        for meal_payload in payload.meal_prices:
            meal_price = MealPriceModel(
                estimate_id=estimate.id, # 새로 생성된 estimate의 ID 사용
                meal_type=meal_payload.meal_type,
                category=meal_payload.category,
                price=meal_payload.price,
                extra=meal_payload.extra,
            )
            db.add(meal_price)


        for opt_payload in payload.estimate_options:
            option = EstimateOptionModel(
                estimate_id=estimate.id, # 새로 생성된 estimate의 ID 사용
                name=opt_payload.name,
                price=opt_payload.price,
                is_required=opt_payload.is_required,
                description=opt_payload.description,
                reference_url=opt_payload.reference_url,
            )
            db.add(option)

        for etc_payload in payload.etcs: # 리스트를 순회합니다
            # 필요한 경우 내용이 비어있지 않은지 확인
            if etc_payload and etc_payload.content.strip() != "":
                etc_item = EtcModel(
                    estimate_id=estimate.id,
                    content=etc_payload.content
                )
                db.add(etc_item)

        # 9. WeddingPackage 생성 (payload.wedding_package 사용) - 단일 객체 또는 null
        if payload.wedding_package is not None:
             # payload.wedding_package 객체의 필드를 사용합니다. 새로운 패키지이므로 payload.wedding_package.id는 무시합니다.
             wp_payload = payload.wedding_package
             wp = WeddingPackageModel(
                 estimate_id=estimate.id, # 새로 생성된 estimate의 ID 사용
                 type=wp_payload.type,
                 name=wp_payload.name,
                 total_price=wp_payload.total_price,
                 is_total_price=wp_payload.is_total_price,
             )
             db.add(wp)
             db.flush() # ID를 얻기 위해 flush

             # 10. WeddingPackageItem 항목 생성 (payload.wedding_package.wedding_package_items 사용) - JSON 키 'wedding_package_items'
             # payload.wedding_package.wedding_package_items 배열을 순회합니다. 새로운 항목이므로 item.id는 무시합니다.
             for item_payload in wp_payload.wedding_package_items:
                 wp_item = WeddingPackageItemModel(
                     wedding_package_id=wp.id, # 새로 생성된 wedding_package의 ID 사용
                     type=item_payload.type,
                     price=item_payload.price,
                     description=item_payload.description,
                     url=item_payload.url,
                 )
                 db.add(wp_item)

        db.commit()

        # 12. Return success response
        # 새로 생성된 견적서의 ID 등을 반환할 수 있습니다.
        return {"message": "관리자 견적서 등록 완료", "estimate_id": estimate.id}

    except SQLAlchemyError as e:
        # 데이터베이스 저장 중 오류 발생 시 롤백
        db.rollback()
        print(f"데이터베이스 저장 오류: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 저장 오류 발생")
    except Exception as e:
        # 기타 예상치 못한 오류 발생 시 롤백
        db.rollback()
        print(f"관리자 견적서 생성 중 서버 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"서버 오류 발생: {e}")
    
@router.put('/update_admin_estimate/{estimate_id}')
async def update_admin_estimate(
    payload: AdminEstimateCreateRequestPayload,
    estimate_id: int = Path(..., description="업데이트할 견적서 ID"),
    db: Session = Depends(get_db)
):
    """
    프론트엔드에서 보낸 데이터를 기반으로 기존 관리자 견적서를 수정합니다.
    """
    print("payload", payload)

    try:
        # 1. ID로 기존 견적서 조회
        existing_estimate = db.query(EstimateModel).filter(EstimateModel.id == estimate_id).first()
        if not existing_estimate:
            raise HTTPException(status_code=404, detail=f"ID '{estimate_id}'에 해당하는 견적서를 찾을 수 없습니다.")

        # 2. 조회된 견적서 기본 정보 업데이트
        existing_estimate.hall_id = payload.hall_id
        existing_estimate.hall_price = payload.hall_price
        existing_estimate.date = payload.date
        # type, created_by_user_id는 일반적으로 수정하지 않습니다.

        # 3. HallInclude 업데이트 또는 생성
        existing_includes = db.query(HallIncludeModel).filter(HallIncludeModel.hall_id == payload.hall_id).all()
        existing_include_ids = {include.id for include in existing_includes}
        payload_include_ids = {include.id for include in payload.hall_includes if include.id is not None}

        # 삭제할 Include
        for include in existing_includes:
            if include.id not in payload_include_ids:
                db.delete(include)

        # 업데이트 또는 생성할 Include
        for inc_payload in payload.hall_includes:
            if inc_payload.id in existing_include_ids:
                # 기존 Include 업데이트
                existing = db.query(HallIncludeModel).filter(HallIncludeModel.id == inc_payload.id).first()
                if existing:
                    existing.category = inc_payload.category
                    existing.subcategory = inc_payload.subcategory
            else:
                # 새로운 Include 생성
                include = HallIncludeModel(
                    hall_id=payload.hall_id,
                    category=inc_payload.category,
                    subcategory=inc_payload.subcategory,
                )
                db.add(include)

        # 4. HallPhoto 업데이트 또는 생성 (유사한 로직)
        existing_photos = db.query(HallPhotoModel).filter(HallPhotoModel.hall_id == payload.hall_id).all()
        existing_photo_ids = {photo.id for photo in existing_photos}
        payload_photo_ids = {photo.id for photo in payload.hall_photos if photo.id is not None}

        for photo in existing_photos:
            if photo.id not in payload_photo_ids:
                db.delete(photo)

        for photo_payload in payload.hall_photos:
            if photo_payload.url:  # URL이 있는 경우만 처리
                if photo_payload.id in existing_photo_ids:
                    existing = db.query(HallPhotoModel).filter(HallPhotoModel.id == photo_payload.id).first()
                    if existing:
                        existing.url = photo_payload.url
                        existing.order_num = photo_payload.order_num
                        existing.caption = photo_payload.caption
                        existing.is_visible = photo_payload.is_visible
                else:
                    photo = HallPhotoModel(
                        hall_id=payload.hall_id,
                        url=photo_payload.url,
                        order_num=photo_payload.order_num,
                        caption=photo_payload.caption,
                        is_visible=photo_payload.is_visible,
                    )
                    db.add(photo)

        # 5. MealPrice 업데이트 또는 생성 (estimate_id 기반)
        existing_meal_prices = db.query(MealPriceModel).filter(MealPriceModel.estimate_id == existing_estimate.id).all()
        existing_meal_price_ids = {mp.id for mp in existing_meal_prices}
        payload_meal_price_ids = {mp.id for mp in payload.meal_prices if mp.id is not None}

        for mp in existing_meal_prices:
            if mp.id not in payload_meal_price_ids:
                db.delete(mp)

        for meal_payload in payload.meal_prices:
            if meal_payload.id in existing_meal_price_ids:
                existing = db.query(MealPriceModel).filter(MealPriceModel.id == meal_payload.id).first()
                if existing:
                    existing.meal_type = meal_payload.meal_type
                    existing.category = meal_payload.category
                    existing.price = meal_payload.price
                    existing.extra = meal_payload.extra
            else:
                meal_price = MealPriceModel(
                    estimate_id=existing_estimate.id,
                    meal_type=meal_payload.meal_type,
                    category=meal_payload.category,
                    price=meal_payload.price,
                    extra=meal_payload.extra,
                )
                db.add(meal_price)

        # 6. EstimateOption 업데이트 또는 생성 (estimate_id 기반)
        existing_options = db.query(EstimateOptionModel).filter(EstimateOptionModel.estimate_id == existing_estimate.id).all()
        existing_option_ids = {opt.id for opt in existing_options}
        payload_option_ids = {opt.id for opt in payload.estimate_options if opt.id is not None}

        for opt in existing_options:
            if opt.id not in payload_option_ids:
                db.delete(opt)

        for opt_payload in payload.estimate_options:
            if opt_payload.id in existing_option_ids:
                existing = db.query(EstimateOptionModel).filter(EstimateOptionModel.id == opt_payload.id).first()
                if existing:
                    existing.name = opt_payload.name
                    existing.price = opt_payload.price
                    existing.is_required = opt_payload.is_required
                    existing.description = opt_payload.description
                    existing.reference_url = opt_payload.reference_url
            else:
                option = EstimateOptionModel(
                    estimate_id=existing_estimate.id,
                    name=opt_payload.name,
                    price=opt_payload.price,
                    is_required=opt_payload.is_required,
                    description=opt_payload.description,
                    reference_url=opt_payload.reference_url,
                )
                db.add(option)

        # 7. Etc 업데이트 또는 생성 (estimate_id 기반)
        existing_etcs = db.query(EtcModel).filter(EtcModel.estimate_id == existing_estimate.id).all()
        existing_etc_ids = {etc.id for etc in existing_etcs}
        payload_etc_ids = {etc.id for etc in payload.etcs if etc.id is not None}

        for etc in existing_etcs:
            if etc.id not in payload_etc_ids:
                db.delete(etc)

        for etc_payload in payload.etcs:
            if etc_payload and etc_payload.content.strip() != "":
                if etc_payload.id in existing_etc_ids:
                    existing = db.query(EtcModel).filter(EtcModel.id == etc_payload.id).first()
                    if existing:
                        existing.content = etc_payload.content
                else:
                    etc_item = EtcModel(
                        estimate_id=existing_estimate.id,
                        content=etc_payload.content
                    )
                    db.add(etc_item)

        # 8. WeddingPackage 업데이트 또는 생성 (estimate_id 기반)
        existing_wp = db.query(WeddingPackageModel).filter(WeddingPackageModel.estimate_id == existing_estimate.id).first()

        if payload.wedding_package:
            if existing_wp:
                # WeddingPackage 업데이트
                existing_wp.type = payload.wedding_package.type
                existing_wp.name = payload.wedding_package.name
                existing_wp.total_price = payload.wedding_package.total_price
                existing_wp.is_total_price = payload.wedding_package.is_total_price

                # WeddingPackageItem 업데이트 또는 생성
                existing_wp_items = db.query(WeddingPackageItemModel).filter(WeddingPackageItemModel.wedding_package_id == existing_wp.id).all()
                existing_wp_item_ids = {item.id for item in existing_wp_items}
                payload_wp_item_ids = {item.id for item in payload.wedding_package.wedding_package_items if item.id is not None}

                for item in existing_wp_items:
                    if item.id not in payload_wp_item_ids:
                        db.delete(item)

                for item_payload in payload.wedding_package.wedding_package_items:
                    if item_payload.id in existing_wp_item_ids:
                        existing_item = db.query(WeddingPackageItemModel).filter(WeddingPackageItemModel.id == item_payload.id).first()
                        if existing_item:
                            existing_item.type = item_payload.type
                            existing_item.price = item_payload.price
                            existing_item.description = item_payload.description
                            existing_item.url = item_payload.url
                    else:
                        new_item = WeddingPackageItemModel(
                            wedding_package_id=existing_wp.id,
                            type=item_payload.type,
                            price=item_payload.price,
                            description=item_payload.description,
                            url=item_payload.url,
                        )
                        db.add(new_item)

            else:
                # WeddingPackage 새로 생성
                new_wp = WeddingPackageModel(
                    estimate_id=existing_estimate.id,
                    type=payload.wedding_package.type,
                    name=payload.wedding_package.name,
                    total_price=payload.wedding_package.total_price,
                    is_total_price=payload.wedding_package.is_total_price,
                )
                db.add(new_wp)
                db.flush()  # new_wp.id를 얻기 위해

                for item_payload in payload.wedding_package.wedding_package_items:
                    new_item = WeddingPackageItemModel(
                        wedding_package_id=new_wp.id,
                        type=item_payload.type,
                        price=item_payload.price,
                        description=item_payload.description,
                        url=item_payload.url,
                    )
                    db.add(new_item)
        elif existing_wp:
            # payload에 wedding_package가 없고 기존 데이터가 있으면 삭제
            db.delete(existing_wp)

        db.commit()

        return {"message": f"ID '{estimate_id}'의 관리자 견적서 수정 완료", "estimate_id": existing_estimate.id}

    except SQLAlchemyError as e:
        db.rollback()
        print(f"데이터베이스 저장 오류: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 저장 오류 발생")
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        print(f"관리자 견적서 수정 중 서버 오류 발생: {e}")
        raise HTTPException(status_code=500, detail=f"서버 오류 발생: {e}")



    

    
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

@router.post('/get_admin_estimate')
async def get_admin_estimate(request : Request, db: Session = Depends(get_db)):
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
            EstimateModel.type == EstimateTypeEnum.admin # 표준 견적만 필터링
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

@router.get("/me")
def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("access_cookie")
    if not token:
        raise HTTPException(status_code=401, detail="Access token missing")

    result = verify_jwt_token(token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    payload = result["payload"]
    new_access_token = result.get("new_access_token")

    if new_access_token:
        response.set_cookie(
            key="access_cookie",
            value=new_access_token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=86400,
            path="/"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(Admin).filter(Admin.uid == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": {
            "name": user.name,
            "profile_image": user.profile_image,
        }
    }



@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_cookie")
    return {"message": "로그아웃 완료"}
