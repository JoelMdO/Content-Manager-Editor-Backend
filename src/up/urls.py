from django.urls import path

from up import views

urlpatterns = [
    path("", views.index, name="index"), #type: ignore
    path("databases", views.databases, name="databases"), #type: ignore
]
