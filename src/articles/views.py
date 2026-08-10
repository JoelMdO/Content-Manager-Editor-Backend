import contextlib
import hmac
import logging
import os
import re
from typing import Optional

from django.conf import settings
from django.db import DatabaseError, connections, transaction

# ADDED 2026-03-16 — RAG corpus endpoint imports
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import (
    ArticleImageCreateSerializer,
    ArticleImageUploadSerializer,
    ArticleManagerSerializer,
)
from .models import ArticleImageModel, ArticleModel

logger = logging.getLogger(__name__)


class ArticleDraftViewSet(APIView):
    """
    CRUD for article drafts.

    NOTE: this view is mounted under the project's URLconf at `/articles/`.

    GET    /articles/                 — list all drafts
    POST   /articles/                 — create draft (send full blocks array)
    GET    /articles/{id}/            — retrieve single draft
    PUT    /articles/{id}/            — full update (replace blocks)
    PATCH  /articles/{id}/            — partial update
    DELETE /articles/{id}/            — delete draft

    POST   /articles/{id}/publish/    — publish the draft
    POST   /articles/{id}/unpublish/  — revert to draft
    GET    /articles/by_article_id/?article_id=xxx  — find by article slug/id
    """

    def post(self, request: Request):
        try:
            serializer = ArticleManagerSerializer(data=request.data, context={"request": request}) # type: ignore
            if not serializer.is_valid(): # type: ignore
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  # type: ignore

            article_id = request.data.get("article_id")
            title = request.data.get("title")
            article_status = request.data.get("status") or "draft"
            existing_article = None
            print(f"ArticleDraftViewSet.post request.data={request.data}, article_id={article_id}, title={title}")

            try:
                ## Check if the article already exists by article_id or title, and if so, update it instead of creating a new one.    
                if article_id:
                    existing_article = ArticleModel.objects.filter(article_id=article_id).first()
                if existing_article is None and title:
                    existing_article = ArticleModel.objects.filter(title=title).first()

                if existing_article:
                    print(
                        f"Existing article found, updating article_id={existing_article.article_id}"
                    )
                    with transaction.atomic():
                        existing_article = serializer.update(
                            existing_article, serializer.validated_data
                        )  # type: ignore
                    return Response({"message": "Article Updated"}, status=status.HTTP_200_OK) # type: ignore

                print(f"Created new article with article_id={article_id}")
                existing_article = serializer.save()  # type: ignore
                return Response({"message": "Article Created"}, status=status.HTTP_201_CREATED) # type: ignore
            except DatabaseError as db_err:
                print(f"Database error saving article draft: {str(db_err)}")
                return Response({"error": "Database 1 error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # type: ignore

            # After the local transaction commits to avoid blocking the
            # primary write. Will write if the article is as published to Neon DB.
            if article_status == "published":  # type: ignore
                try:
                    # Schedule replication to run after the local DB transaction
                    # commits. Use the saved `existing_article`'s method (not the
                    # serializer) so the model-level replication runs as expected.
                    transaction.on_commit(existing_article.replicate_to_neon)  # type: ignore
                except Exception:
                    # If on_commit isn't available or fails, attempt immediate replicate
                    logger.exception("on_commit failed for replicate_to_neon, attempting immediate replicate for article id=%s", getattr(existing_article, "id", None))  # type: ignore
                    with contextlib.suppress(Exception):
                        existing_article.replicate_to_neon()  # type: ignore

            out = ArticleManagerSerializer(existing_article or serializer.instance, context={"request": request}).data  # type: ignore
            return Response(out, status=status.HTTP_200_OK) # type: ignore
        except Exception as e: 
            logger.exception("Error saving article draft: %s", str(e))
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # type: ignore

    # ==================================
    # GET method can handle both list and detail retrieval based on the presence of `title`
    # ==================================
    def get(self, request: Request, title: Optional[str] = None):
        # This method can handle both list and detail retrieval based on the
        # presence of a `title` path parameter OR a `title` query parameter.
        # Support callers that prefer `/articles/?title=...` (e.g., Postman)
        req_title = title or request.GET.get("title")
        logger.debug("ArticleDraftViewSet.get called: method=%s path_title=%s query_params=%s req_title=%s", request.method, title, dict(request.GET), req_title)
        if req_title is not None:
            # Detail retrieval
            try:
                instance = ArticleManagerSerializer.get_article_by_title(req_title)  # type: ignore
                if instance is None:
                    return Response({"error": "Article not found"}, status=status.HTTP_404_NOT_FOUND) # type: ignore
                serializer = ArticleManagerSerializer(instance, context={"request": request})  # type: ignore
                return Response(serializer.data, status=status.HTTP_200_OK) # type: ignore
            except Exception as e:
                logger.exception("Error retrieving article with title=%s: %s", title, str(e))
                return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # type: ignore
        else:
            # List retrieval (brief list for editor: id + title)
            try:
                if getattr(settings, "NEON_URL", "") and "neon" in connections.databases:
                    connections["neon"].ensure_connection()
                data = ArticleManagerSerializer.get_all_drafts(brief=True)  # type: ignore
                return Response(data, status=status.HTTP_200_OK)  # type: ignore
            except Exception as e:
                logger.exception("Error retrieving article drafts list: %s", str(e))
                return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  # type: ignore

class RagCorpusView(APIView): # type: ignore
    """Return published article text for the internal RAG ingestion service."""

    def check_token(self, request: Request) -> bool:  # type: ignore
        expected = getattr(settings, "RAG_INTERNAL_TOKEN", "") or ""
        received = request.META.get("HTTP_X_RAG_TOKEN", "") # type: ignore
        return bool(expected) and hmac.compare_digest(received, expected)

    def extract_plain_text(self, body: object) -> str:  # type: ignore
        if isinstance(body, str):
            return re.sub(r"<[^>]+>", " ", body).strip()
        if not isinstance(body, list):
            return ""

        parts = []
        for block in body: # type: ignore
            if not isinstance(block, dict):
                continue
            content = block.get("content") or block.get("text") or "" # type: ignore
            if isinstance(content, str) and content.strip():
                parts.append(re.sub(r"<[^>]+>", " ", content).strip())
        return " ".join(parts)

    def get(self, request: Request):  # type: ignore
        if not self.check_token(request):
            return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

        lang = request.GET.get("lang", "en").lower()[:2] # type: ignore
        articles = ArticleModel.objects.filter(status="published").values(
            "id", "title", "body"
        )
        results = []
        for article in articles:
            plain_text = self.extract_plain_text(article["body"])
            if plain_text:
                results.append({
                    "id": str(article["id"]),
                    "title": article["title"] or "",
                    "plain_text": plain_text,
                    "language": lang,
                })
        return Response(results, status=status.HTTP_200_OK)

    # Backwards-compatible alias used by older tests
    def _extract_plain_text(self, body: object) -> str:  # type: ignore
        return self.extract_plain_text(body)


class ArticleImageUploadView(APIView): # type: ignore
    """POST /articles/images/

    Accepts multipart/form-data with `file` or JSON with `base64`.
    Requires header `x-internal-proxy-key` to match env `PROXY_KEY`.
    """

    def post(self, request: Request):  # type: ignore
        expected = os.environ.get("PROXY_KEY", "")
        print(f"ArticleImageUploadView.post request={request}")
        # WSGI/Django places HTTP headers into META with HTTP_ prefix and
        # dashes replaced by underscores (uppercased). Also support the
        # `Request.headers` accessor for robustness.
        received = request.META.get("HTTP_X_INTERNAL_PROXY_KEY", "") or getattr(request, "headers", {}).get("X-Internal-Proxy-Key", "")  # type: ignore
        print(f"ArticleImageUploadView.post expected={expected}, received={received}")
        if not expected or not hmac.compare_digest((received or ""), expected):  # type: ignore
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)  # type: ignore

        # Choose serializer input depending on request type
        try:
            print("ArticleImageUploadView.post started")
            if request.content_type and "multipart" in request.content_type: # type: ignore
                print("multipart request detected")
                data = request.data.copy() # type: ignore
                serializer = ArticleImageCreateSerializer(data=data)
            else:
                print("json/base64 request detected")
                serializer = ArticleImageCreateSerializer(data=request.data) # type: ignore

            print("serializer created, validating...")
            if serializer.is_valid(): # type: ignore
                print("serializer valid, saving...")
                instance = serializer.save()  # type: ignore
                print(f"instance saved: {instance}")
                out = ArticleImageUploadSerializer(instance, context={"request": request}).data  # type: ignore
                print(f"serialized output: {out}")
                return Response(out, status=status.HTTP_201_CREATED)  # type: ignore
            print(f"serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  # type: ignore
        except Exception as e:
            print(f"Unhandled error in ArticleImageUploadView.post: {str(e)}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # type: ignore

# CHANGE LOG
# Changed by : JML
# Date       : 2026-05-16
# Reason     : Review how Neon DB is called and when.
# Impact     : New URL /articles/models.py and articles/views.py 