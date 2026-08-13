from django.test import SimpleTestCase

from apps.common.validators import (
    validate_bank_account,
    validate_jshshir,
    validate_mfo,
    validate_oked,
    validate_stir,
    validate_uz_phone,
)


class UzValidatorsTests(SimpleTestCase):
    def test_stir_requires_nine_digits(self):
        validate_stir('123456789')
        with self.assertRaisesMessage(Exception, '9 ta raqam'):
            validate_stir('12345')

    def test_mfo_requires_five_digits(self):
        validate_mfo('00401')
        with self.assertRaisesMessage(Exception, '5 ta raqam'):
            validate_mfo('123')

    def test_bank_account_requires_twenty_digits(self):
        validate_bank_account('1' * 20)
        with self.assertRaisesMessage(Exception, '20 ta raqam'):
            validate_bank_account('123')

    def test_oked_requires_five_digits(self):
        validate_oked('12345')
        with self.assertRaisesMessage(Exception, '5 ta raqam'):
            validate_oked('12')

    def test_phone_accepts_uz_mobile(self):
        validate_uz_phone('+998939498849')
        validate_uz_phone('939498849')

    def test_jshshir_format(self):
        validate_jshshir('301019900010017')
        validate_jshshir('26874128741871')
        with self.assertRaisesMessage(Exception, '14 ta raqam'):
            validate_jshshir('123')
        with self.assertRaisesMessage(Exception, 'birinchi raqami'):
            validate_jshshir('70101990001001')
