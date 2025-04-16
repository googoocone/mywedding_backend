import os
from datetime import timedelta

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1  # 1시간
REFRESH_TOKEN_EXPIRE_DAYS = 7     # 7일