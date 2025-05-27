from http import HTTPStatus
from typing import List, Optional
from fastapi import FastAPI, Form, Request, APIRouter, Depends, HTTPException, Path
from grpc import Status
from pydantic import BaseModel, HttpUrl

from utils.hash import hash_password, verify_password
from utils.security import create_admin_token, verify_admin_jwt_token, verify_jwt_token
from auth.firebase import get_firebase_bucket, extract_firebase_path_from_url
from starlette.responses import Response
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import SQLAlchemyError
from core.database import get_db
from models.admin import Admin

from models.company import WeddingCompany as WeddingCompanyModel
from models.halls import Hall as HallModel, HallInclude as HallIncludeModel, HallPhoto as HallPhotoModel

from models.estimate import Estimate         as EstimateModel
from models.estimate import MealPrice       as MealPriceModel
from models.estimate import EstimateOption  as EstimateOptionModel
from models.estimate import Etc             as EtcModel

from models.package  import WeddingPackage     as WeddingPackageModel
from models.package  import WeddingPackageItem as WeddingPackageItemModel

from models.enums import EstimateTypeEnum


from schemas.update_standard_estimate import StandardEstimateUpdateRequestSchemaV2

from schemas.admin import (
    CodeRequest,
    HallSchema, HallPhotoSchema, HallIncludeSchema,
    EstimateSchema, EstimateOptionSchema,
    HallTypeEnum, MealTypeSchema,
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
          secure=True,           # ✅ 로컬 개발에서는 False
          samesite="None",         # ✅ 기본값으로
          max_age=86400,
          path='/',

          )

          return {"message": "login", "status": 200}
        else : 
           return {"message" : "암호 틀림", "status" : 401} 

    except Exception as e:
        print("❌ 예외 발생:", e)
        raise
    
    
@router.post("/create-standard-estimate")
def create_standard_estimate(
    payload: WeddingCompanyCreate, # 수정된 Pydantic 스키마 사용
    db: Session = Depends(get_db),
):
    print("payload received:", payload.model_dump_json(indent=2)) # Pydantic V2
    # print("payload received (V1):", payload.json(indent=2)) # Pydantic V1
    try:
        company = WeddingCompanyModel(
            name=payload.name,
            address=payload.address,
            phone=payload.phone,
            homepage=str(payload.homepage) if payload.homepage else None,
            accessibility=payload.accessibility,
            lat=payload.mapx, # DB 타입이 숫자라면 float(payload.mapx) 등으로 변환 필요
            lng=payload.mapy, # DB 타입이 숫자라면 float(payload.mapy) 등으로 변환 필요
            ceremony_times=payload.ceremony_times,
        )
        db.add(company)
        db.flush()

        hall_data_to_save = payload.hall.dict(exclude_unset=True)

        # ✨ 수정된 'hall.type' 필드 처리 로직
        # payload.hall.type은 이미 Pydantic에 의해 List[HallTypeEnum] (또는 None/빈 리스트)임
        actual_hall_type_list = payload.hall.type 

        if actual_hall_type_list: # None이 아니고 빈 리스트도 아닌 경우 (내용이 있는 리스트)
            # 각 HallTypeEnum 멤버의 .value (문자열 값)를 사용하여 join
            hall_data_to_save["type"] = ",".join(actual_hall_type_list) 
        else: # 빈 리스트거나 None인 경우 (프론트에서 아무것도 선택 안 함)
            hall_data_to_save["type"] = None # DB에 null로 저장 (또는 "" - DB 컬럼 정책에 따라)
        
        # print(f"Processed hall.type for DB: {hall_data_to_save.get('type')}")

        hall = HallModel(
            wedding_company_id=company.id,
            **hall_data_to_save
        )
        db.add(hall)
        db.flush()

        for inc_payload in payload.hall_includes:
            db.add(HallIncludeModel(hall_id=hall.id, **inc_payload.dict()))

        for photo_payload in payload.hall_photos:
            db.add(HallPhotoModel(hall_id=hall.id, **photo_payload.dict()))

        # estimate.date와 estimate.time이 프론트에서 ""로 오고 스키마에서 Optional[str]=None이면
        # payload.estimate.date는 ""일 수 있음. DB 저장 전에 None으로 변환 필요 시 여기서 처리.
        estimate_data_to_save = payload.estimate.dict(exclude_unset=True)
        if estimate_data_to_save.get("date") == "":
            estimate_data_to_save["date"] = None
        if estimate_data_to_save.get("time") == "":
            estimate_data_to_save["time"] = None
            
        estimate = EstimateModel(
            hall_id=hall.id,
            # **payload.estimate.dict(exclude_unset=True) # 이렇게 하면 date/time 전처리 불가
            **estimate_data_to_save, # 전처리된 데이터 사용
            created_by_user_id="131da9a7-6b64-4a0e-a75d-8cd798d698bd", # 실제 사용자 ID로 변경
        )
        db.add(estimate)
        db.flush()

        for m_payload in payload.meal_price:
            db.add(MealPriceModel(estimate_id=estimate.id, **m_payload.dict()))

        if payload.estimate_options: # Optional 이므로 None일 수 있음
            for opt_payload in payload.estimate_options:
                db.add(EstimateOptionModel(estimate_id=estimate.id, **opt_payload.dict()))

        if payload.etc: # Optional
            db.add(EtcModel(estimate_id=estimate.id, **payload.etc.dict()))

        # # ✨ wedding_package 및 package_items 처리 (스키마 수정 후)
        # if payload.wedding_package: # Optional이므로 None일 수 있음
        #     wp_data = payload.wedding_package.dict(exclude_unset=True)
        #     wp = WeddingPackageModel(
        #         estimate_id=estimate.id,
        #         **wp_data
        #     )
        #     db.add(wp)
        #     db.flush()

        #     if payload.package_items: # Optional이므로 None일 수 있고, 기본값은 빈 리스트
        #         for item_payload in payload.package_items: # 이제 AttributeError 발생 안 함
        #             db.add(WeddingPackageItemModel(wedding_package_id=wp.id, **item_payload.dict()))
        
        db.commit()
        return {"message": "업체 등록 완료", "company_id": company.id}

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc() # 서버 로그에 전체 스택 트레이스 출력
        raise HTTPException(status_code=500, detail=f"DB 저장 실패: {str(e)}")

    
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
        
        estimate = EstimateModel(
            hall_id=payload.hall_id,
            # 최상위 레벨 페이로드에서 필드를 직접 사용
            hall_price=payload.hall_price,
            type=EstimateTypeEnum.admin, # 여전히 admin으로 하드코딩됨
            date=payload.date, # <-- 이제 이게 최상위 레벨에 있습니다
            time = payload.time,
            penalty_amount = payload.penalty_amount,
            penalty_detail = payload.penalty_detail,
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
        existing_estimate.time = payload.time
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

#표준 견적서 가져오는 부분
@router.get("/standard_estimates/{estimate_id}")
async def get_single_standard_estimate( # 함수 이름 변경 (단건 조회 명시)
    estimate_id: int, # 경로 파라미터로 estimate_id 받기
    db: Session = Depends(get_db)
):
    """
    특정 ID의 표준 견적서 상세 정보를 모든 관계 데이터와 함께 가져옵니다.
    프론트엔드 수정 폼 초기화에 사용됩니다.
    """
    try:
        # Estimate를 기준으로 관련된 모든 데이터를 eager loading 합니다.
        # 친구가 제공한 코드의 로딩 옵션을 그대로 활용합니다.
        db_estimate = db.query(EstimateModel).options(
            joinedload(EstimateModel.hall).options(
                joinedload(HallModel.wedding_company),
                selectinload(HallModel.hall_photos),
                selectinload(HallModel.hall_includes)
            ),
            selectinload(EstimateModel.meal_prices),
            selectinload(EstimateModel.estimate_options),
            selectinload(EstimateModel.etcs),
            selectinload(EstimateModel.wedding_packages).selectinload(
                WeddingPackageModel.wedding_package_items
            )
            # 필요하다면 EstimateModel.created_by_user 관계도 로드
        ).filter(
            EstimateModel.id == estimate_id,
            EstimateModel.type == EstimateTypeEnum.standard # 표준 견적서만 필터링
        ).first() # .all() 대신 .first()를 사용하여 단일 객체를 가져옴

        if not db_estimate:
            raise HTTPException(status_code=404, detail=f"ID가 {estimate_id}인 표준 견적서를 찾을 수 없습니다.")

        # Pydantic 모델이 자동으로 SQLAlchemy 객체를 JSON으로 변환합니다.
        # (response_model=DetailedEstimateSchema 설정 덕분)
        return db_estimate

    except SQLAlchemyError as e:
        # 데이터베이스 쿼리 중 발생한 에러 처리
        print(f"데이터베이스 쿼리 오류: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except HTTPException as e:
        # 이미 HTTPException으로 처리된 예외는 다시 발생
        raise e
    except Exception as e:
        # 예상치 못한 다른 예외 발생 시 로깅 및 500 에러 반환
        print(f"표준 견적서 상세 정보 조회 중 서버 오류 발생 ({estimate_id=}): {e}")
        raise HTTPException(status_code=500, detail="표준 견적서 상세 정보 조회 중 서버 오류가 발생했습니다.")


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


def update_child_list_items(
    db: Session,
    db_parent_instance: any, # 예: db_estimate 또는 db_hall 또는 db_package
    current_db_child_list: List[any], # 예: db_estimate.meal_prices
    payload_child_list: Optional[List[BaseModel]], # 예: request_data.meal_prices
    child_model_class: type, # 예: MealPriceModel
    parent_foreign_key_name: str, # 예: "estimate_id" 또는 "hall_id"
    # child_unique_key_name: str = "id" # 자식 항목의 PK 이름 (보통 'id')
):
    """
    부모 객체에 연결된 자식 항목 목록을 업데이트합니다 (Create, Update, Delete).
    payload_child_list의 각 항목은 id (기존 항목) 또는 id 없음 (새 항목)을 가질 수 있습니다.
    """
    if payload_child_list is None: # payload에 해당 목록이 없으면 아무것도 안 함
        return

    existing_child_ids_in_db = {child.id for child in current_db_child_list if child.id}
    payload_child_ids_with_id = {payload_item.id for payload_item in payload_child_list if payload_item.id}

    # 1. 삭제 (Delete): DB에는 있지만 payload에는 없는 ID (기존 항목이 삭제된 경우)
    child_ids_to_delete = existing_child_ids_in_db - payload_child_ids_with_id
    if child_ids_to_delete:
        print(f"Deleting {child_model_class.__name__} IDs: {child_ids_to_delete}")
        for child_id in child_ids_to_delete:
            child_to_delete = db.query(child_model_class).filter_by(id=child_id).first()
            if child_to_delete:
                db.delete(child_to_delete)

    # 2. 수정 (Update) 또는 추가 (Create)
    for payload_item_schema in payload_child_list:
        payload_item_dict = payload_item_schema.model_dump(exclude_unset=True) # Pydantic V2
        # payload_item_dict = payload_item_schema.dict(exclude_unset=True) # Pydantic V1

        item_id = payload_item_dict.get("id")

        if item_id and item_id in existing_child_ids_in_db: # ID가 있고 DB에도 존재하면 수정
            print(f"Updating {child_model_class.__name__} ID: {item_id}")
            db_child_item = db.query(child_model_class).filter_by(id=item_id).first()
            if db_child_item:
                for key, value in payload_item_dict.items():
                    if key != "id": # id는 업데이트 대상이 아님
                        setattr(db_child_item, key, value)
        elif not item_id : # ID가 없으면 새 항목으로 추가 (또는 ID가 있지만 DB에 없는 비정상 케이스도 여기에 포함될 수 있음)
            # 새 항목 추가 시 부모 ID 설정
            payload_item_dict.pop("id", None) # id 필드가 실수로 있어도 제거
            payload_item_dict[parent_foreign_key_name] = db_parent_instance.id
            print(f"Creating new {child_model_class.__name__} with data: {payload_item_dict}")
            new_child_item = child_model_class(**payload_item_dict)
            db.add(new_child_item)
            # current_db_child_list.append(new_child_item) # SQLAlchemy 세션에 반영 (선택적)
    db.flush() # 변경사항(특히 새 ID)을 DB 세션에 반영


@router.put("/standard_estimates/{estimate_id}")
async def update_standard_estimate_full(
    estimate_id: int,
    request_data: StandardEstimateUpdateRequestSchemaV2,
    db: Session = Depends(get_db)
):
    print("request_data", request_data)
    db_estimate = db.query(EstimateModel).options(
        joinedload(EstimateModel.hall).options(
            joinedload(HallModel.wedding_company),
            selectinload(HallModel.hall_photos),
            selectinload(HallModel.hall_includes)
        ),
        selectinload(EstimateModel.meal_prices),
        selectinload(EstimateModel.estimate_options),
        selectinload(EstimateModel.etcs),
        selectinload(EstimateModel.wedding_packages).options(
            selectinload(WeddingPackageModel.wedding_package_items)
        ),
    ).filter(
        EstimateModel.id == estimate_id,
        EstimateModel.type == EstimateTypeEnum.standard
    ).first()

    if not db_estimate:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="수정할 표준 견적서를 찾을 수 없습니다.")
    if not db_estimate.hall:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"견적서에 필수 홀 정보가 누락되었습니다. (ID: {db_estimate.id})")

    bucket = get_firebase_bucket()
    firebase_available = bucket is not None
    if not firebase_available:
        print(f"경고: Firebase 버킷을 가져올 수 없어 Firebase 파일 처리를 건너뜁니다. (Estimate ID: {estimate_id})")

    try:
        # --- 사진 처리 ---
        current_db_photos_map = {photo.id: photo for photo in db_estimate.hall.hall_photos if photo.id}
        persisted_or_created_photo_ids = set()

        if request_data.photos_data:
            print(f"처리할 사진 목록 {len(request_data.photos_data)}개 (홀 ID: {db_estimate.hall.id})")
            for photo_payload in request_data.photos_data:
                db_photo_to_update = current_db_photos_map.get(photo_payload.id) if photo_payload.id else None

                if db_photo_to_update: # 기존 사진 업데이트
                    print(f"사진 업데이트 (ID: {db_photo_to_update.id})")
                    db_photo_to_update.order_num = photo_payload.order_num
                    db_photo_to_update.caption = photo_payload.caption
                    db_photo_to_update.is_visible = photo_payload.is_visible if photo_payload.is_visible is not None else True
                    persisted_or_created_photo_ids.add(db_photo_to_update.id)
                elif photo_payload.url: # 새 사진 추가
                    print(f"새 사진 추가: URL='{photo_payload.url}', Order={photo_payload.order_num}")
                    new_db_photo = HallPhotoModel(
                        hall_id=db_estimate.hall.id,
                        url=photo_payload.url,
                        order_num=photo_payload.order_num,
                        caption=photo_payload.caption,
                        is_visible=photo_payload.is_visible if photo_payload.is_visible is not None else True
                    )
                    db.add(new_db_photo)
                    db.flush()
                    persisted_or_created_photo_ids.add(new_db_photo.id)
                else:
                     print(f"경고: 유효 ID/URL 없는 사진 페이로드 건너뜁니다: {photo_payload}")

            db.flush()

        # 삭제할 사진 처리
        ids_explicitly_marked_for_delete = set(request_data.photo_ids_to_delete or [])
        all_db_photo_ids = set(current_db_photos_map.keys())
        ids_to_actually_delete = ids_explicitly_marked_for_delete.union(all_db_photo_ids - persisted_or_created_photo_ids)

        if ids_to_actually_delete:
            print(f"실제 삭제될 사진 ID 목록: {ids_to_actually_delete}")
            for photo_id_to_delete in ids_to_actually_delete:
                photo_record = current_db_photos_map.get(photo_id_to_delete)
                if photo_record:
                    if firebase_available and photo_record.url:
                        firebase_path = extract_firebase_path_from_url(photo_record.url)
                        if firebase_path:
                            try:
                                # ✨ 수정된 부분: Firebase 경로 직접 사용 (rsplit 제거)
                                blob = bucket.blob(firebase_path)
                                blob.delete()
                                print(f"  Firebase 파일 삭제 성공 (ID: {photo_id_to_delete}): {firebase_path}")
                                # --- 수정 끝 ---
                            except Exception as e_fb_del:
                                # 404 에러는 이미 없으므로 경고로 처리, 그 외는 에러
                                if "No such object" in str(e_fb_del) or (hasattr(e_fb_del, 'code') and e_fb_del.code == 404):
                                    print(f"  경고: Firebase 파일 이미 없음 (ID: {photo_id_to_delete}, Path: {firebase_path}): {e_fb_del}")
                                else:
                                    print(f"  에러: Firebase 파일 삭제 실패 (ID: {photo_id_to_delete}, Path: {firebase_path}): {e_fb_del}")
                        else:
                            print(f"  경고: Firebase 경로 추출 실패 (ID: {photo_id_to_delete}, URL: {photo_record.url})")

                    db.delete(photo_record)
                    print(f"  DB 사진 레코드 삭제 성공 (ID: {photo_id_to_delete})")
            db.flush()
        # --- 사진 처리 끝 ---

        # --- 나머지 견적서 필드 업데이트 ---
        # Estimate 직접 필드
        update_fields = {
            "hall_price": request_data.hall_price, "date": request_data.date, "time": request_data.time,
            "penalty_amount": request_data.penalty_amount, "penalty_detail": request_data.penalty_detail,
            "type": request_data.type
        }
        for field, value in update_fields.items():
            if value is not None:
                setattr(db_estimate, field, value)

        # WeddingCompany 정보 업데이트
        if request_data.wedding_company_update_data and db_estimate.hall.wedding_company:
            company_payload = request_data.wedding_company_update_data
            db_company = db_estimate.hall.wedding_company
            company_fields = {
                "name": company_payload.name, "address": company_payload.address, "phone": company_payload.phone,
                "homepage": company_payload.homepage, "accessibility": company_payload.accessibility,
                "lat": company_payload.lat, "lng": company_payload.lng,
                "ceremony_times": company_payload.ceremony_times
            }
            for field, value in company_fields.items():
                if value is not None:
                     setattr(db_company, field, value)
            print(f"업체 정보 업데이트 완료 (ID: {db_company.id})")

        # Hall 기본 정보 업데이트
        if request_data.hall_update_data and db_estimate.hall:
            hall_payload = request_data.hall_update_data
            db_hall = db_estimate.hall
            hall_fields = {
                "name": hall_payload.name, "interval_minutes": hall_payload.interval_minutes,
                "guarantees": hall_payload.guarantees, "parking": hall_payload.parking,
                "mood": hall_payload.mood
            }
            for field, value in hall_fields.items():
                if value is not None:
                    setattr(db_hall, field, value)

                if hall_payload.type is not None:  # type 필드가 요청 페이로드에 포함된 경우
                    print(f"hall_payload.type (프론트엔드에서 받은 파이썬 리스트): {hall_payload.type}") # 예: ['야외', '가든']

                if hall_payload.type:  # 리스트가 비어있지 않고 내용이 있는 경우 (선택된 타입이 있음)
                    # 파이썬 문자열 리스트를 쉼표로 구분된 단일 문자열로 변환
                    # 예: ['야외', '가든'] -> "야외,가든"
                    comma_separated_string_types = ",".join(hall_payload.type)
                    
                    db_hall.type = comma_separated_string_types # 변환된 단일 문자열을 할당
                    print(f"홀 타입 업데이트 (DB에 저장될 실제 문자열): {db_hall.type}")
                else:  # 빈 리스트 [] 가 전달된 경우 (모든 타입 선택 해제 의미)
                    db_hall.type = None  # DB에 NULL로 저장
                    print("홀 타입 업데이트 (빈 리스트 수신, DB에 None으로 설정)")

            print(f"홀 기본 정보 업데이트 완료 (ID: {db_hall.id})")

        # --- 자식 목록 업데이트 (update_child_list_items 사용) ---
        # (기존 코드와 유사하게 유지, update_child_list_items 함수 구현이 정확해야 함)
        if request_data.hall_includes is not None and db_estimate.hall:
             print(f"홀 포함사항 업데이트 시작 (홀 ID: {db_estimate.hall.id})")
             update_child_list_items(
                 db=db, db_parent_instance=db_estimate.hall,
                 current_db_child_list=db_estimate.hall.hall_includes,
                 payload_child_list=request_data.hall_includes,
                 child_model_class=HallIncludeModel,
                 parent_foreign_key_name="hall_id"
             )

        if request_data.meal_prices is not None:
            print(f"식대 정보 업데이트 시작 (견적 ID: {db_estimate.id})")
            update_child_list_items(
                db=db, db_parent_instance=db_estimate,
                current_db_child_list=db_estimate.meal_prices,
                payload_child_list=request_data.meal_prices,
                child_model_class=MealPriceModel,
                parent_foreign_key_name="estimate_id"
            )

        if request_data.estimate_options is not None:
            print(f"견적 옵션 업데이트 시작 (견적 ID: {db_estimate.id})")
            update_child_list_items(
                db=db, db_parent_instance=db_estimate,
                current_db_child_list=db_estimate.estimate_options,
                payload_child_list=request_data.estimate_options,
                child_model_class=EstimateOptionModel,
                parent_foreign_key_name="estimate_id"
            )

        if request_data.etcs is not None:
            print(f"기타 정보 업데이트 시작 (견적 ID: {db_estimate.id})")
            update_child_list_items(
                db=db, db_parent_instance=db_estimate,
                current_db_child_list=db_estimate.etcs,
                payload_child_list=request_data.etcs,
                child_model_class=EtcModel,
                parent_foreign_key_name="estimate_id"
            )

        # WeddingPackages 업데이트 (기존 로직 유지, 필요시 update_child_list_items 적용 검토)
        if request_data.wedding_packages is not None:
             print(f"웨딩 패키지 업데이트 시작 (견적 ID: {db_estimate.id})")
             # ... (기존 패키지 처리 로직, 여기서는 생략) ...
             # WeddingPackageItems 업데이트 로직도 여기에 포함되어야 함 (주석 처리된 부분 활성화 및 검토 필요)


        db.commit()
        db.refresh(db_estimate)

        print(f"표준 견적서(ID:{estimate_id}) 전체 정보 업데이트 완료")
        return db_estimate

    except SQLAlchemyError as e:
        db.rollback()
        print(f"DB 오류 발생 (Estimate ID: {estimate_id}): {str(e)}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="데이터베이스 처리 중 오류가 발생했습니다.")
    except HTTPException as e: # 명시적으로 발생시킨 HTTP 예외
        db.rollback()
        raise e # 그대로 다시 발생
    except Exception as e:
        db.rollback()
        print(f"일반 서버 오류 발생 (Estimate ID: {estimate_id}): {str(e)}")
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="서버 내부 오류가 발생했습니다.")


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

@router.get('/get_standard_estimate_all')
async def get_admin_estimate_all(db: Session = Depends(get_db)):
    """
    모든 관리자 견적서 목록과 관련 상세 정보를 가져옵니다.
    (업체, 홀, 식대, 옵션, 기타, 패키지 등)
    """
    print("GET /admin/get_admin_estimate_all 엔드포인트 호출됨")

    # SQLAlchemy 쿼리: Estimate를 기준으로 관련 정보 모두 로드
    # selectinload: 1대N 관계 (리스트) 로드 시 효율적 (meal_prices, etcs 등)
    # joinedload: 1대1 관계 (단일 객체) 로드 시 효율적 (hall, wedding_company)
    estimates = db.query(EstimateModel)\
                .options(
                    # Estimate -> MealPrice 목록 로드
                    selectinload(EstimateModel.meal_prices),
                    # Estimate -> EstimateOption 목록 로드
                    selectinload(EstimateModel.estimate_options),
                    # Estimate -> Etc 목록 로드
                    selectinload(EstimateModel.etcs),
                    # Estimate -> WeddingPackage 목록 로드 (일반적으로 견적당 패키지는 0 또는 1개)
                    # 패키지 내 아이템도 함께 로드
                    selectinload(EstimateModel.wedding_packages).selectinload(WeddingPackageModel.wedding_package_items),
                    # Estimate -> Hall 로드, 그리고 Hall -> WeddingCompany 로드
                    joinedload(EstimateModel.hall).joinedload(HallModel.wedding_company),
                    # Hall -> HallPhoto 목록 로드
                    joinedload(EstimateModel.hall).selectinload(HallModel.hall_photos),
                     # Hall -> HallInclude 목록 로드
                    joinedload(EstimateModel.hall).selectinload(HallModel.hall_includes),
                ).filter(EstimateModel.type == "standard").all() # 모든 견적서 가져오기

    print(f"총 {len(estimates)}개의 견적서 불러옴")
    # Pydantic 응답 모델로 자동 직렬화되어 반환됨
    return estimates

@router.get('/get_admin_estimate_all')
async def get_admin_estimate_all(db: Session = Depends(get_db)):
    """
    모든 관리자 견적서 목록과 관련 상세 정보를 가져옵니다.
    (업체, 홀, 식대, 옵션, 기타, 패키지 등)
    """
    print("GET /admin/get_admin_estimate_all 엔드포인트 호출됨")

    # SQLAlchemy 쿼리: Estimate를 기준으로 관련 정보 모두 로드
    # selectinload: 1대N 관계 (리스트) 로드 시 효율적 (meal_prices, etcs 등)
    # joinedload: 1대1 관계 (단일 객체) 로드 시 효율적 (hall, wedding_company)
    estimates = db.query(EstimateModel)\
                .options(
                    # Estimate -> MealPrice 목록 로드
                    selectinload(EstimateModel.meal_prices),
                    # Estimate -> EstimateOption 목록 로드
                    selectinload(EstimateModel.estimate_options),
                    # Estimate -> Etc 목록 로드
                    selectinload(EstimateModel.etcs),
                    # Estimate -> WeddingPackage 목록 로드 (일반적으로 견적당 패키지는 0 또는 1개)
                    # 패키지 내 아이템도 함께 로드
                    selectinload(EstimateModel.wedding_packages).selectinload(WeddingPackageModel.wedding_package_items),
                    # Estimate -> Hall 로드, 그리고 Hall -> WeddingCompany 로드
                    joinedload(EstimateModel.hall).joinedload(HallModel.wedding_company),
                    # Hall -> HallPhoto 목록 로드
                    joinedload(EstimateModel.hall).selectinload(HallModel.hall_photos),
                     # Hall -> HallInclude 목록 로드
                    joinedload(EstimateModel.hall).selectinload(HallModel.hall_includes),
                ).filter(EstimateModel.type == "admin").all() # 모든 견적서 가져오기

    print(f"총 {len(estimates)}개의 견적서 불러옴")
    # Pydantic 응답 모델로 자동 직렬화되어 반환됨
    return estimates

@router.delete('/admin_estimates/{estimate_id}')
async def delete_admin_estimate(estimate_id: int, db: Session = Depends(get_db)):
    """
    특정 ID의 관리자 견적서와 연관된 모든 하위 정보를 삭제합니다.
    (식대, 옵션, 기타, 패키지 등)
    """
    print(f"DELETE /admin/estimates/{estimate_id} 엔드포인트 호출됨")

    # 삭제할 견적서 찾기
    # .first() 대신 .one_or_none()을 사용하여 레코드가 0개 또는 1개임을 명시할 수 있습니다.
    estimate = db.query(EstimateModel).filter(EstimateModel.id == estimate_id).one_or_none()

    if estimate is None:
        # 견적서를 찾을 수 없을 경우 404 Not Found 에러 반환
        raise HTTPException(
            status_code=Status.HTTP_404_NOT_FOUND, # status 모듈 사용 권장
            detail=f"견적서 ID {estimate_id}를 찾을 수 없습니다."
        )

    try:
        # 견적서 삭제
        # SQLAlchemy의 cascade="all" 설정에 따라 연결된 하위 정보(meal_prices, etcs 등)도 자동으로 삭제됩니다.
        db.delete(estimate)
        db.commit() # 데이터베이스에 변경사항 반영 (삭제 실행)
        # db.refresh(estimate) # 삭제된 객체에는 refresh를 할 필요 없습니다.

        print(f"견적서 (ID: {estimate_id}) 및 연관 정보 삭제 완료")

        # 삭제 성공 응답 반환 (예: 성공 메시지)
        # 클라이언트는 200 OK 응답을 받으면 성공으로 처리합니다.
        return {"message": f"견적서 (ID: {estimate_id})가 성공적으로 삭제되었습니다."}

    except Exception as e:
        db.rollback() # 데이터베이스 작업 중 오류 발생 시 롤백하여 불완전한 변경 방지
        print(f"견적서 삭제 중 오류 발생 (ID: {estimate_id}): {e}")
        # 내부 서버 오류 500 에러 반환
        raise HTTPException(
            status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR, # status 모듈 사용 권장
            detail=f"견적서 삭제 중 오류가 발생했습니다: {e}"
        )


# --- 표준 견적서 삭제 엔드포인트 (업체 + 홀 + 사진 삭제) ---
@router.delete('/standard_estimates/{estimate_id}')
async def delete_standard_estimate(estimate_id: int, db: Session = Depends(get_db)):
    """
    특정 ID의 표준 견적서에 연결된 홀과 해당 홀이 속한 '업체(Company)',
    그리고 홀의 모든 정보(사진 포함)를 삭제합니다.
    Firebase Storage에 저장된 사진 파일도 삭제합니다.
    (주의: 이 업체/홀에 연결된 다른 모든 정보도 함께 삭제될 수 있습니다.)
    """
    print(f"DELETE /standard_estimates/{estimate_id} 엔드포인트 호출됨 (업체 포함 삭제)")

    # 1. 삭제 대상 견적서 로드 시, 연관된 홀 -> 사진, 홀 -> 업체를 함께 로드 (Eager Loading)
    # HallModel에 'company'라는 이름의 관계(relationship)가 정의되어 있다고 가정합니다.
    # 만약 관계 이름이 다르면 'HallModel.company' 부분을 실제 이름으로 변경해야 합니다.
    estimate_to_delete = db.query(EstimateModel)\
                            .options(
                                joinedload(EstimateModel.hall) # 견적서 -> 홀
                                .joinedload(HallModel.hall_photos), # 홀 -> 사진들
                                joinedload(EstimateModel.hall) # 견적서 -> 홀
                                .joinedload(HallModel.wedding_company) # <<< 수정됨: 'wedding_company' 관계 속성 사용
                            )\
                            .filter(EstimateModel.id == estimate_id)\
                            .one_or_none()

    if estimate_to_delete is None:
        raise HTTPException(
            status_code=Status.HTTP_404_NOT_FOUND,
            detail=f"견적서 ID {estimate_id}를 찾을 수 없습니다."
        )

    # 2. 견적서에 연결된 Hall 객체 및 Company 객체 가져오기 (joinedload로 이미 로드됨)
    hall_to_delete = estimate_to_delete.hall

    if hall_to_delete is None:
         print(f"경고: 견적서 (ID: {estimate_id})가 연결된 홀 정보를 찾을 수 없습니다. 삭제 작업을 진행할 수 없습니다.")
         # 홀 정보가 없으면 업체 정보도 알 수 없으므로 에러 처리
         raise HTTPException(
             status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"견적서 ID {estimate_id}에 연결된 필수 홀 정보를 찾을 수 없습니다."
         )

    # ✅ 홀에 연결된 Company 객체 가져오기
    # HallModel.company 관계를 통해 CompanyModel 객체에 접근합니다.
    company_to_delete = hall_to_delete.wedding_company

    if company_to_delete is None:
         # 데이터 무결성 문제일 수 있습니다. 홀은 있는데 업체가 없는 경우.
         # 정책에 따라 경고만 출력하고 홀만 삭제하거나, 에러를 발생시킬 수 있습니다.
         # 여기서는 경고 출력 후 홀만 삭제하는 방향으로 진행합니다.
         print(f"경고: 홀 (ID: {hall_to_delete.id})에 연결된 업체 정보를 찾을 수 없습니다. 업체 삭제는 건너뜁니다.")
         # 필요 시 아래 주석 해제하여 에러 발생
         # raise HTTPException(
         #     status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR,
         #     detail=f"홀 ID {hall_to_delete.id}에 연결된 업체 정보가 누락되었습니다."
         # )

    # 3. Firebase Storage 버킷 가져오기 및 초기화
    bucket = get_firebase_bucket()
    firebase_delete_attempted = bucket is not None # 버킷 가져오기 성공 여부
    photos_deleted_count = 0
    photos_failed_count = 0

    if not firebase_delete_attempted:
        print("경고: Firebase Storage 버킷 초기화 또는 가져오기 실패. Firebase 파일 삭제는 건너뜁니다.")
        # TODO: 에러 처리 정책 결정 (예: DB 삭제도 막을지 여부)

    # --- 삭제 로직 시작 (DB 트랜잭션 관리) ---
    try:
        # 4. Firebase Storage에서 사진 파일 삭제 시도 (버킷이 준비된 경우)
        if firebase_delete_attempted and hall_to_delete.hall_photos: # 사진 레코드가 있을 때만
            print(f"Firebase Storage에서 파일 삭제 시도 시작 (홀 ID: {hall_to_delete.id})...")
            for photo_record in hall_to_delete.hall_photos:
                if photo_record.url: # URL이 있는 경우만
                    firebase_path = extract_firebase_path_from_url(photo_record.url)
                    if firebase_path: # 경로 추출 성공 시
                        try:
                            blob = bucket.blob(firebase_path)
                            blob.delete() # 파일 삭제 실행
                            print(f"Firebase 파일 삭제 성공: {firebase_path}")
                            photos_deleted_count += 1
                        except Exception as firebase_error:
                            # 개별 파일 삭제 실패 시 로깅 및 카운트 증가 (전체 프로세스 중단 안 함)
                            print(f"경고: Firebase 파일 삭제 실패: {firebase_path} - {firebase_error}")
                            photos_failed_count += 1
                            # TODO: 실패 알림 또는 재시도 로직 등 고려
            print(f"Firebase 파일 삭제 시도 완료. 성공: {photos_deleted_count}, 실패: {photos_failed_count}")
        elif firebase_delete_attempted:
            print(f"홀 (ID: {hall_to_delete.id})에 삭제할 Firebase 사진 레코드가 없습니다.")
        # else: 버킷 접근 실패 메시지는 위에서 출력됨

        # 5. 데이터베이스 레코드 삭제
        # 주의: 삭제 순서 및 Cascade 설정에 따라 결과가 달라질 수 있습니다.
        # 여기서는 Hall을 먼저 삭제하고, 그 다음에 Company를 삭제합니다.
        # 만약 Company 삭제 시 Hall이 자동으로 Cascade 삭제되도록 설정되어 있다면,
        # Hall 삭제 코드는 불필요할 수 있습니다. (하지만 명시적으로 두는 것이 안전할 수 있음)

        # ✅ Hall 삭제 (연관된 Estimate, HallPhoto 등 DB 레코드가 Cascade 삭제될 수 있음)
        db.delete(hall_to_delete)
        print(f"DB에서 홀 레코드 삭제 시도 (ID: {hall_to_delete.id})")

        # ✅ Company 삭제 (연관된 다른 Hall 등 DB 레코드가 Cascade 삭제될 수 있음)
        if company_to_delete: # Company 객체가 존재하고 연결되어 있는 경우에만 삭제
             db.delete(company_to_delete)
             print(f"DB에서 업체 레코드 삭제 시도 (ID: {company_to_delete.id})")
        else:
             print("DB에서 업체 레코드 삭제 건너뜀 (연결된 업체 정보 없음)")

        # 6. 모든 DB 변경사항 커밋
        db.commit()

        print(f"견적서(ID:{estimate_id})에 연결된 홀(ID:{hall_to_delete.id}) 및 업체(ID:{company_to_delete.id if company_to_delete else 'N/A'}) 관련 정보 DB 삭제 완료")

        # 7. 삭제 성공 응답 반환
        return {
            "message": f"견적서(ID:{estimate_id})와 연결된 업체, 홀 및 모든 연관 정보가 성공적으로 삭제되었습니다.",
            "deleted_estimate_id": estimate_id,
            "deleted_hall_id": hall_to_delete.id,
            "deleted_company_id": company_to_delete.id if company_to_delete else None, # 삭제된 업체 ID 반환
            "firebase_files_deleted": photos_deleted_count,
            "firebase_files_failed_to_delete": photos_failed_count,
            "firebase_delete_attempted": firebase_delete_attempted # Firebase 삭제 시도 여부
        }

    except Exception as e:
        # DB 작업 중 오류 발생 시 롤백
        db.rollback()
        print(f"삭제 처리 중 치명적 오류 발생 (Estimate ID: {estimate_id}): {e}")
        # 중요: Firebase에서 이미 삭제된 파일은 DB 롤백과 별개로 복구되지 않습니다.
        raise HTTPException(
            status_code=Status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"삭제 처리 중 오류가 발생했습니다: {e}"
        )



@router.get("/me")
def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("admin_token")
    if not token:
        raise HTTPException(status_code=401, detail="Access token missing. Please log in.")

    token_data = verify_admin_jwt_token(token) # 수정된 검증 함수 사용

    if not token_data:
        # 토큰이 유효하지 않거나 만료된 경우, 클라이언트 측 쿠키 삭제
        response.delete_cookie(
            key="admin_token",
            path="/",
            # domain=None, # 생성 시 명시 안 했으면 생략 또는 동일하게 설정
            secure=True,   # HTTPS 환경에서만 쿠키 전송 (토큰 생성 시와 일치)
            httponly=True, # JavaScript에서 쿠키 접근 불가 (토큰 생성 시와 일치)
            samesite="None" # CSRF 방지, secure=True와 함께 사용 (토큰 생성 시와 일치)
        )
        # 클라이언트에게 명확한 메시지와 함께 401 응답
        raise HTTPException(status_code=401, detail="Your session has expired or the token is invalid. Please log in again.")

    payload = token_data["payload"]
    admin_id = payload.get("sub") # "sub"는 일반적으로 user ID를 담는 표준 클레임

    if not admin_id:
        # "sub" 클레임이 없는 경우도 유효하지 않은 토큰으로 간주
        response.delete_cookie(key="admin_token", path="/", secure=True, httponly=True, samesite="None")
        raise HTTPException(status_code=401, detail="Invalid token payload. Please log in again.")
    
    admin = db.query(Admin).filter(Admin.id == admin_id).first()

    if not admin:
        # 해당 ID의 관리자가 DB에 없는 경우
        response.delete_cookie(key="admin_token", path="/", secure=True, httponly=True, samesite="None")
        raise HTTPException(status_code=404, detail="Admin not found. Please log in again.")

    return {
        "admin": {
            "id": admin.id, # ID도 반환하는 것이 유용할 수 있습니다.
            "name": admin.name,
            # 필요한 다른 관리자 정보
        }
    }

@router.post("/logout")
def logout(response: Response):
    # 로그아웃 시 쿠키 삭제 로직은 이미 잘 구현되어 있습니다.
    # 생성 시 사용된 옵션과 동일하게 지정해야 합니다.
    response.delete_cookie(
        key="admin_token",
        path="/",
        # domain=None, # 생성 시와 동일하게
        secure=True, 
        httponly=True,
        samesite="None" 
    )
    return {"message": "로그아웃 완료"}