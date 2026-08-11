from rest_framework.serializers import ModelSerializer, SerializerMethodField

from apps.common.company import CompanyProfile


class CompanyProfileSerializer(ModelSerializer):
    class Meta:
        model = CompanyProfile
        fields = (
            'id', 'name', 'stir', 'director_jshshr', 'director_fish',
            'mfo', 'bank_name', 'oked', 'bank_account',
            'address', 'phone', 'email', 'updated_at',
        )
        read_only_fields = ('id', 'updated_at')
