import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_NAME = os.getenv("DB_NAME")
    DATABASE_USER = os.getenv("DB_USER")
    DATABASE_PASSWORD = os.getenv("DB_PASSWORD")
    DATABASE_HOST = os.getenv("DB_HOST")
    DATABASE_PORT = os.getenv("DB_PORT")

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
