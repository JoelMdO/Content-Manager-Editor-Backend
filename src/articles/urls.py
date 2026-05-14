from typing import List, Union

from django.urls import URLPattern, URLResolver, path

from .views import ArticleDraftViewSet, ArticleImageUploadView

urlpatterns: List[Union[URLPattern, URLResolver]] = [
    # Image uploads (keep first to avoid path collision with the title-based route)
    path("images/", ArticleImageUploadView.as_view(), name="article-image-upload"),
    # Also accept title without trailing slash to support clients that omit it
    path("<path:title>", ArticleDraftViewSet.as_view()),
    # Root list/create endpoint
    path("", ArticleDraftViewSet.as_view()),
]