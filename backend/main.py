"""Main module which will be integrated with the frontend"""

import datetime
import os
import sys
from contextlib import asynccontextmanager
from uuid import UUID

from data_models.session import get_db
from data_models.users import User
from security_layer.hashing import hash_password, verify_password
from settings import Settings

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import argparse
import asyncio
import platform
from datetime import timedelta
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from AdpaterModule.CacheAdapter import _UserCacheAdapter
from AdpaterModule.ConvMemoryAdapter import _UserConvMemoryAdapter
from AdpaterModule.HistoryAdapter import _UserHistoryAdapter
from AdpaterModule.MetaDataAdapter import _UserMetadataAdapter
from config import Config
from security_layer.auth import (
    create_access_token,
    create_session_token,
    verify_access_token,
    verify_refresh_token,
)
from system_services.server.ingestion_orchestrator import ingestion_pipeline
from system_services.server.pg_chunk_store import PgChunkStore

parser = argparse.ArgumentParser(description="Mode")
subparser = parser.add_subparsers(dest="command", help="avaliable commands")
subparser.add_parser(
    "fsearch", help="To make the RAG To work as a multimodal file searching model"
)
subparser.add_parser("bot", help="To make the RAG to work as a medical chat bot")

args = parser.parse_args()

state = {
    "shared": None,
    "ready": False,
}


class Query(BaseModel):
    query: str
    access_token: str


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


class DocsUploading(BaseModel):
    filePaths: List[str]
    type: str = "document"
    access_token: str


async def backend_init():
    from system_services.server.system_init import load_shared_components

    if platform.system().lower() not in Config.OS:
        raise OSError(
            f"The operating system {platform.system()} is not supported. Supported OS list: {Config.OS}"
        )
    loop = asyncio.get_event_loop()
    state["shared"] = await loop.run_in_executor(None, load_shared_components)
    state["ready"] = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    await backend_init()
    yield


app = FastAPI(title="AI assistant API", lifespan=lifespan)


@app.post("/upload")
def ingest(upload_req: DocsUploading):
    if not state["ready"]:
        raise HTTPException(
            status_code=503, detail="System is not ready yet. Please wait."
        )

    try:
        user_id_str = verify_access_token(upload_req.access_token)
    except Exception as e:
        print(f"Auth failed in /upload: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    user_id = UUID(user_id_str)

    # Process each path
    results = []
    for path_str in upload_req.filePaths:
        res = ingestion_pipeline(user_id, path_str, state["shared"])
        results.append(res)
        print(f"Ingestion result for {path_str}: {res}")

    return {"message": "Ingestion completed", "results": results}


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


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str
    message: str
    status_code: int


@app.post("/auth/refresh/")
def refresh_token(refresh_req: RefreshRequest, db: Session = Depends(get_db)):
    try:
        user_id_str = verify_refresh_token(refresh_req.refresh_token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    new_access_token = create_access_token(
        user_id=user_id_str,
        expires_delta=timedelta(minutes=int(Settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)),
    )

    return RefreshResponse(
        access_token=new_access_token,
        token_type="access",
        message="Token refreshed successfully",
        status_code=200,
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


@app.post("/query")
def query_endpoint(query: Query):
    if not state["ready"]:
        raise HTTPException(
            status_code=503, detail="System is not ready yet. Please wait."
        )

    try:
        user_id_str = verify_access_token(query.access_token)
    except Exception as e:
        print(f"Auth failed in /query: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    user_id = UUID(user_id_str)
    shared = state["shared"]

    embed_model = shared["embed_model"]
    generator = shared["generator"]
    faiss_manager = shared["faiss_manager"]
    pg_cache = shared["pg_cache"]
    pg_history = shared["pg_history"]
    pg_conv_memory = shared["pg_conv_memory"]

    user_index = faiss_manager.get_index(user_id)
    pg_chunk_store = PgChunkStore()

    from retrieval_layer.retrieval_engine import QueryProcessing, RetrievalEngine

    cache_adapter = _UserCacheAdapter(pg_cache, user_id)
    history_adapter = _UserHistoryAdapter(pg_history, user_id)
    metadata_adapter = _UserMetadataAdapter(pg_chunk_store, user_id)
    conv_memory_adapter = _UserConvMemoryAdapter(pg_conv_memory, user_id)

    query_preprocessor = QueryProcessing(
        conversation_memory=conv_memory_adapter,
        embedding_model=embed_model,
    )

    engine = RetrievalEngine(
        cache=cache_adapter,
        index=user_index,
        embedding_model=embed_model,
        history=history_adapter,
        ann_top_k=Config.ANN_TOP_K,
        history_enabled=True,
        metadata_store=metadata_adapter,
        generator=generator,
        conversation_memory=conv_memory_adapter,
    )

    session_id = str(user_id)

    conv_memory_adapter.add_turn(session_id, "user", query.query)
    intent_query = query_preprocessor.preprocess_query(
        query.query, session_id=session_id
    )
    response = engine.retrieve_and_generate(
        query.query, intent_query, session_id=session_id
    )
    conv_memory_adapter.add_turn(session_id, "assistant", response.answer)

    sources = set()
    if response.citations:
        source_paths = pg_chunk_store.get_source_paths(
            [c["chunk_id"] for c in response.citations if "chunk_id" in c], user_id
        )
        for citation in response.citations:
            chunk_id = citation.get("chunk_id", "")
            path = source_paths.get(chunk_id, citation.get("source_path", ""))
            sources.add(path)

    return {
        "response": response.answer,
        "sources": list(sources),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["system_init.py", "models/*"],
    )
