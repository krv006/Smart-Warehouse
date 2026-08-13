"""O'zbekiston hujjatlari uchun format validatsiyasi."""
import re

from django.core.exceptions import ValidationError

_DIGITS = re.compile(r'\D')


def _digits(value: str) -> str:
    return _DIGITS.sub('', value or '')


def validate_stir(value: str, *, required: bool = False) -> None:
    raw = (value or '').strip()
    if not raw:
        if required:
            raise ValidationError('STIR kiritilishi shart.')
        return
    digits = _digits(raw)
    if len(digits) != 9:
        raise ValidationError('STIR 9 ta raqamdan iborat bo‘lishi kerak.')


def validate_jshshir(value: str, *, required: bool = False) -> None:
    raw = (value or '').strip()
    if not raw:
        if required:
            raise ValidationError('JSHSHIR kiritilishi shart.')
        return
    digits = _digits(raw)
    if len(digits) != 14:
        raise ValidationError('JSHSHIR 14 ta raqamdan iborat bo‘lishi kerak.')
    if digits[0] not in '123456':
        raise ValidationError('JSHSHIR birinchi raqami noto‘g‘ri.')
    weights = (7, 3, 1)
    total = sum(int(digits[i]) * weights[i % 3] for i in range(13))
    if total % 10 != int(digits[13]):
        raise ValidationError('JSHSHIR kontrol raqami noto‘g‘ri.')


def validate_mfo(value: str, *, required: bool = False) -> None:
    raw = (value or '').strip()
    if not raw:
        if required:
            raise ValidationError('MFO kiritilishi shart.')
        return
    digits = _digits(raw)
    if len(digits) != 5:
        raise ValidationError('MFO 5 ta raqamdan iborat bo‘lishi kerak.')


def validate_bank_account(value: str, *, required: bool = False) -> None:
    raw = (value or '').strip()
    if not raw:
        if required:
            raise ValidationError('Hisob raqami kiritilishi shart.')
        return
    digits = _digits(raw)
    if len(digits) != 20:
        raise ValidationError('Hisob raqami 20 ta raqamdan iborat bo‘lishi kerak.')


def validate_oked(value: str, *, required: bool = False) -> None:
    raw = (value or '').strip()
    if not raw:
        if required:
            raise ValidationError('OKED kiritilishi shart.')
        return
    digits = _digits(raw)
    if len(digits) != 5:
        raise ValidationError('OKED 5 ta raqamdan iborat bo‘lishi kerak.')


def validate_uz_phone(value: str, *, required: bool = False) -> None:
    raw = (value or '').strip()
    if not raw:
        if required:
            raise ValidationError('Telefon kiritilishi shart.')
        return
    digits = _digits(raw)
    if digits.startswith('998') and len(digits) == 12:
        local = digits[3:]
    elif len(digits) == 9 and digits[0] == '9':
        local = digits
    else:
        raise ValidationError('Telefon formati: +998 XX XXX XX XX.')
    if local[0] != '9':
        raise ValidationError('Telefon mobil raqam +998 9X ... bilan boshlanishi kerak.')


def normalize_uz_phone(value: str) -> str:
    raw = (value or '').strip()
    if not raw:
        return ''
    digits = _digits(raw)
    if digits.startswith('998') and len(digits) == 12:
        local = digits[3:]
    elif len(digits) == 9 and digits[0] == '9':
        local = digits
    else:
        return raw
    return f'+998{local}'
