from typing import List, Union
from django.urls import path, URLPattern, URLResolver
from . import views

try:
    from rest_framework_simplejwt.views import TokenRefreshView  # type: ignore[import-untyped]
    _simplejwt_available = True
except ImportError:
    _simplejwt_available = False


urlpatterns: List[Union[URLPattern, URLResolver]] = [
    path("login/", views.login_view),
    path("users/", views.upsert_user_view),
    path("password-reset/", views.password_reset_view),
    path("logout/", views.logout_view),
]

if _simplejwt_available:
    urlpatterns += [
        path("token/refresh/", TokenRefreshView.as_view()),  # type: ignore[misc]
    ]