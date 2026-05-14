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

            try:
                # Attempt to check if the data is valid before starting the transaction
                # If valid, proceed with the save inside the transaction.atomic block
                # At Article ManagerSerlizer
                with transaction.atomic():
                    instance = serializer.save()  # type: ignore
            except DatabaseError as db_err:
                logger.exception("Database error saving article draft: %s", str(db_err))
                return Response({"error": "Database 1 error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # type: ignore

            # After the local transaction commits to avoid blocking the
            # primary write. Will write if the article is as published to Neon DB.
            if instance.status == "published":  # type: ignore
                try:
                    # Schedule replication to run after the local DB transaction
                    # commits. Use the saved `instance`'s method (not the
                    # serializer) so the model-level replication runs as expected.
                    transaction.on_commit(instance.replicate_to_neon)  # type: ignore
                except Exception:
                    # If on_commit isn't available or fails, attempt immediate replicate
                    logger.exception("on_commit failed for replicate_to_neon, attempting immediate replicate for article id=%s", getattr(instance, "id", None))  # type: ignore
                    with contextlib.suppress(Exception):
                        serializer.replicate_to_neon()  # type: ignore

            out = ArticleManagerSerializer(instance, context={"request": request}).data  # type: ignore
            return Response(out, status=status.HTTP_201_CREATED) # type: ignore
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
                data = ArticleManagerSerializer.get_all_drafts(brief=True)  # type: ignore
                return Response(data, status=status.HTTP_200_OK)  # type: ignore
            except Exception as e:
                logger.exception("Error retrieving article drafts list: %s", str(e))
                return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)  # type: ignore

# ADDED 2026-03-16 — Internal endpoint for the FastAPI RAG ingestion service
# class RagCorpusView(APIView): # type: ignore
#     """
#     Internal endpoint: GET /articles/rag-corpus/?lang=en|es

#     Returns published articles as a list of:
#     {id, title, plain_text, language}

#     Protected by the X-RAG-Token header (shared secret via RAG_INTERNAL_TOKEN env var).
#     NOT exposed via the public proxy — call only from within the Docker network.
#     """

#     def check_token(self, request: Request) -> bool:  # type: ignore
#         """Validate the X-RAG-Token header against the configured shared secret."""
#         expected = getattr(settings, "RAG_INTERNAL_TOKEN", None)
#         if not expecttitle:
#             # If not configured, deny all access to avoid accidental exposure
#        title   return False
#         received = request.META.get("HTTP_X_RAG_TOKEN", "") # type: ignore
#         # Use a constant-time comparison to prevent timing attacks
#         import hmac
#         return hmac.compare_digest(received, expected)  # type: ignore

#     def extract_plain_text(self, body: object) -> str:  # type: ignore
#         """
#         Extract plain text from the CMS article body JSONField.
#         Body is a list of block dicts: [{"type": "paragraph", "content": "..."}]
#         """
#         if not isinstance(body, list):
#             if isinstance(body, str):
#                 # Strip HTML tags as fallback
#                 return re.sub(r"<[^>]+>", " ", body).strip()
#             return ""

#         parts = []
#         for block in body: # type: ignore
#             if not isinstance(block, dict):
#                 continue
#             content = block.get("content") or block.get("text") or "" # type: ignore
#             if isinstance(content, str) and content.strip():
#                 parts.append(content.strip()) # type: ignore
#             elif isinstance(content, list):
#                 for child in content: # type: ignore
#                     if isinstance(child, dict):
#                         child_text = child.get("text") or child.get("content") or "" # type: ignore
#                         if isinstance(child_text, str):
#                             parts.append(child_text.strip()) # type: ignore
#         return " ".join(parts) # type: ignore

#     # Backwards-compatible alias used by older tests
#     def _extract_plain_text(self, body: object) -> str:  # type: ignore
#         return self.extract_plain_text(body)

#     def get(self, request: Request):  # type: ignore
#         """Return published articles for the requested language."""
#         if not self.check_token(request): # type: ignore
#             return Response( # type: ignore 
#                 {"error": "Unauthorized"},
#                 status=status.HTTP_401_UNAUTHORIZED, # type: ignore
#             )

#         lang = request.GET.get("lang", "en").lower()[:2] # type: ignore

#         # Import here to avoid circular imports at module level
#         from .models import ArticleModel  # type: ignore

#         # Filter by published status; language is not a stored field in the current
#         # ArticleModel — the FastAPI side will ingest into the collection matching
#         # the `lang` param. Include all published articles in both passes.
#         articles = ArticleModel.objects.filter(status="published").values(
#             "id", "title", "body"
#         )

#         results = []
#         for article in articles:
#             plain_text = self.extract_plain_text(article["body"])
#             if not plain_text.strip():
#                 continue
#             results.append({ # type: ignore
#                 "id": str(article["id"]),
#                 "title": article["title"] or "",
#                 "plain_text": plain_text,
#                 "language": lang,
#             })

#         logger.debug("RagCorpusView returning %d articles for lang=%s", len(results), lang)  # type: ignore
#         return Response(results, status=status.HTTP_200_OK) # type: ignore


class ArticleImageUploadView(APIView): # type: ignore
    """POST /articles/images/

    Accepts multipart/form-data with `file` or JSON with `base64`.
    Requires header `x-internal-proxy-key` to match env `PROXY_KEY`.
    """

    def post(self, request: Request):  # type: ignore
        expected = os.environ.get("PROXY_KEY", "")
        received = request.META.get("HTTP_X_INTERNAL_PROXY_KEY", "") # type: ignore
        if not expected or not hmac.compare_digest(received or "", expected): # type: ignore
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN) # type: ignore

        # Choose serializer input depending on request type
        try:
            logger.debug("ArticleImageUploadView.post started")
            if request.content_type and "multipart" in request.content_type: # type: ignore
                logger.debug("multipart request detected")
                data = request.data.copy() # type: ignore
                serializer = ArticleImageCreateSerializer(data=data)
            else:
                logger.debug("json/base64 request detected")
                serializer = ArticleImageCreateSerializer(data=request.data) # type: ignore

            logger.debug("serializer created, validating...")
            if serializer.is_valid(): # type: ignore
                logger.debug("serializer valid, saving...")
                instance = serializer.save()  # type: ignore
                logger.debug("instance saved: %s", instance) # type: ignore
                out = ArticleImageUploadSerializer(instance, context={"request": request}).data  # type: ignore
                logger.debug("serialized output")
                return Response(out, status=status.HTTP_201_CREATED)  # type: ignore
            logger.debug("serializer errors: %s", serializer.errors) # type: ignore
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  # type: ignore
        except Exception as e:
            logger.exception("Unhandled error in ArticleImageUploadView.post: %s", str(e))
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) # type: ignore

# CHANGE LOG
# Changed by : JML
# Date       : 2026-05-16
# Reason     : Review how Neon DB is called and when.
# Impact     : New URL /articles/models.py and articles/views.py 