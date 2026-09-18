import base64, hashlib
from cryptography.fernet import Fernet, InvalidToken
from backend.config import config
def _f(): return Fernet(base64.urlsafe_b64encode(hashlib.sha256(config.JWT_SECRET_KEY.encode()).digest()))
def encrypt_secret(v): return _f().encrypt(v.encode()).decode()
def decrypt_secret(v):
    if not v: return None
    try: return _f().decrypt(v.encode()).decode()
    except InvalidToken: return None
