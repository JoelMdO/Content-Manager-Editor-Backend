from typing import List, Union

from django.urls import URLPattern, URLResolver, path

from .views import ArticleDraftViewSet, ArticleImageUploadView, RagCorpusView

urlpatterns: List[Union[URLPattern, URLResolver]] = [
    path("", ArticleDraftViewSet.as_view()),
    # ADDED 2026-03-16 — internal RAG corpus endpoint for FastAPI ingestion service
    path("rag-corpus/", RagCorpusView.as_view(), name="rag-corpus"),
    # Image uploads
    path("images/", ArticleImageUploadView.as_view(), name="article-image-upload"),
]