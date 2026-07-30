"""Băm mật khẩu bằng PBKDF2-SHA256 từ thư viện chuẩn.

Cố tình không dùng passlib/bcrypt: chỉ cần `hashlib` + `secrets` là đủ cho demo
và tránh thêm dependency phải build native wheel trong container slim.

Định dạng chuỗi lưu trong DB:  pbkdf2_sha256$<số vòng>$<muối hex>$<băm hex>
"""

import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 260_000
SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"{ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    try:
        algorithm, iterations_raw, salt_hex, digest_hex = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)
