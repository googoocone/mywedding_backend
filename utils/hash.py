from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated = "auto")

# 해시 생성
def hash_password(password: str):

    return pwd_context.hash(password)

# 해시 비교
def verify_password(plain_password: str, hashed_password: str):
    
    return pwd_context.verify(plain_password, hashed_password)