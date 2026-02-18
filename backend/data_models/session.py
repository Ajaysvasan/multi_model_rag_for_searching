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
    except Exception as e:
        raise Exception(f"Database session error: {e}")
    finally:
        db.close()
