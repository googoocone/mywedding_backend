import firebase_admin
from firebase_admin import credentials, auth
from datetime import datetime, timedelta
from jose import jwt
import os

# 최초 1회 초기화 (app 시작 시)
cred = credentials.Certificate({
    "type": os.environ["FIREBASE_TYPE"],
    "project_id": os.environ["FIREBASE_PROJECT_ID"],
    "private_key_id": os.environ["FIREBASE_PRIVATE_KEY_ID"],
    "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
    "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
    "client_id": os.environ["FIREBASE_CLIENT_ID"],
    "auth_uri": os.environ["FIREBASE_AUTH_URI"],
    "token_uri": os.environ["FIREBASE_TOKEN_URI"],
    "auth_provider_x509_cert_url": os.environ["FIREBASE_AUTH_PROVIDER_X509_CERT_URL"],
    "client_x509_cert_url": os.environ["FIREBASE_CLIENT_X509_CERT_URL"],
    "universe_domain": os.environ["FIREBASE_UNIVERSE_DOMAIN"],
})
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

def verify_firebase_token(id_token: str) -> dict:
    try:
        
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token  # { uid, email, ... }
    except Exception as e:
        raise ValueError("Invalid Firebase ID token") from e

