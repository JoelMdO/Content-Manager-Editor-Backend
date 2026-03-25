from typing import List, Union
from django.urls import path, URLPattern, URLResolver
from .views import ArticleDraftViewSet, RagCorpusView, ArticleImageUploadView


urlpatterns: List[Union[URLPattern, URLResolver]] = [
    path("", ArticleDraftViewSet.as_view()),
    # ADDED 2026-03-16 — internal RAG corpus endpoint for FastAPI ingestion service
    path("rag-corpus/", RagCorpusView.as_view(), name="rag-corpus"),
    # Image uploads
    path("images/", ArticleImageUploadView.as_view(), name="article-image-upload"),
]