from passlib.context import CryptContext

BCRYPT_MAX_PASSWORD_BYTES = 72

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=True,
)


# True if the password is longer than bcrypt's 72-byte limit.
def _password_exceeds_bcrypt_limit(plain: str) -> bool:
    return len(plain.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES


# Reject passwords that bcrypt can't safely hash.
def validate_password_length(plain: str) -> str:
    if _password_exceeds_bcrypt_limit(plain):
        raise ValueError(
            f"Password must be at most {BCRYPT_MAX_PASSWORD_BYTES} UTF-8 bytes"
        )
    return plain


# Hash a plaintext password for storage.
def hash_password(plain: str) -> str:
    validate_password_length(plain)
    return _pwd_context.hash(plain)


# Check a plaintext password against its stored hash.
def verify_password(plain: str, hashed: str) -> bool:
    if _password_exceeds_bcrypt_limit(plain):
        return False
    return _pwd_context.verify(plain, hashed)
