from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.auth.hash import verify_password
from backend.db.engine import get_db
from backend.config import config
from backend.db import crud
from backend.db.models import PrincipalSecurity, ApiToken
from backend.security_core import verify_totp, dec
import hashlib, json, time


ALGORITHM = "HS256"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(tags=["Login"])


def authenticate_user(db: Session, username: str, password: str):
    main_admin_username = config.ADMIN_USERNAME
    main_admin_password = config.ADMIN_PASSWORD
    if username == main_admin_username and password == main_admin_password:
        return {"username": username, "type": "main_admin"}

    admin = crud.it_is_admin(db, username=username)
    if admin:
        if not admin.is_active:
            return None
        if verify_password(password, admin.password):
            return {"username": admin.username, "type": "admin"}

    return None


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=ALGORITHM)


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    admin = authenticate_user(db, form_data.username, form_data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The username or password is incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    principal = db.query(PrincipalSecurity).filter_by(username=admin["username"], principal_type=admin["type"]).first()
    if principal and principal.totp_enabled:
        otp = (form_data.client_secret or "").strip()
        secret = dec(principal.totp_secret_encrypted)
        if not secret or not verify_totp(secret, otp):
            raise HTTPException(status_code=401, detail="TOTP code required or invalid")

    access_token_expires = timedelta(seconds=config.JWT_ACCESS_TOKEN_EXPIRES)
    access_token = create_access_token(
        data={"sub": admin["username"], "type": admin["type"]},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[ALGORITHM])

        username: str = payload.get("sub")
        user_type: str = payload.get("type")
        if username is None:
            raise credentials_exception
    except JWTError:
        digest = hashlib.sha256(token.encode()).hexdigest()
        api_token = db.query(ApiToken).filter(ApiToken.token_hash == digest, ApiToken.revoked_at.is_(None)).first()
        now = int(time.time())
        if not api_token or (api_token.expires_at and api_token.expires_at <= now):
            raise credentials_exception
        api_token.last_used_at = now
        db.commit()
        return {"username": api_token.created_by, "type": "main_admin", "auth_kind": "api_token", "scopes": json.loads(api_token.scopes)}
    if user_type == "admin":
        admin = crud.get_admin_by_username(db, username)
        if not admin or not admin.is_active:
            raise credentials_exception
    elif user_type != "main_admin":
        raise credentials_exception
    return {"username": username, "type": user_type}
