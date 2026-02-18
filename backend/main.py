"""Main module which will be integrated with the frontend"""

import datetime
import os
import sys
from contextlib import asynccontextmanager

from data_models.session import get_db
from data_models.users import User
from security_layer.hashing import hash_password, verify_password
from settings import Settings

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import asyncio
import platform
from datetime import timedelta

from config import Config
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from security_layer.auth import (
    create_access_token,
    create_session_token,
    verify_access_token,
    verify_refresh_token,
)
from sqlalchemy.orm import Session

state = {
    "engine": None,
    "metadata_store": None,
    "conv_memory": None,
    "session_id": None,
    "query_preprocessor": None,
    "ready": False,
}


class Query(BaseModel):
    query: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    message: str
    status_code: int
    user_id: str


class RegisterResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str
    status_code: int
    user_id: str


async def backend_init():

    from system_services.tui.system_init import initialize_system

    if platform.system().lower() not in Config.OS:
        raise OSError(
            f"The operating system {platform.system()} is not supported. Supporated Os list : {Config.OS}"
        )
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, initialize_system)

    (
        state["engine"],
        state["metadata_store"],
        state["conv_memory"],
        state["session_id"],
        state["query_preprocessor"],
    ) = result
    state["ready"] = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    await backend_init()
    yield


app = FastAPI(title="AI assistant API", lifespan=lifespan)


@app.post("/auth/login/")
def login(login_req: LoginRequest, db: Session = Depends(get_db)):
    email: str = login_req.email
    password: str = login_req.password
    result = db.query(User).filter(User.email == email).first()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invalid credentials"
        )
    db_password = result.password_hash
    print(db_password, "\n", password)
    if not verify_password(password, db_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The entered password is wrong",
        )
    refresh_token = create_session_token(
        user_id=str(result.id),
        expires_delta=timedelta(days=int(Settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)),
    )
    access_token = create_access_token(
        user_id=str(result.id),
        expires_delta=timedelta(minutes=int(Settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)),
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="access",
        message="Login successful",
        status_code=200,
        user_id=str(result.id),
    )


@app.post("/auth/register/")
def register(register_req: RegisterRequest, db: Session = Depends(get_db)):
    email: str = register_req.email
    username = register_req.username
    password: str = register_req.password
    result = db.query(User).filter(User.email == email).first()
    if result is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The user already exists. Try logging in",
        )
    created_at = datetime.datetime.now()
    hashed_password = hash_password(password)
    new_user = User(
        email=email,
        username=username,
        password_hash=hashed_password,
        created_at=created_at,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    refresh_token = create_session_token(
        user_id=str(new_user.id),
        expires_delta=timedelta(days=int(Settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)),
    )
    access_token = create_access_token(
        user_id=str(new_user.id),
        expires_delta=timedelta(minutes=int(Settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)),
    )
    return RegisterResponse(
        message="Registeration successful",
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="access",
        status_code=200,
        user_id=str(new_user.id),
    )


@app.post("query")
def query_endpoint(query: Query):
    if not state["ready"]:
        return {"error": "System is not ready yet. Please wait"}
    intent_query = state["query_preprocessor"].preprocess_query(query.query)
    response = state["engine"].retrieve_and_generate(query, intent_query)
    state["conv_memory"].add_turn(state["session_id"], "assistant", response.answer)
    sources = []
    if response.citations:
        for citation in response.citations:
            source = citation["source_path"]
            sources.append(source)
    print(sources)

    return {
        "response": response.answer,
        "sources": sources,
    }


if __name__ == "__main__":
    # testing if the function is working or not
    pass
