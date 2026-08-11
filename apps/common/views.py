from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.company import CompanyProfile
from apps.common.permissions import IsManagement
from apps.common.serializers import CompanyProfileSerializer


class CompanyProfileView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == 'PATCH':
            return [IsManagement()]
        return super().get_permissions()

    def get(self, request):
        profile = CompanyProfile.get_profile()
        return Response(CompanyProfileSerializer(profile).data)

    def patch(self, request):
        profile = CompanyProfile.get_profile()
        serializer = CompanyProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
