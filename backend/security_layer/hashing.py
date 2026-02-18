from passlib.context import CryptContext

password_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str):
    return password_context.hash(password)


def verify_password(password: str, hashed_password):
    return password_context.verify(password, hashed_password)
