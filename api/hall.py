from fastapi import APIRouter, Path, Request, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload, selectinload,with_loader_criteria
from sqlalchemy.exc import SQLAlchemyError
from core.database import get_db

from models.company import WeddingCompany
from models.estimate import Estimate, EstimateOption
from models.package import WeddingPackage
from models.halls import Hall, HallPhoto

router = APIRouter(prefix='/hall')

@router.get('/get_wedding_halls')
def get_wedding_halls(db:Session = Depends(get_db)):
  print("hello")
#   companies_query = (
#     db.query(WeddingCompany)
#     .options(
#         selectinload(WeddingCompany.halls)
#         .selectinload(Hall.hall_photos),
        
#         selectinload(WeddingCompany.halls)
#         .selectinload(Hall.estimates),
        
#         with_loader_criteria(
#             Estimate, 
#             lambda est: est.type == "standard", 
#             include_aliases=True
#         )
#     )
# )
  companies_query = db.query(WeddingCompany).options(selectinload(WeddingCompany.halls).selectinload(Hall.hall_photos))

  companies = companies_query.all()

  return companies

@router.get(
    "/get_detail_wedding_hall/{company_id}",
    summary="특정 업체의 모든 홀과 그 홀의 모든 견적서 상세 정보를 가져옵니다."
)
async def get_company_full_details(
    company_id: int = Path(..., description="정보를 가져올 업체의 고유 ID"),
    db: Session = Depends(get_db)
):
    """
    주어진 `company_id`에 해당하는 업체의 모든 웨딩 홀과 각 홀에 연결된
    모든 견적서 (표준 및 일반), 그리고 각 견적서에 포함된 식대, 옵션, 기타 비용,
    웨딩 패키지 및 패키지 아이템 상세 정보를 깊이 로딩하여 반환합니다.
    """
    try:
        # WeddingCompany를 기준으로 쿼리 시작
        # company_id로 필터링
        # selectinload를 사용하여 관계된 모든 데이터를 효율적으로 로딩
        company = db.query(WeddingCompany).options(
            # Company -> Halls 로딩 (1:N)
            selectinload(WeddingCompany.halls).options(
                # Hall -> HallPhoto 로딩 (1:N)
                selectinload(Hall.hall_photos),
                # Hall -> HallInclude 로딩 (1:N)
                selectinload(Hall.hall_includes),
                # Hall -> Estimates 로딩 (1:N)
                selectinload(Hall.estimates).options(
                    # Estimate -> MealPrice 로딩 (1:N)
                    selectinload(Estimate.meal_prices),
                    # Estimate -> EstimateOption 로딩 (1:N)
                    selectinload(Estimate.estimate_options),
                    # Estimate -> Etc 로딩 (1:N)
                    selectinload(Estimate.etcs),
                    # Estimate -> WeddingPackage 로딩 (1:N)
                    selectinload(Estimate.wedding_packages).selectinload(
                        # WeddingPackage -> WeddingPackageItem 로딩 (1:N)
                        WeddingPackage.wedding_package_items
                    )
                    # Estimate -> User 관계도 필요하다면 추가: selectinload(EstimateModel.created_by_user)
                    # 여기서 Estimate type 필터링은 없습니다. (standard, admin 모두 가져옴)
                )
            )
        ).filter(
            WeddingCompany.id == company_id
        ).first()

        # 업체가 없는 경우 404 에러 반환
        if not company:
            raise HTTPException(status_code=404, detail=f"업체 ID {company_id}를 찾을 수 없습니다.")

        print("company", company)
        # Pydantic response_model에 의해 SQLAlchemy 객체가 자동으로 스키마로 변환되어 반환됩니다.
        return company

    except SQLAlchemyError as e:
        # 데이터베이스 쿼리 중 발생한 에러 처리
        print(f"데이터베이스 쿼리 오류: {e}")
        raise HTTPException(status_code=500, detail="데이터베이스 오류 발생")
    except HTTPException as e:
        # 이미 HTTPException으로 처리된 예외는 다시 발생
        raise e
    except Exception as e:
        # 예상치 못한 다른 예외 발생 시 로깅 및 500 에러 반환
        print(f"업체 상세 정보를 가져오는 중 서버 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="업체 상세 정보를 가져오는 중 서버 오류가 발생했습니다.")
