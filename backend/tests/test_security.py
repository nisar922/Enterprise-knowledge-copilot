from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.authentication.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.utilis.config import settings


def test_password_hash_and_verify():
    hashed = hash_password("S3cret-pass")
    assert hashed != "S3cret-pass"
    assert verify_password("S3cret-pass", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_access_token_roundtrip():
    payload = decode_access_token(create_access_token(user_id=42, role="admin"))
    assert payload["sub"] == "42"
    assert payload["role"] == "admin"


def test_expired_token_is_rejected():
    expired = jwt.encode(
        {"sub": "1", "role": "employee", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)


def test_token_signed_with_other_key_is_rejected():
    forged = jwt.encode(
        {"sub": "1", "role": "admin", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        "a-completely-different-secret-key-123456",
        algorithm=settings.algorithm,
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(forged)