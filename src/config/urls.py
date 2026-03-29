"""
URL configuration for CMS DB project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

import django
from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def home_view(request):  # type: ignore[no-untyped-def]
    """Minimal home endpoint — confirms the API is running."""
    return JsonResponse({"status": "ok", "django": django.__version__})


urlpatterns = [
    path("", home_view),
    path("up/", include("up.urls")),
    path("articles/", include("articles.urls")),
    path("admin/", admin.site.urls),
    path("auth/", include("users.urls")),
]
if settings.DEBUG and not settings.TESTING:
    urlpatterns = [
        *urlpatterns,
        path("__debug__/", include("debug_toolbar.urls")),
    ]
