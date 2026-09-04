from typing import Generator

from settings import Settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = (
    f"postgresql://{Settings.DATABASE_USER}:"
    f"{Settings.DATABASE_PASSWORD}@"
    f"{Settings.DATABASE_HOST}:"
    f"{Settings.DATABASE_PORT}/"
    f"{Settings.DATABASE_NAME}"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        # Do not catch here: FastAPI throws the route's exception back in at the
        # yield, so wrapping it would turn every HTTPException into a bare 500
        # and drop its status code and detail.
        db.close()
