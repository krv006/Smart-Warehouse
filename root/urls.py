from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (SpectacularAPIView,
                                   SpectacularSwaggerView,
                                   SpectacularRedocView)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth
    path('api/v1/auth/',      include('apps.users.urls')),

    # Core modules
    path('api/v1/warehouse/', include('apps.warehouse.urls')),
    path('api/v1/sales/',     include('apps.sales.urls')),
    path('api/v1/expenses/',  include('apps.expenses.urls')),
    path('api/v1/cash/',      include('apps.cash.urls')),
    path('api/v1/clients/',   include('apps.clients.urls')),
    path('api/v1/reports/',   include('apps.reports.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/orders/',        include('apps.orders.urls')),

    # OpenAPI / Swagger
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('',            SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/',  SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
