import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
from datetime import datetime, timedelta, timezone

import jwt
from jwt import ExpiredSignatureError, PyJWTError
from settings import Settings

JWT_SECRET_KEY = Settings.JWT_SECRET_KEY
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = Settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
JWT_REFRESH_TOKEN_EXPIRE_DAYS = Settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
JWT_ALGORITHM = Settings.JWT_ALGORITHM


class InvalidTokenError(Exception):
    pass


class TokenError(Exception):
    pass


class TokenExpiredError(Exception):
    pass


def create_access_token(user_id: str, expires_delta: timedelta | None = None):
    to_encode = {"sub": user_id, "type": "access", "iat": datetime.now(timezone.utc)}
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str):
    try:
        decoded_token = jwt.decode(token, JWT_SECRET_KEY, algorithms=JWT_ALGORITHM)
    except ExpiredSignatureError:
        raise TokenExpiredError("The token has expired")
    except PyJWTError:
        raise InvalidTokenError("Invalid token")
    user_id = decoded_token["sub"]
    token_type = decoded_token["type"]
    if not user_id:
        raise InvalidTokenError("Missing sub")
    if not token_type or token_type != "access":
        raise TokenError("Invalid token")
    return user_id


def verify_refresh_token(token: str):
    try:
        decoded_token = jwt.decode(token, JWT_SECRET_KEY, algorithms=JWT_ALGORITHM)
    except ExpiredSignatureError:
        raise TokenExpiredError("The token has expired")
    except PyJWTError:
        raise InvalidTokenError("Invalid token")
    user_id = decoded_token["sub"]
    token_type = decoded_token["type"]
    if not user_id:
        raise InvalidTokenError("Missing sub")
    if not token_type or token_type != "refresh":
        raise TokenError("Invalid token")
    return user_id


def create_session_token(user_id: str, expires_delta: timedelta | None = None):
    to_encode = {"sub": user_id, "type": "refresh", "iat": datetime.now(timezone.utc)}
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=1)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt
