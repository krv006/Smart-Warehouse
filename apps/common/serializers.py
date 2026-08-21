from rest_framework.serializers import ModelSerializer, SerializerMethodField

from apps.common.approval import PendingChange
from apps.common.company import CompanyProfile
from apps.common.validators import (
    normalize_uz_phone,
    validate_bank_account,
    validate_jshshir,
    validate_mfo,
    validate_oked,
    validate_stir,
    validate_uz_phone,
)


class CompanyProfileSerializer(ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = (
            'id', 'name', 'stir', 'director_jshshr', 'director_fish',
            'mfo', 'bank_name', 'oked', 'bank_account',
            'address', 'phone', 'email', 'updated_at',
        )
        read_only_fields = ('id', 'updated_at')

    def validate_stir(self, value):
        validate_stir(value)
        return (value or '').strip()

    def validate_director_jshshr(self, value):
        validate_jshshir(value)
        digits = ''.join(ch for ch in (value or '') if ch.isdigit())
        return digits

    def validate_mfo(self, value):
        validate_mfo(value)
        return ''.join(ch for ch in (value or '') if ch.isdigit())

    def validate_oked(self, value):
        validate_oked(value)
        return ''.join(ch for ch in (value or '') if ch.isdigit())

    def validate_bank_account(self, value):
        validate_bank_account(value)
        return ''.join(ch for ch in (value or '') if ch.isdigit())

    def validate_phone(self, value):
        validate_uz_phone(value)
        return normalize_uz_phone(value)


class PendingChangeSerializer(ModelSerializer):
    requested_by_name = SerializerMethodField()
    reviewed_by_name   = SerializerMethodField()

    class Meta:
        model  = PendingChange
        fields = ('id', 'kind', 'summary', 'payload', 'status',
                  'requested_by', 'requested_by_name',
                  'reviewed_by', 'reviewed_by_name',
                  'review_note', 'reviewed_at', 'error', 'created_at')
        read_only_fields = fields

    def get_requested_by_name(self, obj):
        return str(obj.requested_by) if obj.requested_by else None

    def get_reviewed_by_name(self, obj):
        return str(obj.reviewed_by) if obj.reviewed_by else None
