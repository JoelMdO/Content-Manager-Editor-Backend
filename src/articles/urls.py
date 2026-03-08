from typing import List, Union
from django.urls import path, URLPattern, URLResolver
from .views import ArticleDraftViewSet


urlpatterns: List[Union[URLPattern, URLResolver]] = [
path("", ArticleDraftViewSet.as_view()),
]