# main.py
from fastapi import FastAPI, Request, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from api import auth, users, admin,hall

app = FastAPI()

from core.database import engine, Base
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "https://myweddingdiary-admin.co.kr",
        "https://www.myweddingdiary-admin.co.kr",
        "https://myweddingdiary.co.kr",
        "https://www.myweddingdiary.co.kr",
        "https://myweddingdiary-server.co.kr",
        "https://www.myweddingdiary-server.co.kr",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("❌ Validation error:", exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

app.include_router(hall.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)