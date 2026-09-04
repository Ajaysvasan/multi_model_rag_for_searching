# security_layer — API reference

[← Back to BACKEND.md](../BACKEND.md) · [Design notes](security_layer.md)

## Password hashing

```python
from security_layer.hashing import hash_password, verify_password

digest = hash_password("correct horse battery staple")
# '$argon2id$v=19$m=65536,t=3,p=4$...'

verify_password("correct horse battery staple", digest)   # True
verify_password("wrong", digest)                           # False
```

`hash_password` returns a self-describing Argon2 string — store it whole, no
separate salt column. `verify_password` raises on a malformed hash, so wrap it
when the input is untrusted.

## Issuing tokens

```python
from datetime import timedelta
from security_layer.auth import create_access_token, create_session_token
from settings import Settings

access = create_access_token(
    user_id=str(user.id),
    expires_delta=timedelta(minutes=int(Settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)),
)
refresh = create_session_token(
    user_id=str(user.id),
    expires_delta=timedelta(days=int(Settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)),
)
```

| Function | `type` claim | Default lifetime |
|---|---|---|
| `create_access_token(user_id, expires_delta=None)` | `"access"` | 15 minutes |
| `create_session_token(user_id, expires_delta=None)` | `"refresh"` | 1 day |

Both embed `sub`, `type` and `iat`.

## Verifying tokens

```python
from security_layer.auth import (
    verify_access_token, verify_refresh_token,
    TokenExpiredError, InvalidTokenError, TokenError,
)

try:
    user_id = verify_access_token(token)      # -> str (UUID)
except TokenExpiredError:
    ...   # 401, tell the client to refresh
except InvalidTokenError:
    ...   # 401, bad signature or malformed
except TokenError:
    ...   # 401, right signature but wrong token type
```

`verify_refresh_token` is identical but requires `type == "refresh"`. Passing an
access token to it raises `TokenError` — the two are not interchangeable.

## FastAPI integration

```python
from uuid import UUID
from fastapi import HTTPException
from security_layer.auth import verify_access_token

@app.post("/query")
def query_endpoint(payload: Query):
    try:
        user_id = UUID(verify_access_token(payload.access_token))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    ...
```

A header-based dependency is the better shape if you are extending this:

```python
from fastapi import Depends, Header

def current_user(authorization: str = Header(...)) -> UUID:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        raise HTTPException(401, "Expected a Bearer token")
    try:
        return UUID(verify_access_token(token))
    except TokenExpiredError:
        raise HTTPException(401, "Token expired")
    except (InvalidTokenError, TokenError):
        raise HTTPException(401, "Invalid token")
```

## Refresh flow

```python
@app.post("/auth/refresh/")
def refresh(req: RefreshRequest):
    try:
        user_id = verify_refresh_token(req.refresh_token)
    except Exception:
        raise HTTPException(401, "Invalid or expired refresh token")
    return {"access_token": create_access_token(user_id, timedelta(minutes=30))}
```

## Configuration

From `.env` via `settings.Settings`:

| Variable | Example | Notes |
|---|---|---|
| `JWT_SECRET_KEY` | 48+ random bytes | **Required.** `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | `HS256` | |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | |

Rotating `JWT_SECRET_KEY` invalidates every outstanding token.
