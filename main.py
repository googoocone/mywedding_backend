# main.py
from fastapi import FastAPI, Request, APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api import auth, users

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://a805-2406-5900-1000-ca1b-1446-4926-7ff5-5166.ngrok-free.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(users.router)
