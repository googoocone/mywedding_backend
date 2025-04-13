# from fastapi import Request, HTTPException
# from starlette.middleware.base import BaseHTTPMiddleware
# from utils.security import verify_jwt_token

# class AuthMiddleware(BaseHTTPMiddleware):
#     async def dispatch(self, request: Request, call_next):
#         """JWT 인증 미들웨어"""
#         is_development = False
        
#         # 인증 없이 접근해도 되는 경로
#         whitelist = [
#             "/api/v1/auth/login",
#             "/api/v1/auth/logout",
#             "/auth/firebase-login",
#             "/docs",
#             "/openapi.json",
#             "/favicon.ico",

#         ]
#         if is_development:
#             whitelist.extend(["/api/v1/"])

#         # 화이트리스트 경로는 통과
#         if any(request.url.path.startswith(path) for path in whitelist):
#             return await call_next(request)
        
#         # 토큰 확인
#         auth_header = request.headers.get("Authorization")
#         if not auth_header or not auth_header.startswith("Bearer "):
#             raise HTTPException(status_code=401, detail="Unauthorized: Missing token")

#         token = auth_header.split("Bearer ")[1]
#         user_payload = verify_jwt_token(token)
#         print(user_payload)

#         if not user_payload:
#             raise HTTPException(status_code=401, detail="Unauthorized: Invalid token")

#         # 요청에 user 정보 저장
#         request.state.user = {"uid": user_payload["sub"], "role": user_payload["role"]}
#         response = await call_next(request)
#         return response
