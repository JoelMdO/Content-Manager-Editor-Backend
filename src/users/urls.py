from typing import List, Union
from django.urls import path, URLPattern, URLResolver
from . import views


urlpatterns: List[Union[URLPattern, URLResolver]] = [
    path("login/", views.login_view),
    path("users/", views.upsert_user_view),
    path("password-reset/", views.password_reset_view),
    path("logout/", views.logout_view),
]