# main.py 또는 router_likes.py (새 파일로 분리 추천)
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import Uuid, exc # SQLAlchemy 예외 처리용
from typing import List, Optional

from core.database import get_db # get_db 함수가 있는 파일 임포트
from models.likes import LikeModel
from models.company import WeddingCompany
from models.halls import Hall, HallPhoto
from schemas.likes import HallInfoResponse, LikeBatchRequest, LikeBatchResponse, LikeRequest, LikeStatusResponse, LikedWeddingCompanyResponse, WeddingCompanyOut, WeddingHallPhoto
import jwt # PyJWT 라이브러리 임포트

JWT_SECRET = os.getenv('JWT_SECRET_KEY')

router = APIRouter(
    prefix="/likes",
    tags=["likes"]
)

async def get_current_user_id(request:Request):
    token_name = "access_cookie"
    token = request.cookies.get(token_name)

    if not token :
      raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated: Missing token.")
    
    try : 
        decoded_token = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = decoded_token.get("sub")

        return user_id
    except jwt.ExpiredSignatureError:
        # 토큰 만료
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed: Token has expired.")
    except jwt.InvalidTokenError as e:
        # 유효하지 않은 토큰 (서명 불일치 등)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Authentication failed: Invalid token ({e}).")
    except Exception as e:
        # 기타 예외 처리
        print(f"Unexpected error during token decoding: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during authentication.")


@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_like(
    payload: LikeRequest,
    user_id: str = Depends(get_current_user_id), # 인증된 사용자 ID
    db: Session = Depends(get_db)
):
    try:
        # LikesModel 인스턴스 생성
        new_like = LikeModel(
            user_id=user_id,
            wedding_company_id=payload.wedding_company_id
        )
        db.add(new_like)
        db.commit() # 변경사항 커밋
        db.refresh(new_like) # 생성된 객체 업데이트 (created_at 등)

        return {"message": "성공적으로 찜했습니다.", "data": {"user_id": str(new_like.user_id), "wedding_company_id": new_like.wedding_company_id, "created_at": new_like.created_at.isoformat()}}

    except exc.IntegrityError: # 복합 기본 키 충돌 시 (이미 찜한 경우)
        db.rollback() # 트랜잭션 롤백
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 찜한 웨딩홀입니다.")
    except Exception as e:
        db.rollback()
        print(f"Error adding like: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"찜하기에 실패했습니다: {e}")

@router.delete("/", status_code=status.HTTP_200_OK)
async def remove_like(
    payload: LikeRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    try:
        # 해당 찜 레코드 조회
        like_entry = db.query(LikeModel).filter(
            LikeModel.user_id == user_id,
            LikeModel.wedding_company_id == payload.wedding_company_id
        ).first()

        if not like_entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="찜한 기록을 찾을 수 없습니다.")

        db.delete(like_entry)
        db.commit()

        return {"message": "성공적으로 찜을 취소했습니다."}

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        print(f"Error removing like: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"찜 취소에 실패했습니다: {e}")

@router.get("/users", response_model=List[LikedWeddingCompanyResponse], status_code=status.HTTP_200_OK)
async def get_user_likes(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    try:

        liked_companies = db.query(WeddingCompany).join(
            LikeModel, WeddingCompany.id == LikeModel.wedding_company_id
        ).filter(
            LikeModel.user_id == user_id
        ).order_by(
            LikeModel.created_at.desc()
        ).all()

        # 응답 모델에 맞게 데이터 가공 (relationships가 잘 정의되어 있다면 더 간결해질 수 있음)
        result = []
        for company in liked_companies:
            # `halls`와 `hall_photos`는 따로 로드하거나, WeddingCompanyModel에 relationship이 설정되어 있어야 합니다.
            # 예시에서는 WeddingCompanyModel에 halls relationship이 있다고 가정
            # 그리고 HallModel에 hall_photos relationship이 있다고 가정
            halls_data = []
            if hasattr(company, 'halls') and company.halls:
                for hall in company.halls:
                    photos_data = []
                    if hasattr(hall, 'hall_photos') and hall.hall_photos:
                        for photo in hall.hall_photos:
                            photos_data.append(WeddingHallPhoto(url=photo.url))
                    halls_data.append(HallInfoResponse(name=hall.name, hall_photos=photos_data))

            # 찜한 시각은 LikeModel에서 가져와야 하지만, 현재 쿼리에서는 WeddingCompanyModel만 가져오므로
            # LikeModel의 created_at을 가져오려면 쿼리를 수정해야 합니다.
            # 임시로 현재 시간 또는 기본값을 사용하거나, LikeModel과 함께 조인하여 가져와야 함.
            # 여기서는 LikeModel의 created_at을 직접 가져오기 위해 쿼리 변경
            like_entry = db.query(LikeModel).filter(
                LikeModel.user_id == user_id,
                LikeModel.wedding_company_id == company.id
            ).first()

            result.append(LikedWeddingCompanyResponse(
                id=company.id,
                name=company.name,
                address=company.address,
                halls=halls_data,
                liked_at=like_entry.created_at.isoformat() if like_entry else None # 찜한 시각 추가
            ))
        return result

    except Exception as e:
        print(f"Error fetching user likes: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"찜 목록을 불러오는데 실패했습니다: {e}")


# @router.get("/status/{wedding_company_id}", response_model=LikeStatusResponse, status_code=status.HTTP_200_OK)
# async def get_like_status(
#     wedding_company_id: int,
#     request: Request,
#     db: Session = Depends(get_db)
# ):
#     user_id = None
#     try:
#         user_id = await get_current_user_id(request)
#     except HTTPException:
#         pass # 로그인하지 않은 경우 user_id는 None으로 유지

#     if not user_id:
#         return LikeStatusResponse(is_liked=False)

#     try:
#         # 찜 레코드 존재 여부 확인
#         like_exists = db.query(LikeModel).filter(
#             LikeModel.user_id == user_id,
#             LikeModel.wedding_company_id == wedding_company_id
#         ).first() is not None

#         return LikeStatusResponse(is_liked=like_exists)
#     except Exception as e:
#         print(f"Error checking like status: {e}")
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"찜 상태 확인에 실패했습니다: {e}")
    
    
@router.post('/status/batch', response_model=LikeBatchResponse, status_code=status.HTTP_200_OK)
async def get_like_status_batch(
    request_body: LikeBatchRequest,
    request : Request,
    db: Session = Depends(get_db)
):
    user_id = None
    try:
        user_id = await get_current_user_id(request)
    except HTTPException:
        pass

    if not user_id:
        # 로그인하지 않은 경우 모든 ID에 대해 False 반환
        return LikeBatchResponse(like_statuses={_id: False for _id in request_body.hall_ids})

    # 사용자가 좋아요를 누른 모든 wedding_company_id 조회
    # SQLAlchemy의 .in_() 메서드를 사용하여 여러 ID를 한 번에 조회합니다.
    liked_company_ids = db.query(LikeModel.wedding_company_id).filter(
        LikeModel.user_id == user_id,
        LikeModel.wedding_company_id.in_(request_body.hall_ids)
    ).all()
    # 결과는 [(1,), (3,), ...] 와 같은 튜플 리스트로 반환되므로 단일 값 리스트로 변환
    liked_company_ids_set = {company_id for company_id, in liked_company_ids}

    # 요청받은 모든 wedding_company_id에 대한 찜 상태 맵 생성
    result = {
        _id: (_id in liked_company_ids_set)
        for _id in request_body.hall_ids
    }

    return LikeBatchResponse(like_statuses=result)

@router.get('/my_likes', response_model=List[WeddingCompanyOut], status_code=status.HTTP_200_OK)
async def get_my_liked_halls(
    request: Request,
    db: Session = Depends(get_db)
):
    user_id = None
    try:
        user_id = await get_current_user_id(request)
    except HTTPException as e:
        # 로그인하지 않은 경우 401 Unauthorized 반환
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다."
        )

    try:
        # 1. 현재 user_id가 찜한 모든 wedding_company_id를 Likes 테이블에서 조회
        liked_company_ids_query = db.query(LikeModel.wedding_company_id).filter(
            LikeModel.user_id == user_id
        ).all()
        liked_company_ids = [comp_id for comp_id, in liked_company_ids_query]

        if not liked_company_ids:
            return [] # 찜한 웨딩홀이 없으면 빈 리스트 반환

        # 2. 찜한 wedding_company_id 목록을 사용하여 WeddingCompany 상세 정보 조회
        # 이때, Hall 및 HallPhoto 정보도 함께 eager loading (join)하여 N+1 쿼리 방지
        wedding_companies = db.query(WeddingCompany).filter(
            WeddingCompany.id.in_(liked_company_ids)
        ).options(

            joinedload(WeddingCompany.halls).joinedload(Hall.hall_photos)
        ).all()

        # 좋아요를 누른 순서대로 정렬하려면 추가적인 로직이 필요할 수 있습니다.
        # 현재는 ID 순서 또는 DB 조회 순서로 반환됩니다.

        return wedding_companies

    except Exception as e:
        print(f"Error fetching liked halls for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="찜한 웨딩홀 목록을 불러오는 중 서버 오류가 발생했습니다."
        )