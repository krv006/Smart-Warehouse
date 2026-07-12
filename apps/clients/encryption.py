"""
Fernet symmetric encryption helpers.

Usage:
    from apps.clients.encryption import encrypt, decrypt

    encrypted = encrypt("1234567890")
    plain     = decrypt(encrypted)

Set FERNET_KEY in environment (generate once with Fernet.generate_key()):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

_key = os.environ.get('FERNET_KEY', '').encode()

if _key:
    _fernet = Fernet(_key)
else:
    # Kalitsiz mijoz PII ochiq matnda saqlanadi — production'da TAQIQLANADI
    if not settings.DEBUG:
        raise RuntimeError(
            "FERNET_KEY environment o'zgaruvchisi kiritilishi shart "
            "(DEBUG=False). Aks holda mijoz ma'lumotlari (F.I.Sh, INN, "
            "telefon) shifrlashsiz saqlanadi. Kalit yaratish:\n"
            '  python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    _fernet = None
    logger.warning(
        "FERNET_KEY o'rnatilmagan — mijoz ma'lumotlari OCHIQ MATNDA "
        "saqlanadi (faqat DEBUG rejimida ruxsat etiladi)."
    )


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
        # Shifrlash yoqilmasidan avval yozilgan (ochiq matn) qiymat bo'lishi
        # mumkin; lekin kalit almashgan bo'lsa ham shu yerga tushadi — shuning
        # uchun ogohlantirish yoziladi.
        logger.warning(
            "Fernet decrypt xatosi (InvalidToken) — qiymat ochiq matn "
            "deb qabul qilindi. Kalit almashmaganini tekshiring."
        )
        return value
