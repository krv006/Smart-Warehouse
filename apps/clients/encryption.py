"""
Fernet symmetric encryption helpers.

Usage:
    from apps.clients.encryption import encrypt, decrypt

    encrypted = encrypt("1234567890")
    plain     = decrypt(encrypted)

Set FERNET_KEY in environment (generate once with Fernet.generate_key()):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import os

from cryptography.fernet import Fernet, InvalidToken

_key    = os.environ.get('FERNET_KEY', '').encode()
_fernet = Fernet(_key) if _key else None


def encrypt(value: str | None) -> str | None:
    if value is None or _fernet is None:
        return value
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if value is None or _fernet is None:
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        return value
