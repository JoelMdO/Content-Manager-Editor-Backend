from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
# ADDED 2026-03-16 — RAG corpus endpoint imports
from rest_framework.views import APIView
from django.conf import settings
import re
import os
import hmac
import logging

logger = logging.getLogger(__name__)

from .serializers import ArticleManagerSerializer, ArticleImageCreateSerializer, ArticleImageUploadSerializer


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
            serializer = ArticleManagerSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)# type: ignore
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)# type: ignore
        except Exception as e:
            logger.exception("Error saving article draft")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ADDED 2026-03-16 — Internal endpoint for the FastAPI RAG ingestion service
class RagCorpusView(APIView):
    """
    Internal endpoint: GET /articles/rag-corpus/?lang=en|es

    Returns published articles as a list of:
      {id, title, plain_text, language}

    Protected by the X-RAG-Token header (shared secret via RAG_INTERNAL_TOKEN env var).
    NOT exposed via the public proxy — call only from within the Docker network.
    """

    def check_token(self, request: Request) -> bool:  # type: ignore
        """Validate the X-RAG-Token header against the configured shared secret."""
        expected = getattr(settings, "RAG_INTERNAL_TOKEN", None)
        if not expected:
            # If not configured, deny all access to avoid accidental exposure
            return False
        received = request.META.get("HTTP_X_RAG_TOKEN", "")
        # Use a constant-time comparison to prevent timing attacks
        import hmac
        return hmac.compare_digest(received, expected)

    def extract_plain_text(self, body: object) -> str:  # type: ignore
        """
        Extract plain text from the CMS article body JSONField.
        Body is a list of block dicts: [{"type": "paragraph", "content": "..."}]
        """
        if not isinstance(body, list):
            if isinstance(body, str):
                # Strip HTML tags as fallback
                return re.sub(r"<[^>]+>", " ", body).strip()
            return ""

        parts = []
        for block in body: # type: ignore
            if not isinstance(block, dict):
                continue
            content = block.get("content") or block.get("text") or "" # type: ignore
            if isinstance(content, str) and content.strip():
                parts.append(content.strip()) # type: ignore
            elif isinstance(content, list):
                for child in content: # type: ignore
                    if isinstance(child, dict):
                        child_text = child.get("text") or child.get("content") or "" # type: ignore
                        if isinstance(child_text, str):
                            parts.append(child_text.strip()) # type: ignore
        return " ".join(parts) # type: ignore

    def get(self, request: Request):  # type: ignore
        """Return published articles for the requested language."""
        if not self.check_token(request):
            return Response(
                {"error": "Unauthorized"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        lang = request.GET.get("lang", "en").lower()[:2]

        # Import here to avoid circular imports at module level
        from .models import ArticleModel  # type: ignore

        # Filter by published status; language is not a stored field in the current
        # ArticleModel — the FastAPI side will ingest into the collection matching
        # the `lang` param. Include all published articles in both passes.
        articles = ArticleModel.objects.filter(status="published").values(
            "id", "title", "body"
        )

        results = []
        for article in articles:
            plain_text = self.extract_plain_text(article["body"])
            if not plain_text.strip():
                continue
            results.append({ # type: ignore
                "id": str(article["id"]),
                "title": article["title"] or "",
                "plain_text": plain_text,
                "language": lang,
            })

        logger.debug("RagCorpusView returning %d articles for lang=%s", len(results), lang)  # type: ignore
        return Response(results, status=status.HTTP_200_OK)


class ArticleImageUploadView(APIView):
    """POST /articles/images/

    Accepts multipart/form-data with `file` or JSON with `base64`.
    Requires header `x-internal-proxy-key` to match env `PROXY_KEY`.
    """

    def post(self, request: Request):  # type: ignore
        expected = os.environ.get("PROXY_KEY", "")
        received = request.META.get("HTTP_X_INTERNAL_PROXY_KEY", "")
        if not expected or not hmac.compare_digest(received or "", expected):
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        # Choose serializer input depending on request type
        try:
            logger.debug("ArticleImageUploadView.post started")
            if request.content_type and "multipart" in request.content_type:
                logger.debug("multipart request detected")
                data = request.data.copy()
                serializer = ArticleImageCreateSerializer(data=data)
            else:
                logger.debug("json/base64 request detected")
                serializer = ArticleImageCreateSerializer(data=request.data)

            logger.debug("serializer created, validating...")
            if serializer.is_valid():
                logger.debug("serializer valid, saving...")
                instance = serializer.save()  # type: ignore
                logger.debug("instance saved: %s", instance) # type: ignore
                out = ArticleImageUploadSerializer(instance, context={"request": request}).data  # type: ignore
                logger.debug("serialized output")
                return Response(out, status=status.HTTP_201_CREATED)  # type: ignore
            logger.debug("serializer errors: %s", serializer.errors) # type: ignore
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  # type: ignore
        except Exception as e:
            logger.exception("Unhandled error in ArticleImageUploadView.post")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# CHANGE LOG
# Changed by : Copilot
# Date       : 2026-03-16
# Reason     : Added RagCorpusView to expose published article text to the
#              FastAPI RAG ingestion service via a shared-secret-protected endpoint.
# Impact     : New URL /articles/rag-corpus/ registered in articles/urls.py.
#              Requires RAG_INTERNAL_TOKEN to be set in Django settings / env.